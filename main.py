import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import ALLOWED_USER_ID, BOT_TOKEN, DAILY_TIME, TIMEZONE
from db import has_daily_message, init_db
from handlers import router, send_day_card
from middleware import AccessMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def daily_job(bot: Bot) -> None:
    """Send daily card if not already sent today."""
    import zoneinfo
    from datetime import datetime

    tz = zoneinfo.ZoneInfo(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")

    if await has_daily_message(today):
        logger.info("Daily card already sent for %s, skipping.", today)
        return

    logger.info("Sending daily card for %s", today)
    await send_day_card(bot, ALLOWED_USER_ID, today)


async def main() -> None:
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    dp.update.outer_middleware(AccessMiddleware())
    dp.include_router(router)

    hour, minute = map(int, DAILY_TIME.split(":"))
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_job,
        trigger=CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
        args=[bot],
    )
    scheduler.start()
    logger.info("Scheduler started: daily card at %s (%s)", DAILY_TIME, TIMEZONE)

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
