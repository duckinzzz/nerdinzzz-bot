import os

from utils.logging_utils import logger

ENV = os.getenv("ENV").lower()
BOT_TOKEN = os.getenv("BOT_TOKEN")
LLM_TOKEN = os.getenv("LLM_TOKEN")
STT_TOKEN = os.getenv("STT_TOKEN")
TTS_TOKEN = os.getenv("TTS_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8080))
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")
CF_API_TOKEN = os.getenv("CF_API_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")
if not LLM_TOKEN:
    raise ValueError("LLM_TOKEN Token not found")

logger.info(f"Bot starting in {ENV} mode | token ends with ...{BOT_TOKEN[-6:]}")
