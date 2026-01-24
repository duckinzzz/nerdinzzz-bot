from aiogram import F, Router
from aiogram.types import Message

from core.config import BOT_USERNAME
from utils import llm_utils, tti_utils
from utils.db_utils import get_chat_llm
from utils.logging_utils import log_message

text_router = Router()


@text_router.message(
    F.content_type == "text",
    F.chat.type.in_(["group", "supergroup"]),
    lambda m: m.text and m.text.startswith(f"@{BOT_USERNAME} ")
)
async def text_group_handler(message: Message):
    chat_id = message.chat.id
    text = message.text.replace(f'@{BOT_USERNAME} ', '').strip()

    if not text:
        return

    if text.lower().startswith("нарисуй"):
        prompt = text.lower().replace("нарисуй", '').strip()

        if not prompt:
            await message.reply("❌ Укажите, что нарисовать")
            return

        ans = await message.reply('🖌️ Рисую...')
        llm_prompt = await llm_utils.make_prompt(prompt)
        if not llm_prompt:
            await message.reply("❌ Не получилось обработать промпт")
            return
        image = await tti_utils.generate_image(llm_prompt)
        await ans.delete()

        if image:
            log_message(request_type='image_generation', message=message, llm_prompt=llm_prompt)
            await message.reply_photo(photo=image)
        else:
            await message.reply("❌ Не получилось сгенерировать изображение")
        return

    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)

    log_message(request_type='llm_question', message=message, llm_response=llm_response, llm_code=llm_code)
    await message.reply(llm_response)


@text_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: Message):
    text = message.text
    chat_id = message.chat.id

    if text.lower().startswith("нарисуй"):
        prompt = text.lower().replace("нарисуй", '').strip()

        if not prompt:
            await message.answer("❌ Укажите, что нарисовать")
            return

        ans = await message.answer('🖌️ Рисую...')
        llm_prompt = await llm_utils.make_prompt(prompt)
        if not llm_prompt:
            await message.answer("❌ Не получилось обработать промпт")
            return

        image = await tti_utils.generate_image(llm_prompt)
        await ans.delete()

        if image:
            log_message(request_type='image_generation', message=message, llm_prompt=llm_prompt)
            await message.answer_photo(photo=image)
        else:
            await message.answer("❌ Не получилось сгенерировать изображение")

        return

    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)

    log_message(request_type='llm_question', message=message, llm_response=llm_response, llm_code=llm_code)
    await message.answer(llm_response)
