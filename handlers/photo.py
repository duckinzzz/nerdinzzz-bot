import asyncio
from collections import defaultdict
from typing import Optional

from aiogram import F, Router
from aiogram.types import Message, PhotoSize

from core.config import BOT_USERNAME
from core.constants import LLM_MODELS
from utils.db_utils import get_chat_llm
from utils.llm_utils import get_ocr_response
from utils.logging_utils import log_message

photo_router = Router()

album_buffer: dict[str, Optional[list[Message]]] = defaultdict(list)

MAX_IMAGES_PER_REQUEST = 5
MAX_BASE64_MB = 4
MAX_IMAGE_RESOLUTION_MP = 33


class PhotoValidationError(Exception):
    pass


def validate_photo_limits(photo: PhotoSize) -> None:
    errors = []

    if photo.file_size > MAX_BASE64_MB * 1024 * 1024:
        errors.append(f"размер > {MAX_BASE64_MB} МБ")

    if (photo.width * photo.height) / 1_000_000 > MAX_IMAGE_RESOLUTION_MP:
        errors.append(f"разрешение > {MAX_IMAGE_RESOLUTION_MP} МП")

    if errors:
        raise PhotoValidationError("❌ Изображение превышает лимиты:\n- " + "\n- ".join(errors))


async def send_response(message: Message, text: str) -> None:
    if message.chat.type in ("group", "supergroup"):
        await message.reply(text)
    else:
        await message.answer(text)


async def check_multimodal_support(chat_id: int, message: Message) -> Optional[str]:
    llm_code = await get_chat_llm(chat_id)
    is_multimodal = LLM_MODELS.get(llm_code, {}).get("multimodal", False)

    if not is_multimodal:
        await send_response(
            message,
            "❌ Текущая модель не обрабатывает изображения, выберите другую:\n"
            "`/set_llm meta-llama/llama-4-maverick-17b-128e-instruct`\n"
            "`/set_llm meta-llama/llama-4-scout-17b-16e-instruct`"
        )
        return None

    return llm_code


async def process_single_photo(message: Message, llm_code: str) -> None:
    try:
        validate_photo_limits(message.photo[-1])
    except PhotoValidationError as e:
        await send_response(message, str(e))
        return
    caption = message.caption or ""
    caption = caption.replace(f"@{BOT_USERNAME}", "").strip()
    response = await get_ocr_response(caption, [message.photo[-1]], llm_code)

    log_message(message=message, ocr_response=response, llm_code=llm_code)
    await send_response(message, response)


async def process_album(messages: list[Message], llm_code: str) -> None:
    first_message = messages[0]

    if len(messages) > MAX_IMAGES_PER_REQUEST:
        await send_response(
            first_message,
            f"❌ Пришлите не больше {MAX_IMAGES_PER_REQUEST} изображений"
        )
        return

    try:
        for idx, msg in enumerate(messages, 1):
            validate_photo_limits(msg.photo[-1])
    except PhotoValidationError as e:
        error_msg = str(e).replace("Изображение", f"Изображение {idx}")
        await send_response(first_message, error_msg)
        return
    caption = first_message.caption or ""
    caption = caption.replace(f"@{BOT_USERNAME}", "").strip()
    photos = [msg.photo[-1] for msg in messages]

    response = await get_ocr_response(caption, photos, llm_code)

    log_message(
        message=first_message,
        ocr_response=response,
        llm_code=llm_code,
        album_size=len(messages)
    )
    await send_response(first_message, response)


@photo_router.message(F.content_type == "photo")
async def handle_photo(message: Message):
    chat_id = message.chat.id
    media_id = message.media_group_id
    is_group = message.chat.type in ("group", "supergroup")
    caption = message.caption or ""

    if is_group:
        if not media_id:  # одиночное фото
            if not caption.startswith(f"@{BOT_USERNAME}"):
                return
        else:  # альбом
            # Первое сообщение альбома
            if media_id not in album_buffer:
                if caption.startswith(f"@{BOT_USERNAME}"):
                    album_buffer[media_id] = []
                else:
                    # Помечаем альбом как игнорируемый
                    album_buffer[media_id] = None
                    return

            # Альбом помечен как игнорируемый
            if album_buffer[media_id] is None:
                return

    llm_code = await check_multimodal_support(chat_id, message)
    if not llm_code:
        return

    if not media_id:
        await process_single_photo(message, llm_code)
        return

    album_buffer[media_id].append(message)
    # Ждём остальные фото из альбома
    await asyncio.sleep(0.5)

    messages = album_buffer.pop(media_id, None)
    if not messages:
        return

    await process_album(messages, llm_code)
