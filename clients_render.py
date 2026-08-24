from __future__ import annotations

from html import escape

# Telegram documents no length limit for rich_message HTML, so this is a
# conservative safety net rather than a known ceiling.
SAFE_HTML_LEN = 8000

# A page never holds more rows than this, however short they are.
MAX_ROWS_PER_PAGE = 20

# Only used when a single row is too large to fit a page on its own. Normal
# rows are never clipped -- the page simply holds fewer of them.
CELL_CAPS = (400, 200, 120, 60, 30)

# Values longer than this get their own quoted block in the company card.
INLINE_VALUE_LEN = 60

ALIGN_LEFT = "left"
ALIGN_RIGHT = "right"

EMPTY_CELL = "—"
VIDEO_CELL = "🎥 есть"


def _plural(n: int, one: str, few: str, many: str) -> str:
    """Russian plural form for a count."""
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _clip(text: str, cap: int | None) -> str:
    text = " ".join(text.split())
    if cap is None or len(text) <= cap:
        return text
    return text[: cap - 1] + "…"


def _cell(text: str, *, header: bool = False, align: str = ALIGN_LEFT) -> str:
    tag = "th" if header else "td"
    attr = "" if align == ALIGN_LEFT else f' align="{align}"'
    return f"<{tag}{attr}>{escape(text)}</{tag}>"


def _value(row: dict, column: dict) -> str:
    return (row["values"].get(column["id"]) or "").strip()


def _display(row: dict, column: dict, cap: int | None) -> str:
    """What the cell shows. A video holds a Telegram file id, never shown raw."""
    from clients_db import is_video

    value = _value(row, column)
    if not value:
        return EMPTY_CELL
    if is_video(column):
        return VIDEO_CELL
    return _clip(value, cap)


def _row_html(columns: list[dict], row: dict, number: int, cap: int | None) -> str:
    cells = [_cell(str(number), align=ALIGN_RIGHT)]
    for column in columns:
        cells.append(_cell(_display(row, column, cap)))
    return f"<tr>{''.join(cells)}</tr>"


def _header_html(columns: list[dict]) -> str:
    cells = [_cell("#", header=True, align=ALIGN_RIGHT)]
    cells += [_cell(c["name"], header=True) for c in columns]
    return f"<tr>{''.join(cells)}</tr>"


def paginate_rows(
    columns: list[dict], rows: list[dict], page: int
) -> tuple[list[dict], int, int, int]:
    """Split rows into pages that each fit the size budget.

    Pages hold as many whole rows as will fit rather than a fixed count, so a
    long value is shown in full instead of being cut short.

    Returns (rows_on_page, clamped_page, total_pages, index_of_first_row).
    """
    if not rows:
        return [], 0, 1, 0

    overhead = len(_header_html(columns)) + 200  # header, caption and title
    pages: list[list[dict]] = []
    current: list[dict] = []
    current_len = overhead

    for i, row in enumerate(rows):
        size = len(_row_html(columns, row, i + 1, None))
        too_long = current_len + size > SAFE_HTML_LEN
        too_many = len(current) >= MAX_ROWS_PER_PAGE
        if current and (too_long or too_many):
            pages.append(current)
            current, current_len = [], overhead
        current.append(row)
        current_len += size
    if current:
        pages.append(current)

    page = max(0, min(page, len(pages) - 1))
    start = sum(len(p) for p in pages[:page])
    return pages[page], page, len(pages), start


def _subtitle(row_count: int, column_count: int, page: int, pages: int) -> str:
    parts = [
        f"{row_count} {_plural(row_count, 'компания', 'компании', 'компаний')}",
        f"{column_count} {_plural(column_count, 'колонка', 'колонки', 'колонок')}",
    ]
    if pages > 1:
        parts.append(f"стр. {page + 1}/{pages}")
    return " · ".join(parts)


def _build(
    columns: list[dict], rows: list[dict], page: int, pages: int,
    total_rows: int, start: int, cap: int | None,
) -> str:
    body = "".join(
        _row_html(columns, row, start + n + 1, cap) for n, row in enumerate(rows)
    )
    caption = escape(_subtitle(total_rows, len(columns), page, pages))
    html = (
        "<h3>Клиенты</h3>"
        "<table bordered striped>"
        f"<caption>{caption}</caption>"
        f"{_header_html(columns)}{body}"
        "</table>"
    )
    if not rows:
        html += "<p>Пока нет компаний. Нажми «➕ Компания».</p>"
    return html


def build_table_html(
    columns: list[dict], rows: list[dict], page: int = 0, pages: int = 1,
    total_rows: int | None = None, start: int = 0,
) -> str:
    """Render one page of the client table as Telegram rich-message HTML."""
    if total_rows is None:
        total_rows = len(rows)

    if not columns:
        return "<h3>Клиенты</h3><p>Нет колонок. Добавь колонку в «Редактировать → Колонки».</p>"

    html = _build(columns, rows, page, pages, total_rows, start, None)
    if len(html) <= SAFE_HTML_LEN:
        return html

    # A single row bigger than a whole page: clip it so the table still renders.
    # The full text stays readable through the company card.
    for cap in CELL_CAPS:
        html = _build(columns, rows, page, pages, total_rows, start, cap)
        if len(html) <= SAFE_HTML_LEN:
            return html
    return html


def _paragraphs(value: str) -> str:
    """Keep the author's line breaks -- HTML would otherwise collapse them."""
    lines = [line.strip() for line in value.splitlines()]
    return "".join(f"<p>{escape(line)}</p>" for line in lines if line)


def build_company_html(columns: list[dict], row: dict, number: int) -> list[str]:
    """Render one company with every value in full, split across messages if long."""
    from clients_db import row_label

    from clients_db import is_video

    head = f"<h3>{escape(row_label(row, columns, limit=64))}</h3>"
    blocks: list[str] = []
    for column in columns:
        name = escape(column["name"])
        value = _value(row, column)
        if not value:
            blocks.append(f"<p><b>{name}</b>: {EMPTY_CELL}</p>")
        elif is_video(column):
            blocks.append(f"<p><b>{name}</b>: {VIDEO_CELL} — кнопка «▶️ Видео» ниже</p>")
        elif len(value) <= INLINE_VALUE_LEN and "\n" not in value:
            blocks.append(f"<p><b>{name}</b>: {escape(value)}</p>")
        else:
            blocks.append(f"<p><b>{name}</b></p><blockquote>{_paragraphs(value)}</blockquote>")

    chunks: list[str] = []
    current = head
    for block in blocks:
        if len(current) + len(block) > SAFE_HTML_LEN and current != head:
            chunks.append(current)
            current = ""
        current += block
    if current:
        chunks.append(current)
    return chunks
