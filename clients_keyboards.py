from __future__ import annotations

from aiogram.types import DisabledButton, InlineKeyboardButton, InlineKeyboardMarkup

from clients_db import row_label

BACK = "⬅️ Назад"


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def table_keyboard(page: int = 0, pages: int = 1) -> InlineKeyboardMarkup:
    rows = [
        [_btn("➕ Компания", "cl:add"), _btn("✏️ Редактировать", "cl:edit")],
        [_btn("🔍 Открыть компанию", "cl:show")],
    ]
    if pages > 1:
        def _pager(text: str, target: int | None) -> InlineKeyboardButton:
            if target is None:
                return InlineKeyboardButton(text=text, disabled=DisabledButton())
            return _btn(text, f"cl:p:{target}")

        rows.append([
            _pager("◀️", page - 1 if page > 0 else None),
            InlineKeyboardButton(text=f"{page + 1}/{pages}", disabled=DisabledButton()),
            _pager("▶️", page + 1 if page < pages - 1 else None),
        ])
    return _kb(rows)


def edit_keyboard() -> InlineKeyboardMarkup:
    return _kb([
        [_btn("✏️ Изменить ячейку", "cl:cell")],
        [_btn("🗂 Колонки", "cl:cols")],
        [_btn("🗑 Удалить компанию", "cl:rowdel"), _btn("↕️ Порядок", "cl:rowmv")],
        [_btn(BACK, "cl:root")],
    ])


def columns_keyboard() -> InlineKeyboardMarkup:
    return _kb([
        [_btn("➕ Добавить", "cl:coladd"), _btn("✏️ Переименовать", "cl:colren")],
        [_btn("🗑 Удалить", "cl:coldel"), _btn("↔️ Порядок", "cl:colmv")],
        [_btn(BACK, "cl:edit")],
    ])


def companies_keyboard(
    rows: list[dict], columns: list[dict], prefix: str, back: str
) -> InlineKeyboardMarkup:
    buttons = [[_btn(row_label(r, columns), f"{prefix}:{r['id']}")] for r in rows]
    if not buttons:
        buttons = [[_btn("Нет компаний", "cl:noop")]]
    buttons.append([_btn(BACK, back)])
    return _kb(buttons)


def columns_list_keyboard(
    columns: list[dict], prefix: str, back: str
) -> InlineKeyboardMarkup:
    buttons = [[_btn(c["name"], f"{prefix}:{c['id']}")] for c in columns]
    if not buttons:
        buttons = [[_btn("Нет колонок", "cl:noop")]]
    buttons.append([_btn(BACK, back)])
    return _kb(buttons)


def cell_columns_keyboard(company_id: int, columns: list[dict]) -> InlineKeyboardMarkup:
    buttons = [[_btn(c["name"], f"cl:cellv:{company_id}:{c['id']}")] for c in columns]
    buttons.append([_btn(BACK, "cl:cell")])
    return _kb(buttons)


def confirm_keyboard(yes_data: str, back: str) -> InlineKeyboardMarkup:
    return _kb([[_btn("🗑 Да, удалить", yes_data), _btn("Отмена", back)]])


def move_column_keyboard(column_id: int) -> InlineKeyboardMarkup:
    return _kb([
        [_btn("◀️ Влево", f"cl:colmvd:{column_id}:l"),
         _btn("Вправо ▶️", f"cl:colmvd:{column_id}:r")],
        [_btn("✅ Готово", "cl:cols")],
    ])


def move_company_keyboard(company_id: int) -> InlineKeyboardMarkup:
    return _kb([
        [_btn("⬆️ Вверх", f"cl:rowmvd:{company_id}:u"),
         _btn("⬇️ Вниз", f"cl:rowmvd:{company_id}:d")],
        [_btn("✅ Готово", "cl:edit")],
    ])


def input_keyboard(
    skip: bool = True,
    finish: bool = False,
    quick_values: list[str] | None = None,
) -> InlineKeyboardMarkup:
    """Prompt keyboard. Quick values fill the cell without typing anything."""
    rows: list[list[InlineKeyboardButton]] = []
    if quick_values:
        rows.append([
            _btn(f"⏳ {value}" if value == "жду" else value, f"cl:qv:{i}")
            for i, value in enumerate(quick_values)
        ])
    row = []
    if skip:
        row.append(_btn("⏭ Пропустить", "cl:skip"))
    if finish:
        row.append(_btn("✅ Хватит", "cl:done"))
    if row:
        rows.append(row)
    rows.append([_btn("✖️ Отмена", "cl:cancel")])
    return _kb(rows)


def card_keyboard(videos: list[tuple[int, int, str]]) -> InlineKeyboardMarkup:
    """Close button, plus one play button per video the company has."""
    rows = [
        [_btn(f"▶️ {name}", f"cl:vid:{company_id}:{column_id}")]
        for company_id, column_id, name in videos
    ]
    rows.append([_btn("✖️ Закрыть", "cl:close")])
    return _kb(rows)


def close_keyboard() -> InlineKeyboardMarkup:
    return _kb([[_btn("✖️ Закрыть", "cl:close")]])
