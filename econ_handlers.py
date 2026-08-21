from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputRichMessage, Message

import econ_db as edb
from econ_keyboards import (
    close_keyboard,
    confirm_keyboard,
    input_keyboard,
    list_keyboard,
    note_keyboard,
    notes_keyboard,
    prompt_keyboard,
)
from econ_render import build_list_html, build_note_html
from keyboards import MENU_LABELS

logger = logging.getLogger(__name__)
econ_router = Router(name="econ")

BUTTON_TEXT = "Экономика"


class EconSG(StatesGroup):
    add_title = State()
    add_body = State()
    edit_title = State()
    edit_body = State()
    search = State()


async def _send_list(bot: Bot, chat_id: int, state: FSMContext,
                     notes=None, query: str | None = None) -> None:
    if notes is None:
        notes = await edb.get_notes()
    marks, per_topic = await edb.progress()
    pending = await edb.pending_topics()
    html = build_list_html(notes, marks, per_topic, pending, query)
    msg = await bot.send_rich_message(
        chat_id=chat_id,
        rich_message=InputRichMessage(html=html, skip_entity_detection=True),
        reply_markup=list_keyboard(bool(notes)),
    )
    await state.update_data(econ_msg_id=msg.message_id, econ_chat_id=chat_id)


async def _refresh_list(bot: Bot, state: FSMContext, markup=None) -> None:
    data = await state.get_data()
    chat_id, msg_id = data.get("econ_chat_id"), data.get("econ_msg_id")
    if not chat_id or not msg_id:
        return
    notes = await edb.get_notes()
    marks, per_topic = await edb.progress()
    html = build_list_html(notes, marks, per_topic, await edb.pending_topics())
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            rich_message=InputRichMessage(html=html, skip_entity_detection=True),
            reply_markup=markup if markup is not None else list_keyboard(bool(notes)),
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning("Econ list refresh failed: %s", e)


