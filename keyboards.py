from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Сегодня"), KeyboardButton(text="Статистика")]],
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
        btn_kwargs: dict = {
            "text": h["emoji"],
            "callback_data": f"toggle:{date}:{h['key']}",
        }
        if h.get("custom_emoji_id"):
            btn_kwargs["icon_custom_emoji_id"] = h["custom_emoji_id"]
        buttons.append(InlineKeyboardButton(**btn_kwargs))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def build_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Неделя", callback_data="stats:week"),
        InlineKeyboardButton(text="Месяц", callback_data="stats:month"),
        InlineKeyboardButton(text="Всё время", callback_data="stats:all"),
    ]])
