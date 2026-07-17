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
HABIT_STYLE: dict[str, tuple[str, tuple[int, int, int]]] = {
    "math":      ("math.png",    (0x00, 0x88, 0xFF)),  # #0088FF
    "dev":       ("sites.png",   (0x61, 0x55, 0xF5)),  # #6155F5
    "sport":     ("sport.png",   (0x34, 0xC7, 0x59)),  # #34C759
    "economics": ("economy.png", (0xFF, 0x8D, 0x28)),  # #FF8D28
}

HABIT_LABEL: dict[str, str] = {
    "math": "Математика",
    "dev": "Сайты",
    "sport": "Спорт",
    "economics": "Экономика",
}

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
    from datetime import date as date_cls

    d = date_cls.fromisoformat(date_str)
    date_label = f"{d.day} {MONTHS_RU[d.month]}, {WEEKDAYS_RU[d.weekday()]}"
    done_count = sum(1 for v in state.values() if v)

    # fixed order by sort_order, no reordering by completion
    sorted_habits = sorted(habits, key=lambda h: h["sort_order"])

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_WHITE)
    draw = ImageDraw.Draw(img)

    # fonts
    font_title = ImageFont.truetype(str(FONT_TITLE), 64)
    font_sub = ImageFont.truetype(str(FONT_SUBTITLE), 48)
    font_name = ImageFont.truetype(str(FONT_HABIT_NAME), 32)
    font_time = ImageFont.truetype(str(FONT_TIME), 24)

    # layout: 4 cards × 250 = 1000, remaining 80 px spread as gaps
    # 5 gaps (left edge, 3 between, right edge) but spec says align left edge
    # with title. Use: left_pad = 16, gap between cards = 16, total = 16 + 3*16 + 16 = 80. ✓
    left_pad = 16
    gap = 16

    # header
    title_y = 30
    draw.text((left_pad, title_y), date_label, font=font_title, fill=TEXT_BLACK)
    title_bbox = draw.textbbox((left_pad, title_y), date_label, font=font_title)
    sub_y = title_bbox[3] + 8
    draw.text((left_pad, sub_y), f"{done_count}/4 выполнено", font=font_sub, fill=TEXT_GRAY)
    sub_bbox = draw.textbbox((left_pad, sub_y), f"{done_count}/4 выполнено", font=font_sub)

    # card row — push down for breathing room
    cards_y = sub_bbox[3] + 60

    for i, h in enumerate(sorted_habits):
        done = state.get(h["key"], False)
        key = h["key"]
        cx = left_pad + i * (CARD_W + gap)

        # pick image
        if done and key in HABIT_STYLE:
            card_path = CARDS_DIR / HABIT_STYLE[key][0]
        else:
            card_path = CLEAR_IMG

        if card_path.exists():
            card_img = Image.open(card_path).convert("RGBA")
            card_img = card_img.resize((CARD_W, CARD_H), Image.LANCZOS)
            if not done:
                # round corners on clear.jpg only
                mask = Image.new("L", (CARD_W, CARD_H), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle([0, 0, CARD_W, CARD_H], radius=CORNER_RADIUS, fill=255)
                card_img.putalpha(mask)
            img.paste(card_img, (cx, cards_y), card_img)
        else:
            draw.rectangle([cx, cards_y, cx + CARD_W, cards_y + CARD_H], fill=(0xF0, 0xF0, 0xF0))

        # label: habit name centered under card
        label = HABIT_LABEL.get(key, h["name"])
        name_color = HABIT_STYLE[key][1] if key in HABIT_STYLE else TEXT_BLACK
        name_bbox = draw.textbbox((0, 0), label, font=font_name)
        name_w = name_bbox[2] - name_bbox[0]
        name_x = cx + (CARD_W - name_w) // 2
        name_y = cards_y + CARD_H + 10
        draw.text((name_x, name_y), label, font=font_name, fill=name_color)

        # time centered under name
        time_text = f"{h['target_hours']} часа"
        time_bbox = draw.textbbox((0, 0), time_text, font=font_time)
        time_w = time_bbox[2] - time_bbox[0]
        time_x = cx + (CARD_W - time_w) // 2
        time_y = name_y + (name_bbox[3] - name_bbox[1]) + 6
        draw.text((time_x, time_y), time_text, font=font_time, fill=TEXT_GRAY)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
