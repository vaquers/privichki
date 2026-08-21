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
    MAX_ROWS_PER_PAGE,
    SAFE_HTML_LEN,
    _plural,
    build_company_html,
    build_table_html,
    paginate_rows,
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
        self.assertEqual(len(kb.inline_keyboard), 2)
        self.assertEqual(_all_callbacks(kb), ["cl:add", "cl:edit", "cl:show"])

    def test_pager_appears_and_clamps_at_edges(self) -> None:
        first = _all_callbacks(table_keyboard(page=0, pages=3))
        self.assertIn("cl:noop", first)      # no page before the first
        self.assertIn("cl:p:1", first)

        middle = _all_callbacks(table_keyboard(page=1, pages=3))
        self.assertIn("cl:p:0", middle)
        self.assertIn("cl:p:2", middle)

        last = table_keyboard(page=2, pages=3)
        pager = last.inline_keyboard[-1]
        self.assertEqual(pager[2].callback_data, "cl:noop")
        self.assertEqual(pager[1].text, "3/3")


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
        self.assertEqual(paginate_rows(COLUMNS, [], 0), ([], 0, 1, 0))

    def test_short_rows_are_capped_by_row_count(self) -> None:
        rows = _rows(MAX_ROWS_PER_PAGE * 2)
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 0)
        self.assertEqual(len(page_rows), MAX_ROWS_PER_PAGE)
        self.assertEqual((page, pages, start), (0, 2, 0))

    def test_start_index_tracks_variable_page_sizes(self) -> None:
        rows = _rows(MAX_ROWS_PER_PAGE + 3)
        _, _, _, start = paginate_rows(COLUMNS, rows, 1)
        self.assertEqual(start, MAX_ROWS_PER_PAGE)

    def test_long_rows_reduce_the_page_size_instead_of_being_cut(self) -> None:
        long_rows = [
            {"id": i, "sort_order": i, "values": {1: "О" * 3000, 2: "и" * 3000}}
            for i in range(6)
        ]
        page_rows, _, pages, _ = paginate_rows(COLUMNS, long_rows, 0)
        self.assertLess(len(page_rows), MAX_ROWS_PER_PAGE)
        self.assertGreater(pages, 1)
        # every row still lands on exactly one page
        seen = sum(len(paginate_rows(COLUMNS, long_rows, p)[0]) for p in range(pages))
        self.assertEqual(seen, len(long_rows))

    def test_out_of_range_pages_clamp(self) -> None:
        rows = _rows(MAX_ROWS_PER_PAGE + 1)
        self.assertEqual(paginate_rows(COLUMNS, rows, 99)[1], 1)
        self.assertEqual(paginate_rows(COLUMNS, rows, -5)[1], 0)


class NoTruncationTests(TestCase):
    def test_a_long_value_is_shown_in_full_in_the_table(self) -> None:
        text = "Здравствуйте, пишу по поводу сотрудничества. " * 6
        rows = [{"id": 1, "sort_order": 0, "values": {1: text, 2: "x"}}]
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 0)
        html = build_table_html(COLUMNS, page_rows, page, pages, 1, start)
        self.assertIn(text.strip(), html)
        self.assertNotIn("…", html)

    def test_a_single_oversized_row_is_clipped_but_still_renders(self) -> None:
        rows = [{"id": 1, "sort_order": 0, "values": {1: "О" * 40000, 2: "и" * 40000}}]
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 0)
        self.assertEqual(len(page_rows), 1)
        html = build_table_html(COLUMNS, page_rows, page, pages, 1, start)
        self.assertLessEqual(len(html), SAFE_HTML_LEN)
        self.assertIn("…", html)


class CompanyCardTests(TestCase):
    def test_card_shows_every_column_in_full(self) -> None:
        text = "Очень длинный текст обращения. " * 20
        row = {"id": 1, "values": {1: "ООО «Ромашка»", 2: text}}
        chunks = build_company_html(COLUMNS, row, 1)
        joined = "".join(chunks)
        self.assertIn("ООО «Ромашка»", joined)
        self.assertIn(text.strip(), joined)
        self.assertNotIn("…", joined)

    def test_short_values_stay_inline_and_long_ones_are_quoted(self) -> None:
        row = {"id": 1, "values": {1: "Да", 2: "длинно " * 30}}
        html = "".join(build_company_html(COLUMNS, row, 1))
        self.assertIn("<b>Компания</b>: Да", html)
        self.assertIn("<blockquote>", html)

    def test_missing_values_render_as_a_dash(self) -> None:
        html = "".join(build_company_html(COLUMNS, {"id": 1, "values": {}}, 1))
        self.assertIn("<b>Контакт</b>: —", html)

    def test_line_breaks_survive_as_paragraphs(self) -> None:
        row = {"id": 1, "values": {2: "первая строка\nвторая строка\n\nтретья"}}
        html = "".join(build_company_html(COLUMNS, row, 1))
        self.assertIn("<p>первая строка</p>", html)
        self.assertIn("<p>вторая строка</p>", html)
        self.assertIn("<p>третья</p>", html)

    def test_card_is_split_when_it_would_be_too_long(self) -> None:
        row = {"id": 1, "values": {1: "О" * 6000, 2: "и" * 6000}}
        chunks = build_company_html(COLUMNS, row, 1)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), SAFE_HTML_LEN * 2)

    def test_card_escapes_user_input(self) -> None:
        row = {"id": 1, "values": {1: "<script>", 2: "a & b"}}
        html = "".join(build_company_html(COLUMNS, row, 1))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


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
        rows = _rows(MAX_ROWS_PER_PAGE + 2)
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 1)
        html = build_table_html(COLUMNS, page_rows, page, pages, len(rows), start)
        self.assertIn(f'<td align="right">{MAX_ROWS_PER_PAGE + 1}</td>', html)
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
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 0)
        html = build_table_html(COLUMNS, page_rows, page, pages, len(rows), start)
        self.assertIn("25 компаний", html)

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
