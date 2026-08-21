import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
ALLOWED_USER_ID: int = int(os.environ["ALLOWED_USER_ID"])
DAILY_TIME: str = os.getenv("DAILY_TIME", "08:00")
EVENING_TIME: str = os.getenv("EVENING_TIME", "21:00")
WEEK_SUMMARY_TIME: str = os.getenv("WEEK_SUMMARY_TIME", "21:30")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Minsk")

FONT_BOLD = BASE_DIR / "assets" / "fonts" / "Inter-Bold.ttf"
FONT_MEDIUM = BASE_DIR / "assets" / "fonts" / "Inter-Medium.ttf"
FONT_REGULAR = BASE_DIR / "assets" / "fonts" / "Inter-Regular.ttf"

DATABASE_URL: str = os.environ["DATABASE_URL"]
