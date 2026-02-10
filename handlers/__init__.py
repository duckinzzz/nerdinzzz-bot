from aiogram import Router

from core.middlewares import LuckyEmojiMiddleware
from .admin import admin_router
from .base import base_router
from .photo import photo_router
from .text import text_router
from .voice import voice_router


def get_main_router() -> Router:
    main_router = Router()

    main_router.message.outer_middleware(LuckyEmojiMiddleware())

    main_router.include_router(base_router)
    main_router.include_router(admin_router)
    main_router.include_router(photo_router)
    main_router.include_router(voice_router)
    main_router.include_router(text_router)

    return main_router
