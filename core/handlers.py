import tempfile

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command

from core.app import bot
from core.config import BOT_USERNAME
from core.constants import LLM_MODELS, SUPPORTED_MSG_TYPES
from utils import llm_utils, stt_utils
from utils.db_utils import get_chat_llm, set_chat_llm
from utils.logging_utils import log_message, logger

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name or user.id}"
    uid = message.from_user.id

    welcome_text = (
        f"🤓 *Nerdinzzz* – ваш умный чат-бот на базе LLM (OpenAI, Qwen, Llama и другие)!\n\n"
        "Он мгновенно отвечает на текстовые сообщения и умеет переводить голосовые в текст.\n\n"
        "Просто напишите сообщение или отправьте голосовое, и бот сразу даст ответ!\n\n"
        "🔗 Добавьте бота, разрешите доступ к сообщениям, и он автоматически:\n"
        "   • Преобразует голосовые сообщения в текст\n"
        f"   • Ответит на вопросы, если упомянуть `@{BOT_USERNAME}`"
    )

    await message.answer(welcome_text, parse_mode="Markdown")
    logger.info(f"User {username} ({uid}) started the bot")


@start_router.message(F.content_type == "voice")
async def voice_handler(message: types.Message):
    voice = message.voice
    file = await bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        await bot.download_file(
            file.file_path,
            destination=tmp.name
        )
        stt_response = await stt_utils.stt(tmp.name)

        log_message(message=message, stt_response=stt_response)
        await message.reply(stt_response)


@start_router.message(F.content_type == "video_note")
async def video_note_handler(message: types.Message):
    video_note = message.video_note
    file = await bot.get_file(video_note.file_id)

    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        await bot.download_file(
            file.file_path,
            destination=tmp.name)
        stt_response = await stt_utils.stt_from_video(tmp.name)

        log_message(message=message, stt_response=stt_response)
        await message.reply(stt_response)


@start_router.message(Command("set_llm"))
async def set_llm_handler(message: types.Message):
    chat_id = message.chat.id
    text = message.text.replace("/set_llm ", "").strip()
    if not text:
        await message.answer("❌ Укажите код модели после /set_llm")
        return

    model_code = text
    if model_code not in LLM_MODELS:
        await message.answer("❌ Такой модели нет")
        return

    if message.chat.type in ("group", "supergroup"):
        member = await bot.get_chat_member(chat_id=chat_id, user_id=message.from_user.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("❌ Только админ может менять модель в группе")
            return

    await set_chat_llm(chat_id, model_code)
    await message.answer(
        f"Модель `{LLM_MODELS[model_code]['name']}` установлена ✅",
        parse_mode="Markdown"
    )
    logger.warning(f"Chat {chat_id}: LLM changed to {model_code} by {message.from_user.id}")


# text + group + mention
@start_router.message(F.content_type == "text",
                      lambda m: m.chat.type in ("group", "supergroup"),
                      lambda m: m.text and m.text.startswith(f"@{BOT_USERNAME} "))
async def text_group_handler(message: types.Message):
    chat_id = message.chat.id
    text = message.text.replace(f'@{BOT_USERNAME} ', '').strip()
    if not text: return

    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)

    log_message(message=message, llm_response=llm_response, llm_code=llm_code)
    await message.reply(llm_response)


@start_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)

    log_message(message=message, llm_response=llm_response, llm_code=llm_code)
    await message.answer(llm_response)


@start_router.message(~F.content_type.in_(SUPPORTED_MSG_TYPES), F.chat.type == "private")
async def unsupported_handler(message: types.Message):
    log_message(message=message)
    await message.answer("❌ Неподдерживаемый формат сообщения")
