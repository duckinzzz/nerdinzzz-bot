"""Shared helpers for message handlers.

Import with: from handlers.helpers import reply_or_answer
"""

from typing import Any

from aiogram.types import BufferedInputFile, InputFile, Message, MessageEntity


async def reply_or_answer(
    message: Message,
    text: str | None = None,
    *,
    photo: BufferedInputFile | InputFile | None = None,
    voice: BufferedInputFile | InputFile | None = None,
    entities: list[MessageEntity] | None = None,
    parse_mode: str | None = None,
) -> Any:
    """Send a response to the user — reply in groups, answer in private chats."""
    is_group = message.chat.type in ("group", "supergroup")

    if photo:
        return await (message.reply_photo(photo=photo) if is_group else message.answer_photo(photo=photo))
    if voice:
        return await (message.reply_voice(voice=voice) if is_group else message.answer_voice(voice=voice))
    if text:
        return await (message.reply(text, entities=entities, parse_mode=parse_mode) if is_group
                      else message.answer(text, entities=entities, parse_mode=parse_mode))
    return None
