from __future__ import annotations

import json

from db import get_pool

KIND_TEXT = "text"
KIND_VIDEO = "video"

# The table as it should look: (name, kind, quick values offered as buttons).
# Order matters -- the first column is used as the row label in menus.
SEED_COLUMNS: list[tuple[str, str, list[str]]] = [
    ("Компания", KIND_TEXT, []),
    ("Текст сообщения", KIND_TEXT, []),
    ("Текст ответа", KIND_TEXT, ["жду"]),
    ("Видео сайта", KIND_VIDEO, []),
    ("Комментарий", KIND_TEXT, []),
]

# Columns from earlier versions that carry the same data under a new name.
RENAMED_COLUMNS = {"Текст обращения": "Текст сообщения"}

# Columns from earlier versions that are no longer wanted. Their values are
# copied into client_values_archive before the column goes, because dropping a
# column takes its data with it and that cannot be undone.
DROPPED_COLUMNS = [
    "Персональное обращение",
    "Ответ",
    "Созвон",
    "Причина",
    "Вывод",
    "Контакт",
    "Статус",
]


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
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS client_values_archive (
                id SERIAL PRIMARY KEY,
                company_id INTEGER,
                column_name TEXT NOT NULL,
                value TEXT NOT NULL,
                archived_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute(
            f"ALTER TABLE client_columns ADD COLUMN IF NOT EXISTS kind TEXT "
            f"NOT NULL DEFAULT '{KIND_TEXT}'"
        )
        await conn.execute(
            "ALTER TABLE client_columns ADD COLUMN IF NOT EXISTS quick_values TEXT"
        )
        await _migrate_columns(conn)


async def _migrate_columns(conn) -> None:
    """Bring the column set in line with SEED_COLUMNS, keeping the data that stays."""
    existing = {
        r["name"]: r["id"]
        for r in await conn.fetch("SELECT id, name FROM client_columns")
    }

    # 1. renames first, so the data lands under the new name instead of being
    #    archived with the old column and recreated empty
    for old, new in RENAMED_COLUMNS.items():
        if old in existing and new not in existing:
            await conn.execute(
                "UPDATE client_columns SET name = $2 WHERE id = $1", existing[old], new
            )
            existing[new] = existing.pop(old)

    # 2. archive and drop what is no longer wanted
    for name in DROPPED_COLUMNS:
        column_id = existing.get(name)
        if column_id is None:
            continue
        await conn.execute(
            "INSERT INTO client_values_archive (company_id, column_name, value) "
            "SELECT company_id, $2, value FROM client_values "
            "WHERE column_id = $1 AND value <> ''",
            column_id, name,
        )
        await conn.execute("DELETE FROM client_columns WHERE id = $1", column_id)
        existing.pop(name)

    # 3. create anything missing and set kind/quick values on the known columns
    for order, (name, kind, quick) in enumerate(SEED_COLUMNS):
        quick_json = json.dumps(quick, ensure_ascii=False) if quick else None
        if name in existing:
            await conn.execute(
                "UPDATE client_columns SET kind = $2, quick_values = $3, sort_order = $4 "
                "WHERE id = $1",
                existing[name], kind, quick_json, order,
            )
        else:
            await conn.execute(
                "INSERT INTO client_columns (name, sort_order, kind, quick_values) "
                "VALUES ($1, $2, $3, $4)",
                name, order, kind, quick_json,
            )

    # 4. push any hand-made columns after the seeded ones, keeping their order
    extras = await conn.fetch(
        "SELECT id FROM client_columns WHERE name <> ALL($1::text[]) "
        "ORDER BY sort_order, id",
        [name for name, _, _ in SEED_COLUMNS],
    )
    for i, row in enumerate(extras):
        await conn.execute(
            "UPDATE client_columns SET sort_order = $2 WHERE id = $1",
            row["id"], len(SEED_COLUMNS) + i,
        )


# --- read -------------------------------------------------------------------

def _parse_quick(raw) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def is_video(column: dict) -> bool:
    return column.get("kind") == KIND_VIDEO


async def get_columns() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, sort_order, kind, quick_values FROM client_columns "
            "ORDER BY sort_order, id"
        )
        return [
            {**dict(r), "quick_values": _parse_quick(r["quick_values"])} for r in rows
        ]


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
    """Human label for a company row -- value of the first text column."""
    for col in columns:
        if is_video(col):
            continue
        text = " ".join((row["values"].get(col["id"]) or "").split())
        if text:
            return text if len(text) <= limit else text[: limit - 1] + "…"
    return f"Компания #{row['id']}"


# --- companies --------------------------------------------------------------

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


# --- columns ----------------------------------------------------------------

async def add_column(name: str, kind: str = KIND_TEXT) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM client_columns"
        )
        return await conn.fetchval(
            "INSERT INTO client_columns (name, sort_order, kind) VALUES ($1, $2, $3) "
            "RETURNING id",
            name, row["n"], kind,
        )


async def rename_column(column_id: int, name: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE client_columns SET name = $2 WHERE id = $1", column_id, name)


async def delete_column(column_id: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        name = await conn.fetchval("SELECT name FROM client_columns WHERE id = $1", column_id)
        if name is not None:
            await conn.execute(
                "INSERT INTO client_values_archive (company_id, column_name, value) "
                "SELECT company_id, $2, value FROM client_values "
                "WHERE column_id = $1 AND value <> ''",
                column_id, name,
            )
        await conn.execute("DELETE FROM client_columns WHERE id = $1", column_id)


# --- reordering -------------------------------------------------------------

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
