import tempfile

from aiogram import Router, types, F
from aiogram.filters import CommandStart

from core.bot_core import logger, bot, BOT_USERNAME
from utils import llm_utils, stt_utils
from utils.logging_utils import log_message

start_router = Router()
SUPPORTED_TYPES = ["text", "voice"]


@start_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name or user.id}"
    uid = message.from_user.id

    welcome_text = (
        f"🤓 *Nerdinzzz* – ваш умный чат-бот на базе `{llm_utils.llm_model_name}`!\n\n"
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


# text + group + mention
@start_router.message(F.content_type == "text",
                      lambda m: m.chat.type in ("group", "supergroup"),  # группы
                      lambda m: m.text and m.text.startswith(f"@{BOT_USERNAME} "))
async def text_group_handler(message: types.Message):
    text = message.text.replace(f'@{BOT_USERNAME} ', '').strip()
    if not text: return
    llm_response = await llm_utils.get_llm_response(text)

    log_message(message=message, llm_response=llm_response)
    await message.reply(llm_response, parse_mode="markdown")


@start_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: types.Message):
    text = message.text
    llm_response = await llm_utils.get_llm_response(text)
    log_message(message=message, llm_response=llm_response)
    await message.answer(llm_response, parse_mode="markdown")


@start_router.message(~F.content_type.in_(SUPPORTED_TYPES), F.chat.type == "private")
async def unsupported_handler(message: types.Message):
    log_message(message=message)
    await message.answer("❌ Неподдерживаемый формат сообщения")