async def _set_markup(callback: CallbackQuery, markup) -> None:
    try:
        await callback.message.edit_reply_markup(reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def _prompt(bot: Bot, state: FSMContext, chat_id: int, text: str, markup) -> None:
    data = await state.get_data()
    old = data.get("econ_prompt_id")
    if old:
        try:
            await bot.delete_message(chat_id, old)
        except TelegramBadRequest:
            pass
    msg = await bot.send_message(chat_id, text, reply_markup=markup)
    await state.update_data(econ_prompt_id=msg.message_id, econ_prompt_chat=chat_id)


async def _clear_prompt(bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    msg_id, chat_id = data.get("econ_prompt_id"), data.get("econ_prompt_chat")
    if msg_id and chat_id:
        try:
            await bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest:
            pass
    await state.update_data(econ_prompt_id=None)


async def _consume(message: Message) -> str:
    text = (message.text or "").strip()
    try:
        await message.delete()
    except TelegramBadRequest:
        pass
    return text


async def offer_note(bot: Bot, chat_id: int) -> None:
    """Ask for a write-up when a topic has just been finished on the day card."""
    pending = await edb.pending_topics()
    if pending <= 0:
        return
    number = await edb.topics_completed()
    await bot.send_message(
        chat_id,
        f"📈 Тема {number} пройдена. Запишем конспект?",
        reply_markup=prompt_keyboard(),
    )


# --- entry point -------------------------------------------------------------

@econ_router.message(F.text == BUTTON_TEXT)
async def btn_econ(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    await _send_list(message.bot, message.chat.id, state)


# --- callbacks ---------------------------------------------------------------

@econ_router.callback_query(F.data.startswith("ec:"))
async def cb_econ(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    action = parts[1]
    bot = callback.bot
    chat_id = callback.message.chat.id

    if action == "noop":
        await callback.answer()
        return

    if action == "close":
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await callback.answer()
        return

    if action == "skip":
        if await state.get_state() == EconSG.add_body.state:
            data = await state.get_data()
            await edb.add_note(data["new_title"], "")
            await state.set_state(None)
            await _clear_prompt(bot, state)
            await _refresh_list(bot, state)
            await callback.answer("Записано без текста")
            return
        await callback.answer()
        return

    if action == "cancel":
        await state.set_state(None)
        await _clear_prompt(bot, state)
        await callback.answer("Отменено")
        return

    if action == "list":
        await _refresh_list(bot, state)
        await callback.answer()
        return

    if action == "add":
        await state.set_state(EconSG.add_title)
        await state.update_data(econ_chat_id=chat_id)
        number = await edb.notes_count() + 1
        await _prompt(bot, state, chat_id,
                      f"Тема {number}. Как называется?", input_keyboard())
        await callback.answer()
        return

    if action == "search":
        await state.set_state(EconSG.search)
        await _prompt(bot, state, chat_id, "Что ищем?", input_keyboard())
        await callback.answer()
        return

    if action == "open":
        notes = await edb.get_notes()
        if len(parts) == 2:
            await _set_markup(callback, notes_keyboard(notes, "ec:open", "ec:list"))
            await callback.answer()
            return
        note = await edb.get_note(int(parts[2]))
        if note is None:
            await callback.answer("Не найдено", show_alert=True)
            return
        chunks = build_note_html(note)
        for i, chunk in enumerate(chunks):
            await bot.send_rich_message(
                chat_id=chat_id,
                rich_message=InputRichMessage(html=chunk, skip_entity_detection=True),
                reply_markup=note_keyboard(note["id"]) if i == len(chunks) - 1 else None,
            )
        await callback.answer()
        return

    if action == "edit":
        notes = await edb.get_notes()
        if len(parts) == 2:
            await _set_markup(callback, notes_keyboard(notes, "ec:edit", "ec:list"))
            await callback.answer()
            return
        await _set_markup(callback, note_keyboard(int(parts[2])))
        await callback.answer()
        return

    if action in ("ret", "reb"):
        note_id = int(parts[2])
        note = await edb.get_note(note_id)
        if note is None:
            await callback.answer("Не найдено", show_alert=True)
            return
        await state.update_data(note_id=note_id, econ_chat_id=chat_id)
        if action == "ret":
            await state.set_state(EconSG.edit_title)
            await _prompt(bot, state, chat_id,
                          f"Новое название вместо «{note['title']}»:", input_keyboard())
        else:
            await state.set_state(EconSG.edit_body)
            await _prompt(bot, state, chat_id,
                          f"Новый текст для «{note['title']}»:", input_keyboard())
        await callback.answer()
        return

    if action == "del":
        note_id = int(parts[2])
        await _set_markup(callback, confirm_keyboard(f"ec:delok:{note_id}", "ec:close"))
        await callback.answer("Удалить тему?")
        return

    if action == "delok":
        await edb.delete_note(int(parts[2]))
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            pass
        await _refresh_list(bot, state)
        await callback.answer("Тема удалена")
        return

    await callback.answer()


# --- text input --------------------------------------------------------------

@econ_router.message(EconSG.add_title, ~F.text.in_(MENU_LABELS))
async def input_add_title(message: Message, state: FSMContext) -> None:
    title = await _consume(message)
    if not title:
        return
    await state.update_data(new_title=title)
    await state.set_state(EconSG.add_body)
    await _prompt(message.bot, state, message.chat.id,
                  f"«{title}» — теперь сам конспект:", input_keyboard(skip=True))


@econ_router.message(EconSG.add_body, ~F.text.in_(MENU_LABELS))
async def input_add_body(message: Message, state: FSMContext) -> None:
    body = await _consume(message)
    data = await state.get_data()
    await edb.add_note(data["new_title"], body)
    await state.set_state(None)
    await _clear_prompt(message.bot, state)
    await _refresh_list(message.bot, state)
    await message.answer("✅ Тема записана.")


@econ_router.message(EconSG.edit_title, ~F.text.in_(MENU_LABELS))
async def input_edit_title(message: Message, state: FSMContext) -> None:
    title = await _consume(message)
    if not title:
        return
    data = await state.get_data()
    await edb.update_note(data["note_id"], title=title)
    await state.set_state(None)
    await _clear_prompt(message.bot, state)
    await _refresh_list(message.bot, state)
    await message.answer("✅ Название обновлено.")


@econ_router.message(EconSG.edit_body, ~F.text.in_(MENU_LABELS))
async def input_edit_body(message: Message, state: FSMContext) -> None:
    body = await _consume(message)
    data = await state.get_data()
    await edb.update_note(data["note_id"], body=body)
    await state.set_state(None)
    await _clear_prompt(message.bot, state)
    await _refresh_list(message.bot, state)
    await message.answer("✅ Текст обновлён.")


@econ_router.message(EconSG.search, ~F.text.in_(MENU_LABELS))
async def input_search(message: Message, state: FSMContext) -> None:
    query = await _consume(message)
    await state.set_state(None)
    await _clear_prompt(message.bot, state)
    if not query:
        return
    found = await edb.search_notes(query)
    await _send_list(message.bot, message.chat.id, state, notes=found, query=query)
