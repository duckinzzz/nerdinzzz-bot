import random
from typing import Callable, Dict, Any

from aiogram import BaseMiddleware
from aiogram.types import Message, reaction_type_emoji

from core.constants import EMOJIS_RANDOM_POOL, EMOJIS_WEIGHTS, REACTION_PROB
from utils.db_utils import save_message
from utils.logging_utils import logger


class LuckyEmojiMiddleware(BaseMiddleware):
    async def __call__(self, handler, message, data):
        if message.chat.type in ["group", "supergroup"] and random.random() < REACTION_PROB:
            emoji = random.choices(EMOJIS_RANDOM_POOL, weights=EMOJIS_WEIGHTS, k=1)[0]
            await message.react([reaction_type_emoji.ReactionTypeEmoji(emoji=emoji)])

        return await handler(message, data)


class MessageHistoryMiddleware(BaseMiddleware):
    """Сохраняет все сообщения в БД для истории чата"""

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Any],
            message: Message,
            data: Dict[str, Any]
    ) -> Any:
        # Сохраняем сообщение в БД
        try:
            await save_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
                user_id=message.from_user.id if message.from_user else 0,
                username=message.from_user.username if message.from_user else None,
                text=message.text or message.caption or ""
            )
        except Exception as e:
            logger.error(f"Failed to save message to history: {e}")

        return await handler(message, data)
