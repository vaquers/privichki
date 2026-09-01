from __future__ import annotations

from db import get_pool

# Longest task title accepted. Callback payloads carry only the id, so this is
# about the button staying readable, not about protocol limits.
MAX_TITLE = 60


async def init_tasks_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS day_tasks (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS day_tasks_date_idx ON day_tasks (date)"
        )


async def get_tasks(date: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, date, title, completed, sort_order FROM day_tasks "
            "WHERE date = $1 ORDER BY sort_order, id",
            date,
        )
        return [{**dict(r), "completed": bool(r["completed"])} for r in rows]


async def get_task(task_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM day_tasks WHERE id = $1", task_id)
        return {**dict(row), "completed": bool(row["completed"])} if row else None


async def add_task(date: str, title: str) -> int:
    title = " ".join(title.split())[:MAX_TITLE]
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchval(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM day_tasks WHERE date = $1",
            date,
        )
        return await conn.fetchval(
            "INSERT INTO day_tasks (date, title, sort_order) VALUES ($1, $2, $3) "
            "RETURNING id",
            date, title, order,
        )


async def toggle_task(task_id: int) -> bool:
    """Flip the task and return its new state."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return bool(await conn.fetchval(
            "UPDATE day_tasks SET completed = 1 - completed WHERE id = $1 "
            "RETURNING completed",
            task_id,
        ))


async def delete_task(task_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM day_tasks WHERE id = $1", task_id)


async def tasks_progress(date: str) -> tuple[int, int]:
    """(completed, total) for the day."""
    tasks = await get_tasks(date)
    return sum(1 for t in tasks if t["completed"]), len(tasks)


async def tasks_by_date(start: str, end: str) -> dict[str, tuple[int, int]]:
    """{date: (completed, total)} across a range -- used to fill the calendar."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT date, COUNT(*) AS total, "
            "       COALESCE(SUM(completed), 0) AS done "
            "FROM day_tasks WHERE date >= $1 AND date <= $2 GROUP BY date",
            start, end,
        )
    return {r["date"]: (int(r["done"]), int(r["total"])) for r in rows}
