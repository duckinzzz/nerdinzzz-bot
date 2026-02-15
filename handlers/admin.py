from aiogram import Router, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import ChatMemberAdministrator, ChatMemberOwner
from aiogram.types import Message

from core.config import ADMIN_ID
from core.constants import LLM_MODELS
from utils.db_utils import set_chat_llm, get_chat_llm
from utils.logging_utils import log_event

admin_router = Router()


@admin_router.message(Command("set_llm"))
async def set_llm_handler(message: Message, command: CommandObject, bot: Bot):
    chat_id = message.chat.id

    if not command.args:
        curr_llm = await get_chat_llm(chat_id)
        models_list = "\n".join([f"<code>{code}</code>" for code in LLM_MODELS.keys()])

        ans = (
            f"Текущая модель: <code>{curr_llm}</code>\n\n"
            f"Введите <code>/set_llm [модель]</code>\n\n"
            f"{models_list}"
        )
        return await message.reply(ans, parse_mode="HTML")

    model_code = command.args.strip()
    if model_code not in LLM_MODELS:
        return await message.reply("❌ Такой модели нет в списке доступных")

    if message.chat.type in ("group", "supergroup"):
        member = await bot.get_chat_member(chat_id, message.from_user.id)
        if message.from_user.id != ADMIN_ID and not isinstance(member, (ChatMemberAdministrator, ChatMemberOwner)):
            return await message.answer("❌ Только админ может менять модель в группе")

    await set_chat_llm(chat_id, model_code)

    model_name = LLM_MODELS[model_code].get('name', model_code)

    log_event(
        event='llm_change',
        chat_id=chat_id,
        model_code=model_code,
        by_user=message.from_user.id
    )
    return await message.answer(f"✅ Установлена модель: *{model_name}*", parse_mode="Markdown")
