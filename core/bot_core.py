import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from utils.logging_utils import logger

ENV = os.getenv("ENV").lower()
BOT_TOKEN = os.getenv("BOT_TOKEN")
LLM_TOKEN = os.getenv("LLM_TOKEN")
STT_TOKEN = os.getenv("STT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")
if not LLM_TOKEN:
    raise ValueError("LLM_TOKEN Token not found")

logger.info(f"Bot starting in {ENV} mode | token ends with ...{BOT_TOKEN[-6:]}")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
dp['llm'] = "openai/gpt-oss-120b"
