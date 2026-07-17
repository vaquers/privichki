from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
)

from config import TIMEZONE
from db import ensure_day_rows, get_day_state, get_habits, toggle_habit
from keyboards import build_habits_keyboard, build_main_keyboard, build_stats_keyboard
from render import render_day_card
from stats import compute_stats

logger = logging.getLogger(__name__)
router = Router()


def _today() -> str:
    import zoneinfo
    tz = zoneinfo.ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


async def send_day_card(bot: Bot, chat_id: int, date: str) -> None:
    await ensure_day_rows(date)
    habits = await get_habits()
    state = await get_day_state(date)
    img = render_day_card(date, habits, state)
    kb = build_habits_keyboard(date, habits, state)
    await bot.send_photo(
        chat_id=chat_id,
        photo=BufferedInputFile(img.read(), filename=f"day_{date}.png"),
        reply_markup=kb,
    )


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я твой трекер привычек.\nКаждое утро присылаю карточку дня.",
        reply_markup=build_main_keyboard(),
    )
    await send_day_card(message.bot, message.chat.id, _today())


@router.message(F.text == "Сегодня")
async def btn_today(message: Message) -> None:
    await send_day_card(message.bot, message.chat.id, _today())


@router.message(F.text == "Статистика")
async def btn_stats(message: Message) -> None:
    await message.answer("Выбери период:", reply_markup=build_stats_keyboard())


@router.callback_query(lambda cb: cb.data and cb.data.startswith("stats:"))
async def cb_stats(callback: CallbackQuery) -> None:
    period = callback.data.split(":")[1]
    text = await compute_stats(period)
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(lambda cb: cb.data and cb.data.startswith("toggle:"))
async def cb_toggle(callback: CallbackQuery) -> None:
    _, date, habit_key = callback.data.split(":")
    await toggle_habit(date, habit_key)

    habits = await get_habits()
    state = await get_day_state(date)
    img = render_day_card(date, habits, state)
    kb = build_habits_keyboard(date, habits, state)

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

    await callback.answer()
