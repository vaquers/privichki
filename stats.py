from __future__ import annotations

from datetime import date, timedelta

from db import get_pool, get_habits


def _monday_of_week(d: date) -> date:
    """Return Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


async def compute_stats(period: str) -> dict:
    """Return stats dict for render_stats_card."""
    today = date.today()

    if period == "week":
        start = _monday_of_week(today)
        title = "Статистика за неделю"
    elif period == "month":
        start = today - timedelta(days=29)
        title = "Статистика за месяц"
    else:
        start = None
        title = "Статистика за всё время"

    habits = await get_habits()
    pool = await get_pool()

    async with pool.acquire() as conn:
        if start:
            date_filter = "WHERE date >= $1 AND date <= $2"
            params: list = [start.isoformat(), today.isoformat()]
        else:
            date_filter = "WHERE date <= $1"
            params = [today.isoformat()]

        total_days: int | None = (today - start).days + 1 if start else None

        if not start:
            row = await conn.fetchrow(
                "SELECT MIN(date) as d FROM daily_log WHERE completed = 1"
            )
            if row and row["d"]:
                start = date.fromisoformat(row["d"])
                total_days = (today - start).days + 1
                date_filter = "WHERE date >= $1 AND date <= $2"
                params = [start.isoformat(), today.isoformat()]
            else:
                return {"title": title, "habits": [], "perfect_days": 0, "total_days": 0}

        habit_count = len(habits)

        # perfect days
        rows = await conn.fetch(
            f"SELECT date, SUM(completed) as s FROM daily_log {date_filter} "
            f"GROUP BY date HAVING SUM(completed) = ${len(params) + 1}",
            *params, habit_count,
        )
        perfect_days = len(rows)

        habit_stats = []
        for h in habits:
            row = await conn.fetchrow(
                f"SELECT COUNT(*) as cnt FROM daily_log {date_filter} "
                f"AND habit_key = ${len(params) + 1} AND completed = 1",
                *params, h["key"],
            )
            done = row["cnt"]
            pct = round(done / total_days * 100) if total_days else 0
            streak = await _calc_streak(conn, h["key"], today)

            habit_stats.append({
                "key": h["key"],
                "name": h["name"],
                "emoji": h["emoji"],
                "done": done,
                "total": total_days,
                "pct": pct,
                "streak": streak,
            })

        return {
            "title": title,
            "habits": habit_stats,
            "perfect_days": perfect_days,
            "total_days": total_days,
        }


async def _calc_streak(conn, habit_key: str, today: date) -> int:
    streak = 0
    d = today
    while True:
        row = await conn.fetchrow(
            "SELECT completed FROM daily_log WHERE date = $1 AND habit_key = $2",
            d.isoformat(), habit_key,
        )
        if row and row["completed"]:
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak
