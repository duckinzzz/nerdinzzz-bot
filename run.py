import os

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from core.bot_core import bot, dp, logger
from core.handlers import start_router

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8080))
ENV = os.getenv("ENV", "dev")

from aiohttp.web_app import Application


async def on_startup(_: Application) -> None:
    dp.include_router(start_router)
    await bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    logger.info(f"[{ENV}] Webhook set to {WEBHOOK_URL}")


async def on_shutdown(_: Application) -> None:
    await bot.delete_webhook()
    await bot.session.close()
    logger.info(f"[{ENV}] Webhook removed, bot shutdown")


def main():
    app = web.Application()

    app.on_startup.append(on_startup)  # type: ignore ¯\_(•_• )_/¯
    app.on_shutdown.append(on_shutdown)  # type: ignore

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    logger.info(f"[{ENV}] Starting aiohttp server at {WEBHOOK_HOST}:{WEBHOOK_PORT} for webhook path {WEBHOOK_PATH}")
    web.run_app(
        app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT
    )


if __name__ == "__main__":
    main()
