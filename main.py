import asyncio
import logging
import zoneinfo
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from clients_db import init_clients_db
from clients_handlers import clients_router
from config import (
    ALLOWED_USER_ID,
    BOT_TOKEN,
    DAILY_TIME,
    EVENING_TIME,
    TIMEZONE,
    WEEK_SUMMARY_TIME,
)
from db import (
    ensure_day_rows,
    get_day_habits,
    get_day_state,
    has_daily_message,
    init_db,
    is_day_skipped,
)
from econ_db import init_econ_db
from econ_handlers import econ_router
from handlers import router, send_day_card
from middleware import AccessMiddleware
from render import HABIT_LABEL
from stats import compute_week_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _today() -> str:
    return datetime.now(zoneinfo.ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")


async def daily_job(bot: Bot) -> None:
    """Send the morning card if it has not gone out yet."""
    today = _today()
    if await has_daily_message(today):
        logger.info("Daily card already sent for %s, skipping.", today)
        return

    logger.info("Sending daily card for %s", today)
    await send_day_card(bot, ALLOWED_USER_ID, today)


async def evening_job(bot: Bot) -> None:
    """Nudge about whatever is still open, unless the day was skipped."""
    today = _today()
    if await is_day_skipped(today):
        return

    await ensure_day_rows(today)
    habits = await get_day_habits(today)
    state = await get_day_state(today)
    left = [h for h in habits if not state.get(h["key"], False)]
    if not left:
        return

    names = ", ".join(HABIT_LABEL.get(h["key"], h["name"]) for h in left)
    await bot.send_message(
        ALLOWED_USER_ID,
        f"⏰ Осталось {len(left)} из {len(habits)}: {names}",
    )


async def week_summary_job(bot: Bot) -> None:
    """Sunday wrap-up for the week that is ending."""
    if datetime.now(zoneinfo.ZoneInfo(TIMEZONE)).weekday() != 6:
        return

    s = await compute_week_summary()
    if not s["total"]:
        return

    lines = [
        f"<b>Итог недели</b> {s['start'].strftime('%d.%m')}–{s['end'].strftime('%d.%m')}",
        f"Закрыто {s['done']} из {s['total']} — {s['pct']}%",
    ]
    if s["weakest"]:
        w = s["weakest"]
        lines.append(f"Просело: {w['name']} — {w['done']}/{w['total']}")
    lines.append(f"Тем по экономике всего: {s['topics']}")
    if s["skipped"]:
        lines.append(f"Пропущенных дней: {s['skipped']}")

    await bot.send_message(ALLOWED_USER_ID, "\n".join(lines))


async def main() -> None:
    await init_db()
    await init_clients_db()
    await init_econ_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    dp.update.outer_middleware(AccessMiddleware())
    # Order matters: the habit router owns the reply-keyboard buttons it handles,
    # so an unfinished input flow in a later router cannot swallow them.
    dp.include_router(router)
    dp.include_router(clients_router)
    dp.include_router(econ_router)

    scheduler = AsyncIOScheduler()
    for time_str, job in (
        (DAILY_TIME, daily_job),
        (EVENING_TIME, evening_job),
        (WEEK_SUMMARY_TIME, week_summary_job),
    ):
        hour, minute = map(int, time_str.split(":"))
        scheduler.add_job(
            job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
            args=[bot],
        )
    scheduler.start()
    logger.info(
        "Scheduler started: card %s, reminder %s, weekly %s (%s)",
        DAILY_TIME, EVENING_TIME, WEEK_SUMMARY_TIME, TIMEZONE,
    )

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
