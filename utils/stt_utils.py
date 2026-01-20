import tempfile

import ffmpeg
import imageio_ffmpeg as iio
from groq import Groq

from core.config import STT_TOKEN

client = Groq(api_key=STT_TOKEN)


async def stt(path: str) -> str:
    with open(path, "rb") as audio:
        result = client.audio.transcriptions.create(
            file=audio,
            model="whisper-large-v3",
            response_format="text",
            temperature=0
        )
    return str(result)


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
