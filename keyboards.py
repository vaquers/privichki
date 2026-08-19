from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# Telegram requires button text even when a custom emoji is used as its icon.
# A zero-width space keeps the habit buttons icon-only without duplicating the
# custom emoji with its regular Unicode fallback.
CUSTOM_EMOJI_BUTTON_TEXT = "\u200b"


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Статистика")],
            [KeyboardButton(text="Манул")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def build_habits_keyboard(
    date: str,
    habits: list[dict],
    state: dict[str, bool],
) -> InlineKeyboardMarkup:
    """4 emoji-only buttons in one row, fixed order by sort_order."""
    sorted_habits = sorted(habits, key=lambda h: h["sort_order"])
    buttons = []
    for h in sorted_habits:
        custom_emoji_id = h.get("custom_emoji_id")
        buttons.append(InlineKeyboardButton(
            text=CUSTOM_EMOJI_BUTTON_TEXT if custom_emoji_id else h["emoji"],
            icon_custom_emoji_id=custom_emoji_id,
            style=ButtonStyle.SUCCESS if state.get(h["key"], False) else None,
            callback_data=f"toggle:{date}:{h['key']}",
        ))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def build_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Неделя", callback_data="stats:week"),
        InlineKeyboardButton(text="Месяц", callback_data="stats:month"),
        InlineKeyboardButton(text="Всё время", callback_data="stats:all"),
    ]])
