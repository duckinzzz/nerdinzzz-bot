import base64
import re
import tempfile

from aiogram import types
from groq import AsyncGroq, APIStatusError as GroqAPIStatusError
from openai import AsyncOpenAI, APIStatusError

from core.app import bot
from core.config import LLM_TOKEN, STT_TOKEN
from core.constants import LLM_MODEL
from utils.logging_utils import log_error

# DeepSeek — text generation
client = AsyncOpenAI(
    api_key=LLM_TOKEN,
    base_url="https://api.deepseek.com",
)

# Groq — vision/OCR (DeepSeek V4 Flash doesn't support images)
groq_client = AsyncGroq(api_key=STT_TOKEN)
OCR_MODEL = "qwen/qwen3.6-27b"


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


async def download_photo_to_base64(bot, photo: types.PhotoSize) -> str:
    """
    Download photo from Telegram and return base64 string.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        file = await bot.get_file(photo.file_id)
        await bot.download_file(file.file_path, tmp.name)
        tmp.flush()
        return encode_image(tmp.name)


async def get_ocr_response(caption: str, photos: list[types.PhotoSize]) -> str:
    """
    caption: text description / caption
    photos: list of Telegram PhotoSize objects

    Uses Groq (qwen3.6-27b) for vision
    """
    system_prompt = """
    Ты — Nerdinzzz 🤓, OCR-бот. Твой создатель — @duckinzzz.

    ЖЁСТКИЕ ПРАВИЛА:
    1. Если на изображении есть ЛЮБОЙ текст (даже обрезанный, частичный, на любом языке) — выведи его ДОСЛОВНО, как есть. Ничего не добавляй, не summarise, не переводи.
    2. Только если текста на изображении НЕТ СОВСЕМ — дай краткое описание (2-3 предложения), что на нём изображено.
    3. Никаких вступлений, приветствий, прощаний.
    4. Выводи текст «как есть», не экранируй символы.
    """

    # Encode all photos to base64
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

    kwargs: dict = {
        "model": OCR_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_completion_tokens": 4096,
        "top_p": 1,
        "stream": False,
        "stop": None,
    }

    try:
        completion = await groq_client.chat.completions.create(**kwargs)
        raw = completion.choices[0].message.content or ""

        # Strip Qwen reasoning tags — Telegram can't parse them as Markdown
        content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        if not content:
            log_error(request_type='process_image', caption=caption, error='empty_response')
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте другое изображение."

        return content

    except GroqAPIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='process_image', caption=caption, error=e)
            return "❌ Сообщение слишком длинное, попробуйте укоротить сообщение"
        log_error(request_type='process_image', caption=caption, error=e)
        return "❌ Ошибка при обработке изображения"
    except Exception as e:
        log_error(request_type='process_image', caption=caption, error=e)
        return "❌ Ошибка при обработке изображения"


async def get_llm_response(user_prompt: str) -> str:
    system_prompt = """
    Ты — Nerdinzzz 🤓, LLM чат-бот на базе DeepSeek V4.
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

    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_completion_tokens": 4096,
        "top_p": 1,
        "stream": False,
        "stop": None,
    }

    try:
        completion = await client.chat.completions.create(**kwargs)
        content = completion.choices[0].message.content.strip()

        if not content:
            log_error(request_type='llm_question', user_prompt=user_prompt, error='empty_response')
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте переформулировать вопрос."

        return content.strip()

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
            return "❌ Сообщение слишком длинное, попробуйте укоротить сообщение"
        log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
        return "❌ Ошибка при обработке запроса"
    except Exception as e:
        log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
        return "❌ Ошибка при обработке запроса"


async def make_prompt(user_prompt: str) -> str:
    system_prompt = """
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

    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 1,
        "max_completion_tokens": 4096,
        "top_p": 1,
        "stream": False,
        "stop": None,
    }

    try:
        completion = await client.chat.completions.create(**kwargs)
        prompt = completion.choices[0].message.content.strip()

        if not prompt:
            log_error(request_type='image_generation', user_prompt=user_prompt, error="generated_empty_prompt")
            return ''
        if "i can't help with" in prompt.lower():
            log_error(request_type='image_generation', user_prompt=user_prompt, error="prompt_restricted")
            return ''
        return prompt

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='image_generation', user_prompt=user_prompt, error=e)
        log_error(request_type='image_generation', user_prompt=user_prompt, error=e)
        return ''
    except Exception as e:
        log_error(request_type='image_generation', user_prompt=user_prompt, error=e)
        return ''


async def generate_summary(messages_json: list[dict], chat_id: int, total_count: int, bot_username: str) -> str:
    """
    Generate a summary of chat messages.

    messages_json: list of dicts with {username, text, message_id}
    chat_id: chat ID
    total_count: number of messages
    bot_username: bot's username (to filter out its own responses)

    Returns summary in format:
    🤓 AI проанализировал N сообщений.
    Вот что вы пропустили:
    [Topics with descriptions]
    """
    from core.constants import SUMMARY_PROMPT

    system_prompt = SUMMARY_PROMPT

    # Build context from messages, excluding bot's own responses
    messages_text = []
    for msg in messages_json:
        username = msg.get('username') or f"user_{msg['user_id']}"
        if not username.startswith('@'):
            username = f"@{username}"

        # Skip messages from the bot (but keep requests to it)
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

    kwargs: dict = {
        "model": LLM_MODEL,
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

        # Format header
        header = f"🤓 Я проанализировал {total_count} сообщений.\nВот что вы пропустили:\n\n"
        return header + summary

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='summary', chat_id=chat_id, error=e)
            return "❌ Сообщение слишком длинное, попробуйте укоротить сообщение"
        log_error(request_type='summary', chat_id=chat_id, error=e)
        return "❌ Ошибка при генерации саммари"
    except Exception as e:
        log_error(request_type='summary', chat_id=chat_id, error=e)
        return "❌ Ошибка при генерации саммари"
