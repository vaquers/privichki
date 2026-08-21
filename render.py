from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CORNER_RADIUS = 20

from config import BASE_DIR

# --- fonts (Unbounded) ---
_FONTS = BASE_DIR / "assets" / "fonts"
FONT_TITLE = _FONTS / "Unbounded-Bold.ttf"
FONT_SUBTITLE = _FONTS / "Unbounded-Medium.ttf"
FONT_HABIT_NAME = _FONTS / "Unbounded-Bold.ttf"
FONT_TIME = _FONTS / "Unbounded-Regular.ttf"

# --- card images ---
CARDS_DIR = BASE_DIR / "assets" / "cards"
CLEAR_IMG = CARDS_DIR / "clear.jpg"

# per-habit: colored card path + text color
# key -> (card image file, text colour). A None image means the card is drawn
# as a flat plate in the habit colour -- used until real art exists.
HABIT_STYLE: dict[str, tuple[str | None, tuple[int, int, int]]] = {
    "math":      ("math.png",    (0x00, 0x88, 0xFF)),  # #0088FF
    "dev":       ("sites.png",   (0x61, 0x55, 0xF5)),  # #6155F5
    "sport":     ("sport.png",   (0x34, 0xC7, 0x59)),  # #34C759
    "economics": ("economy.png", (0xFF, 0x8D, 0x28)),  # #FF8D28
    "shower":    (None,          (0x06, 0xB6, 0xD4)),  # #06B6D4
    "sleep":     (None,          (0x64, 0x74, 0x8B)),  # #64748B
}

HABIT_LABEL: dict[str, str] = {
    "math": "Математика",
    "dev": "Сайты",
    "sport": "Спорт",
    "economics": "Экономика",
    "shower": "Душ",
    "sleep": "Сон",
}

# Cards are laid out in rows of this many.
GRID_COLS = 3

# --- colors ---
BG_WHITE = (0xFF, 0xFF, 0xFF)
TEXT_BLACK = (0x00, 0x00, 0x00)
TEXT_GRAY = (0x8E, 0x8E, 0x93)

# --- dimensions ---
WIDTH, HEIGHT = 1080, 747
CARD_W, CARD_H = 250, 333

MONTHS_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
WEEKDAYS_RU = [
    "понедельник", "вторник", "среда", "четверг",
    "пятница", "суббота", "воскресенье",
]


def render_day_card(date_str: str, habits: list[dict], state: dict[str, bool]) -> BytesIO:
    """Card for one day, showing only the habits scheduled on it."""
    from datetime import date as date_cls

    d = date_cls.fromisoformat(date_str)
    date_label = f"{d.day} {MONTHS_RU[d.month]}, {WEEKDAYS_RU[d.weekday()]}"

    day_habits = sorted(habits, key=lambda h: h["sort_order"])
    total = len(day_habits)
    done_count = sum(1 for h in day_habits if state.get(h["key"], False))
    counter = f"{done_count}/{total} выполнено"

    side_pad = 24
    gap = 20
    card_w = (WIDTH - 2 * side_pad - (GRID_COLS - 1) * gap) // GRID_COLS
    card_h = round(card_w * CARD_H / CARD_W)

    font_title = ImageFont.truetype(str(FONT_TITLE), 64)
    font_sub = ImageFont.truetype(str(FONT_SUBTITLE), 48)
    font_name = ImageFont.truetype(str(FONT_HABIT_NAME), 32)
    font_time = ImageFont.truetype(str(FONT_TIME), 26)

    caption_h = 78                       # habit name + subtitle under each card
    row_h = card_h + caption_h
    rows = max(1, -(-total // GRID_COLS))  # ceil

    header_h = 200
    height = header_h + rows * row_h + (rows - 1) * gap + 30

    img = Image.new("RGB", (WIDTH, height), BG_WHITE)
    draw = ImageDraw.Draw(img)

    draw.text((side_pad, 30), date_label, font=font_title, fill=TEXT_BLACK)
    title_bbox = draw.textbbox((side_pad, 30), date_label, font=font_title)
    draw.text((side_pad, title_bbox[3] + 8), counter, font=font_sub, fill=TEXT_GRAY)

    for i, h in enumerate(day_habits):
        row, col = divmod(i, GRID_COLS)
        in_row = min(GRID_COLS, total - row * GRID_COLS)
        # centre a partial last row instead of leaving it hanging left
        row_w = in_row * card_w + (in_row - 1) * gap
        row_x = (WIDTH - row_w) // 2
        cx = row_x + col * (card_w + gap)
        cy = header_h + row * (row_h + gap)

        key = h["key"]
        done = state.get(key, False)
        art, colour = HABIT_STYLE.get(key, (None, TEXT_BLACK))

        _draw_card(img, draw, cx, cy, card_w, card_h, done, art, colour)

        label = HABIT_LABEL.get(key, h["name"])
        name_bbox = draw.textbbox((0, 0), label, font=font_name)
        name_x = cx + (card_w - (name_bbox[2] - name_bbox[0])) // 2
        name_y = cy + card_h + 12
        draw.text((name_x, name_y), label, font=font_name, fill=colour)

        subtitle = h.get("subtitle") or ""
        if subtitle:
            sub_bbox = draw.textbbox((0, 0), subtitle, font=font_time)
            sub_x = cx + (card_w - (sub_bbox[2] - sub_bbox[0])) // 2
            sub_y = name_y + (name_bbox[3] - name_bbox[1]) + 10
            draw.text((sub_x, sub_y), subtitle, font=font_time, fill=TEXT_GRAY)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_card(img, draw, x: int, y: int, w: int, h: int,
               done: bool, art: str | None, colour: tuple[int, int, int]) -> None:
    """One habit card: artwork when done and available, a flat plate otherwise."""
    if done and art is None:
        draw.rounded_rectangle([x, y, x + w, y + h], radius=CORNER_RADIUS, fill=colour)
        return

    path = CARDS_DIR / art if (done and art) else CLEAR_IMG
    if not path.exists():
        fill = colour if done else (0xF0, 0xF0, 0xF0)
        draw.rounded_rectangle([x, y, x + w, y + h], radius=CORNER_RADIUS, fill=fill)
        return

    card = Image.open(path).convert("RGBA").resize((w, h), Image.LANCZOS)
    if not done:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, w, h], radius=CORNER_RADIUS, fill=255
        )
        card.putalpha(mask)
    img.paste(card, (x, y), card)


