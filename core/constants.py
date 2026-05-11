DEFAULT_LLM = "openai/gpt-oss-120b"

# Количество сообщений для хранения и анализа
MESSAGE_HISTORY_LIMIT = 50

# Модель для генерации саммари (с большим контекстным окном)
SUMMARY_MODEL = "llama-3.3-70b-versatile"

# Промпт для генерации саммари
SUMMARY_PROMPT = """
Ты — ассистент для создания кратких саммари переписки в чате.

Твоя задача:
1. Проанализировать предоставленные сообщения из чата
2. Выделить ключевые темы обсуждения
3. Сгруппировать сообщения по темам
4. Для каждой темы создать краткое описание (1-3 предложения)

Формат ответа:
- Перед названием темы ставь смайлик 🔸 (например: 🔸 Здоровье)
- Используй маркированные списки для пунктов
- Пиши на русском языке
- Будь краток, но информативен
- Не добавляй вступлений или заключений, только саммари
- НЕ добавляй ссылки на сообщения
- НЕ используй жирный шрифт

Формат упоминания пользователей:
- Пиши просто: @username сказал/спросил/ответил...
- НЕ пиши "Пользователь @user"

Пример формата:
🔸 Здоровье
- @duckinzzz описал проблему с ушной инфекцией
- @aaaanyonaaaa спросил про лекарства

🔸 Обсуждение стикеров
- @duckinzzz поделился ссылкой на пак стикеров
"""

LLM_MODELS = {
    "llama-3.1-8b-instant": {
        "name": "Llama 3.1 8B",
        "reasoning": False,
        "multimodal": False,
    },
    "llama-3.3-70b-versatile": {
        "name": "Llama 3.3 70B",
        "reasoning": False,
        "multimodal": False,
    },
    "openai/gpt-oss-120b": {
        "name": "GPT OSS 120B",
        "reasoning": True,
        "multimodal": False,
    },
    "openai/gpt-oss-20b": {
        "name": "GPT OSS 20B",
        "reasoning": True,
        "multimodal": False,
    },
    "meta-llama/llama-4-scout-17b-16e-instruct": {
        "name": "Llama 4 Scout 17B 16E",
        "reasoning": False,
        "multimodal": True,
    },
    "qwen/qwen3-32b": {
        "name": "Qwen3 32B",
        "reasoning": True,
        "multimodal": False,
    },
}

SUPPORTED_MSG_TYPES = ["text",
                       "voice",
                       "video_note",
                       "photo"]

HALLUCINATIONS = {
    'thanks for watching',
    'thank you',
    'thank you for watching',
    'preparation for cooking',
    'you',
    'продолжение следует',
    'hello everyone',
    'takk for watching',
}

HALLUCINATIONS_WORDS = {
    'dimatorzok'
}

REACTION_PROB = 0.0025
EMOJIS_RANDOM_POOL = ["👌", "🥱", "😈", "🤯", "🕊", "🖕"]
EMOJIS_WEIGHTS = [50, 25, 15, 7, 3, 1]
EMOJIS_SUPPORTED = ["❤", "👍", "👎", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "🤬", "😢",
                    "🎉", "🤩", "🤮", "💩", "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳",
                    "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔", "🤨", "😐", "🍓",
                    "🍾", "💋", "🖕", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈",
                    "😇", "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪", "🗿", "🆒",
                    "💘", "🙉", "🦄", "😘", "💊", "🙊", "😎", "👾", "🤷‍♂", "🤷", "🤷‍♀", "😡"]
