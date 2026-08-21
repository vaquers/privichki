from __future__ import annotations

from db import get_pool

# Two half-topic marks on the day card add up to one finished topic.
MARKS_PER_TOPIC = 2
ECON_HABIT_KEY = "economics"


async def init_econ_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS econ_notes (
                id SERIAL PRIMARY KEY,
                number INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


async def get_notes() -> list[dict]:
    """Newest topic first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, number, title, body, created_at, updated_at "
            "FROM econ_notes ORDER BY number DESC, id DESC"
        )
        return [dict(r) for r in rows]


async def get_note(note_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM econ_notes WHERE id = $1", note_id)
        return dict(row) if row else None


async def add_note(title: str, body: str = "") -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        number = await conn.fetchval(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM econ_notes"
        )
        return await conn.fetchval(
            "INSERT INTO econ_notes (number, title, body) VALUES ($1, $2, $3) RETURNING id",
            number, title, body,
        )


async def update_note(note_id: int, *, title: str | None = None,
                      body: str | None = None) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if title is not None:
            await conn.execute(
                "UPDATE econ_notes SET title = $2, updated_at = NOW() WHERE id = $1",
                note_id, title,
            )
        if body is not None:
            await conn.execute(
                "UPDATE econ_notes SET body = $2, updated_at = NOW() WHERE id = $1",
                note_id, body,
            )


async def delete_note(note_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM econ_notes WHERE id = $1", note_id)


async def search_notes(query: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, number, title, body, created_at, updated_at FROM econ_notes "
            "WHERE title ILIKE $1 OR body ILIKE $1 ORDER BY number DESC",
            f"%{query}%",
        )
        return [dict(r) for r in rows]


# --- topic cycle ------------------------------------------------------------

async def marks_done() -> int:
    """How many half-topic marks have been ticked in total."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM daily_log WHERE habit_key = $1 AND completed = 1",
            ECON_HABIT_KEY,
        ) or 0


async def topics_completed() -> int:
    return await marks_done() // MARKS_PER_TOPIC


async def notes_count() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM econ_notes") or 0


async def pending_topics() -> int:
    """Finished topics that still have no write-up."""
    return max(0, await topics_completed() - await notes_count())


async def progress() -> tuple[int, int]:
    """(marks into the current topic, marks needed) -- e.g. (1, 2) is half way."""
    return await marks_done() % MARKS_PER_TOPIC, MARKS_PER_TOPIC
