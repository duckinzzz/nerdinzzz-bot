from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from core.config import BOT_USERNAME
from utils.logging_utils import logger

base_router = Router()


@base_router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name or user.id}"
    uid = message.from_user.id

    welcome_text = (
        f"🤓 *Nerdinzzz* – ваш умный чат-бот на базе LLM (OpenAI, Qwen, Llama и другие)!\n\n"
        "Он мгновенно отвечает на текстовые сообщения и умеет переводить голосовые в текст.\n\n"
        "Просто напишите сообщение или отправьте голосовое, и бот сразу даст ответ!\n\n"
        "🔗 Добавьте бота, разрешите доступ к сообщениям, и он автоматически:\n"
        "   • Преобразует голосовые сообщения в текст\n"
        f"   • Ответит на вопросы, если упомянуть `@{BOT_USERNAME}`\n\n"
        f"Чтобы сменить модель, воспользуйтесь командой `/set_llm`"
    )

    await message.answer(welcome_text, parse_mode="Markdown")
    logger.info(f"User {username} ({uid}) started the bot")
