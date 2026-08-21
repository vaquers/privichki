from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputRichMessage, Message

import clients_db as cdb
from clients_keyboards import (
    cell_columns_keyboard,
    columns_keyboard,
    close_keyboard,
    columns_list_keyboard,
    companies_keyboard,
    confirm_keyboard,
    edit_keyboard,
    input_keyboard,
    move_column_keyboard,
    move_company_keyboard,
    table_keyboard,
)
from clients_render import build_company_html, build_table_html, paginate_rows
from keyboards import MENU_LABELS

logger = logging.getLogger(__name__)
clients_router = Router(name="clients")

BUTTON_TEXT = "Манул"


class ClientsSG(StatesGroup):
    add_company = State()    # walking columns for a new company
    edit_cell = State()      # single cell value
    add_column = State()     # new column name
    rename_column = State()  # new name for existing column
    fill_column = State()    # walking companies for a freshly added column


# --- table rendering helpers -------------------------------------------------

async def _table_html(page: int) -> tuple[str, int, int]:
    columns, rows = await cdb.get_table()
    page_rows, page, pages, start = paginate_rows(columns, rows, page)
    html = build_table_html(
        columns, page_rows, page, pages, total_rows=len(rows), start=start
    )
    return html, page, pages


async def send_table(bot: Bot, chat_id: int, state: FSMContext, page: int = 0) -> Message:
    html, page, pages = await _table_html(page)
    msg = await bot.send_rich_message(
        chat_id=chat_id,
        rich_message=InputRichMessage(html=html, skip_entity_detection=True),
        reply_markup=table_keyboard(page, pages),
    )
    await state.update_data(table_msg_id=msg.message_id, table_chat_id=chat_id, page=page)
    return msg


async def refresh_table(bot: Bot, state: FSMContext, keep_markup=None) -> None:
    """Re-render the stored table message in place."""
    data = await state.get_data()
    chat_id = data.get("table_chat_id")
    msg_id = data.get("table_msg_id")
    if not chat_id or not msg_id:
        return
    html, page, pages = await _table_html(data.get("page", 0))
    markup = keep_markup if keep_markup is not None else table_keyboard(page, pages)
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            rich_message=InputRichMessage(html=html, skip_entity_detection=True),
            reply_markup=markup,
        )
        await state.update_data(page=page)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning("Table refresh failed: %s", e)


async def _set_markup(callback: CallbackQuery, markup) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def _prompt(bot: Bot, state: FSMContext, chat_id: int, text: str, markup) -> None:
    """Show a single input prompt message, replacing any previous one."""
    data = await state.get_data()
    old = data.get("prompt_msg_id")
    if old:
        try:
            await bot.delete_message(chat_id, old)
        except TelegramBadRequest:
            pass
    msg = await bot.send_message(chat_id, text, reply_markup=markup)
    await state.update_data(prompt_msg_id=msg.message_id, prompt_chat_id=chat_id)


