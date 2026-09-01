from datetime import date
from unittest import TestCase

from aiogram.enums import ButtonStyle

from calendar_view import (
    format_month,
    month_grid,
    month_title,
    parse_month,
    shift_month,
)
from keyboards import (
    TASK_LABEL_LEN,
    build_calendar_keyboard,
    build_habits_keyboard,
    build_task_delete_keyboard,
)
from stats import day_status

HABITS = [{"key": "dev", "name": "Сайты", "emoji": "💻",
           "sort_order": 0, "custom_emoji_id": "1"}]


def _tasks(*specs) -> list[dict]:
    return [
        {"id": i + 1, "title": title, "completed": done}
        for i, (title, done) in enumerate(specs)
    ]


def _flat(kb):
    return [b for row in kb.inline_keyboard for b in row]


class MonthMathTests(TestCase):
    def test_shift_wraps_across_the_year(self) -> None:
        self.assertEqual(shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(shift_month(2026, 8, 0), (2026, 8))

    def test_shift_over_many_months(self) -> None:
        self.assertEqual(shift_month(2026, 8, 12), (2027, 8))
        self.assertEqual(shift_month(2026, 8, -20), (2024, 12))

    def test_month_string_round_trips(self) -> None:
        self.assertEqual(format_month(2026, 8), "2026-08")
        self.assertEqual(parse_month("2026-08"), (2026, 8))

    def test_title_uses_the_nominative_month(self) -> None:
        self.assertEqual(month_title(2026, 8), "Август 2026")

    def test_grid_starts_on_monday_and_pads_both_ends(self) -> None:
        grid = month_grid(2026, 8)          # 1 Aug 2026 is a Saturday
        self.assertTrue(all(len(week) == 7 for week in grid))
        self.assertEqual(grid[0][:5], [None] * 5)
        self.assertEqual(grid[0][5], date(2026, 8, 1))
        self.assertIsNone(grid[-1][-1])

    def test_grid_holds_every_day_exactly_once(self) -> None:
        for year, month, length in ((2026, 2, 28), (2024, 2, 29), (2026, 8, 31)):
            with self.subTest(month=month):
                days = [d for week in month_grid(year, month) for d in week if d]
                self.assertEqual(len(days), length)
                self.assertEqual(len(set(days)), length)


class DayStatusTests(TestCase):
    def _entry(self, **kw) -> dict:
        base = {"habits_done": 0, "habits_total": 0,
                "tasks_done": 0, "tasks_total": 0, "skipped": False}
        return {**base, **kw}

    def test_missing_day_is_empty(self) -> None:
        self.assertEqual(day_status(None), "empty")

    def test_skipped_beats_everything(self) -> None:
        entry = self._entry(habits_done=6, habits_total=6, skipped=True)
        self.assertEqual(day_status(entry), "skipped")

    def test_all_done_is_perfect(self) -> None:
        self.assertEqual(
            day_status(self._entry(habits_done=6, habits_total=6)), "perfect"
        )

    def test_tasks_count_towards_the_day(self) -> None:
        entry = self._entry(habits_done=6, habits_total=6, tasks_done=1, tasks_total=2)
        self.assertEqual(day_status(entry), "partial")

    def test_nothing_done_reads_as_empty_not_partial(self) -> None:
        self.assertEqual(day_status(self._entry(habits_total=6)), "empty")


class TaskKeyboardTests(TestCase):
    def test_tasks_are_green_and_habits_blue(self) -> None:
        kb = build_habits_keyboard(
            "2026-08-25", HABITS, {"dev": True},
            tasks=_tasks(("позвонить", True), ("забрать", False)),
        )
        by_text = {b.text: b.style for b in _flat(kb)}
        self.assertEqual(by_text["Сайты"], ButtonStyle.PRIMARY)
        self.assertEqual(by_text["позвонить"], ButtonStyle.SUCCESS)
        self.assertIsNone(by_text["забрать"])

    def test_add_button_is_alone_until_a_task_exists(self) -> None:
        kb = build_habits_keyboard("2026-08-25", HABITS, {})
        self.assertEqual([b.text for b in kb.inline_keyboard[-1]], ["Добавить задачу"])

        kb = build_habits_keyboard("2026-08-25", HABITS, {}, tasks=_tasks(("a", False)))
        self.assertEqual(
            [b.text for b in kb.inline_keyboard[-1]],
            ["Добавить задачу", "Удалить задачу"],
        )

    def test_tasks_sit_between_the_habits_and_the_skip_button(self) -> None:
        kb = build_habits_keyboard(
            "2026-08-25", HABITS, {}, tasks=_tasks(("a", False), ("b", False), ("c", False))
        )
        rows = [[b.callback_data for b in row] for row in kb.inline_keyboard]
        self.assertTrue(rows[0][0].startswith("toggle:"))
        self.assertTrue(rows[1][0].startswith("task:"))
        self.assertEqual(len(rows[1]), 2)      # two per row
        self.assertEqual(len(rows[2]), 1)
        self.assertTrue(rows[3][0].startswith("skip:"))

    def test_long_titles_are_shortened_on_the_button(self) -> None:
        kb = build_habits_keyboard(
            "2026-08-25", HABITS, {}, tasks=_tasks(("о" * 100, False))
        )
        label = [b.text for b in _flat(kb) if b.callback_data.startswith("task:")][0]
        self.assertEqual(len(label), TASK_LABEL_LEN)
        self.assertTrue(label.endswith("…"))

    def test_delete_list_offers_every_task_and_a_way_back(self) -> None:
        kb = build_task_delete_keyboard("2026-08-25", _tasks(("a", False), ("b", True)))
        data = [b.callback_data for b in _flat(kb)]
        self.assertEqual(data, ["taskdel:2026-08-25:1", "taskdel:2026-08-25:2",
                                "dayback:2026-08-25"])


class CalendarKeyboardTests(TestCase):
    def _kb(self, statuses=None, today="2026-08-25"):
        return build_calendar_keyboard(
            2026, 8, month_grid(2026, 8), statuses or {}, today
        )

    def test_header_navigates_to_the_neighbouring_months(self) -> None:
        header = self._kb().inline_keyboard[0]
        self.assertEqual(header[0].callback_data, "cal:m:2026-07")
        self.assertEqual(header[1].text, "Август 2026")
        self.assertEqual(header[2].callback_data, "cal:m:2026-09")

    def test_weekday_header_is_inert(self) -> None:
        row = self._kb().inline_keyboard[1]
        self.assertEqual([b.text for b in row], ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"])
        self.assertTrue(all(b.callback_data == "cal:noop" for b in row))

    def test_every_day_of_the_month_is_clickable(self) -> None:
        days = [b.callback_data for b in _flat(self._kb())
                if b.callback_data.startswith("cal:d:")]
        self.assertEqual(len(days), 31)
        self.assertIn("cal:d:2026-08-01", days)
        self.assertIn("cal:d:2026-08-31", days)

    def test_padding_cells_are_inert(self) -> None:
        first_week = self._kb().inline_keyboard[2]
        blanks = [b for b in first_week if b.text == " "]
        self.assertEqual(len(blanks), 5)
        self.assertTrue(all(b.callback_data == "cal:noop" for b in blanks))

    def test_colour_carries_the_day_state(self) -> None:
        kb = self._kb({"2026-08-03": "perfect", "2026-08-05": "skipped"})
        by_day = {
            b.callback_data.rsplit(":", 1)[1]: b.style
            for b in _flat(kb) if b.callback_data.startswith("cal:d:")
        }
        self.assertEqual(by_day["2026-08-03"], ButtonStyle.SUCCESS)
        self.assertEqual(by_day["2026-08-05"], ButtonStyle.DANGER)
        self.assertEqual(by_day["2026-08-25"], ButtonStyle.PRIMARY)   # today
        self.assertIsNone(by_day["2026-08-10"])

    def test_a_marked_day_keeps_its_colour_even_when_it_is_today(self) -> None:
        kb = self._kb({"2026-08-25": "perfect"})
        today_button = [b for b in _flat(kb) if b.callback_data == "cal:d:2026-08-25"][0]
        self.assertEqual(today_button.style, ButtonStyle.SUCCESS)
