DEFAULT_LLM = "openai/gpt-oss-120b"

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
    "meta-llama/llama-4-maverick-17b-128e-instruct": {
        "name": "Llama 4 Maverick 17B 128E",
        "reasoning": False,
        "multimodal": True,
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
    "moonshotai/kimi-k2-instruct-0905": {
        "name": "Kimi K2 0905",
        "reasoning": False,
        "multimodal": False,
    },
}

SUPPORTED_MSG_TYPES = ["text",
                       "voice",
                       "video_note",
                       "photo"]
HALLUCINATIONS = {
    'thanks for watching!',
    'thank you.',
    'thank you for watching.',
    'preparation for cooking',
    'you',
    'субтитры сделал dimatorzok',
}

REACT_EMOJIS = ["🍌", "🍓", "💯", "🎉", "🏆", "🤓"]
EMOJIS_WEIGHTS = [50, 25, 15, 7, 3, 1]
