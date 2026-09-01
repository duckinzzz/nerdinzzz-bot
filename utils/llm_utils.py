import base64
import html
import re
import tempfile

from aiogram import types
from openai import AsyncOpenAI, APIStatusError

from core.app import bot
from core.config import LLM_TOKEN
from core.constants import LLM_MODEL
from utils.logging_utils import log_error, log_event
from utils.tools import get_tool_registry

# DeepSeek — text generation & vision/OCR
client = AsyncOpenAI(
    api_key=LLM_TOKEN,
    base_url="https://api.deepseek.com",
)

# DeepSeek vision model (only it accepts images; others return 400)
OCR_MODEL = "deepseek-v4-flash-vision-exp"


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

    Uses DeepSeek (deepseek-v4-flash-vision-exp) for vision
    """
    system_prompt = """
    Ты — Nerdinzzz 🤓, ассистент по анализу изображений. Твой создатель — @duckinzzz.

    Отвечай на вопрос пользователя об изображении. Это может быть распознавание текста
    («что написано») либо описание/объяснение («что это такое»).
    Если пользователь просит прочитать текст — выведи его точно, как написан, не исправляя опечатки.
    Если спрашивает, что изображено — опиши, что видно, без догадок; если что-то неясно — так и скажи.
    Если просьбы нет и непонятно, что нужно, — кратко опиши изображение (2-3 предложения).

    Никаких вступлений, приветствий, прощаний. Отвечай по делу.
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
        completion = await client.chat.completions.create(**kwargs)
        raw = completion.choices[0].message.content or ""

        # Strip reasoning tags — Telegram can't parse them as Markdown
        content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

        if not content:
            log_error(request_type='process_image', caption=caption, error='empty_response')
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте другое изображение."

        return content

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='process_image', caption=caption, error=e)
            return "❌ Сообщение слишком длинное, попробуйте укоротить сообщение"
        log_error(request_type='process_image', caption=caption, error=e)
        return "❌ Ошибка при обработке изображения"
    except Exception as e:
        log_error(request_type='process_image', caption=caption, error=e)
        return "❌ Ошибка при обработке изображения"


async def get_llm_response(
        user_prompt: str,
        chat_id: int | None = None,
        history: list[dict] | None = None,
) -> str:
    system_prompt = """
    Ты — Nerdinzzz 🤓, LLM чат-бот на базе DeepSeek V4.
    Твой создатель — @duckinzzz.
    Твоя задача:
    - Помни весь диалог из истории сообщений и отвечай с учётом контекста предыдущих реплик.
    - Если пользователь сообщил о себе факт (имя, занятие и т.п.) — запомни его и используй в последующих ответах, не требуя повторить.
    - Чётко различай роли: «user» — это собеседник, «assistant» — ты. Не приписывай собеседнику то, что сказал ты, и наоборот.
    - Быстро и точно отвечать на текстовые сообщения.
    - Преобразовывать голосовые сообщения в текст (если требуется).
    - Отвечать кратко, ясно и по делу, максимум 3-4 предложения.
    - Если нужен список — только ключевые пункты.
    - Используй нумерацию или маркеры для структурированных ответов, если необходимо.
    - Не задавай встречных вопросов.
    - Не объясняй свои действия и не добавляй приветствия или прощания.
    - Всегда придерживайся нейтрального и дружелюбного тона.
    - Не экранируй символы, кавычки или специальные знаки — выводи текст «как есть».
    - Если нужны актуальные данные (погода, курсы валют и т.д.) — используй доступные инструменты.
    """

    messages: list[dict] = [
        {"role": "system", "content": system_prompt.lower()},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    registry = get_tool_registry()
    tools = registry.get_openai_definitions() if registry.has_tools() else None

    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "reasoning_effort": "low",
        "max_completion_tokens": 4096,
        "top_p": 1,
        "stream": False,
        "stop": None,
    }
    if tools:
        kwargs["tools"] = tools

    try:
        # First LLM call — may return tool_calls
        completion = await client.chat.completions.create(**kwargs)
        msg = completion.choices[0].message

        # Function calling loop (max 2 rounds: 1 tool round + 1 final response)
        for _ in range(2):
            if not msg.tool_calls:
                break

            # Refresh typing indicator — Telegram expires it after ~5s
            if chat_id is not None:
                await bot.send_chat_action(chat_id=chat_id, action="typing")

            tool_results = await registry.execute(msg.tool_calls)
            log_event(
                event="tool_calls",
                tools=[tc.function.name for tc in msg.tool_calls],
            )

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }}
                    for tc in msg.tool_calls
                ],
            })
            messages.extend(tool_results)

            # Follow-up LLM call — with tool results
            kwargs["messages"] = messages
            completion = await client.chat.completions.create(**kwargs)
            msg = completion.choices[0].message

        content = (msg.content or "").strip()

        if not content:
            log_error(request_type='llm_question', user_prompt=user_prompt, error='empty_response')
            return "❌ Модель не смогла ответить на ваш вопрос. Попробуйте переформулировать вопрос."

        return content

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
            return "❌ Сообщение слишком длинное, попробуйте укоротить сообщение"
        log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
        return "❌ Ошибка при обработке запроса"
    except Exception as e:
        log_error(request_type='llm_question', user_prompt=user_prompt, error=e)
        return "❌ Ошибка при обработке запроса"


