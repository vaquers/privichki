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

# Reply-keyboard labels. Input flows must not swallow these, otherwise a
# half-finished flow traps every button press.
MENU_LABELS = ["Сегодня", "Статистика", "Манул", "Экономика"]


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Статистика")],
            [KeyboardButton(text="Манул"), KeyboardButton(text="Экономика")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# Buttons are laid out in rows of this many, matching the card grid.
GRID_COLS = 3


def build_habits_keyboard(
    date: str,
    habits: list[dict],
    state: dict[str, bool],
    skipped: bool = False,
) -> InlineKeyboardMarkup:
    """Emoji-only buttons for the day's habits, in rows matching the card grid."""
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

    rows = [buttons[i:i + GRID_COLS] for i in range(0, len(buttons), GRID_COLS)]
    rows.append([InlineKeyboardButton(
        text="↩️ Вернуть день" if skipped else "🚫 Пропустить день",
        callback_data=f"skip:{date}:{0 if skipped else 1}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Неделя", callback_data="stats:week"),
        InlineKeyboardButton(text="Месяц", callback_data="stats:month"),
        InlineKeyboardButton(text="Всё время", callback_data="stats:all"),
    ]])


def build_site_offer_keyboard() -> InlineKeyboardMarkup:
    """Offered after a site is ticked off: log it in the client table too."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Записать в таблицу", callback_data="cl:quickadd")],
        [InlineKeyboardButton(text="Позже", callback_data="cl:close")],
    ])
