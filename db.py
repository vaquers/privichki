from __future__ import annotations

import asyncpg

from config import DATABASE_URL
from schedule import dumps, every_day, habits_for_date

# (key, name, icon_path, emoji, sort_order, custom_emoji_id, schedule)
# custom_emoji_id values come from the t.me/addemoji/vaquers_privichki pack;
# re-read them with scripts/fetch_emoji_ids.py vaquers_privichki
# The schedule maps weekday (Monday = 0) to the subtitle shown that day. A day
# missing from the map means the habit is not shown at all.
SEED_HABITS = [
    ("math", "Математика", "assets/icons/math.png", "➗", 0, "5210892256105504887",
     {"0": "репет", "1": "1/3 дз", "3": "1/3 дз", "5": "1/3 дз"}),
    ("dev", "Разработка сайтов", "assets/icons/dev.png", "💻", 1, "5208818817693687314",
     every_day("1 сайт")),
    ("sport", "Спорт", "assets/icons/sport.png", "🏋️", 2, "5208527451407294933",
     every_day("тренировка")),
    ("economics", "Экономика", "assets/icons/economics.png", "📈", 3, "5208736869717680376",
     every_day("пол темы")),
    ("shower", "Душ", "assets/icons/shower.png", "🚿", 4, "5208823576517453495",
     every_day("холодный")),
    ("sleep", "Сон", "assets/icons/sleep.png", "💤", 5, "5211227650101651587",
     every_day("8 часов")),
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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS skipped_days (
                date TEXT PRIMARY KEY,
                reason TEXT NOT NULL DEFAULT ''
            )
        """)
        # Added after the first release: the weekly schedule and its per-day
        # subtitles replace the fixed "N часов" caption.
        await conn.execute("ALTER TABLE habits ADD COLUMN IF NOT EXISTS schedule TEXT")
        await conn.execute("ALTER TABLE habits ALTER COLUMN target_hours DROP NOT NULL")

        for key, name, icon, emoji, order, emoji_id, sched in SEED_HABITS:
            # The schedule is only written when the row has none, so edits made
            # later are never overwritten on restart.
            await conn.execute(
                """INSERT INTO habits
                       (key, name, icon_path, emoji, sort_order, custom_emoji_id, schedule)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (key) DO UPDATE SET
                       custom_emoji_id = EXCLUDED.custom_emoji_id,
                       sort_order = EXCLUDED.sort_order,
                       schedule = COALESCE(habits.schedule, EXCLUDED.schedule)""",
                key, name, icon, emoji, order, emoji_id, dumps(sched),
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
    """Create a log row for every habit scheduled on that date.

    The rows themselves are the record of what was expected that day, which is
    what the statistics count against.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        for h in habits_for_date(await get_habits(), date):
            await conn.execute(
                "INSERT INTO daily_log (date, habit_key) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                date, h["key"],
            )


async def get_day_habits(date: str) -> list[dict]:
    """Habits scheduled on that date, with the day's subtitle attached."""
    return habits_for_date(await get_habits(), date)


# --- skipped days -----------------------------------------------------------

async def set_day_skipped(date: str, skipped: bool, reason: str = "") -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if skipped:
            await conn.execute(
                "INSERT INTO skipped_days (date, reason) VALUES ($1, $2) "
                "ON CONFLICT (date) DO UPDATE SET reason = $2",
                date, reason,
            )
        else:
            await conn.execute("DELETE FROM skipped_days WHERE date = $1", date)


async def is_day_skipped(date: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM skipped_days WHERE date = $1)", date
        )


async def get_skipped_days() -> set[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT date FROM skipped_days")
        return {r["date"] for r in rows}


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