async def make_prompt(user_prompt: str, system_instruction: str | None = None) -> str:
    system_prompt = system_instruction or """
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
        "reasoning_effort": "low",
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


def make_message_link(chat_id: int, message_id: int) -> str:
    """
    Build a t.me/c/ deep-link to a message in a private chat/channel.

    Private supergroup ids are negative with a '-100' prefix
    (e.g. -1002539915851), which Telegram strips from the link:
    https://t.me/c/2539915851/{message_id}
    """
    s = str(chat_id)
    if s.startswith("-100"):
        s = s[4:]
    elif s.startswith("-"):
        s = s[1:]
    return f"https://t.me/c/{s}/{message_id}"


def links_to_html(text: str) -> str:
    """
    Escape text for Telegram HTML parse_mode, then convert LLM's
    [word](https://t.me/...) markdown-style links into <a> hyperlinks.
    """
    text = html.escape(text)
    return re.sub(
        r"\[([^\]]+)\]\((https://t\.me/[^)\s]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )


async def generate_summary(messages_json: list[dict], chat_id: int, total_count: int, bot_username: str) -> str:
    """
    Generate a summary of chat messages.

    messages_json: list of dicts with {username, first_name, text, message_id}
    chat_id: chat ID
    total_count: number of messages
    bot_username: bot's username (to filter out its own responses)

    Returns HTML summary with a header and word-links to source messages.
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

        # Use first name when available, fall back to @username
        display = msg.get('first_name') or username
        text = msg.get('text', '')
        link = make_message_link(chat_id, msg.get('message_id'))
        messages_text.append(f"{display} [сообщение {link}]: {text}")

    context = "\n".join(messages_text)

    user_prompt = f"""Количество сообщений (без ответов бота): {total_count}

Сообщения:
{context}

Сделай саммари на русском языке.
Чтобы связать слово с сообщением, оберни его в ссылку так: [слово](https://t.me/c/.../MESSAGE_ID).
Используй только ссылки [сообщение https://t.me/c/...] из контекста выше, не выдумывай новых."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "reasoning_effort": "low",
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

        # Format header + escape content and convert word-links to HTML
        header = f"🤓 Я проанализировал {total_count} сообщений.\nВот что вы пропустили:\n\n"
        return header + links_to_html(summary)

    except APIStatusError as e:
        if e.status_code == 413:
            log_error(request_type='summary', chat_id=chat_id, error=e)
            return "❌ Сообщение слишком длинное, попробуйте укоротить сообщение"
        log_error(request_type='summary', chat_id=chat_id, error=e)
        return "❌ Ошибка при генерации саммари"
    except Exception as e:
        log_error(request_type='summary', chat_id=chat_id, error=e)
        return "❌ Ошибка при генерации саммари"
