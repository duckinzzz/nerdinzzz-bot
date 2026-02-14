from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from core.config import BOT_TOKEN

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=None),
)
dp = Dispatcher()
