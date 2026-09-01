from unittest import TestCase

from clients_db import (
    DROPPED_COLUMNS,
    KIND_TEXT,
    KIND_VIDEO,
    RENAMED_COLUMNS,
    SEED_COLUMNS,
    is_video,
    row_label,
)
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
    {"id": 1, "name": "Компания", "sort_order": 0, "kind": KIND_TEXT, "quick_values": []},
    {"id": 2, "name": "Контакт", "sort_order": 1, "kind": KIND_TEXT, "quick_values": []},
]
VIDEO_COLUMN = {"id": 3, "name": "Видео сайта", "sort_order": 2,
                "kind": KIND_VIDEO, "quick_values": []}


def _rows(n: int) -> list[dict]:
    return [
        {"id": i, "sort_order": i, "values": {1: f"Компания {i}", 2: ""}}
        for i in range(n)
    ]


def _all_callbacks(keyboard) -> list[str]:
    return [b.callback_data for row in keyboard.inline_keyboard for b in row
            if b.callback_data is not None]


class SeedColumnTests(TestCase):
    def test_table_holds_exactly_the_agreed_columns(self) -> None:
        self.assertEqual(
            [name for name, _, _ in SEED_COLUMNS],
            ["Компания", "Текст сообщения", "Текст ответа", "Видео сайта", "Комментарий"],
        )

    def test_only_the_site_video_column_is_a_video(self) -> None:
        kinds = {name: kind for name, kind, _ in SEED_COLUMNS}
        self.assertEqual(kinds["Видео сайта"], KIND_VIDEO)
        self.assertTrue(all(k == KIND_TEXT for n, k in kinds.items() if n != "Видео сайта"))

    def test_reply_column_offers_a_waiting_shortcut(self) -> None:
        quick = {name: values for name, _, values in SEED_COLUMNS}
        self.assertEqual(quick["Текст ответа"], ["жду"])
        self.assertEqual(quick["Компания"], [])

    def test_company_stays_first_because_row_labels_depend_on_it(self) -> None:
        self.assertEqual(SEED_COLUMNS[0][0], "Компания")

    def test_dropped_columns_are_not_also_seeded(self) -> None:
        seeded = {name for name, _, _ in SEED_COLUMNS}
        self.assertEqual(seeded & set(DROPPED_COLUMNS), set())

    def test_renames_point_at_a_column_that_exists(self) -> None:
        seeded = {name for name, _, _ in SEED_COLUMNS}
        for old, new in RENAMED_COLUMNS.items():
            self.assertIn(new, seeded)
            self.assertNotIn(old, seeded)


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
        first = table_keyboard(page=0, pages=3).inline_keyboard[-1]
        self.assertIsNotNone(first[0].disabled)      # no page before the first
        self.assertEqual(first[2].callback_data, "cl:p:1")

        middle = _all_callbacks(table_keyboard(page=1, pages=3))
        self.assertIn("cl:p:0", middle)
        self.assertIn("cl:p:2", middle)

        last = table_keyboard(page=2, pages=3).inline_keyboard[-1]
        self.assertIsNotNone(last[2].disabled)       # nor after the last
        self.assertEqual(last[1].text, "3/3")
        self.assertIsNotNone(last[1].disabled)       # the counter is a label


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

    def test_long_values_no_longer_blow_up_a_page(self) -> None:
        # The summary reduces a long value to a tick, so page size is governed
        # by the row cap rather than by how much someone typed.
        long_rows = [
            {"id": i, "sort_order": i, "values": {1: "О" * 3000, 2: "и" * 3000}}
            for i in range(6)
        ]
        # the collapsed text counts towards the page, so fewer blocks fit
        page_rows, _, pages, _ = paginate_rows(COLUMNS, long_rows, 0)
        self.assertLess(len(page_rows), 6)
        self.assertGreater(pages, 1)
        seen = sum(len(paginate_rows(COLUMNS, long_rows, p)[0]) for p in range(pages))
        self.assertEqual(seen, len(long_rows))

    def test_every_company_lands_on_exactly_one_page(self) -> None:
        rows = _rows(MAX_ROWS_PER_PAGE * 2 + 3)
        pages = paginate_rows(COLUMNS, rows, 0)[2]
        seen = sum(len(paginate_rows(COLUMNS, rows, p)[0]) for p in range(pages))
        self.assertEqual(seen, len(rows))

    def test_out_of_range_pages_clamp(self) -> None:
        rows = _rows(MAX_ROWS_PER_PAGE + 1)
        self.assertEqual(paginate_rows(COLUMNS, rows, 99)[1], 1)
        self.assertEqual(paginate_rows(COLUMNS, rows, -5)[1], 0)


