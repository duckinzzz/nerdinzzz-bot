import base64
import tempfile

from aiogram import types
from groq import AsyncGroq, APIStatusError

from core.app import bot
from core.config import LLM_TOKEN
from core.constants import LLM_MODELS
from utils.logging_utils import log_error

client = AsyncGroq(api_key=LLM_TOKEN)


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
        content = completion.choices[0].message.content.strip()

        if not content:
            log_error(request_type='process_image', caption=caption, error='empty_response')
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте другое изображение."

        return content.strip()

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='process_image', caption=caption, error=e)
            return "❌ Сообщение слишком длинное, попробуйте сменить модель, или укоротить сообщение"
        log_error(request_type='process_image', caption=caption, error=e)
        return f"❌ Ошибка при обработке изображения"
    except Exception as e:
        log_error(request_type='process_image', caption=caption, error=e)
        return f"❌ Ошибка при обработке изображения"


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
        content = completion.choices[0].message.content.strip()

        if not content:
            log_error(request_type='llm_question', user_prompt=user_prompt, error='empty_response')
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте переформулировать вопрос или сменить модель."

        return content.strip()

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
            return "❌ Сообщение слишком длинное, попробуйте сменить модель, или укоротить сообщение"
        log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
        return f"❌ Ошибка при обработке запроса"
    except Exception as e:
        log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
        return f"❌ Ошибка при обработке запроса"


async def make_prompt(user_prompt: str) -> str:
    llm_code = 'openai/gpt-oss-120b'

    system_prompt = f"""
        Rewrite user input into image generation prompt.
        No violence. More realistic style if not specified. 
        Just transform user input to text-to-image prompt.
        Return only the prompt.
        ENGLISH ONLY
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
        "max_completion_tokens": 4096,
        "top_p": 1,
        "stream": False,
        "stop": None
    }

    try:
        completion = await client.chat.completions.create(**kwargs)
        prompt = completion.choices[0].message.content.strip()

        if not prompt:
            log_error(request_type='image_generation', user_prompt=user_prompt, error="generated_empty_prompt")
            return ''
        if 'I can’t help with'.lower() in prompt.lower():
            log_error(request_type='image_generation', user_prompt=user_prompt, error="prompt_restricted")
            return ''
        return prompt

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='image_generation', user_prompt=user_prompt, error=e)
            # Возвращаем пустую строку, вызывающий код должен обработать ошибку
        log_error(request_type='image_generation', user_prompt=user_prompt, error=e)
        return ''
    except Exception as e:
        log_error(request_type='image_generation', user_prompt=user_prompt, error=e)
        return ''


async def generate_summary(messages_json: list[dict], chat_id: int, total_count: int, bot_username: str) -> str:
    """
    Генерирует саммари по сообщениям чата.

    messages_json: список словарей вида {username, text, message_id}
    chat_id: ID чата
    total_count: количество сообщений
    bot_username: юзернейм бота (для фильтрации его ответов)

    Возвращает саммари в формате:
    🤓 AI проанализировал N сообщений.
    Вот что вы пропустили:
    [Темы с описанием]
    """
    from core.constants import SUMMARY_MODEL, SUMMARY_PROMPT

    system_prompt = SUMMARY_PROMPT

    # Формируем контекст из сообщений, исключая ответы бота
    messages_text = []
    for msg in messages_json:
        username = msg.get('username') or f"user_{msg['user_id']}"
        if not username.startswith('@'):
            username = f"@{username}"

        # Пропускаем сообщения от бота (но оставляем запросы к нему)
        if username.lower() == f"@{bot_username}".lower():
            continue

        text = msg.get('text', '')
        messages_text.append(f"{username}: {text}")

    context = "\n".join(messages_text)

    user_prompt = f"""Количество сообщений (без ответов бота): {total_count}

Сообщения:
{context}

Сделай саммари на русском языке."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    kwargs = {
        "model": SUMMARY_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_completion_tokens": 8192,
        "top_p": 1,
        "stream": False,
    }

    try:
        completion = await client.chat.completions.create(**kwargs)
        summary = completion.choices[0].message.content.strip()

        if not summary:
            log_error(request_type='summary', chat_id=chat_id, error='empty_response')
            return "❌ Не удалось сгенерировать саммари. Попробуйте позже."

        # Формируем заголовок
        header = f"🤓 Я проанализировал {total_count} сообщений.\nВот что вы пропустили:\n\n"
        return header + summary

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='summary', chat_id=chat_id, error=e)
            return "❌ Сообщение слишком длинное, попробуйте сменить модель, или укоротить сообщение"
        log_error(request_type='summary', chat_id=chat_id, error=e)
        return f"❌ Ошибка при генерации саммари"
    except Exception as e:
        log_error(request_type='summary', chat_id=chat_id, error=e)
        return "❌ Ошибка при генерации саммари"