def render_stats_card(data: dict) -> BytesIO:
    """Render stats card PNG, mobile-friendly large elements."""
    title = data["title"]
    habits = data["habits"]
    perfect_days = data["perfect_days"]
    total_days = data["total_days"]

    STATS_W = 1080
    left_pad = 60
    right_pad = 60
    content_w = STATS_W - left_pad - right_pad

    font_sub = ImageFont.truetype(str(FONT_SUBTITLE), 44)
    font_habit = ImageFont.truetype(str(FONT_HABIT_NAME), 44)
    font_small = ImageFont.truetype(str(FONT_TIME), 30)

    # auto-size title to fit width
    title_size = 64
    font_title = ImageFont.truetype(str(FONT_TITLE), title_size)
    # use temporary image for measuring
    _tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while _tmp.textbbox((0, 0), title, font=font_title)[2] > content_w and title_size > 36:
        title_size -= 2
        font_title = ImageFont.truetype(str(FONT_TITLE), title_size)

    weekdays = data.get("weekdays") or []

    # pre-calculate height
    row_h = 195
    header_h = 250
    footer_h = 100
    weekday_h = 190 if weekdays else 0
    STATS_H = header_h + len(habits) * row_h + weekday_h + footer_h

    img = Image.new("RGB", (STATS_W, STATS_H), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # header
    y = 50
    draw.text((left_pad, y), title, font=font_title, fill=TEXT_BLACK)
    title_bbox = draw.textbbox((left_pad, y), title, font=font_title)
    y = title_bbox[3] + 12

    perfect_text = f"{perfect_days}/{total_days} идеальных дней"
    if data.get("skipped"):
        perfect_text += f" · пропущено {data['skipped']}"
    draw.text((left_pad, y), perfect_text, font=font_sub, fill=TEXT_GRAY)
    sub_bbox = draw.textbbox((left_pad, y), perfect_text, font=font_sub)
    y = sub_bbox[3] + 55

    if not habits:
        draw.text((left_pad, y), "Нет данных", font=font_sub, fill=TEXT_GRAY)
    else:
        bar_h = 28
        bar_radius = 14

        for h in habits:
            key = h["key"]
            color = HABIT_STYLE.get(key, ("", TEXT_BLACK))[1]
            label = HABIT_LABEL.get(key, h["name"])

            # habit name + percentage on same line
            draw.text((left_pad, y), label, font=font_habit, fill=color)
            pct_text = f"{h['pct']}%"
            pct_bbox = draw.textbbox((0, 0), pct_text, font=font_habit)
            pct_w = pct_bbox[2] - pct_bbox[0]
            draw.text((left_pad + content_w - pct_w, y), pct_text, font=font_habit, fill=color)

            name_bbox = draw.textbbox((left_pad, y), label, font=font_habit)

            # progress bar
            bar_y = name_bbox[3] + 14
            draw.rounded_rectangle(
                [left_pad, bar_y, left_pad + content_w, bar_y + bar_h],
                radius=bar_radius, fill=(0xE8, 0xE8, 0xED),
            )
            if h["pct"] > 0:
                fill_w = max(bar_h, int(content_w * h["pct"] / 100))
                draw.rounded_rectangle(
                    [left_pad, bar_y, left_pad + fill_w, bar_y + bar_h],
                    radius=bar_radius, fill=color,
                )

            # stats line below bar
            stat_y = bar_y + bar_h + 10
            stat_line = f"{h['done']}/{h['total']} дней"
            if h.get("streak"):
                stat_line += f"  ·  серия {h['streak']}"
            draw.text((left_pad, stat_y), stat_line, font=font_small, fill=TEXT_GRAY)

            y += row_h

    if weekdays:
        y += 10
        draw.text((left_pad, y), "По дням недели", font=font_habit, fill=TEXT_BLACK)
        head_bbox = draw.textbbox((left_pad, y), "По дням недели", font=font_habit)
        y = head_bbox[3] + 26

        slot = content_w // 7
        col_w = slot - 14
        max_bar = 70
        for i, wd in enumerate(weekdays):
            x = left_pad + i * slot
            bar_h_i = round(max_bar * wd["pct"] / 100)
            base = y + max_bar
            draw.rounded_rectangle([x, y, x + col_w, base], radius=8,
                                   fill=(0xE8, 0xE8, 0xED))
            if bar_h_i > 0:
                draw.rounded_rectangle([x, base - bar_h_i, x + col_w, base], radius=8,
                                       fill=(0x61, 0x55, 0xF5))
            name_bbox = draw.textbbox((0, 0), wd["name"], font=font_small)
            draw.text((x + (col_w - (name_bbox[2] - name_bbox[0])) // 2, base + 10),
                      wd["name"], font=font_small, fill=TEXT_GRAY)
            pct_text = f"{wd['pct']}%"
            pct_bbox = draw.textbbox((0, 0), pct_text, font=font_small)
            draw.text((x + (col_w - (pct_bbox[2] - pct_bbox[0])) // 2, base + 46),
                      pct_text, font=font_small, fill=TEXT_GRAY)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
