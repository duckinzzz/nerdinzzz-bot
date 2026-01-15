import inspect
import json
import logging
import sys

from aiogram import types

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("./bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bot_core")


def log_message(message: types.Message, **kwargs):
    caller_name = inspect.stack()[1].function

    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name or user.id}"
    chat = message.chat

    data = {
        "handler": caller_name,
        "userID": user.id,
        "username": username,
        "content_type": str(message.content_type).split('.')[-1],
    }
    if message.text:
        data.update({'text': message.text})

    if chat:
        data.update({
            "chatID": chat.id,
            "chat_type": chat.type,
        })

    data.update(kwargs)

    logger.info(json.dumps(data, ensure_ascii=False))
