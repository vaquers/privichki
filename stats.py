from __future__ import annotations

from datetime import date, timedelta

from db import get_pool, get_habits


async def compute_stats(period: str) -> str:
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
                return title + "\n\nНет данных."

        habit_count = len(habits)
        lines = [title, ""]

        # perfect days
        rows = await conn.fetch(
            f"SELECT date, SUM(completed) as s FROM daily_log {date_filter} "
            f"GROUP BY date HAVING SUM(completed) = ${len(params) + 1}",
            *params, habit_count,
        )
        perfect_days = len(rows)

        for h in habits:
            row = await conn.fetchrow(
                f"SELECT COUNT(*) as cnt FROM daily_log {date_filter} "
                f"AND habit_key = ${len(params) + 1} AND completed = 1",
                *params, h["key"],
            )
            done = row["cnt"]
            pct = round(done / total_days * 100) if total_days else 0

            streak = await _calc_streak(conn, h["key"], today)

            lines.append(f"{h['emoji']} {h['name']}")
            lines.append(f"   {done}/{total_days} дней ({pct}%) | стрик: {streak} 🔥")
            lines.append("")

        lines.append(f"⭐ Идеальных дней: {perfect_days}/{total_days}")
        return "\n".join(lines)


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
