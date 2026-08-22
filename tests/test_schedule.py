from unittest import TestCase

from db import SEED_HABITS
from econ_render import build_list_html, build_note_html
from keyboards import MENU_LABELS, build_habits_keyboard, build_main_keyboard
from schedule import (
    describe,
    dumps,
    every_day,
    habits_for_date,
    habits_for_weekday,
    is_scheduled,
    parse,
    scheduled_days,
    subtitle_for,
)

MATH = {
    "key": "math", "name": "Математика", "emoji": "➗", "sort_order": 0,
    "custom_emoji_id": None,
    "schedule": dumps({"0": "репет", "1": "1/3 дз", "3": "1/3 дз", "5": "1/3 дз"}),
}
DEV = {
    "key": "dev", "name": "Сайты", "emoji": "💻", "sort_order": 1,
    "custom_emoji_id": None, "schedule": dumps(every_day("1 сайт")),
}
SLEEP = {
    "key": "sleep", "name": "Сон", "emoji": "😴", "sort_order": 2,
    "custom_emoji_id": None, "schedule": dumps(every_day("8 часов")),
}
ALL = [MATH, DEV, SLEEP]


class ParseTests(TestCase):
    def test_missing_or_broken_schedule_means_no_days(self) -> None:
        for raw in (None, "", "not json", "[1,2]"):
            with self.subTest(raw=raw):
                self.assertEqual(parse(raw), {})

    def test_dict_passes_through(self) -> None:
        self.assertEqual(parse({"0": "x"}), {"0": "x"})

    def test_round_trip_keeps_cyrillic_readable(self) -> None:
        raw = dumps({"0": "репет"})
        self.assertIn("репет", raw)
        self.assertEqual(parse(raw), {"0": "репет"})


class ScheduleTests(TestCase):
    def test_subtitle_varies_by_weekday(self) -> None:
        self.assertEqual(subtitle_for(MATH, 0), "репет")
        self.assertEqual(subtitle_for(MATH, 1), "1/3 дз")
        self.assertIsNone(subtitle_for(MATH, 2))

    def test_is_scheduled_follows_the_map(self) -> None:
        self.assertTrue(is_scheduled(MATH, 5))
        self.assertFalse(is_scheduled(MATH, 6))
        self.assertTrue(all(is_scheduled(DEV, d) for d in range(7)))

    def test_an_empty_subtitle_still_counts_as_scheduled(self) -> None:
        habit = {"schedule": dumps({"2": ""})}
        self.assertTrue(is_scheduled(habit, 2))
        self.assertEqual(subtitle_for(habit, 2), "")

    def test_day_list_carries_the_subtitle_and_keeps_order(self) -> None:
        monday = habits_for_weekday(ALL, 0)
        self.assertEqual([h["key"] for h in monday], ["math", "dev", "sleep"])
        self.assertEqual(monday[0]["subtitle"], "репет")

    def test_unscheduled_habits_drop_out_of_the_day(self) -> None:
        self.assertEqual([h["key"] for h in habits_for_weekday(ALL, 2)], ["dev", "sleep"])

    def test_sort_order_wins_over_input_order(self) -> None:
        shuffled = [SLEEP, DEV, MATH]
        self.assertEqual([h["key"] for h in habits_for_weekday(shuffled, 0)],
                         ["math", "dev", "sleep"])

    def test_date_lookup_matches_weekday_lookup(self) -> None:
        # 2026-08-17 is a Monday, 2026-08-19 a Wednesday
        self.assertEqual([h["key"] for h in habits_for_date(ALL, "2026-08-17")],
                         ["math", "dev", "sleep"])
        self.assertEqual([h["key"] for h in habits_for_date(ALL, "2026-08-19")],
                         ["dev", "sleep"])

    def test_describe_reads_naturally(self) -> None:
        self.assertEqual(describe(MATH), "Пн, Вт, Чт, Сб")
        self.assertEqual(describe(DEV), "каждый день")
        self.assertEqual(describe({"schedule": None}), "выключено")

    def test_scheduled_days_are_sorted_ints(self) -> None:
        self.assertEqual(scheduled_days(MATH), [0, 1, 3, 5])


