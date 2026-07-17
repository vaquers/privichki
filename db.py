from __future__ import annotations

import asyncpg

from config import DATABASE_URL

# (key, name, icon_path, emoji, target_hours, sort_order, custom_emoji_id)
SEED_HABITS = [
    ("math", "Математика", "assets/icons/math.png", "➗", 2, 0, "5388947482640162600"),
    ("dev", "Разработка сайтов", "assets/icons/dev.png", "💻", 2, 1, "5388815249187053647"),
    ("sport", "Спорт", "assets/icons/sport.png", "🏋️", 2, 2, "5390842774398481198"),
    ("economics", "Экономика", "assets/icons/economics.png", "📈", 2, 3, "5388832605149893738"),
]

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon_path TEXT NOT NULL,
                emoji TEXT NOT NULL,
                target_hours INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                custom_emoji_id TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_log (
                date TEXT NOT NULL,
                habit_key TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                PRIMARY KEY (date, habit_key)
            )
        """)
        for h in SEED_HABITS:
            await conn.execute(
                """INSERT INTO habits (key, name, icon_path, emoji, target_hours, sort_order, custom_emoji_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (key) DO UPDATE SET custom_emoji_id = $7""",
                *h,
            )


async def get_habits() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM habits ORDER BY sort_order")
        return [dict(r) for r in rows]


async def get_day_state(date: str) -> dict[str, bool]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT habit_key, completed FROM daily_log WHERE date = $1", date
        )
        return {r["habit_key"]: bool(r["completed"]) for r in rows}


async def ensure_day_rows(date: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        habits = await get_habits()
        for h in habits:
            await conn.execute(
                "INSERT INTO daily_log (date, habit_key) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                date, h["key"],
            )


async def toggle_habit(date: str, habit_key: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT completed FROM daily_log WHERE date = $1 AND habit_key = $2",
            date, habit_key,
        )
        if row is None:
            await conn.execute(
                "INSERT INTO daily_log (date, habit_key, completed, completed_at) "
                "VALUES ($1, $2, 1, NOW()::TEXT)",
                date, habit_key,
            )
            return True

        new_val = 0 if row["completed"] else 1
        if new_val:
            await conn.execute(
                "UPDATE daily_log SET completed = 1, completed_at = NOW()::TEXT "
                "WHERE date = $1 AND habit_key = $2",
                date, habit_key,
            )
        else:
            await conn.execute(
                "UPDATE daily_log SET completed = 0, completed_at = NULL "
                "WHERE date = $1 AND habit_key = $2",
                date, habit_key,
            )
        return bool(new_val)


async def has_daily_message(date: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) as cnt FROM daily_log WHERE date = $1", date
        )
        return row["cnt"] > 0
