from unittest import TestCase

from clients_db import LEGACY_SEED_COLUMNS, SEED_COLUMNS, row_label
from clients_keyboards import (
    cell_columns_keyboard,
    columns_list_keyboard,
    companies_keyboard,
    edit_keyboard,
    input_keyboard,
    table_keyboard,
)
from clients_render import (
    ROWS_PER_PAGE,
    SAFE_HTML_LEN,
    _plural,
    build_table_html,
    paginate,
)
from keyboards import build_main_keyboard


COLUMNS = [
    {"id": 1, "name": "Компания", "sort_order": 0},
    {"id": 2, "name": "Контакт", "sort_order": 1},
]


def _rows(n: int) -> list[dict]:
    return [
        {"id": i, "sort_order": i, "values": {1: f"Компания {i}", 2: ""}}
        for i in range(n)
    ]


def _all_callbacks(keyboard) -> list[str]:
    return [b.callback_data for row in keyboard.inline_keyboard for b in row]


class SeedColumnTests(TestCase):
    def test_seeded_columns_match_the_agreed_set(self) -> None:
        self.assertEqual(
            SEED_COLUMNS,
            [
                "Компания",
                "Персональное обращение",
                "Ответ",
                "Созвон",
                "Причина",
                "Вывод",
                "Текст обращения",
                "Текст ответа",
            ],
        )

    def test_company_stays_first_because_row_labels_depend_on_it(self) -> None:
        self.assertEqual(SEED_COLUMNS[0], "Компания")

    def test_legacy_set_is_kept_distinct_for_the_upgrade_check(self) -> None:
        self.assertNotEqual(SEED_COLUMNS, LEGACY_SEED_COLUMNS)
        self.assertEqual(len(set(SEED_COLUMNS)), len(SEED_COLUMNS))


class MainKeyboardTests(TestCase):
    def test_manul_button_present(self) -> None:
        labels = [b.text for row in build_main_keyboard().keyboard for b in row]
        self.assertIn("Манул", labels)
        self.assertIn("Сегодня", labels)
        self.assertIn("Статистика", labels)


class TableKeyboardTests(TestCase):
    def test_single_page_has_no_pager(self) -> None:
        kb = table_keyboard(page=0, pages=1)
        self.assertEqual(len(kb.inline_keyboard), 1)
        self.assertEqual(_all_callbacks(kb), ["cl:add", "cl:edit"])

    def test_pager_appears_and_clamps_at_edges(self) -> None:
        first = _all_callbacks(table_keyboard(page=0, pages=3))
        self.assertIn("cl:noop", first)      # no page before the first
        self.assertIn("cl:p:1", first)

        middle = _all_callbacks(table_keyboard(page=1, pages=3))
        self.assertIn("cl:p:0", middle)
        self.assertIn("cl:p:2", middle)

        last = table_keyboard(page=2, pages=3)
        self.assertEqual(last.inline_keyboard[1][2].callback_data, "cl:noop")
        self.assertEqual(last.inline_keyboard[1][1].text, "3/3")


class SelectionKeyboardTests(TestCase):
    def test_companies_keyboard_labels_rows_and_keeps_back(self) -> None:
        kb = companies_keyboard(_rows(2), COLUMNS, "cl:rowdel", "cl:edit")
        self.assertEqual(kb.inline_keyboard[0][0].text, "Компания 0")
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "cl:rowdel:0")
        self.assertEqual(kb.inline_keyboard[-1][0].callback_data, "cl:edit")

    def test_empty_lists_stay_navigable(self) -> None:
        kb = companies_keyboard([], COLUMNS, "cl:rowdel", "cl:edit")
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "cl:noop")
        self.assertEqual(kb.inline_keyboard[-1][0].callback_data, "cl:edit")

        kb = columns_list_keyboard([], "cl:coldel", "cl:cols")
        self.assertEqual(kb.inline_keyboard[0][0].callback_data, "cl:noop")

    def test_cell_keyboard_carries_both_ids(self) -> None:
        kb = cell_columns_keyboard(7, COLUMNS)
        self.assertEqual(
            _all_callbacks(kb), ["cl:cellv:7:1", "cl:cellv:7:2", "cl:cell"]
        )


class CallbackDataTests(TestCase):
    def test_all_callbacks_fit_telegram_64_byte_limit(self) -> None:
        keyboards = [
            table_keyboard(0, 3),
            edit_keyboard(),
            companies_keyboard(_rows(3), COLUMNS, "cl:rowdel", "cl:edit"),
            cell_columns_keyboard(999999, COLUMNS),
            input_keyboard(skip=True, finish=True),
        ]
        for kb in keyboards:
            for data in _all_callbacks(kb):
                self.assertLessEqual(len(data.encode()), 64, data)

    def test_input_keyboard_variants(self) -> None:
        self.assertEqual(_all_callbacks(input_keyboard(skip=False)), ["cl:cancel"])
        self.assertEqual(
            _all_callbacks(input_keyboard(skip=True, finish=True)),
            ["cl:skip", "cl:done", "cl:cancel"],
        )


