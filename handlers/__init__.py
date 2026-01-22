from aiogram import Router

from .admin import admin_router
from .base import base_router
from .photo import photo_router
from .text import text_router
from .voice import voice_router


def get_main_router() -> Router:
    """Объединяет все роутеры"""
    main_router = Router()

    main_router.include_router(base_router)
    main_router.include_router(admin_router)
    main_router.include_router(photo_router)
    main_router.include_router(voice_router)
    main_router.include_router(text_router)

    return main_router
