from __future__ import annotations

import zoneinfo
from datetime import date, datetime, timedelta

from config import TIMEZONE
from db import get_habits, get_pool, get_skipped_days
from schedule import WEEKDAYS_SHORT


def _today_tz() -> date:
    """Today's date in configured timezone."""
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    return datetime.now(tz).date()


def _period_bounds(period: str, today: date) -> tuple[date | None, str]:
    if period == "week":
        return today - timedelta(days=today.weekday()), "Статистика за неделю"
    if period == "month":
        return today - timedelta(days=29), "Статистика за месяц"
    return None, "Статистика за всё время"


async def compute_stats(period: str) -> dict:
    """Completion figures measured against what was actually scheduled.

    Every row in daily_log is a habit that was scheduled that day, so the rows
    are the record of what was expected. Percentages divide by those rows rather
    than by calendar days, and days marked as skipped are left out entirely.
    """
    today = _today_tz()
    start, title = _period_bounds(period, today)

    habits = await get_habits()
    skipped = await get_skipped_days()
    pool = await get_pool()

    async with pool.acquire() as conn:
        if start is None:
            first = await conn.fetchval("SELECT MIN(date) FROM daily_log")
            if not first:
                return _empty(title)
            start = date.fromisoformat(first)

        lo, hi = start.isoformat(), today.isoformat()
        rows = await conn.fetch(
            "SELECT date, habit_key, completed FROM daily_log "
            "WHERE date >= $1 AND date <= $2",
            lo, hi,
        )
        streak_rows = await conn.fetch(
            "SELECT date, habit_key, completed FROM daily_log ORDER BY date DESC"
        )

    rows = [r for r in rows if r["date"] not in skipped]
    if not rows:
        return _empty(title)

    by_habit: dict[str, list[bool]] = {}
    by_date: dict[str, list[bool]] = {}
    for r in rows:
        done = bool(r["completed"])
        by_habit.setdefault(r["habit_key"], []).append(done)
        by_date.setdefault(r["date"], []).append(done)

    total_days = len(by_date)
    perfect_days = sum(1 for marks in by_date.values() if marks and all(marks))

    streaks = _streaks(streak_rows, skipped, today.isoformat())

    habit_stats = []
    for h in sorted(habits, key=lambda x: x["sort_order"]):
        marks = by_habit.get(h["key"])
        if not marks:
            continue  # never scheduled inside this period
        done = sum(marks)
        habit_stats.append({
            "key": h["key"],
            "name": h["name"],
            "emoji": h["emoji"],
            "done": done,
            "total": len(marks),
            "pct": round(done / len(marks) * 100),
            "streak": streaks.get(h["key"], 0),
        })

    return {
        "title": title,
        "habits": habit_stats,
        "perfect_days": perfect_days,
        "total_days": total_days,
        "weekdays": _weekday_breakdown(rows),
        "skipped": sum(1 for d in skipped if lo <= d <= hi),
    }


def _empty(title: str) -> dict:
    return {
        "title": title, "habits": [], "perfect_days": 0,
        "total_days": 0, "weekdays": [], "skipped": 0,
    }


def _weekday_breakdown(rows) -> list[dict]:
    """Completion rate per weekday -- shows which day of the week slips."""
    done = [0] * 7
    total = [0] * 7
    for r in rows:
        wd = date.fromisoformat(r["date"]).weekday()
        total[wd] += 1
        done[wd] += bool(r["completed"])
    return [
        {
            "name": WEEKDAYS_SHORT[i],
            "done": done[i],
            "total": total[i],
            "pct": round(done[i] / total[i] * 100) if total[i] else 0,
        }
        for i in range(7)
    ]


