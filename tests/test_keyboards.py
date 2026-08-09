from unittest import TestCase

from aiogram.enums import ButtonStyle

from keyboards import CUSTOM_EMOJI_BUTTON_TEXT, build_habits_keyboard


class BuildHabitsKeyboardTests(TestCase):
    def setUp(self) -> None:
        self.habits = [
            {
                "key": "plain",
                "emoji": "📚",
                "sort_order": 1,
                "custom_emoji_id": None,
            },
            {
                "key": "custom",
                "emoji": "💻",
                "sort_order": 0,
                "custom_emoji_id": "123456789",
            },
        ]

    def test_custom_emoji_replaces_regular_emoji_in_button_text(self) -> None:
        keyboard = build_habits_keyboard("2026-08-10", self.habits, {})
        custom_button, plain_button = keyboard.inline_keyboard[0]

        self.assertEqual(custom_button.text, CUSTOM_EMOJI_BUTTON_TEXT)
        self.assertEqual(custom_button.icon_custom_emoji_id, "123456789")
        self.assertEqual(plain_button.text, "📚")
        self.assertIsNone(plain_button.icon_custom_emoji_id)

    def test_completed_habit_has_success_style(self) -> None:
        keyboard = build_habits_keyboard(
            "2026-08-10",
            self.habits,
            {"custom": True, "plain": False},
        )
        custom_button, plain_button = keyboard.inline_keyboard[0]

        self.assertEqual(custom_button.style, ButtonStyle.SUCCESS)
        self.assertIsNone(plain_button.style)
