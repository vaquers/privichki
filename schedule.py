from __future__ import annotations

import json
from datetime import date as date_cls

# Monday is 0, matching datetime.date.weekday().
WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def every_day(subtitle: str) -> dict[str, str]:
    """Schedule for a habit that runs daily with the same subtitle."""
    return {str(d): subtitle for d in range(7)}


def dumps(schedule: dict[str, str]) -> str:
    return json.dumps(schedule, ensure_ascii=False)


def parse(raw: str | dict | None) -> dict[str, str]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def subtitle_for(habit: dict, weekday: int) -> str | None:
    """Subtitle shown under the habit on that weekday, or None if it is off."""
    return parse(habit.get("schedule")).get(str(weekday))


def is_scheduled(habit: dict, weekday: int) -> bool:
    return subtitle_for(habit, weekday) is not None


def habits_for_weekday(habits: list[dict], weekday: int) -> list[dict]:
    """Scheduled habits for that weekday, in display order, subtitle attached."""
    result = []
    for h in sorted(habits, key=lambda x: x["sort_order"]):
        subtitle = subtitle_for(h, weekday)
        if subtitle is not None:
            result.append({**h, "subtitle": subtitle})
    return result


def habits_for_date(habits: list[dict], date_str: str) -> list[dict]:
    return habits_for_weekday(habits, date_cls.fromisoformat(date_str).weekday())


def scheduled_days(habit: dict) -> list[int]:
    return sorted(int(d) for d in parse(habit.get("schedule")))


def describe(habit: dict) -> str:
    """Human summary of when a habit runs, e.g. 'Пн, Вт, Чт, Сб' or 'каждый день'."""
    days = scheduled_days(habit)
    if len(days) == 7:
        return "каждый день"
    if not days:
        return "выключено"
    return ", ".join(WEEKDAYS_SHORT[d] for d in days)
