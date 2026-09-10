import html
import tempfile

from aiogram import F, Router
from aiogram.types import Message, reaction_type_emoji

from core.app import bot
from utils import stt_utils
from utils.logging_utils import log_message

voice_router = Router()


async def reply_transcript(message: Message, stt_response: str | None) -> None:
    if stt_response:
        log_message(request_type='stt_request', message=message, stt_response=stt_response)
        # <blockquote expandable> — сворачиваемая цитата (Bot API 7.3+)
        await message.reply(
            f"<blockquote expandable>{html.escape(stt_response)}</blockquote>",
            parse_mode="HTML",
        )
    else:
        log_message(request_type='stt_request', message=message, stt_response='')
        await message.react([reaction_type_emoji.ReactionTypeEmoji(emoji="🙉")])


@voice_router.message(F.content_type == "voice")
async def voice_handler(message: Message):
    voice = message.voice
    file = await bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg") as tmp:
        await bot.download_file(file.file_path, destination=tmp.name)
        stt_response = await stt_utils.stt(tmp.name)
        await reply_transcript(message, stt_response)


@voice_router.message(F.content_type == "video_note")
async def video_note_handler(message: Message):
    video_note = message.video_note
    file = await bot.get_file(video_note.file_id)

    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        await bot.download_file(file.file_path, destination=tmp.name)
        stt_response = await stt_utils.stt_from_video(tmp.name)
        await reply_transcript(message, stt_response)
