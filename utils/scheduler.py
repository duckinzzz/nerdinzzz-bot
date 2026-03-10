import asyncio

from aiogram import Bot

from utils.db_utils import cleanup_all_chats
from utils.logging_utils import logger


async def run_daily_cleanup(bot: Bot) -> None:
    """
    Периодическая очистка старых сообщений (каждые 24 часа).
    Оставляет последние MESSAGE_HISTORY_LIMIT сообщений в каждом чате.
    """
    while True:
        await asyncio.sleep(86400)  # 24 часа

        try:
            results = await cleanup_all_chats()
            total_deleted = sum(results.values())
            if total_deleted > 0:
                logger.info(f"Cleanup: deleted {total_deleted} old messages across {len(results)} chats")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