async def _clear_prompt(bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    msg_id, chat_id = data.get("prompt_msg_id"), data.get("prompt_chat_id")
    if msg_id and chat_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest:
            pass
    await state.update_data(prompt_msg_id=None)


async def _finish(bot: Bot, state: FSMContext) -> None:
    await state.set_state(None)
    await _clear_prompt(bot, state)
    await refresh_table(bot, state)


# --- entry point -------------------------------------------------------------

@clients_router.message(F.text == BUTTON_TEXT)
async def btn_clients(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    await send_table(message.bot, message.chat.id, state, page=0)


# --- add company flow --------------------------------------------------------

async def _ask_next_company_field(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    columns = data["columns"]
    idx = data["idx"]
    if idx >= len(columns):
        values = {int(k): v for k, v in data["values"].items()}
        await cdb.add_company(values)
        await _finish(bot, state)
        await bot.send_message(chat_id, "✅ Компания добавлена.")
        return
    col = columns[idx]
    await _prompt(
        bot, state, chat_id,
        f"Введи значение для «{col['name']}»  ({idx + 1}/{len(columns)})",
        input_keyboard(skip=True),
    )


async def _store_company_field(bot: Bot, chat_id: int, state: FSMContext, value: str) -> None:
    data = await state.get_data()
    columns = data["columns"]
    idx = data["idx"]
    values = dict(data["values"])
    values[str(columns[idx]["id"])] = value
    await state.update_data(values=values, idx=idx + 1)
    await _ask_next_company_field(bot, chat_id, state)


# --- fill-column flow (after adding a new column) ----------------------------

async def _ask_next_column_fill(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    targets = data["targets"]
    idx = data["idx"]
    if idx >= len(targets):
        await _finish(bot, state)
        await bot.send_message(chat_id, "✅ Колонка заполнена.")
        return
    target = targets[idx]
    await _prompt(
        bot, state, chat_id,
        f"«{data['column_name']}» для «{target['label']}»  ({idx + 1}/{len(targets)})",
        input_keyboard(skip=True, finish=True),
    )


# --- callbacks ---------------------------------------------------------------

@clients_router.callback_query(F.data.startswith("cl:"))
async def cb_clients(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    action = parts[1]
    bot = callback.bot
    chat_id = callback.message.chat.id

    # remember which message holds the table
    await state.update_data(
        table_msg_id=callback.message.message_id, table_chat_id=chat_id
    )

    if action == "noop":
        await callback.answer()
        return

    if action == "p":
        await state.update_data(page=int(parts[2]))
        await refresh_table(bot, state)
        await callback.answer()
        return

    if action == "root":
        data = await state.get_data()
        _, page, pages = await _table_html(data.get("page", 0))
        await _set_markup(callback, table_keyboard(page, pages))
        await callback.answer()
        return

    if action == "edit":
        await _set_markup(callback, edit_keyboard())
        await callback.answer()
        return

    if action == "cols":
        await _set_markup(callback, columns_keyboard())
        await callback.answer()
        return

    if action == "cancel":
        await state.set_state(None)
        await _clear_prompt(bot, state)
        await callback.answer("Отменено")
        return

    # --- opened from the day card after a site was ticked off ---
    if action == "quickadd":
        await send_table(bot, chat_id, state, page=0)
        columns = await cdb.get_columns()
        if not columns:
            await callback.answer("Сначала добавь колонку", show_alert=True)
            return
        await state.set_state(ClientsSG.add_company)
        await state.update_data(columns=columns, idx=0, values={})
        await _ask_next_company_field(bot, chat_id, state)
        await callback.answer()
        return

    # --- add company ---
    if action == "add":
        columns = await cdb.get_columns()
        if not columns:
            await callback.answer("Сначала добавь колонку", show_alert=True)
            return
        await state.set_state(ClientsSG.add_company)
        await state.update_data(columns=columns, idx=0, values={})
        await _ask_next_company_field(bot, chat_id, state)
        await callback.answer()
        return

    if action == "skip":
        current = await state.get_state()
        if current == ClientsSG.add_company.state:
            await _store_company_field(bot, chat_id, state, "")
        elif current == ClientsSG.fill_column.state:
            data = await state.get_data()
            await state.update_data(idx=data["idx"] + 1)
            await _ask_next_column_fill(bot, chat_id, state)
        await callback.answer()
        return

    if action == "done":
        await _finish(bot, state)
        await callback.answer("Готово")
        return

    # --- company card: every value in full ---
    if action == "show":
        columns, rows = await cdb.get_table()
        if len(parts) == 2:
            await _set_markup(callback, companies_keyboard(rows, columns, "cl:show", "cl:root"))
            await callback.answer()
            return
        company_id = int(parts[2])
        row = next((r for r in rows if r["id"] == company_id), None)
        if row is None:
            await callback.answer("Не найдено", show_alert=True)
            return
        number = next(i for i, r in enumerate(rows) if r["id"] == company_id) + 1
        chunks = build_company_html(columns, row, number)
        for i, chunk in enumerate(chunks):
            await bot.send_rich_message(
                chat_id=chat_id,
                rich_message=InputRichMessage(html=chunk, skip_entity_detection=True),
                reply_markup=close_keyboard() if i == len(chunks) - 1 else None,
            )
        await callback.answer()
        return

    if action == "close":
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.answer()
        return

    # --- cell editing ---
    if action == "cell":
        columns, rows = await cdb.get_table()
        await _set_markup(callback, companies_keyboard(rows, columns, "cl:cellc", "cl:edit"))
        await callback.answer()
        return

    if action == "cellc":
        columns = await cdb.get_columns()
        await _set_markup(callback, cell_columns_keyboard(int(parts[2]), columns))
        await callback.answer()
        return

    if action == "cellv":
        company_id, column_id = int(parts[2]), int(parts[3])
        columns, rows = await cdb.get_table()
        column = next((c for c in columns if c["id"] == column_id), None)
        row = next((r for r in rows if r["id"] == company_id), None)
        if column is None or row is None:
            await callback.answer("Не найдено", show_alert=True)
            return
        current = row["values"].get(column_id, "") or "—"
        await state.set_state(ClientsSG.edit_cell)
        await state.update_data(company_id=company_id, column_id=column_id)
        await _prompt(
            bot, state, chat_id,
            f"«{column['name']}» для «{cdb.row_label(row, columns)}»\n"
            f"Сейчас: {current}\n\nВведи новое значение:",
            input_keyboard(skip=False),
        )
        await callback.answer()
        return

    # --- columns ---
    if action == "coladd":
        await state.set_state(ClientsSG.add_column)
        await _prompt(bot, state, chat_id, "Название новой колонки:", input_keyboard(skip=False))
        await callback.answer()
        return

    if action == "colren":
        if len(parts) == 2:
            columns = await cdb.get_columns()
            await _set_markup(callback, columns_list_keyboard(columns, "cl:colren", "cl:cols"))
        else:
            column_id = int(parts[2])
            columns = await cdb.get_columns()
            column = next((c for c in columns if c["id"] == column_id), None)
            if column is None:
                await callback.answer("Не найдено", show_alert=True)
                return
            await state.set_state(ClientsSG.rename_column)
            await state.update_data(column_id=column_id)
            await _prompt(
                bot, state, chat_id,
                f"Новое название для «{column['name']}»:", input_keyboard(skip=False),
            )
        await callback.answer()
        return

    if action == "coldel":
        columns = await cdb.get_columns()
        if len(parts) == 2:
            await _set_markup(callback, columns_list_keyboard(columns, "cl:coldel", "cl:cols"))
        else:
            if len(columns) <= 1:
                await callback.answer("Нельзя удалить последнюю колонку", show_alert=True)
                return
            column_id = int(parts[2])
            column = next((c for c in columns if c["id"] == column_id), None)
            name = column["name"] if column else "?"
            await _set_markup(
                callback,
                confirm_keyboard(f"cl:coldelok:{column_id}", "cl:cols"),
            )
            await callback.answer(f"Удалить колонку «{name}» со всеми данными?")
        return

    if action == "coldelok":
        await cdb.delete_column(int(parts[2]))
        await refresh_table(bot, state, keep_markup=columns_keyboard())
        await callback.answer("Колонка удалена")
        return

    if action == "colmv":
        if len(parts) == 2:
            columns = await cdb.get_columns()
            await _set_markup(callback, columns_list_keyboard(columns, "cl:colmv", "cl:cols"))
        else:
            await _set_markup(callback, move_column_keyboard(int(parts[2])))
        await callback.answer()
        return

    if action == "colmvd":
        column_id, direction = int(parts[2]), parts[3]
        moved = await cdb.move_column(column_id, -1 if direction == "l" else 1)
        if moved:
            await refresh_table(bot, state, keep_markup=move_column_keyboard(column_id))
        await callback.answer("Перемещено" if moved else "Дальше некуда")
        return

    # --- rows ---
    if action == "rowdel":
        columns, rows = await cdb.get_table()
        if len(parts) == 2:
            await _set_markup(callback, companies_keyboard(rows, columns, "cl:rowdel", "cl:edit"))
        else:
            company_id = int(parts[2])
            row = next((r for r in rows if r["id"] == company_id), None)
            label = cdb.row_label(row, columns) if row else "?"
            await _set_markup(callback, confirm_keyboard(f"cl:rowdelok:{company_id}", "cl:edit"))
            await callback.answer(f"Удалить «{label}»?")
            return
        await callback.answer()
        return

    if action == "rowdelok":
        await cdb.delete_company(int(parts[2]))
        await refresh_table(bot, state, keep_markup=edit_keyboard())
        await callback.answer("Компания удалена")
        return

    if action == "rowmv":
        columns, rows = await cdb.get_table()
        if len(parts) == 2:
            await _set_markup(callback, companies_keyboard(rows, columns, "cl:rowmv", "cl:edit"))
        else:
            await _set_markup(callback, move_company_keyboard(int(parts[2])))
        await callback.answer()
        return

    if action == "rowmvd":
        company_id, direction = int(parts[2]), parts[3]
        moved = await cdb.move_company(company_id, -1 if direction == "u" else 1)
        if moved:
            await refresh_table(bot, state, keep_markup=move_company_keyboard(company_id))
        await callback.answer("Перемещено" if moved else "Дальше некуда")
        return

    await callback.answer()


# --- text input handlers -----------------------------------------------------

async def _consume(message: Message) -> str:
    text = (message.text or "").strip()
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    return text


@clients_router.message(ClientsSG.add_company, ~F.text.in_(MENU_LABELS))
async def input_add_company(message: Message, state: FSMContext) -> None:
    value = await _consume(message)
    await _store_company_field(message.bot, message.chat.id, state, value)


@clients_router.message(ClientsSG.edit_cell, ~F.text.in_(MENU_LABELS))
async def input_edit_cell(message: Message, state: FSMContext) -> None:
    value = await _consume(message)
    data = await state.get_data()
    await cdb.set_value(data["company_id"], data["column_id"], value)
    await _finish(message.bot, state)


@clients_router.message(ClientsSG.add_column, ~F.text.in_(MENU_LABELS))
async def input_add_column(message: Message, state: FSMContext) -> None:
    name = await _consume(message)
    if not name:
        return
    column_id = await cdb.add_column(name)
    columns, rows = await cdb.get_table()
    targets = [{"id": r["id"], "label": cdb.row_label(r, columns)} for r in rows]
    if not targets:
        await _finish(message.bot, state)
        await message.answer("✅ Колонка добавлена.")
        return
    await state.set_state(ClientsSG.fill_column)
    await state.update_data(
        column_id=column_id, column_name=name, targets=targets, idx=0
    )
    await refresh_table(message.bot, state)
    await _ask_next_column_fill(message.bot, message.chat.id, state)


@clients_router.message(ClientsSG.rename_column, ~F.text.in_(MENU_LABELS))
async def input_rename_column(message: Message, state: FSMContext) -> None:
    name = await _consume(message)
    if not name:
        return
    data = await state.get_data()
    await cdb.rename_column(data["column_id"], name)
    await _finish(message.bot, state)


@clients_router.message(ClientsSG.fill_column, ~F.text.in_(MENU_LABELS))
async def input_fill_column(message: Message, state: FSMContext) -> None:
    value = await _consume(message)
    data = await state.get_data()
    target = data["targets"][data["idx"]]
    await cdb.set_value(target["id"], data["column_id"], value)
    await state.update_data(idx=data["idx"] + 1)
    await refresh_table(message.bot, state)
    await _ask_next_column_fill(message.bot, message.chat.id, state)