class SeedTests(TestCase):
    def test_six_habits_with_the_agreed_subtitles(self) -> None:
        by_key = {h[0]: h for h in SEED_HABITS}
        self.assertEqual(set(by_key), {"math", "dev", "sport", "economics", "shower", "sleep"})
        self.assertEqual(by_key["math"][6]["0"], "репет")
        self.assertEqual(by_key["math"][6]["1"], "1/3 дз")
        self.assertNotIn("2", by_key["math"][6])
        self.assertEqual(by_key["dev"][6]["3"], "1 сайт")
        self.assertEqual(by_key["sport"][6]["3"], "тренировка")
        self.assertEqual(by_key["economics"][6]["3"], "пол темы")
        self.assertEqual(by_key["shower"][6]["3"], "холодный")
        self.assertEqual(by_key["sleep"][6]["3"], "8 часов")

    def test_every_habit_has_a_custom_emoji(self) -> None:
        # An empty id makes the button render as a zero-width space, i.e. blank.
        missing = [h[0] for h in SEED_HABITS if not h[5]]
        self.assertEqual(missing, [])

    def test_custom_emoji_ids_are_unique(self) -> None:
        ids = [h[5] for h in SEED_HABITS]
        self.assertEqual(len(set(ids)), len(ids))

    def test_week_adds_up_to_39_marks(self) -> None:
        habits = [{"schedule": dumps(h[6]), "sort_order": i, "key": h[0]}
                  for i, h in enumerate(SEED_HABITS)]
        per_day = [len(habits_for_weekday(habits, d)) for d in range(7)]
        self.assertEqual(per_day, [6, 6, 5, 6, 5, 6, 5])
        self.assertEqual(sum(per_day), 39)


class KeyboardTests(TestCase):
    def _habits(self, n: int) -> list[dict]:
        return [{"key": f"h{i}", "emoji": "✅", "sort_order": i, "custom_emoji_id": None}
                for i in range(n)]

    def test_buttons_wrap_into_rows_of_three(self) -> None:
        kb = build_habits_keyboard("2026-08-17", self._habits(6), {})
        habit_rows = kb.inline_keyboard[:-1]
        self.assertEqual([len(r) for r in habit_rows], [3, 3])

    def test_five_habits_leave_a_short_second_row(self) -> None:
        kb = build_habits_keyboard("2026-08-17", self._habits(5), {})
        self.assertEqual([len(r) for r in kb.inline_keyboard[:-1]], [3, 2])

    def test_skip_button_flips_with_the_day_state(self) -> None:
        kb = build_habits_keyboard("2026-08-17", self._habits(1), {})
        self.assertEqual(kb.inline_keyboard[-1][0].callback_data, "skip:2026-08-17:1")
        kb = build_habits_keyboard("2026-08-17", self._habits(1), {}, skipped=True)
        self.assertEqual(kb.inline_keyboard[-1][0].callback_data, "skip:2026-08-17:0")
        self.assertIn("Вернуть", kb.inline_keyboard[-1][0].text)

    def test_main_keyboard_has_all_four_sections(self) -> None:
        labels = [b.text for row in build_main_keyboard().keyboard for b in row]
        self.assertEqual(labels, MENU_LABELS)


class EconRenderTests(TestCase):
    def _note(self, **kw) -> dict:
        base = {"id": 1, "number": 1, "title": "Инфляция",
                "body": "Рост цен.", "created_at": None, "updated_at": None}
        return {**base, **kw}

    def test_list_shows_topic_progress(self) -> None:
        html = build_list_html([self._note()], marks=1, per_topic=2)
        self.assertIn("тем записано: 1", html)
        self.assertIn("текущая тема: 1/2", html)

    def test_list_flags_topics_awaiting_a_write_up(self) -> None:
        html = build_list_html([], marks=0, per_topic=2, pending=2)
        self.assertIn("ждут конспекта: 2", html)

    def test_empty_list_invites_the_first_topic(self) -> None:
        self.assertIn("Пока нет ни одной темы", build_list_html([], 0, 2))

    def test_search_view_reports_misses(self) -> None:
        self.assertIn("Ничего не нашлось", build_list_html([], 0, 2, query="ставка"))

    def test_titles_are_escaped(self) -> None:
        html = build_list_html([self._note(title="<b>x</b>")], 0, 2)
        self.assertNotIn("<b>x</b>", html)
        self.assertIn("&lt;b&gt;", html)

    def test_note_keeps_paragraphs_and_full_text(self) -> None:
        body = "Первый абзац.\n\nВторой абзац."
        html = "".join(build_note_html(self._note(body=body)))
        self.assertIn("<p>Первый абзац.</p>", html)
        self.assertIn("<p>Второй абзац.</p>", html)
        self.assertNotIn("…", html)

    def test_note_without_text_says_so(self) -> None:
        html = "".join(build_note_html(self._note(body="")))
        self.assertIn("Текст пока не записан", html)

    def test_very_long_note_is_split(self) -> None:
        body = "\n".join("абзац " * 40 for _ in range(60))
        chunks = build_note_html(self._note(body=body))
        self.assertGreater(len(chunks), 1)
