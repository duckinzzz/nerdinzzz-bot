import tempfile

import ffmpeg
import imageio_ffmpeg as iio
from groq import Groq

from core.config import STT_TOKEN
from core.constants import HALLUCINATIONS
from utils.logging_utils import log_event

client = Groq(api_key=STT_TOKEN)

import unicodedata


def process_transcription(result):
    if not result.segments:
        return '[тишина]'

    avg_logprob = sum(s['avg_logprob'] for s in result.segments) / len(result.segments)

    norm_text = unicodedata.normalize("NFKC", result.text).casefold().strip('.!?, ')
    if not norm_text:
        return '[тишина]'

    if norm_text in HALLUCINATIONS or avg_logprob < -1.0:
        return '[тишина]'

    return result.text


async def stt(path: str) -> str:
    with open(path, "rb") as audio:
        response = client.audio.transcriptions.create(
            file=audio,
            model="whisper-large-v3",
            response_format="verbose_json",
            temperature=0
        )
    log_event(event='transcription', data=response.model_dump())
    return process_transcription(response)


async def stt_from_video(video_path: str) -> str:
    ffmpeg_path = iio.get_ffmpeg_exe()

    with tempfile.NamedTemporaryFile(suffix=".wav") as audio_tmp:
        (
            ffmpeg
            .input(video_path)
            .output(audio_tmp.name, format='wav', acodec='pcm_s16le', ac=1, ar=16000)
            .run(cmd=ffmpeg_path, overwrite_output=True, quiet=True)
        )
        text = await stt(audio_tmp.name)
    return text