class VideoCellTests(TestCase):
    def test_video_cell_shows_a_marker_not_the_file_id(self) -> None:
        cols = COLUMNS + [VIDEO_COLUMN]
        rows = [{"id": 1, "sort_order": 0, "values": {1: "Ромашка", 3: "BAACAgIAAxkBAAI"}}]
        page, pg, pages, start = paginate_rows(cols, rows, 0)
        html = build_table_html(cols, page, pg, pages, 1, start)
        self.assertNotIn("BAACAgIAAxkBAAI", html)
        self.assertIn("видео ✓", html)

    def test_empty_video_cell_is_a_dash(self) -> None:
        cols = COLUMNS + [VIDEO_COLUMN]
        rows = [{"id": 1, "sort_order": 0, "values": {1: "Ромашка"}}]
        page, pg, pages, start = paginate_rows(cols, rows, 0)
        html = build_table_html(cols, page, pg, pages, 1, start)
        self.assertNotIn("🎥", html)

    def test_card_never_prints_the_file_id(self) -> None:
        cols = COLUMNS + [VIDEO_COLUMN]
        row = {"id": 1, "values": {1: "Ромашка", 3: "BAACAgIAAxkBAAI"}}
        html = "".join(build_company_html(cols, row, 1))
        self.assertNotIn("BAACAgIAAxkBAAI", html)
        self.assertIn("Видео", html)

    def test_row_label_skips_a_video_column(self) -> None:
        cols = [VIDEO_COLUMN] + COLUMNS
        row = {"id": 7, "values": {3: "BAACAgIAAxkBAAI", 1: "Ромашка"}}
        self.assertEqual(row_label(row, cols), "Ромашка")

    def test_is_video_reads_the_kind(self) -> None:
        self.assertTrue(is_video(VIDEO_COLUMN))
        self.assertFalse(is_video(COLUMNS[0]))


class QuickValueKeyboardTests(TestCase):
    def test_quick_values_become_buttons(self) -> None:
        kb = input_keyboard(skip=True, quick_values=["жду"])
        self.assertIn("cl:qv:0", _all_callbacks(kb))
        self.assertTrue(any("жду" in b.text for row in kb.inline_keyboard for b in row))

    def test_no_quick_values_means_no_extra_row(self) -> None:
        self.assertEqual(_all_callbacks(input_keyboard(skip=True)), ["cl:skip", "cl:cancel"])


class NoTruncationTests(TestCase):
    def test_the_list_stays_short_and_the_card_keeps_the_full_text(self) -> None:
        text = "Здравствуйте, пишу по поводу сотрудничества. " * 6
        row = {"id": 1, "sort_order": 0, "values": {1: "Ромашка", 2: text}}
        page_rows, page, pages, start = paginate_rows(COLUMNS, [row], 0)
        listing = build_table_html(COLUMNS, page_rows, page, pages, 1, start)
        self.assertIn("контакт ✓", listing)
        self.assertIn("<blockquote expandable>", listing)

        card = "".join(build_company_html(COLUMNS, row, 1))
        self.assertIn(text.strip(), card)

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
    def test_renders_one_numbered_block_per_company(self) -> None:
        html = build_table_html(COLUMNS, _rows(2))
        self.assertTrue(html.startswith("<h3>Клиенты</h3>"))
        self.assertIn("<b>1. Компания 0</b>", html)
        self.assertIn("<b>2. Компания 1</b>", html)
        # a squeezed table is exactly what this layout replaced
        self.assertNotIn("<table", html)

    def test_numbering_continues_across_pages(self) -> None:
        rows = _rows(MAX_ROWS_PER_PAGE + 2)
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 1)
        html = build_table_html(COLUMNS, page_rows, page, pages, len(rows), start)
        self.assertIn(f"<b>{MAX_ROWS_PER_PAGE + 1}. ", html)
        self.assertIn(f"стр. 2/{pages}", html)

    def test_a_company_with_nothing_filled_in_says_so(self) -> None:
        html = build_table_html(COLUMNS, [{"id": 1, "values": {1: "Ромашка", 2: "   "}}])
        self.assertIn("<b>1. Ромашка</b>", html)
        self.assertIn("пусто", html)

    def test_summary_names_only_the_filled_fields(self) -> None:
        html = build_table_html(
            COLUMNS, [{"id": 1, "values": {1: "Ромашка", 2: "Иван"}}]
        )
        self.assertIn("контакт: Иван", html)

    def test_a_long_value_is_a_tick_in_the_summary_and_a_collapsed_quote(self) -> None:
        html = build_table_html(
            COLUMNS, [{"id": 1, "values": {1: "Ромашка", 2: "и" * 200}}]
        )
        self.assertIn("контакт ✓", html)          # scannable summary
        self.assertIn("<blockquote expandable>", html)
        self.assertIn("и" * 200, html)            # full text, collapsed by default

    def test_user_input_is_html_escaped(self) -> None:
        rows = [{"id": 1, "values": {1: '<script>alert("x")</script>', 2: "a & b"}}]
        html = build_table_html(COLUMNS, rows)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("a &amp; b", html)

    def test_column_names_are_escaped_too(self) -> None:
        cols = [
            {"id": 1, "name": "Компания", "sort_order": 0,
             "kind": "text", "quick_values": []},
            {"id": 2, "name": "<b>Контакт</b>", "sort_order": 1,
             "kind": "text", "quick_values": []},
        ]
        html = build_table_html(cols, [{"id": 1, "values": {1: "x", 2: "Иван"}}])
        self.assertNotIn("<b>Контакт</b>", html)
        self.assertIn("&lt;b&gt;", html)

    def test_caption_counts_all_rows_not_just_the_page(self) -> None:
        rows = _rows(25)
        page_rows, page, pages, start = paginate_rows(COLUMNS, rows, 0)
        html = build_table_html(COLUMNS, page_rows, page, pages, len(rows), start)
        self.assertIn("25 компаний", html)

    def test_whitespace_is_collapsed(self) -> None:
        rows = [{"id": 1, "values": {1: "Ромашка\n\nООО", 2: "a   b"}}]
        html = build_table_html(COLUMNS, rows)
        self.assertIn("Ромашка ООО", html)
        self.assertIn("a b", html)

    def test_an_empty_list_invites_the_first_company(self) -> None:
        html = build_table_html(COLUMNS, [])
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
