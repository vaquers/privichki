from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
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
from keyboards import (
    build_habits_keyboard,
    build_main_keyboard,
    build_site_offer_keyboard,
    build_stats_keyboard,
)
from render import render_day_card, render_stats_card
from stats import compute_stats

logger = logging.getLogger(__name__)
router = Router()


def _today() -> str:
    import zoneinfo
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


async def _render_day(date: str):
    """Card image and keyboard for the habits scheduled on that date."""
    habits = await get_day_habits(date)
    state = await get_day_state(date)
    skipped = await is_day_skipped(date)
    img = render_day_card(date, habits, state)
    kb = build_habits_keyboard(date, habits, state, skipped=skipped)
    return img, kb


async def send_day_card(bot: Bot, chat_id: int, date: str) -> None:
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
