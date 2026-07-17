from __future__ import annotations

from datetime import date, timedelta

import aiosqlite

from config import DB_PATH
from db import get_db, get_habits


async def compute_stats(period: str) -> str:
    """Build stats text for given period: week/month/all."""
    today = date.today()

    if period == "week":
        start = today - timedelta(days=6)
        title = "📊 Статистика за неделю"
    elif period == "month":
        start = today - timedelta(days=29)
        title = "📊 Статистика за месяц"
    else:
        start = None
        title = "📊 Статистика за всё время"

    habits = await get_habits()
    db = await get_db()

    try:
        lines = [title, ""]

        total_days = (today - start).days + 1 if start else None
        perfect_days = 0

        # count perfect days
        if start:
            date_filter = "WHERE date >= ? AND date <= ?"
            params: tuple = (start.isoformat(), today.isoformat())
        else:
            date_filter = "WHERE date <= ?"
            params = (today.isoformat(),)

        # get first date if 'all'
        if not start:
            cursor = await db.execute("SELECT MIN(date) as d FROM daily_log WHERE completed = 1")
            row = await cursor.fetchone()
            if row and row["d"]:
                start = date.fromisoformat(row["d"])
                total_days = (today - start).days + 1
            else:
                return title + "\n\nНет данных."

        habit_count = len(habits)

        # perfect days: dates where all habits completed
        cursor = await db.execute(
            f"SELECT date, SUM(completed) as s FROM daily_log {date_filter} "
            "GROUP BY date HAVING s = ?",
            (*params, habit_count),
        )
        perfect_rows = await cursor.fetchall()
        perfect_days = len(perfect_rows)

        for h in habits:
            # completed count
            cursor = await db.execute(
                f"SELECT COUNT(*) as cnt FROM daily_log {date_filter} "
                "AND habit_key = ? AND completed = 1",
                (*params, h["key"]),
            )
            row = await cursor.fetchone()
            done = row["cnt"]
            pct = round(done / total_days * 100) if total_days else 0

            # current streak
            streak = await _calc_streak(db, h["key"], today)

            lines.append(f"{h['emoji']} {h['name']}")
            lines.append(f"   {done}/{total_days} дней ({pct}%) | стрик: {streak} 🔥")
            lines.append("")

        lines.append(f"⭐ Идеальных дней: {perfect_days}/{total_days}")

        return "\n".join(lines)
    finally:
        await db.close()


async def _calc_streak(db: aiosqlite.Connection, habit_key: str, today: date) -> int:
    """Count consecutive completed days ending today (or yesterday if today not yet done)."""
    streak = 0
    d = today
    while True:
        cursor = await db.execute(
            "SELECT completed FROM daily_log WHERE date = ? AND habit_key = ?",
            (d.isoformat(), habit_key),
        )
        row = await cursor.fetchone()
        if row and row["completed"]:
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak
