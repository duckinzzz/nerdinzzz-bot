import re

from aiogram import F, Router
from aiogram.types import Message, BufferedInputFile, MessageEntity
from groq import RateLimitError
from telegramify_markdown import convert

from core.config import BOT_USERNAME
from core.app import bot
from core.constants import CONTEXT_LIMIT, REPLY_CHUNK_LIMIT
from utils import llm_utils, tti_utils, tts_utils
from utils.db_utils import get_context_messages, save_context_message, trim_context
from utils.logging_utils import log_message, log_error
from utils.text_utils import split_message_with_entities

text_router = Router()


def _is_reply_to_bot(message: Message) -> bool:
    """True if the message replies to a message sent by this bot.

    In groups a reply to the bot's message is treated as addressing the bot,
    so an explicit @username mention is not required.
    """
    reply = message.reply_to_message
    if reply is None or reply.from_user is None or message.bot is None:
        return False
    return reply.from_user.id == message.bot.id


async def process_text_request(message: Message, text: str) -> None:
    """Handle a text request: image/voice generation or LLM reply."""
    chat_id = message.chat.id
    is_group = message.chat.type in ("group", "supergroup")

    async def send_response(
            response_text: str | None = None,
            photo=None,
            voice=None,
            entities=None,
    ) -> Message | None:
        if photo:
            if is_group:
                return await message.reply_photo(photo=photo)
            else:
                return await message.answer_photo(photo=photo)
        elif voice:
            if is_group:
                return await message.reply_voice(voice=voice)
            else:
                return await message.answer_voice(voice=voice)
        else:
            # Telegram rejects messages over 4096 chars, so long replies go out in chunks
            chunks = split_message_with_entities(response_text or "", entities or [], REPLY_CHUNK_LIMIT)
            first = None
            for chunk_text, chunk_entities in chunks:
                if not chunk_text:
                    continue
                built = [MessageEntity(**e) for e in chunk_entities] or None
                if is_group:
                    sent = await message.reply(chunk_text, entities=built)
                else:
                    sent = await message.answer(chunk_text, entities=built)
                if first is None:
                    first = sent
            return first

    async def drop(sent: Message | None) -> None:
        """Delete a service message ("Рисую..."), if it went out."""
        if sent is not None:
            await sent.delete()

    # TEXT TO IMAGE
    if text.lower().startswith("нарисуй"):
        # Send the user's words straight to the image model, no LLM rewriting
        prompt = re.sub(r"^нарисуй\s*", "", text, flags=re.IGNORECASE).strip()
        if not prompt:
            await send_response("❌ Укажите, что нарисовать")
            return

        ans = await send_response('🖌️ Рисую...')
        try:
            image = await tti_utils.generate_image(prompt)
        except tti_utils.ImageFlagged:
            await drop(ans)
            await send_response("🚫 Изображение не прошло цензуру")
            return
        await drop(ans)
        if image:
            log_message(request_type='image_generation', message=message, llm_prompt=prompt)
            await send_response(photo=image)
        else:
            await send_response("❌ Не получилось сгенерировать изображение")
        return

    # TEXT TO SPEECH
    if text.lower().startswith("скажи"):
        prompt = text.lower().replace("скажи", '').strip()
        if not prompt:
            await send_response("❌ Укажите, что сказать")
            return
        if not any(char.isalpha() for char in prompt):
            await send_response("❌ Нужна хотя бы одна буква")
            return
        if len(prompt) > 200:
            await send_response(f"❌ Лимит символов ({len(prompt)}/200)")
            return

        ans = await send_response('🗣 Ща выдам...')
        try:
            voice = await tts_utils.generate_voice(prompt)
            await drop(ans)
            await send_response(voice=BufferedInputFile(voice, 'voice'))
        except RateLimitError as e:
            await drop(ans)
            wait_time = getattr(e, "wait_time", None)
            if wait_time:
                await send_response(f"⏳ Подождите {wait_time}, или попробуйте менее длинное сообщение")
            else:
                await send_response("⏳ Слишком много запросов")
        except Exception as e:
            await drop(ans)
            log_error(request_type='text_to_speech', message=message, error=e)
            await send_response("❌ Не смог выговорить")
        return

    # Regular LLM request
    history = await get_context_messages(chat_id)
    # Keep the user's own words — `formatted` below is the bot's answer
    user_text = text
    llm_response = await llm_utils.get_llm_response(user_text, chat_id=chat_id, history=history)
    formatted, entities = convert(llm_response)
    log_message(request_type='llm_question', message=message, llm_response=llm_response)
    await send_response(formatted, entities=entities)

    # Save the dialog to context, then trim to the limit
    await save_context_message(chat_id, "user", user_text)
    await save_context_message(chat_id, "assistant", llm_response)
    await trim_context(chat_id, keep_users=CONTEXT_LIMIT)



@text_router.message(
    F.content_type == "text",
    F.chat.type.in_(["group", "supergroup"]),
    lambda m: (m.text and m.text.startswith(f"@{BOT_USERNAME}")) or _is_reply_to_bot(m)
)
async def text_group_handler(message: Message):
    text = (message.text or "").replace(f'@{BOT_USERNAME}', '').strip()
    if not text:
        return
    await process_text_request(message, text)


@text_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: Message):
    await process_text_request(message, message.text or "")
