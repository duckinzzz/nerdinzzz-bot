import base64
import re
import tempfile

from aiogram import types
from groq import AsyncGroq

from core.app import bot
from core.config import LLM_TOKEN
from core.constants import LLM_MODELS
from utils.logging_utils import logger

client = AsyncGroq(api_key=LLM_TOKEN)


def remove_reasoning_tags(text: str) -> str:
    """
    Удаляет reasoning теги из ответа модели.
    Reasoning обычно обернут в <think>...</think> или <reasoning>...</reasoning>
    """
    # Удаляем <think>...</think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Удаляем <reasoning>...</reasoning>
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL)
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\n\n+', '\n\n', text)
    return text.strip()


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


async def download_photo_to_base64(bot, photo: types.PhotoSize) -> str:
    """
    Скачивает фото из Telegram и возвращает base64 строку
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, tmp.name)
        tmp.flush()
        return encode_image(tmp.name)


async def get_ocr_response(caption: str, photos: list[types.PhotoSize], llm_code: str) -> str:
    """
    caption: текстовое описание / подпись
    photos: список объектов types.PhotoSize из Telegram
    llm_code: ключ из LLM_MODELS
    """
    llm = LLM_MODELS[llm_code]

    system_prompt = f"""
    Ты — Nerdinzzz 🤓, LLM чат-бот на базе {llm['name']}.
    Твой создатель — @duckinzzz.
    Твоя задача:
    - Быстро и точно распознавать содержимое изображений.
    - Преобразовывать текст с фото в текст (OCR) или давать краткий комментарий по изображению.
    - Отвечать кратко, ясно и по делу, максимум 3-4 предложения.
    - Если нужен список — только ключевые пункты.
    - Используй нумерацию или маркеры для структурированных ответов, если необходимо.
    - Не задавай встречных вопросов.
    - Не объясняй свои действия и не добавляй приветствия или прощания.
    - Всегда придерживайся нейтрального и дружелюбного тона.
    - Не экранируй символы, кавычки или специальные знаки — выводи текст «как есть».
    """

    # Кодируем все фото в base64
    encoded_photos = []
    for photo in photos:
        b64 = await download_photo_to_base64(bot, photo)
        encoded_photos.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })

    user_content = [{"type": "text", "text": caption}] + encoded_photos

    messages = [
        {"role": "system", "content": system_prompt.lower()},
        {"role": "user", "content": user_content}
    ]

    kwargs = {
        "model": llm_code,
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 4096,  # Увеличено для reasoning моделей
        "top_p": 1,
        "stream": False,
        "stop": None,
    }

    # Настройка reasoning для разных моделей
    if llm.get('reasoning'):
        # Для GPT-OSS моделей: используем low effort + показываем reasoning
        if llm_code.startswith('openai/gpt-oss'):
            kwargs["reasoning_effort"] = "low"  # минимальное рассуждение
            # НЕ используем include_reasoning=False, т.к. это всё равно не отключает генерацию
            # Вместо этого показываем reasoning пользователю
        # Для Qwen моделей: можно полностью отключить
        elif llm_code.startswith('qwen/'):
            kwargs["reasoning_effort"] = "none"

    try:
        completion = await client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content

        if not content or not content.strip():
            logger.error(
                f"LLM {llm_code} returned empty content. "
                f"Caption: {caption[:100]}"
            )
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте другое изображение или модель."

        return content.strip()

    except Exception as e:
        logger.error(f"Error in get_ocr_response: {e}")
        return f"❌ Ошибка при обработке изображения: {str(e)}"


async def get_llm_response(user_prompt: str, llm_code: str) -> str:
    llm = LLM_MODELS[llm_code]

    system_prompt = f"""
    Ты — Nerdinzzz 🤓, LLM чат-бот на базе {llm['name']}.
    Твой создатель — @duckinzzz.
    Твоя задача:
    - Быстро и точно отвечать на текстовые сообщения.
    - Преобразовывать голосовые сообщения в текст (если требуется).
    - Отвечать кратко, ясно и по делу, максимум 3-4 предложения.
    - Если нужен список — только ключевые пункты.
    - Используй нумерацию или маркеры для структурированных ответов, если необходимо.
    - Не задавай встречных вопросов.
    - Не объясняй свои действия и не добавляй приветствия или прощания.
    - Всегда придерживайся нейтрального и дружелюбного тона.
    - Не экранируй символы, кавычки или специальные знаки — выводи текст «как есть».
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt.lower()
        },
        {"role": "user", "content": user_prompt}
    ]

    kwargs = {
        "model": llm_code,
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 4096,  # Увеличено для reasoning моделей
        "top_p": 1,
        "stream": False,
        "stop": None,
    }

    # Настройка reasoning для разных моделей
    if llm.get('reasoning'):
        # Для GPT-OSS моделей: используем low effort + показываем reasoning
        if llm_code.startswith('openai/gpt-oss'):
            kwargs["reasoning_effort"] = "low"  # минимальное рассуждение
            # НЕ используем include_reasoning=False, т.к. это всё равно не отключает генерацию
            # Вместо этого показываем reasoning пользователю
        # Для Qwen моделей: можно полностью отключить
        elif llm_code.startswith('qwen/'):
            kwargs["reasoning_effort"] = "none"

    try:
        completion = await client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content

        if not content or not content.strip():
            logger.error(
                f"LLM {llm_code} returned empty content. "
                f"Prompt: {user_prompt[:100]}"
            )
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте переформулировать вопрос или сменить модель."

        return content.strip()

    except Exception as e:
        logger.error(f"Error in get_llm_response: {e}")
        return f"❌ Ошибка при обработке запроса: {str(e)}"
