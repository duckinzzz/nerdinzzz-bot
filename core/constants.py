DEFAULT_LLM = "openai/gpt-oss-120b"

LLM_MODELS = {
    "llama-3.1-8b-instant": {
        "name": "Llama 3.1 8B",
    },
    "llama-3.3-70b-versatile": {
        "name": "Llama 3.3 70B",
    },
    "openai/gpt-oss-120b": {
        "name": "GPT OSS 120B",
    },
    "openai/gpt-oss-20b": {
        "name": "GPT OSS 20B",
    },
    "meta-llama/llama-4-maverick-17b-128e-instruct": {
        "name": "Llama 4 Maverick 17B 128E",
    },
    "meta-llama/llama-4-scout-17b-16e-instruct": {
        "name": "Llama 4 Scout 17B 16E",
    },
    "qwen/qwen3-32b": {
        "name": "Qwen3 32B",
    },
    "moonshotai/kimi-k2-instruct-0905": {
        "name": "Kimi K2 0905",
    },
}

LLM_WITH_REASONING = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
]

SUPPORTED_MSG_TYPES = ["text",
                       "voice",
                       "video_note"]
