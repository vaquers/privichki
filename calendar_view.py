from __future__ import annotations

from calendar import monthrange
from datetime import date

# Nominative forms -- the calendar header reads "Август 2026", not "августа".
MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def format_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def parse_month(value: str) -> tuple[int, int]:
    year, month = value.split("-")
    return int(year), int(month)


def month_title(year: int, month: int) -> str:
    return f"{MONTHS_RU[month]} {year}"


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_grid(year: int, month: int) -> list[list[date | None]]:
    """Weeks of the month, Monday first, padded with None outside the month."""
    days_in_month = monthrange(year, month)[1]
    first_weekday = date(year, month, 1).weekday()

    cells: list[date | None] = [None] * first_weekday
    cells += [date(year, month, d) for d in range(1, days_in_month + 1)]
    while len(cells) % 7:
        cells.append(None)

    return [cells[i:i + 7] for i in range(0, len(cells), 7)]