def _streaks(rows, skipped: set[str], today: str) -> dict[str, int]:
    """Consecutive scheduled days completed, counting back from the latest.

    Only days the habit was actually scheduled on count, so a habit that runs
    three times a week does not lose its streak on the days in between. Skipped
    days are stepped over, and today is not held against a habit while the day
    is still running.
    """
    streaks: dict[str, int] = {}
    broken: set[str] = set()
    for r in rows:                       # already ordered newest first
        key = r["habit_key"]
        if key in broken or r["date"] in skipped:
            continue
        if r["completed"]:
            streaks[key] = streaks.get(key, 0) + 1
        elif r["date"] == today:
            continue                     # day still in progress
        else:
            broken.add(key)
            streaks.setdefault(key, 0)
    return streaks


async def compute_week_summary() -> dict:
    """Figures for the Sunday wrap-up: the calendar week that is ending."""
    today = _today_tz()
    monday = today - timedelta(days=today.weekday())
    skipped = await get_skipped_days()
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT date, habit_key, completed FROM daily_log "
            "WHERE date >= $1 AND date <= $2",
            monday.isoformat(), today.isoformat(),
        )
        topics = await conn.fetchval("SELECT COUNT(*) FROM econ_notes") or 0

    rows = [r for r in rows if r["date"] not in skipped]
    done = sum(1 for r in rows if r["completed"])
    total = len(rows)

    by_habit: dict[str, list[bool]] = {}
    for r in rows:
        by_habit.setdefault(r["habit_key"], []).append(bool(r["completed"]))

    habits = {h["key"]: h for h in await get_habits()}
    weakest = None
    if by_habit:
        key = min(by_habit, key=lambda k: sum(by_habit[k]) / len(by_habit[k]))
        marks = by_habit[key]
        if sum(marks) < len(marks):
            weakest = {
                "name": habits.get(key, {}).get("name", key),
                "done": sum(marks),
                "total": len(marks),
            }

    return {
        "start": monday,
        "end": today,
        "done": done,
        "total": total,
        "pct": round(done / total * 100) if total else 0,
        "weakest": weakest,
        "topics": topics,
        "skipped": sum(1 for d in skipped if monday.isoformat() <= d <= today.isoformat()),
    }


async def month_overview(year: int, month: int) -> dict[str, dict]:
    """Per-day figures for one month, used to colour the calendar.

    Only days that actually have rows appear: a day the bot never logged is
    absent rather than counted as a miss.
    """
    from calendar import monthrange

    from tasks_db import tasks_by_date

    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    lo, hi = first.isoformat(), last.isoformat()

    skipped = await get_skipped_days()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT date, COUNT(*) AS total, COALESCE(SUM(completed), 0) AS done "
            "FROM daily_log WHERE date >= $1 AND date <= $2 GROUP BY date",
            lo, hi,
        )
    tasks = await tasks_by_date(lo, hi)

    overview: dict[str, dict] = {}
    for r in rows:
        overview[r["date"]] = {
            "habits_done": int(r["done"]),
            "habits_total": int(r["total"]),
            "tasks_done": 0,
            "tasks_total": 0,
            "skipped": r["date"] in skipped,
        }
    for day, (done, total) in tasks.items():
        entry = overview.setdefault(day, {
            "habits_done": 0, "habits_total": 0,
            "tasks_done": 0, "tasks_total": 0,
            "skipped": day in skipped,
        })
        entry["tasks_done"] = done
        entry["tasks_total"] = total

    for day in skipped:
        if lo <= day <= hi and day not in overview:
            overview[day] = {
                "habits_done": 0, "habits_total": 0,
                "tasks_done": 0, "tasks_total": 0, "skipped": True,
            }
    return overview


def day_status(entry: dict | None) -> str:
    """'skipped', 'perfect', 'partial' or 'empty' for one calendar cell."""
    if entry is None:
        return "empty"
    if entry["skipped"]:
        return "skipped"
    total = entry["habits_total"] + entry["tasks_total"]
    done = entry["habits_done"] + entry["tasks_done"]
    if total == 0:
        return "empty"
    if done == total:
        return "perfect"
    return "partial" if done else "empty"
