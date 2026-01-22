from aiogram import F, Router
from aiogram.types import Message

from core.constants import SUPPORTED_MSG_TYPES
from utils.logging_utils import log_message

unsupported_router = Router()


@unsupported_router.message(
    ~F.content_type.in_(SUPPORTED_MSG_TYPES),
    F.chat.type == "private"
)
async def unsupported_handler(message: Message):
    log_message(message=message)
    await message.answer("❌ Неподдерживаемый формат сообщения")
