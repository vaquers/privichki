from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
)

from config import TIMEZONE
from db import (
    ensure_day_rows,
    get_day_habits,
    get_day_state,
    is_day_skipped,
    set_day_skipped,
    toggle_habit,
)
from econ_handlers import offer_note
import tasks_db as tdb
from calendar_view import month_grid, parse_month
from stats import day_status, month_overview
from keyboards import (
    MENU_LABELS,
    menu_fingerprint,
    build_calendar_keyboard,
    build_habits_keyboard,
    build_main_keyboard,
    build_site_offer_keyboard,
    build_stats_keyboard,
    build_task_delete_keyboard,
)
from render import render_day_card, render_stats_card
from stats import compute_stats

logger = logging.getLogger(__name__)
router = Router()


def _today() -> str:
    import zoneinfo
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


class DaySG(StatesGroup):
    add_task = State()


async def _render_day(date: str):
    """Card image and keyboard for the habits and tasks of that date."""
    habits = await get_day_habits(date)
    state = await get_day_state(date)
    skipped = await is_day_skipped(date)
    tasks = await tdb.get_tasks(date)
    img = render_day_card(date, habits, state, tasks)
    kb = build_habits_keyboard(date, habits, state, skipped=skipped, tasks=tasks)
    return img, kb


async def send_day_card(bot: Bot, chat_id: int, date: str) -> None:
    # Rows are only pre-created from today onwards. Opening an old day from the
    # calendar must not invent unfinished rows for it, because the statistics
    # count every row as something that was expected that day.
    if date >= _today():
        await ensure_day_rows(date)
    img, kb = await _render_day(date)
    await bot.send_photo(
        chat_id=chat_id,
        photo=BufferedInputFile(img.read(), filename=f"day_{date}.png"),
        reply_markup=kb,
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я твой трекер привычек.\nКаждое утро присылаю карточку дня.",
        reply_markup=build_main_keyboard(),
    )
    await send_day_card(message.bot, message.chat.id, _today())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Меню обновлено.", reply_markup=build_main_keyboard())


@router.message(F.text == "Сегодня")
async def btn_today(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_day_card(message.bot, message.chat.id, _today())


@router.message(F.text == "Статистика")
async def btn_stats(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выбери период:", reply_markup=build_stats_keyboard())


@router.callback_query(lambda cb: cb.data and cb.data.startswith("stats:"))
async def cb_stats(callback: CallbackQuery) -> None:
    period = callback.data.split(":")[1]
    data = await compute_stats(period)
    img = render_stats_card(data)
    await callback.message.answer_photo(
        photo=BufferedInputFile(img.read(), filename=f"stats_{period}.png"),
    )
    await callback.answer()


async def _update_day_message(callback: CallbackQuery, date: str) -> None:
    img, kb = await _render_day(date)
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=BufferedInputFile(img.read(), filename=f"day_{date}.png"),
            ),
            reply_markup=kb,
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(lambda cb: cb.data and cb.data.startswith("toggle:"))
async def cb_toggle(callback: CallbackQuery) -> None:
    _, date, habit_key = callback.data.split(":")
    now_done = await toggle_habit(date, habit_key)

    await _update_day_message(callback, date)
    await callback.answer()

    if not now_done:
        return

    # Ticking these off opens the next step rather than ending there.
    if habit_key == "economics":
        await offer_note(callback.bot, callback.message.chat.id)
    elif habit_key == "dev":
        await callback.message.answer(
            "💻 Сайт готов. Занести его в таблицу?",
            reply_markup=build_site_offer_keyboard(),
        )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("skip:"))
async def cb_skip(callback: CallbackQuery) -> None:
    _, date, flag = callback.data.split(":")
    skipped = flag == "1"
    await set_day_skipped(date, skipped)
    await _update_day_message(callback, date)
    await callback.answer(
        "День отмечен как пропущенный — в статистику не пойдёт"
        if skipped else "День снова считается"
    )


# --- per-day tasks -----------------------------------------------------------

@router.callback_query(lambda cb: cb.data and cb.data.startswith("task:"))
async def cb_task_toggle(callback: CallbackQuery) -> None:
    _, date, task_id = callback.data.split(":")
    await tdb.toggle_task(int(task_id))
    await _update_day_message(callback, date)
    await callback.answer()


@router.callback_query(lambda cb: cb.data and cb.data.startswith("taskadd:"))
async def cb_task_add(callback: CallbackQuery, state: FSMContext) -> None:
    date = callback.data.split(":")[1]
    await state.set_state(DaySG.add_task)
    await state.update_data(task_date=date, day_msg_id=callback.message.message_id)
    await callback.message.answer(f"Задача на {date}. Напиши её текстом:")
    await callback.answer()


@router.message(DaySG.add_task, ~F.text.in_(MENU_LABELS))
async def input_task(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    data = await state.get_data()
    date = data.get("task_date")
    await state.set_state(None)
    if not title or not date:
        return
    await tdb.add_task(date, title)
    await send_day_card(message.bot, message.chat.id, date)


@router.callback_query(lambda cb: cb.data and cb.data.startswith("taskdel:"))
async def cb_task_delete(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    date = parts[1]
    if len(parts) == 2:
        tasks = await tdb.get_tasks(date)
        if not tasks:
            await callback.answer("Задач нет")
            return
        await callback.message.edit_reply_markup(
            reply_markup=build_task_delete_keyboard(date, tasks)
        )
        await callback.answer("Какую убрать?")
        return

    await tdb.delete_task(int(parts[2]))
    await _update_day_message(callback, date)
    await callback.answer("Задача удалена")


@router.callback_query(lambda cb: cb.data and cb.data.startswith("dayback:"))
async def cb_day_back(callback: CallbackQuery) -> None:
    date = callback.data.split(":")[1]
    await _update_day_message(callback, date)
    await callback.answer()


# --- calendar ----------------------------------------------------------------

async def _calendar_markup(year: int, month: int):
    overview = await month_overview(year, month)
    statuses = {day: day_status(entry) for day, entry in overview.items()}
    return build_calendar_keyboard(
        year, month, month_grid(year, month), statuses, _today()
    )


@router.message(F.text == "Календарь")
async def btn_calendar(message: Message, state: FSMContext) -> None:
    await state.clear()
    today = datetime.fromisoformat(_today())
    await message.answer(
        "Выбери день. Зелёный — всё закрыто, красный — пропущен.",
        reply_markup=await _calendar_markup(today.year, today.month),
    )


@router.callback_query(lambda cb: cb.data and cb.data.startswith("cal:"))
async def cb_calendar(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    action = parts[1]

    if action == "noop":
        await callback.answer()
        return

    if action == "m":
        year, month = parse_month(parts[2])
        try:
            await callback.message.edit_reply_markup(
                reply_markup=await _calendar_markup(year, month)
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise
        await callback.answer()
        return

    if action == "d":
        await send_day_card(callback.bot, callback.message.chat.id, parts[2])
        await callback.answer()
        return

    await callback.answer()
