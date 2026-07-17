"""Fetch custom_emoji_id list from a Telegram sticker set."""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from dotenv import load_dotenv

# load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN not found in .env")
    sys.exit(1)

SET_NAME = "MajkVazovskij36"
URL = f"https://api.telegram.org/bot{BOT_TOKEN}/getStickerSet?name={SET_NAME}"

try:
    resp = urlopen(Request(URL))
    data = json.loads(resp.read().decode())
except HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}")
    sys.exit(1)

if not data.get("ok"):
    print(f"API error: {data}")
    sys.exit(1)

stickers = data["result"]["stickers"]
print(f"Set: {data['result']['name']} — {len(stickers)} sticker(s)\n")

results = []
for i, s in enumerate(stickers):
    eid = s.get("custom_emoji_id", "N/A")
    emoji = s.get("emoji", "?")
    print(f"  {i+1}. emoji={emoji}  custom_emoji_id={eid}")
    results.append({"index": i + 1, "emoji": emoji, "custom_emoji_id": eid})

out_path = Path(__file__).resolve().parent / "emoji_ids.json"
out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
print(f"\nSaved to {out_path}")
