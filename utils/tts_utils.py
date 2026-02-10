import re
from datetime import timedelta

import ffmpeg
import imageio_ffmpeg as iio
from groq import Groq
from groq import RateLimitError

from core.config import TTS_TOKEN
from utils.logging_utils import log_error

client = Groq(api_key=TTS_TOKEN)


def wav_to_ogg(wav_bytes: bytes) -> bytes:
    ffmpeg_path = iio.get_ffmpeg_exe()

    process = ffmpeg.input('pipe:0').output(
        'pipe:1', format='opus', acodec='libopus', audio_bitrate='64k'
    ).run_async(
        cmd=ffmpeg_path,
        pipe_stdin=True,
        pipe_stdout=True,
        pipe_stderr=True
    )

    ogg_bytes, _ = process.communicate(input=wav_bytes)
    return ogg_bytes


def format_wait_time(raw_time: str) -> str:
    try:
        total_seconds = 0
        h_match = re.search(r"(\d+)h", raw_time)
        m_match = re.search(r"(\d+)m", raw_time)
        s_match = re.search(r"(\d+)s", raw_time)
        if h_match:
            total_seconds += int(h_match.group(1)) * 3600
        if m_match:
            total_seconds += int(m_match.group(1)) * 60
        if s_match:
            total_seconds += int(s_match.group(1))

        td = timedelta(seconds=total_seconds)
        parts = []
        if td.seconds // 3600 > 0:
            parts.append(f"{td.seconds // 3600}ч")
        if (td.seconds % 3600) // 60 > 0:
            parts.append(f"{(td.seconds % 3600) // 60}м")
        if td.seconds % 60 > 0:
            parts.append(f"{td.seconds % 60}с")
        return " ".join(parts) or "менее секунды"
    except Exception as e:
        log_error(request_type='format_wait_time', error=e)
        return raw_time


async def generate_voice(prompt: str) -> bytes:
    try:
        response = client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice="daniel",
            response_format="wav",
            input=prompt,
        )
        wav_bytes = response.read()
        return wav_to_ogg(wav_bytes)

    except RateLimitError as e:
        text = (
            getattr(e.response, "text", None)
            if getattr(e, "response", None)
            else str(e)
        )

        match = re.search(r"Please try again in ([\dhms]+)", text)
        e.wait_time = format_wait_time(match.group(1)) if match else None
        raise
