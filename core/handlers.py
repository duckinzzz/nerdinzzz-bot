import tempfile

from aiogram import Router, types, F
from aiogram.filters import CommandStart

from core.bot_core import logger, bot, BOT_USERNAME, ADMIN_ID, dp
from utils import llm_utils, stt_utils
from utils.logging_utils import log_message

start_router = Router()
SUPPORTED_TYPES = ["text", "voice"]
LLM_MODELS = {
    "llama-3.1-8b-instant": {
        "name": "Llama 3.1 8B",
    },
    "llama-3.3-70b-versatile": {
        "name": "Llama 3.3 70B",
    },
    "openai/gpt-oss-120b": {
        "name": "GPT OSS 120B",
    },
    "openai/gpt-oss-20b": {
        "name": "GPT OSS 20B",
    },
    "meta-llama/llama-4-maverick-17b-128e-instruct": {
        "name": "Llama 4 Maverick 17B 128E",
    },
    "meta-llama/llama-4-scout-17b-16e-instruct": {
        "name": "Llama 4 Scout 17B 16E",
    },
    "qwen/qwen3-32b": {
        "name": "Qwen3 32B",
    },
    "moonshotai/kimi-k2-instruct-0905": {
        "name": "Kimi K2 0905",
    },
}


@start_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name or user.id}"
    uid = message.from_user.id

    welcome_text = (
        f"🤓 *Nerdinzzz* – ваш умный чат-бот на базе `{LLM_MODELS[dp['llm']]["name"]}`!\n\n"
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


# text + group + mention
@start_router.message(F.content_type == "text",
                      lambda m: m.chat.type in ("group", "supergroup"),  # группы
                      lambda m: m.text and m.text.startswith(f"@{BOT_USERNAME} "))
async def text_group_handler(message: types.Message):
    text = message.text.replace(f'@{BOT_USERNAME} ', '').strip()
    if not text: return
    llm_response = await llm_utils.get_llm_response(text)

    log_message(message=message, llm_response=llm_response)
    await message.reply(llm_response, parse_mode=None)


@start_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: types.Message):
    text = message.text
    if message.from_user.id == ADMIN_ID and text.startswith(f"/set_llm "):
        log_message(message=message)
        model_code = text.replace("/set_llm ", '').strip()
        if model_code not in LLM_MODELS:
            await message.answer(f'Такой модели нет в наборе❌')
            return
        dp['llm'] = model_code
        await message.answer(f'Модель  `{LLM_MODELS[model_code]["name"]}`  установлена✅', parse_mode="Markdown")
        logger.warning(f"LLM changed to {model_code}")
        return

    llm_response = await llm_utils.get_llm_response(text)
    log_message(message=message, llm_response=llm_response)
    await message.answer(llm_response, parse_mode=None)


@start_router.message(~F.content_type.in_(SUPPORTED_TYPES), F.chat.type == "private")
async def unsupported_handler(message: types.Message):
    log_message(message=message)
    await message.answer("❌ Неподдерживаемый формат сообщения")
