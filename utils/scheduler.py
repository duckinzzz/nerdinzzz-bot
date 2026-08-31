import asyncio

from aiogram import Bot

from utils.db_utils import cleanup_all_chats
from utils.logging_utils import logger


async def run_daily_cleanup(bot: Bot) -> None:
    """Trim old messages in every chat every 24 hours."""
    while True:
        await asyncio.sleep(86400)  # 24 hours

        try:
            results = await cleanup_all_chats()
            total_deleted = sum(results.values())
            if total_deleted > 0:
                logger.info(f"Cleanup: deleted {total_deleted} old messages across {len(results)} chats")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
