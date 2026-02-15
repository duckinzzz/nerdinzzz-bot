from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner, Message, CallbackQuery

from core.config import ADMIN_ID
from core.constants import LLM_MODELS
from keyboards.set_llm import set_llm_kb
from utils.db_utils import set_chat_llm, get_chat_llm
from utils.logging_utils import log_event

admin_router = Router()


@admin_router.message(Command("set_llm"))
async def set_llm_handler(message: Message, bot: Bot):
    chat_id = message.chat.id

    if message.chat.type in ("group", "supergroup"):
        member = await bot.get_chat_member(chat_id, message.from_user.id)
        if message.from_user.id != ADMIN_ID and not isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            return await message.answer("❌ Вы не админ")

    curr_llm = await get_chat_llm(chat_id)
    return await message.answer("Выберите модель из списка:", reply_markup=set_llm_kb(curr_llm))


@admin_router.callback_query(F.data.startswith("sl:"))
async def set_llm_callback(callback: CallbackQuery, bot: Bot):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    model_code = callback.data.split(":")[1]

    if callback.message.chat.type in ("group", "supergroup"):
        member = await bot.get_chat_member(chat_id, user_id)
        if user_id != ADMIN_ID and not isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            return await callback.answer("❌ Вы не админ")

    if model_code not in LLM_MODELS:
        return await callback.answer("❌ Ошибка: модель не найдена")

    await set_chat_llm(chat_id, model_code)
    model_name = LLM_MODELS[model_code].get('name', model_code)

    log_event(
        event='llm_change_cb',
        chat_id=chat_id,
        model_code=model_code,
        by_user=user_id
    )

    await callback.message.delete()
    return await callback.message.answer(
        f"✅ Установлена модель: *{model_name}*",
        parse_mode="Markdown"
    )
