from __future__ import annotations

from html import escape

# Rows shown per page. Native tables have no pixel limit, but the rich-message
# HTML still has to stay comfortably small, so pages are kept short.
ROWS_PER_PAGE = 10

# Telegram documents no length limit for rich_message HTML, so this is a safety
# net rather than a known ceiling: cell values are clipped for readability first,
# and shrunk further only if a page somehow still exceeds the budget.
SAFE_HTML_LEN = 8000
CELL_CAPS = (80, 50, 30, 20, 12)

ALIGN_LEFT = "left"
ALIGN_RIGHT = "right"

EMPTY_CELL = "—"


def _plural(n: int, one: str, few: str, many: str) -> str:
    """Russian plural form for a count."""
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def paginate(rows: list[dict], page: int) -> tuple[list[dict], int, int]:
    """Return (rows_on_page, clamped_page, total_pages)."""
    pages = max(1, (len(rows) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    start = page * ROWS_PER_PAGE
    return rows[start:start + ROWS_PER_PAGE], page, pages


def _clip(text: str, cap: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= cap else text[: cap - 1] + "…"


def _cell(text: str, *, header: bool = False, align: str = ALIGN_LEFT) -> str:
    tag = "th" if header else "td"
    attr = "" if align == ALIGN_LEFT else f' align="{align}"'
    return f"<{tag}{attr}>{escape(text)}</{tag}>"


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
    total_rows: int, cap: int,
) -> str:
    head = "".join(
        [_cell("#", header=True, align=ALIGN_RIGHT)]
        + [_cell(_clip(c["name"], cap), header=True) for c in columns]
    )
    body = []
    for n, row in enumerate(rows):
        number = page * ROWS_PER_PAGE + n + 1
        cells = [_cell(str(number), align=ALIGN_RIGHT)]
        for column in columns:
            value = (row["values"].get(column["id"]) or "").strip()
            cells.append(_cell(_clip(value, cap) if value else EMPTY_CELL))
        body.append(f"<tr>{''.join(cells)}</tr>")

    caption = escape(_subtitle(total_rows, len(columns), page, pages))
    table = (
        "<table bordered striped>"
        f"<caption>{caption}</caption>"
        f"<tr>{head}</tr>"
        f"{''.join(body)}"
        "</table>"
    )
    html = f"<h3>Клиенты</h3>{table}"
    if not rows:
        html += "<p>Пока нет компаний. Нажми «➕ Компания».</p>"
    return html


def build_table_html(
    columns: list[dict], rows: list[dict], page: int = 0, pages: int = 1,
    total_rows: int | None = None,
) -> str:
    """Render one page of the client table as Telegram rich-message HTML."""
    if total_rows is None:
        total_rows = len(rows)

    if not columns:
        return "<h3>Клиенты</h3><p>Нет колонок. Добавь колонку в «Редактировать → Колонки».</p>"

    for cap in CELL_CAPS:
        html = _build(columns, rows, page, pages, total_rows, cap)
        if len(html) <= SAFE_HTML_LEN:
            return html
    return html
