import asyncio
import tempfile
from collections import defaultdict

from aiogram import F, types
from aiogram import Router
from aiogram.filters import CommandStart, Command

from core.app import bot
from core.config import BOT_USERNAME, ADMIN_ID
from core.constants import LLM_MODELS, SUPPORTED_MSG_TYPES
from utils import llm_utils, stt_utils
from utils.db_utils import get_chat_llm, set_chat_llm
from utils.llm_utils import get_ocr_response
from utils.logging_utils import log_message, logger

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    username = f"@{user.username}" if user.username else f"{user.first_name or user.id}"
    uid = message.from_user.id

    welcome_text = (
        f"🤓 *Nerdinzzz* – ваш умный чат-бот на базе LLM (OpenAI, Qwen, Llama и другие)!\n\n"
        "Он мгновенно отвечает на текстовые сообщения и умеет переводить голосовые в текст.\n\n"
        "Просто напишите сообщение или отправьте голосовое, и бот сразу даст ответ!\n\n"
        "🔗 Добавьте бота, разрешите доступ к сообщениям, и он автоматически:\n"
        "   • Преобразует голосовые сообщения в текст\n"
        f"   • Ответит на вопросы, если упомянуть `@{BOT_USERNAME}`"
    )

    await message.answer(welcome_text, parse_mode="Markdown")
    logger.info(f"User {username} ({uid}) started the bot")


# Буфер для альбомов
album_buffer: dict[str, list[types.Message]] = defaultdict(list)

# Пример лимитов Groq
MAX_IMAGES_PER_REQUEST = 5
MAX_BASE64_MB = 4
MAX_IMAGE_RESOLUTION_MP = 33  # мегапиксели


def check_image_limits(message: types.Message) -> list[str]:
    """Возвращает список ошибок по лимитам изображения"""
    errors = []

    # Размер файла в МБ
    if message.photo[-1].file_size > MAX_BASE64_MB * 1024 * 1024:
        errors.append(f"размер > {MAX_BASE64_MB} МБ")

    # Разрешение в мегапикселях
    width = message.photo[-1].width
    height = message.photo[-1].height
    if (width * height) / 1_000_000 > MAX_IMAGE_RESOLUTION_MP:
        errors.append(f"разрешение > {MAX_IMAGE_RESOLUTION_MP} МП")

    return errors


@start_router.message(F.content_type == types.ContentType.PHOTO)
async def handle_photo(message: types.Message):
    chat = message.chat
    chat_id = chat.id
    is_group = chat.type in ("group", "supergroup")

    media_id = message.media_group_id

    # ---------- GROUP / SUPERGROUP ----------
    if is_group:
        # одиночное фото
        if not media_id:
            if not (message.caption and message.caption.startswith(f"@{BOT_USERNAME}")):
                return

        # альбом
        else:
            # если это первое сообщение альбома — принимаем решение
            if media_id not in album_buffer:
                if not (message.caption and message.caption.startswith(f"@{BOT_USERNAME}")):
                    # помечаем альбом как запрещённый
                    album_buffer[media_id] = None
                    return

                album_buffer[media_id] = []

            # если альбом ранее помечен как запрещённый
            if album_buffer.get(media_id) is None:
                return

    # ---------- PRIVATE ----------
    # в личке всегда разрешено

    # ---------- проверяем модель ----------
    llm_code = await get_chat_llm(chat_id)
    is_multimodal = LLM_MODELS.get(llm_code, {}).get("multimodal", False)
    if not is_multimodal:
        await message.answer(
            "❌ Текущая модель не обрабатывает изображения, выберите другую:\n"
            "`/set_llm meta-llama/llama-4-maverick-17b-128e-instruct`\n"
            "`/set_llm meta-llama/llama-4-scout-17b-16e-instruct`",
            parse_mode="Markdown"
        )
        return

    # ---------- одиночное фото ----------
    if not media_id:
        errors = check_image_limits(message)
        if errors:
            await message.answer(
                "❌ Изображение превышает лимиты:\n- " + "\n- ".join(errors)
            )
            return

        caption = message.caption.replace(f"@{BOT_USERNAME}", '') or ""
        response = await get_ocr_response(
            caption,
            [message.photo[-1]],
            llm_code
        )
        await message.answer(str(response))
        return

    # ---------- альбом ----------
    album_buffer[media_id].append(message)

    await asyncio.sleep(0.5)

    messages = album_buffer.pop(media_id, None)
    if not messages:
        return

    # лимит фото
    if len(messages) > MAX_IMAGES_PER_REQUEST:
        await message.answer(
            f"❌ Пришлите не больше {MAX_IMAGES_PER_REQUEST} изображений"
        )
        return

    # лимиты по каждому изображению
    for idx, msg in enumerate(messages, 1):
        errors = check_image_limits(msg)
        if errors:
            await message.answer(
                f"❌ Изображение {idx} превышает лимиты:\n- " + "\n- ".join(errors)
            )
            return

    caption = messages[0].caption.replace(f"@{BOT_USERNAME}", '').strip() or ""
    photos = [msg.photo[-1] for msg in messages]

    response = await get_ocr_response(caption, photos, llm_code)
    await message.answer(response)


@start_router.message(F.content_type == "voice")
async def voice_handler(message: types.Message):
    voice = message.voice
    file = await bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        await bot.download_file(
            file.file_path,
            destination=tmp.name
        )
        stt_response = await stt_utils.stt(tmp.name)

        log_message(message=message, stt_response=stt_response)
        await message.reply(stt_response)


@start_router.message(F.content_type == "video_note")
async def video_note_handler(message: types.Message):
    video_note = message.video_note
    file = await bot.get_file(video_note.file_id)

    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        await bot.download_file(
            file.file_path,
            destination=tmp.name)
        stt_response = await stt_utils.stt_from_video(tmp.name)

        log_message(message=message, stt_response=stt_response)
        await message.reply(stt_response)


@start_router.message(Command("set_llm"))
async def set_llm_handler(message: types.Message):
    chat_id = message.chat.id
    text = message.text.replace("/set_llm ", "").strip()
    if not text:
        await message.answer("❌ Укажите код модели после /set_llm")
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


# text + group + mention
@start_router.message(F.content_type == "text",
                      lambda m: m.chat.type in ("group", "supergroup"),
                      lambda m: m.text and m.text.startswith(f"@{BOT_USERNAME} "))
async def text_group_handler(message: types.Message):
    chat_id = message.chat.id
    text = message.text.replace(f'@{BOT_USERNAME} ', '').strip()
    if not text: return

    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)

    log_message(message=message, llm_response=llm_response, llm_code=llm_code)
    await message.reply(llm_response)


@start_router.message(F.content_type == "text", F.chat.type == "private")
async def text_private_handler(message: types.Message):
    text = message.text
    chat_id = message.chat.id

    llm_code = await get_chat_llm(chat_id)
    llm_response = await llm_utils.get_llm_response(text, llm_code)

    log_message(message=message, llm_response=llm_response, llm_code=llm_code)
    await message.answer(llm_response)


@start_router.message(~F.content_type.in_(SUPPORTED_MSG_TYPES), F.chat.type == "private")
async def unsupported_handler(message: types.Message):
    log_message(message=message)
    await message.answer("❌ Неподдерживаемый формат сообщения")
