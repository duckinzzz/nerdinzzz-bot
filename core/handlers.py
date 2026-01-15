import json

from aiogram import Router, types, F
from aiogram.filters import CommandStart

from core.bot_core import logger
from utils import llm_utils
from utils.llm_utils import get_llm_response

start_router = Router()
SUPPORTED_TYPES = ["text"]


def get_user_name(user: types.User):
    if user.username:
        return f"@{user.username}"
    else:
        return f"{user.first_name or user.id}"


@start_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user_name = get_user_name(message.from_user)
    uid = message.from_user.id

    welcome_text = (
        f"Nerdinzzz 🤓 – LLM чат-бот на базе {llm_utils.llm_model_name}."
        f"\nПросто спросите!"
    )

    await message.answer(welcome_text)
    logger.info(f"User {user_name} ({uid}) started the bot")


@start_router.message(F.content_type == "text")
async def text_handler(message: types.Message):
    user_name = get_user_name(message.from_user)
    text = message.text
    llm_response = await get_llm_response(text)
    clean_response = formatting.escape_md(llm_response)
    log_data = {
        "userID": message.from_user.id,
        "username": user_name,
        "text": text,
        "response": llm_response,
        "clean_response": clean_response
    }
    logger.info(json.dumps(log_data, ensure_ascii=False))

    await message.answer(clean_response, parse_mode="markdown")


@start_router.message(~F.content_type.in_(SUPPORTED_TYPES))
async def unsupported_handler(message: types.Message):
    await message.answer("❌ Неподдерживаемый формат сообщения")
