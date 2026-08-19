from __future__ import annotations

from db import get_pool

# Default columns created on first run. Order matters: the first column is used
# as the row label in selection menus.
SEED_COLUMNS = [
    "Компания",
    "Персональное обращение",
    "Ответ",
    "Созвон",
    "Причина",
    "Вывод",
    "Текст обращения",
    "Текст ответа",
]

# Columns seeded by earlier versions. A database still holding exactly these and
# no companies is re-seeded with SEED_COLUMNS; anything else is left untouched so
# that hand-made columns and real data are never dropped on startup.
LEGACY_SEED_COLUMNS = ["Компания", "Контакт", "Статус", "Комментарий"]


async def init_clients_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS client_columns (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS client_companies (
                id SERIAL PRIMARY KEY,
                sort_order INTEGER NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS client_values (
                company_id INTEGER NOT NULL REFERENCES client_companies(id) ON DELETE CASCADE,
                column_id INTEGER NOT NULL REFERENCES client_columns(id) ON DELETE CASCADE,
                value TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (company_id, column_id)
            )
        """)
        await _seed_columns(conn)


async def _seed_columns(conn) -> None:
    """Install SEED_COLUMNS on a fresh table, or upgrade an untouched legacy one."""
    rows = await conn.fetch("SELECT name FROM client_columns ORDER BY sort_order, id")
    existing = [r["name"] for r in rows]

    if existing == SEED_COLUMNS:
        return
    if existing:
        if existing != LEGACY_SEED_COLUMNS:
            return  # customised by hand -- not ours to rewrite
        if await conn.fetchval("SELECT COUNT(*) FROM client_companies"):
            return  # real data present -- keep the columns it was entered under
        await conn.execute("DELETE FROM client_columns")

    for i, name in enumerate(SEED_COLUMNS):
        await conn.execute(
            "INSERT INTO client_columns (name, sort_order) VALUES ($1, $2)", name, i
        )


# --- read ---

async def get_columns() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, sort_order FROM client_columns ORDER BY sort_order, id"
        )
        return [dict(r) for r in rows]


async def get_rows() -> list[dict]:
    """Companies with their values: [{id, sort_order, values: {column_id: str}}]."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        companies = await conn.fetch(
            "SELECT id, sort_order FROM client_companies ORDER BY sort_order, id"
        )
        values = await conn.fetch("SELECT company_id, column_id, value FROM client_values")

    by_company: dict[int, dict[int, str]] = {}
    for v in values:
        by_company.setdefault(v["company_id"], {})[v["column_id"]] = v["value"]

    return [
        {"id": c["id"], "sort_order": c["sort_order"], "values": by_company.get(c["id"], {})}
        for c in companies
    ]


async def get_table() -> tuple[list[dict], list[dict]]:
    return await get_columns(), await get_rows()


def row_label(row: dict, columns: list[dict], limit: int = 28) -> str:
    """Human label for a company row — value of the first column, or a fallback."""
    for col in columns:
        text = (row["values"].get(col["id"]) or "").strip()
        if text:
            return text if len(text) <= limit else text[: limit - 1] + "…"
    return f"Компания #{row['id']}"


# --- companies ---

async def add_company(values: dict[int, str]) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM client_companies"
            )
            company_id = await conn.fetchval(
                "INSERT INTO client_companies (sort_order) VALUES ($1) RETURNING id",
                row["n"],
            )
            for column_id, value in values.items():
                await conn.execute(
                    "INSERT INTO client_values (company_id, column_id, value) "
                    "VALUES ($1, $2, $3)",
                    company_id, column_id, value,
                )
    return company_id


async def delete_company(company_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM client_companies WHERE id = $1", company_id)


async def set_value(company_id: int, column_id: int, value: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO client_values (company_id, column_id, value) VALUES ($1, $2, $3) "
            "ON CONFLICT (company_id, column_id) DO UPDATE SET value = $3",
            company_id, column_id, value,
        )


# --- columns ---

async def add_column(name: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM client_columns"
        )
        return await conn.fetchval(
            "INSERT INTO client_columns (name, sort_order) VALUES ($1, $2) RETURNING id",
            name, row["n"],
        )


async def rename_column(column_id: int, name: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE client_columns SET name = $2 WHERE id = $1", column_id, name)


async def delete_column(column_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM client_columns WHERE id = $1", column_id)


# --- reordering ---

async def _move(table: str, item_id: int, delta: int) -> bool:
    """Swap sort_order with the neighbour in the given direction."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                f"SELECT id FROM {table} ORDER BY sort_order, id FOR UPDATE"
            )
            ids = [r["id"] for r in rows]
            if item_id not in ids:
                return False
            i = ids.index(item_id)
            j = i + delta
            if j < 0 or j >= len(ids):
                return False
            ids[i], ids[j] = ids[j], ids[i]
            for order, cur_id in enumerate(ids):
                await conn.execute(
                    f"UPDATE {table} SET sort_order = $2 WHERE id = $1", cur_id, order
                )
    return True


async def move_column(column_id: int, delta: int) -> bool:
    return await _move("client_columns", column_id, delta)


async def move_company(company_id: int, delta: int) -> bool:
    return await _move("client_companies", company_id, delta)