class PaginateTests(TestCase):
    def test_empty_input_yields_one_page(self) -> None:
        rows, page, pages = paginate([], 0)
        self.assertEqual((rows, page, pages), ([], 0, 1))

    def test_splits_and_clamps_out_of_range_pages(self) -> None:
        data = _rows(ROWS_PER_PAGE * 2 + 1)
        self.assertEqual(paginate(data, 0)[2], 3)
        self.assertEqual(len(paginate(data, 0)[0]), ROWS_PER_PAGE)
        self.assertEqual(len(paginate(data, 2)[0]), 1)

        # beyond the last page and before the first both clamp
        self.assertEqual(paginate(data, 99)[1], 2)
        self.assertEqual(paginate(data, -5)[1], 0)


class RowLabelTests(TestCase):
    def test_falls_back_through_empty_columns(self) -> None:
        row = {"id": 4, "values": {1: "   ", 2: "Иван"}}
        self.assertEqual(row_label(row, COLUMNS), "Иван")

    def test_fallback_when_row_is_blank(self) -> None:
        self.assertEqual(row_label({"id": 4, "values": {}}, COLUMNS), "Компания #4")

    def test_truncates_to_limit(self) -> None:
        row = {"id": 4, "values": {1: "О" * 100}}
        self.assertEqual(len(row_label(row, COLUMNS)), 28)
        self.assertTrue(row_label(row, COLUMNS).endswith("…"))


class TableHtmlTests(TestCase):
    def test_renders_a_native_table_with_header_cells(self) -> None:
        html = build_table_html(COLUMNS, _rows(2))
        self.assertIn("<table bordered striped>", html)
        self.assertIn("<th>Компания</th>", html)
        self.assertIn('<th align="right">#</th>', html)
        self.assertIn("<td>Компания 0</td>", html)
        self.assertEqual(html.count("<tr>"), 3)          # header + 2 rows
        self.assertTrue(html.startswith("<h3>Клиенты</h3>"))

    def test_row_numbers_continue_across_pages(self) -> None:
        rows = _rows(ROWS_PER_PAGE + 2)
        page_rows, page, pages = paginate(rows, 1)
        html = build_table_html(COLUMNS, page_rows, page, pages, total_rows=len(rows))
        self.assertIn(f'<td align="right">{ROWS_PER_PAGE + 1}</td>', html)
        self.assertIn(f"стр. 2/{pages}", html)

    def test_blank_values_render_as_a_dash(self) -> None:
        html = build_table_html(COLUMNS, [{"id": 1, "values": {1: "Ромашка", 2: "   "}}])
        self.assertIn("<td>—</td>", html)

    def test_user_input_is_html_escaped(self) -> None:
        rows = [{"id": 1, "values": {1: '<script>alert("x")</script>', 2: "a & b"}}]
        html = build_table_html(COLUMNS, rows)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("a &amp; b", html)

    def test_column_names_are_escaped_too(self) -> None:
        cols = [{"id": 1, "name": "<b>Компания</b>", "sort_order": 0}]
        html = build_table_html(cols, [{"id": 1, "values": {1: "x"}}])
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;b&gt;", html)

    def test_caption_counts_all_rows_not_just_the_page(self) -> None:
        rows = _rows(25)
        page_rows, page, pages = paginate(rows, 0)
        html = build_table_html(COLUMNS, page_rows, page, pages, total_rows=len(rows))
        self.assertIn("25 компаний", html)

    def test_long_values_are_clipped_to_stay_under_the_size_budget(self) -> None:
        wide = [{"id": i, "name": f"Колонка {i}", "sort_order": i} for i in range(8)]
        rows = [
            {"id": i, "sort_order": i, "values": {c["id"]: "О" * 400 for c in wide}}
            for i in range(ROWS_PER_PAGE)
        ]
        html = build_table_html(wide, rows, 0, 1, total_rows=len(rows))
        self.assertLessEqual(len(html), SAFE_HTML_LEN)
        self.assertIn("…", html)
        self.assertEqual(html.count("<tr>"), ROWS_PER_PAGE + 1)   # no rows dropped

    def test_whitespace_inside_cells_is_collapsed(self) -> None:
        rows = [{"id": 1, "values": {1: "Ромашка\n\nООО", 2: "a   b"}}]
        html = build_table_html(COLUMNS, rows)
        self.assertIn("Ромашка ООО", html)
        self.assertIn("a b", html)

    def test_empty_table_still_shows_the_header_and_a_hint(self) -> None:
        html = build_table_html(COLUMNS, [])
        self.assertIn("<th>Компания</th>", html)
        self.assertIn("Пока нет компаний", html)

    def test_no_columns_yields_a_hint_instead_of_a_table(self) -> None:
        html = build_table_html([], [])
        self.assertNotIn("<table", html)
        self.assertIn("Нет колонок", html)


class PluralTests(TestCase):
    def test_russian_plural_forms(self) -> None:
        cases = {1: "компания", 2: "компании", 5: "компаний", 11: "компаний",
                 21: "компания", 22: "компании", 14: "компаний", 101: "компания"}
        for n, expected in cases.items():
            with self.subTest(n=n):
                self.assertEqual(
                    _plural(n, "компания", "компании", "компаний"), expected
                )
