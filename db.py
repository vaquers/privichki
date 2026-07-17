from __future__ import annotations

import aiosqlite
from config import DB_PATH

# (key, name, icon_path, emoji, target_hours, sort_order, custom_emoji_id)
SEED_HABITS = [
    ("math", "Математика", "assets/icons/math.png", "➗", 2, 0, "5388947482640162600"),
    ("dev", "Разработка сайтов", "assets/icons/dev.png", "💻", 2, 1, "5388815249187053647"),
    ("sport", "Спорт", "assets/icons/sport.png", "🏋️", 2, 2, "5390842774398481198"),
    ("economics", "Экономика", "assets/icons/economics.png", "📈", 2, 3, "5388832605149893738"),
]


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS habits (
                key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                icon_path TEXT NOT NULL,
                emoji TEXT NOT NULL,
                target_hours INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                custom_emoji_id TEXT
            );
            CREATE TABLE IF NOT EXISTS daily_log (
                date TEXT NOT NULL,
                habit_key TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                PRIMARY KEY (date, habit_key)
            );
        """)
        # migrate: add column if missing (existing DB)
        try:
            await db.execute("ALTER TABLE habits ADD COLUMN custom_emoji_id TEXT")
        except Exception:
            pass  # column already exists
        for h in SEED_HABITS:
            await db.execute(
                "INSERT INTO habits (key, name, icon_path, emoji, target_hours, sort_order, custom_emoji_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET custom_emoji_id = excluded.custom_emoji_id",
                h,
            )
        await db.commit()
    finally:
        await db.close()


async def get_habits() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM habits ORDER BY sort_order")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_day_state(date: str) -> dict[str, bool]:
    """Return {habit_key: completed} for given date."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT habit_key, completed FROM daily_log WHERE date = ?", (date,)
        )
        rows = await cursor.fetchall()
        return {r["habit_key"]: bool(r["completed"]) for r in rows}
    finally:
        await db.close()


async def ensure_day_rows(date: str) -> None:
    """Create rows for all habits on this date if missing."""
    db = await get_db()
    try:
        habits = await get_habits()
        for h in habits:
            await db.execute(
                "INSERT OR IGNORE INTO daily_log (date, habit_key) VALUES (?, ?)",
                (date, h["key"]),
            )
        await db.commit()
    finally:
        await db.close()


async def toggle_habit(date: str, habit_key: str) -> bool:
    """Toggle completed state. Return new state."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT completed FROM daily_log WHERE date = ? AND habit_key = ?",
            (date, habit_key),
        )
        row = await cursor.fetchone()
        if row is None:
            await db.execute(
                "INSERT INTO daily_log (date, habit_key, completed, completed_at) "
                "VALUES (?, ?, 1, datetime('now'))",
                (date, habit_key),
            )
            await db.commit()
            return True

        new_val = 0 if row["completed"] else 1
        completed_at = "datetime('now')" if new_val else None
        if new_val:
            await db.execute(
                "UPDATE daily_log SET completed = 1, completed_at = datetime('now') "
                "WHERE date = ? AND habit_key = ?",
                (date, habit_key),
            )
        else:
            await db.execute(
                "UPDATE daily_log SET completed = 0, completed_at = NULL "
                "WHERE date = ? AND habit_key = ?",
                (date, habit_key),
            )
        await db.commit()
        return bool(new_val)
    finally:
        await db.close()


async def has_daily_message(date: str) -> bool:
    """Check if rows exist for this date (proxy for 'message sent')."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM daily_log WHERE date = ?", (date,)
        )
        row = await cursor.fetchone()
        return row["cnt"] > 0
    finally:
        await db.close()
