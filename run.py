import asyncio
import os

from core.bot_core import bot, dp, logger
from core.handlers import start_router


async def announce_start():
    logger.info(f"Bot started in {os.getenv('ENV', 'unknown')} mode")


async def main():
    dp.include_router(start_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await announce_start()

    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
