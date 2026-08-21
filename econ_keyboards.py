from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BACK = "⬅️ Назад"


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def list_keyboard(has_notes: bool) -> InlineKeyboardMarkup:
    rows = [[_btn("➕ Тема", "ec:add")]]
    if has_notes:
        rows[0].append(_btn("🔍 Поиск", "ec:search"))
        rows.append([_btn("📖 Открыть", "ec:open"), _btn("✏️ Редактировать", "ec:edit")])
    return _kb(rows)


def notes_keyboard(notes: list[dict], prefix: str, back: str) -> InlineKeyboardMarkup:
    rows = [
        [_btn(f"{n['number']}. {_short(n['title'])}", f"{prefix}:{n['id']}")]
        for n in notes
    ]
    if not rows:
        rows = [[_btn("Пока нет тем", "ec:noop")]]
    rows.append([_btn(BACK, back)])
    return _kb(rows)


def note_keyboard(note_id: int) -> InlineKeyboardMarkup:
    return _kb([
        [_btn("✏️ Название", f"ec:ret:{note_id}"), _btn("📝 Текст", f"ec:reb:{note_id}")],
        [_btn("🗑 Удалить", f"ec:del:{note_id}")],
        [_btn("✖️ Закрыть", "ec:close")],
    ])


def confirm_keyboard(yes: str, back: str) -> InlineKeyboardMarkup:
    return _kb([[_btn("🗑 Да, удалить", yes), _btn("Отмена", back)]])


def input_keyboard(skip: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if skip:
        rows.append([_btn("⏭ Пропустить", "ec:skip")])
    rows.append([_btn("✖️ Отмена", "ec:cancel")])
    return _kb(rows)


def close_keyboard() -> InlineKeyboardMarkup:
    return _kb([[_btn("✖️ Закрыть", "ec:close")]])


def prompt_keyboard() -> InlineKeyboardMarkup:
    """Offered right after a topic is finished on the day card."""
    return _kb([
        [_btn("📝 Записать сейчас", "ec:add")],
        [_btn("Позже", "ec:close")],
    ])


def _short(text: str, limit: int = 40) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
