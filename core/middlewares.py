import random

from aiogram import BaseMiddleware
from aiogram.types import reaction_type_emoji

from core.constants import EMOJIS_RANDOM_POOL, EMOJIS_WEIGHTS, REACTION_PROB


class LuckyEmojiMiddleware(BaseMiddleware):
    async def __call__(self, handler, message, data):
        if message.chat.type in ["group", "supergroup"] and random.random() < REACTION_PROB:
            emoji = random.choices(EMOJIS_RANDOM_POOL, weights=EMOJIS_WEIGHTS, k=1)[0]
            await message.react([reaction_type_emoji.ReactionTypeEmoji(emoji=emoji)])

        return await handler(message, data)
