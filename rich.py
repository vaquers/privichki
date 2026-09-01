"""Building blocks for rich-message HTML (Bot API 10.3).

Only the tags listed in the "Rich HTML style" section of the Bot API docs are
supported, and only a short list of named HTML entities, so everything here
escapes through `esc` rather than using html.escape's full output.
"""

from __future__ import annotations

from html import escape

# Button styles accepted by <tg-button>. "link" draws the button as a plain
# link without borders and is allowed for callback buttons only.
STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER = "danger"
STYLE_LINK = "link"

ALIGN_LEFT = "left"
ALIGN_CENTER = "center"
ALIGN_RIGHT = "right"


def esc(text: str) -> str:
    """Escape for rich HTML. &quot; is named, &#x27; is numeric -- both supported."""
    return escape(str(text), quote=True)


def paragraph(text: str, *, bold: bool = False) -> str:
    body = f"<b>{text}</b>" if bold else text
    return f"<p>{body}</p>"


def button(
    text: str,
    data: str | None = None,
    *,
    style: str | None = None,
    disabled: bool = False,
) -> str:
    """One <tg-button>. Without data it is rendered as a dead label."""
    if disabled or data is None:
        attrs = ' type="disabled"'
        if style:
            attrs += f' style="{style}"'
        return f"<tg-button{attrs}>{esc(text)}</tg-button>"

    attrs = f' type="callback_data" data="{esc(data)}"'
    if style:
        attrs += f' style="{style}"'
    return f"<tg-button{attrs}>{esc(text)}</tg-button>"


def button_row(buttons: list[str], *, align: str | None = None) -> str:
    if not buttons:
        return ""
    attr = f' align="{align}"' if align else ""
    return f"<tg-button-row{attr}>{''.join(buttons)}</tg-button-row>"


def expandable_quote(text: str) -> str:
    """<blockquote expandable> -- collapsed by default, opened by a tap.

    Line breaks become <br>, since the quote body is HTML and would otherwise
    collapse the author's paragraphs into one run.
    """
    lines = [esc(line.strip()) for line in text.splitlines() if line.strip()]
    return f"<blockquote expandable>{'<br>'.join(lines)}</blockquote>"


def quote(text: str) -> str:
    lines = [esc(line.strip()) for line in text.splitlines() if line.strip()]
    return f"<blockquote>{'<br>'.join(lines)}</blockquote>"


def video(media_id: str) -> str:
    """Embed a video that travels in the message's own media list."""
    return f'<video src="tg://video?id={media_id}"></video>'


def media_id_for(prefix: str, number: int) -> str:
    """Ids may hold only A-Z, a-z, 0-9, _ and - and are at most 64 characters."""
    return f"{prefix}-{number}"
