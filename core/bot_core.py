import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

if not os.getenv("DOCKER"):
    load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("./bot.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bot_core")

ENV = os.getenv("ENV").lower()
BOT_TOKEN = os.getenv("BOT_TOKEN")
LLM_TOKEN = os.getenv("LLM_TOKEN")

if not BOT_TOKEN:
    raise ValueError(f"BOT_TOKEN not found")
if not LLM_TOKEN:
    raise ValueError(f"LLM_TOKEN Token not found")

logger.info(f"Bot starting in {ENV} mode | token ends with ...{BOT_TOKEN[-6:]}")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
