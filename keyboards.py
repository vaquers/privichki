from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# The custom emoji is drawn before the button text and Telegram rejects empty
# text, so an icon-only button is always left of centre by half that gap. Short
# labels make the icon read as a prefix instead of a misaligned icon.
BUTTON_LABEL = {
    "math": "Матем",
    "dev": "Сайты",
    "sport": "Спорт",
    "economics": "Эконом",
    "shower": "Душ",
    "sleep": "Сон",
}

# Reply-keyboard labels. Input flows must not swallow these, otherwise a
# half-finished flow traps every button press.
MENU_LABELS = ["Сегодня", "Статистика", "Манул", "Экономика", "Календарь"]

# Longest task label on a button before it gets an ellipsis.
TASK_LABEL_LEN = 24


def build_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня"), KeyboardButton(text="Статистика")],
            [KeyboardButton(text="Манул"), KeyboardButton(text="Экономика")],
            [KeyboardButton(text="Календарь")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# Buttons are laid out in rows of this many, matching the card grid.
GRID_COLS = 3


def _task_label(title: str) -> str:
    title = " ".join(title.split())
    return title if len(title) <= TASK_LABEL_LEN else title[: TASK_LABEL_LEN - 1] + "…"


def build_habits_keyboard(
    date: str,
    habits: list[dict],
    state: dict[str, bool],
    skipped: bool = False,
    tasks: list[dict] | None = None,
) -> InlineKeyboardMarkup:
    """Buttons for the day: scheduled habits, then this day's own tasks.

    Habits turn blue when done and tasks turn green, so the two kinds stay
    apart at a glance.
    """
    sorted_habits = sorted(habits, key=lambda h: h["sort_order"])
    buttons = []
    for h in sorted_habits:
        buttons.append(InlineKeyboardButton(
            text=BUTTON_LABEL.get(h["key"], h["name"]),
            icon_custom_emoji_id=h.get("custom_emoji_id"),
            style=ButtonStyle.PRIMARY if state.get(h["key"], False) else None,
            callback_data=f"toggle:{date}:{h['key']}",
        ))

    rows = [buttons[i:i + GRID_COLS] for i in range(0, len(buttons), GRID_COLS)]

    tasks = tasks or []
    task_buttons = [
        InlineKeyboardButton(
            text=_task_label(t["title"]),
            style=ButtonStyle.SUCCESS if t["completed"] else None,
            callback_data=f"task:{date}:{t['id']}",
        )
        for t in tasks
    ]
    rows += [task_buttons[i:i + 2] for i in range(0, len(task_buttons), 2)]

    rows.append([InlineKeyboardButton(
        text="Вернуть день" if skipped else "Пропустить день",
        callback_data=f"skip:{date}:{0 if skipped else 1}",
    )])

    last = [InlineKeyboardButton(text="Добавить задачу", callback_data=f"taskadd:{date}")]
    if tasks:
        last.append(
            InlineKeyboardButton(text="Удалить задачу", callback_data=f"taskdel:{date}")
        )
    rows.append(last)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_task_delete_keyboard(date: str, tasks: list[dict]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=_task_label(t["title"]), callback_data=f"taskdel:{date}:{t['id']}"
        )]
        for t in tasks
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"dayback:{date}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_calendar_keyboard(
    year: int, month: int, grid, statuses: dict[str, str], today: str
) -> InlineKeyboardMarkup:
    """Month grid. Colour carries the day's state so the month reads at a glance."""
    from calendar_view import format_month, month_title, shift_month

    style_for = {
        "perfect": ButtonStyle.SUCCESS,
        "skipped": ButtonStyle.DANGER,
    }

    prev_y, prev_m = shift_month(year, month, -1)
    next_y, next_m = shift_month(year, month, 1)
    rows = [[
        InlineKeyboardButton(text="‹", callback_data=f"cal:m:{format_month(prev_y, prev_m)}"),
        InlineKeyboardButton(text=month_title(year, month), callback_data="cal:noop"),
        InlineKeyboardButton(text="›", callback_data=f"cal:m:{format_month(next_y, next_m)}"),
    ]]
    rows.append([
        InlineKeyboardButton(text=d, callback_data="cal:noop")
        for d in ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
    ])

    for week in grid:
        row = []
        for day in week:
            if day is None:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal:noop"))
                continue
            iso = day.isoformat()
            status = statuses.get(iso, "empty")
            style = style_for.get(status)
            if style is None and iso == today:
                style = ButtonStyle.PRIMARY
            row.append(InlineKeyboardButton(
                text=str(day.day), style=style, callback_data=f"cal:d:{iso}"
            ))
        rows.append(row)
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
