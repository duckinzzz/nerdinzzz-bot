import tempfile

import unicodedata
from aiogram import F, Router
from aiogram.types import Message

from core.app import bot
from utils import stt_utils
from utils.logging_utils import log_message

voice_router = Router()

hallucinations = {
    'thanks for watching!',
    'thank you.',
    'thank you for watching.',
    'preparation for cooking',
    'you',
    'субтитры сделал dimatorzok',
}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip().casefold()


@voice_router.message(F.content_type == "voice")
async def voice_handler(message: Message):
    voice = message.voice
    file = await bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        await bot.download_file(file.file_path, destination=tmp.name)
        stt_response = await stt_utils.stt(tmp.name)
        clean = normalize(stt_response)

        log_message(request_type='stt_request', message=message, stt_response=stt_response)
        await message.reply(
            stt_response.strip() if clean not in hallucinations else '[тишина]'
        )


@voice_router.message(F.content_type == "video_note")
async def video_note_handler(message: Message):
    video_note = message.video_note
    file = await bot.get_file(video_note.file_id)

    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        await bot.download_file(file.file_path, destination=tmp.name)
        stt_response = await stt_utils.stt(tmp.name)
        clean = normalize(stt_response)

        log_message(request_type='stt_request', message=message, stt_response=stt_response)
        await message.reply(
            stt_response.strip() if clean not in hallucinations else '[тишина]'
        )
