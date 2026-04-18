from aiogram import F, Router
from aiogram.types import Message, BufferedInputFile
from groq import RateLimitError
from telegramify_markdown import convert

from core.config import BOT_USERNAME
from utils import llm_utils, tti_utils, tts_utils
from utils.db_utils import get_chat_llm
from utils.logging_utils import log_message, log_error

text_router = Router()


async def process_text_request(message: Message, text: str) -> None:
    """Обработка текстового запроса: генерация изображения, голоса или LLM-ответ."""
    chat_id = message.chat.id
    is_group = message.chat.type in ("group", "supergroup")

    # Вспомогательная функция для отправки ответа
    async def send_response(response_text: str = None, photo=None, voice=None, entities=None):
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
            if is_group:
                return await message.reply(response_text, entities=entities)
            else:
                return await message.answer(response_text, entities=entities)

    # TEXT TO IMAGE
    if text.lower().startswith("нарисуй"):
        prompt = text.lower().replace("нарисуй", '').strip()
        if not prompt:
            await send_response("❌ Укажите, что нарисовать")
            return

        ans = await send_response('🖌️ Рисую...')
        llm_prompt = await llm_utils.make_prompt(prompt)
        if not llm_prompt:
            await ans.delete()
            await send_response("❌ Не получилось обработать промпт")
            return

        image = await tti_utils.generate_image(llm_prompt)
        await ans.delete()
        if image:
            log_message(request_type='image_generation', message=message, llm_prompt=llm_prompt)
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
            await ans.delete()
            await send_response(voice=BufferedInputFile(voice, 'voice'))
        except RateLimitError as e:
            await ans.delete()
            wait_time = getattr(e, "wait_time", None)
            if wait_time:
                await send_response(f"⏳ Подождите {wait_time}, или попробуйте менее длинное сообщение")
            else:
                await send_response("⏳ Слишком много запросов")
        except Exception as e:
            await ans.delete()
            log_error(request_type='text_to_speech', message=message, error=e)
            await send_response("❌ Не смог выговорить")
        return

    # Обычный LLM запрос
    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)
    text, entities = convert(llm_response)
    log_message(request_type='llm_question', message=message, llm_response=llm_response, llm_code=llm_code)
    await send_response(text, entities=[e.to_dict() for e in entities])



@text_router.message(
    F.content_type == "text",
    F.chat.type.in_(["group", "supergroup"]),
    lambda m: m.text and m.text.startswith(f"@{BOT_USERNAME}")
)
async def text_group_handler(message: Message):
    text = message.text.replace(f'@{BOT_USERNAME}', '').strip()
    if not text:
        return
    await process_text_request(message, text)


@text_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: Message):
    await process_text_request(message, message.text)
