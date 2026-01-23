from textwrap import dedent

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.app import bot
from core.config import ADMIN_ID
from core.constants import LLM_MODELS
from utils.db_utils import set_chat_llm, get_chat_llm
from utils.logging_utils import logger

admin_router = Router()


@admin_router.message(Command("set_llm"))
async def set_llm_handler(message: Message):
    chat_id = message.chat.id
    curr_llm = await get_chat_llm(chat_id)
    text = message.text.replace("/set_llm", "").strip()
    if not text:
        ans = dedent(f"""
        Текущая модель в чате: <code>{curr_llm}</code>
        
        Введите /set_llm [модель]

        <code>openai/gpt-oss-120b</code>
        <code>openai/gpt-oss-20b</code>
        <code>llama-3.1-8b-instant</code>
        <code>llama-3.3-70b-versatile</code>
        <code>qwen/qwen3-32b</code>
        <code>moonshotai/kimi-k2-instruct-0905</code>
        """).strip()

        await message.reply(ans, parse_mode="HTML")

        return

    model_code = text
    if model_code not in LLM_MODELS:
        await message.answer("❌ Такой модели нет")
        return

    if message.chat.type in ("group", "supergroup"):
        member = await bot.get_chat_member(chat_id=chat_id, user_id=message.from_user.id)
        if message.from_user.id != ADMIN_ID and member.status not in ("administrator", "creator"):
            await message.answer("❌ Только админ может менять модель в группе")
            return

    await set_chat_llm(chat_id, model_code)
    await message.answer(
        f"Модель `{LLM_MODELS[model_code]['name']}` установлена ✅",
        parse_mode="Markdown"
    )
    logger.warning(f"Chat {chat_id}: LLM changed to {model_code} by {message.from_user.id}")
