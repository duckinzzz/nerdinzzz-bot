from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiohttp.web_app import Application

from core.app import bot, dp
from core.config import WEBHOOK_HOST, WEBHOOK_PORT, WEBHOOK_PATH, ENV, WEBHOOK_URL
from handlers import get_main_router
from utils import db_utils
from utils.logging_utils import logger


async def on_startup(_: Application) -> None:
    await db_utils.init_db()
    dp.include_router(get_main_router())
    await bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True)
    logger.info(f"[{ENV}] Webhook set to {WEBHOOK_URL}")


async def on_shutdown(_: Application) -> None:
    await bot.delete_webhook()
    await bot.session.close()
    await db_utils.close_db()
    logger.info(f"[{ENV}] Webhook removed, bot shutdown")


def main():
    app = web.Application()

    app.on_startup.append(on_startup)  # type: ignore ¯\_(•_• )_/¯
    app.on_shutdown.append(on_shutdown)  # type: ignore

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info(f"[{ENV}] Starting aiohttp server at {WEBHOOK_HOST}:{WEBHOOK_PORT} for webhook path {WEBHOOK_PATH}")
    web.run_app(app, host=WEBHOOK_HOST, port=WEBHOOK_PORT)


if __name__ == "__main__":
    main()
