from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from core.config import BOT_USERNAME
from utils.db_utils import get_last_messages
from utils.llm_utils import generate_summary
from utils.logging_utils import log_message, log_error

summary_router = Router()


@summary_router.message(Command("summary"))
async def summary_handler(message: Message, bot: Bot):
    """
    Обработчик команды /summary.
    Получает последние сообщения из чата и генерирует саммари.
    """
    chat_id = message.chat.id

    if message.chat.type not in ("group", "supergroup"):
        return await message.answer(
            "❌ Команда /summary доступна только в групповых чатах"
        )

    status_msg = await message.reply("⏳ Анализирую историю чата...")

    try:
        messages = await get_last_messages(chat_id)

        if len(messages) < 2:
            await status_msg.delete()
            await message.reply(
                "❌ Недостаточно сообщений для саммари.\n"
                f"Найдено всего: {len(messages)}"
            )
            return

        messages_json = [
            {
                "message_id": msg.message_id,
                "user_id": msg.user_id,
                "username": msg.username,
                "text": msg.text
            }
            for msg in messages
        ]

        summary = await generate_summary(
            messages_json=messages_json,
            chat_id=chat_id,
            total_count=len(messages),
            bot_username=BOT_USERNAME
        )

        await status_msg.delete()
        log_message(
            request_type='summary',
            message=message,
            messages_count=len(messages),
            chat_id=chat_id
        )
        await message.reply(summary)

    except Exception as e:
        await status_msg.delete()
        log_error(request_type='summary', message=message, error=e, chat_id=chat_id)
        await message.reply("❌ Ошибка при генерации саммари. Попробуйте позже.")
