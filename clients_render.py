from __future__ import annotations

from html import escape

import rich

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

# Telegram squeezes a wide table into the screen instead of scrolling it, so on
# a phone five columns collapse to a letter per line. The list shows one company
# per block with a compact summary line; the full values live in the card behind
# «Открыть компанию».
SHORT_LABEL = {
    "Текст сообщения": "сообщение",
    "Текст ответа": "ответ",
    "Видео сайта": "видео",
    "Комментарий": "коммент",
}

# A value up to this length is quoted verbatim in the summary; longer ones are
# reduced to a tick, since the point of the line is scanning, not reading.
INLINE_SUMMARY_LEN = 18

# A collapsed quote still ships its whole text in the message, so a single very
# long value would blow the size budget on its own. Past this, the quote is cut
# and the rest is read in the card.
MAX_QUOTE_LEN = 1500


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

    overhead = 200  # title and caption
    pages: list[list[dict]] = []
    current: list[dict] = []
    current_len = overhead

    for i, row in enumerate(rows):
        size = len(_company_block(columns, row, i + 1))
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


def _short_label(column: dict) -> str:
    return SHORT_LABEL.get(column["name"], column["name"].lower())


def _summary(columns: list[dict], row: dict) -> str:
    """One scannable line: only the fields that actually hold something."""
    from clients_db import is_video

    parts = []
    for column in columns[1:]:
        value = _value(row, column)
        label = escape(_short_label(column))
        if is_video(column):
            if value:
                parts.append(f"{label} ✓")
            continue
        if not value:
            continue
        flat = " ".join(value.split())
        if len(flat) <= INLINE_SUMMARY_LEN:
            parts.append(f"{label}: {escape(flat)}")
        else:
            parts.append(f"{label} ✓")
    return " · ".join(parts)


def _company_block(columns: list[dict], row: dict, number: int,
                   with_quotes: bool = True) -> str:
    """Heading, the long fields as collapsed quotes, then this company's buttons.

    The full text sits in the message itself: a tap expands it in place, so
    reading a message no longer means opening a separate card.
    """
    from clients_db import is_video, row_label

    parts = [rich.paragraph(f"{number}. {rich.esc(row_label(row, columns, limit=40))}",
                            bold=True)]

    summary = _summary(columns, row)
    if summary:
        parts.append(f"<p>{summary}</p>")

    quoted = False
    if with_quotes:
        for column in columns[1:]:
            if is_video(column):
                continue
            value = _value(row, column)
            if len(" ".join(value.split())) > INLINE_SUMMARY_LEN:
                parts.append(rich.paragraph(rich.esc(_short_label(column)), bold=True))
                parts.append(rich.expandable_quote(_clip(value, MAX_QUOTE_LEN)))
                quoted = True

    if not summary and not quoted:
        parts.append("<p>пусто</p>")

    company_id = row["id"]
    buttons = [rich.button("Открыть", f"cl:show:{company_id}", style=rich.STYLE_PRIMARY)]
    reply_column = next(
        (c for c in columns if c.get("quick_values") and not is_video(c)), None
    )
    if reply_column is not None:
        buttons.append(rich.button(
            "Ответ", f"cl:cellv:{company_id}:{reply_column['id']}",
            style=rich.STYLE_SUCCESS,
        ))
    video_column = next((c for c in columns if is_video(c)), None)
    if video_column is not None and _value(row, video_column):
        buttons.append(rich.button("Видео", f"cl:vid:{company_id}"))
    parts.append(rich.button_row(buttons))

    return "".join(parts)


def _build(
    columns: list[dict], rows: list[dict], page: int, pages: int,
    total_rows: int, start: int, with_quotes: bool = True,
) -> str:
    caption = escape(_subtitle(total_rows, len(columns), page, pages))
    html = f"<h3>Клиенты</h3><p>{caption}</p>"
    if not rows:
        return html + "<p>Пока нет компаний. Нажми «➕ Компания».</p>"
    return html + "".join(
        _company_block(columns, row, start + n + 1, with_quotes)
        for n, row in enumerate(rows)
    )


def build_table_html(
    columns: list[dict], rows: list[dict], page: int = 0, pages: int = 1,
    total_rows: int | None = None, start: int = 0,
) -> str:
    """Render one page of companies as Telegram rich-message HTML."""
    if total_rows is None:
        total_rows = len(rows)
    if not columns:
        return "<h3>Клиенты</h3><p>Нет колонок. Добавь колонку в «Редактировать → Колонки».</p>"

    html = _build(columns, rows, page, pages, total_rows, start)
    if len(html) <= SAFE_HTML_LEN:
        return html
    # Too much text to inline even after clipping: fall back to summaries only,
    # which always fit. The full values stay reachable through «Открыть».
    return _build(columns, rows, page, pages, total_rows, start, with_quotes=False)


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
            # Embedded by reference: the file itself travels in the message's
            # media list, so the video plays inside the card.
            blocks.append(f"<p><b>{name}</b></p>")
            blocks.append(rich.video(rich.media_id_for("vid", column["id"])))
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
