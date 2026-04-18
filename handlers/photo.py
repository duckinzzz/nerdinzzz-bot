import asyncio

from aiogram import F, Router
from aiogram.types import Message, PhotoSize

from core.config import BOT_USERNAME
from utils.llm_utils import get_ocr_response
from utils.logging_utils import log_message

photo_router = Router()

album_buffer: dict[str, list[Message]] = {}

MAX_IMAGES_PER_REQUEST = 5
MAX_BASE64_MB = 4
MAX_IMAGE_RESOLUTION_MP = 33


class PhotoValidationError(Exception):
    pass


def get_largest_photo(message: Message) -> PhotoSize:
    if not message.photo:
        raise ValueError("Сообщение не содержит фото")
    return message.photo[-1]


def validate_photo_limits(photo: PhotoSize) -> None:
    errors = []

    if photo.file_size and photo.file_size > MAX_BASE64_MB * 1024 * 1024:
        errors.append(f"размер > {MAX_BASE64_MB} МБ")

    if (photo.width * photo.height) / 1_000_000 > MAX_IMAGE_RESOLUTION_MP:
        errors.append(f"разрешение > {MAX_IMAGE_RESOLUTION_MP} МП")

    if errors:
        raise PhotoValidationError("❌ Изображение превышает лимиты:\n- " + "\n- ".join(errors))


async def send_response(message: Message, text: str) -> None:
    if message.chat.type in ("group", "supergroup"):
        await message.reply(text, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


async def process_single_photo(message: Message, llm_code: str) -> None:
    try:
        photo = get_largest_photo(message)
        validate_photo_limits(photo)
    except PhotoValidationError as e:
        await send_response(message, str(e))
        return

    caption = message.caption or ""
    caption = caption.replace(f"@{BOT_USERNAME}", "").strip()
    response = await get_ocr_response(caption, [photo], llm_code)

    log_message(message=message,
                request_type='process_image',
                amount=1,
                caption=caption,
                ocr_response=response,
                llm_code=llm_code)
    await send_response(message, response)


async def process_album(messages: list[Message], llm_code: str) -> None:
    first_message = messages[0]

    if len(messages) > MAX_IMAGES_PER_REQUEST:
        await send_response(
            first_message,
            f"❌ Пришлите не больше {MAX_IMAGES_PER_REQUEST} изображений"
        )
        return

    for idx, msg in enumerate(messages, 1):
        try:
            photo = get_largest_photo(msg)
            validate_photo_limits(photo)
        except PhotoValidationError as e:
            error_msg = str(e).replace("Изображение", f"Изображение {idx}")
            await send_response(first_message, error_msg)
            return

    caption = first_message.caption or ""
    caption = caption.replace(f"@{BOT_USERNAME}", "").strip()
    photos = [get_largest_photo(msg) for msg in messages]

    response = await get_ocr_response(caption, photos, llm_code)

    log_message(
        message=first_message,
        request_type='process_image',
        amount=len(messages),
        caption=caption,
        ocr_response=response,
        llm_code=llm_code,
    )
    await send_response(first_message, response)


@photo_router.message(F.content_type == "photo")
async def handle_photo(message: Message):
    media_id = message.media_group_id
    is_group = message.chat.type in ("group", "supergroup")
    caption = message.caption or ""

    # Для групповых чатов проверяем упоминание бота
    if is_group:
        if not caption.startswith(f"@{BOT_USERNAME}"):
            # Для альбомов проверяем, был ли уже добавлен media_id (если предыдущее фото имело упоминание)
            if not media_id or media_id not in album_buffer:
                return
        # Если есть упоминание и media_id отсутствует в буфере, инициализируем список
        if media_id and media_id not in album_buffer:
            album_buffer[media_id] = []
    # Для приватных чатов всегда инициализируем буфер для альбомов
    else:
        if media_id and media_id not in album_buffer:
            album_buffer[media_id] = []

    llm_code = "meta-llama/llama-4-scout-17b-16e-instruct"

    # Одиночное фото
    if not media_id:
        await process_single_photo(message, llm_code)
        return

    # Альбом: добавляем сообщение в буфер
    album_buffer[media_id].append(message)
    await asyncio.sleep(0.5)

    # Извлекаем накопленные сообщения (если это последнее фото альбома)
    messages = album_buffer.pop(media_id, None)
    if not messages:
        return

    await process_album(messages, llm_code)
