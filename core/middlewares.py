import random

from aiogram import BaseMiddleware
from aiogram.types import reaction_type_emoji

from core.constants import REACT_EMOJIS, EMOJIS_WEIGHTS


class LuckyEmojiMiddleware(BaseMiddleware):
    async def __call__(self, handler, message, data):
        if message.chat.type in ["group", "supergroup"] and random.random() < 0.01:
            emoji = random.choices(REACT_EMOJIS, weights=EMOJIS_WEIGHTS, k=1)[0]
            await message.react([reaction_type_emoji.ReactionTypeEmoji(emoji=emoji)])

        return await handler(message, data)
