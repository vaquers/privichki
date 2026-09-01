from __future__ import annotations

from html import escape

import rich

SAFE_HTML_LEN = 8000
PREVIEW_LEN = 90


def _paragraphs(value: str) -> str:
    """Keep the author's line breaks -- HTML would otherwise collapse them."""
    lines = [line.strip() for line in value.splitlines()]
    return "".join(f"<p>{escape(line)}</p>" for line in lines if line)


def _date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def _preview(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= PREVIEW_LEN else text[: PREVIEW_LEN - 1] + "…"


def build_list_html(notes: list[dict], marks: int, per_topic: int,
                    pending: int = 0, query: str | None = None) -> str:
    """The topic list shown by the Экономика button."""
    if query is not None:
        head = f"<h3>Поиск: {escape(query)}</h3>"
        if not notes:
            return head + "<p>Ничего не нашлось.</p>"
        head += f"<p>Найдено тем: {len(notes)}</p>"
    else:
        head = "<h3>Экономика</h3>"
        status = [f"тем записано: {len(notes)}"]
        status.append(f"текущая тема: {marks}/{per_topic}")
        if pending:
            status.append(f"ждут конспекта: {pending}")
        head += f"<p>{escape(' · '.join(status))}</p>"
        if not notes:
            return head + "<p>Пока нет ни одной темы. Нажми «➕ Тема».</p>"

    items = []
    for n in notes:
        line = f"<b>{n['number']}. {escape(n['title'])}</b>"
        when = _date(n.get("created_at"))
        if when:
            line += f" · {when}"
        items.append(f"<p>{line}</p>")
        if n.get("body"):
            # The whole write-up is here, collapsed: a tap opens it in place.
            items.append(rich.expandable_quote(n["body"]))
        items.append(rich.button_row([
            rich.button("Открыть", f"ec:open:{n['id']}", style=rich.STYLE_PRIMARY),
            rich.button("Название", f"ec:ret:{n['id']}"),
            rich.button("Текст", f"ec:reb:{n['id']}"),
            rich.button("Удалить", f"ec:del:{n['id']}", style=rich.STYLE_DANGER),
        ]))

    html = head + "".join(items)
    while len(html) > SAFE_HTML_LEN and items:
        items = items[:-2] if len(items) > 1 else items[:-1]
        html = head + "".join(items) + "<p>…список обрезан, уточни поиском</p>"
    return html


def build_note_html(note: dict) -> list[str]:
    """One topic in full, split across messages when very long."""
    head = f"<h3>{note['number']}. {escape(note['title'])}</h3>"
    when = _date(note.get("created_at"))
    meta = f"<p>{when}</p>" if when else ""

    body = note.get("body") or ""
    if not body.strip():
        return [head + meta + "<p>Текст пока не записан.</p>"]

    paragraphs = [p for p in (line.strip() for line in body.splitlines()) if p]
    chunks: list[str] = []
    current = head + meta
    for para in paragraphs:
        block = f"<p>{escape(para)}</p>"
        if len(current) + len(block) > SAFE_HTML_LEN and current not in (head + meta, ""):
            chunks.append(current)
            current = ""
        current += block
    if current:
        chunks.append(current)
    return chunks
