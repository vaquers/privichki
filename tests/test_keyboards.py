from unittest import TestCase

from aiogram.enums import ButtonStyle

from keyboards import BUTTON_LABEL, build_habits_keyboard


class BuildHabitsKeyboardTests(TestCase):
    def setUp(self) -> None:
        self.habits = [
            {
                "key": "sport",
                "name": "Спорт",
                "emoji": "🏋",
                "sort_order": 1,
                "custom_emoji_id": None,
            },
            {
                "key": "dev",
                "name": "Разработка сайтов",
                "emoji": "💻",
                "sort_order": 0,
                "custom_emoji_id": "123456789",
            },
        ]

    def _habit_buttons(self, keyboard):
        # the last row is the skip-day button
        return [b for row in keyboard.inline_keyboard[:-1] for b in row]

    def test_button_carries_the_short_label_and_the_icon(self) -> None:
        dev, sport = self._habit_buttons(build_habits_keyboard("2026-08-17", self.habits, {}))

        self.assertEqual(dev.text, "Сайты")
        self.assertEqual(dev.icon_custom_emoji_id, "123456789")
        self.assertEqual(sport.text, "Спорт")
        self.assertIsNone(sport.icon_custom_emoji_id)

    def test_label_is_never_empty(self) -> None:
        # Telegram rejects an empty button text outright.
        for button in self._habit_buttons(
            build_habits_keyboard("2026-08-17", self.habits, {})
        ):
            self.assertTrue(button.text.strip(), button)

    def test_unknown_habit_falls_back_to_its_full_name(self) -> None:
        habits = [{"key": "reading", "name": "Чтение", "emoji": "📚",
                   "sort_order": 0, "custom_emoji_id": None}]
        button = self._habit_buttons(build_habits_keyboard("2026-08-17", habits, {}))[0]
        self.assertEqual(button.text, "Чтение")

    def test_every_seeded_habit_has_a_short_label(self) -> None:
        from db import SEED_HABITS

        self.assertEqual({h[0] for h in SEED_HABITS}, set(BUTTON_LABEL))

    def test_completed_habit_is_highlighted_in_blue(self) -> None:
        keyboard = build_habits_keyboard(
            "2026-08-17",
            self.habits,
            {"dev": True, "sport": False},
        )
        dev, sport = self._habit_buttons(keyboard)

        self.assertEqual(dev.style, ButtonStyle.PRIMARY)
        self.assertIsNone(sport.style)
