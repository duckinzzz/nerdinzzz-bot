import tempfile

import ffmpeg
import imageio_ffmpeg as iio
import unicodedata
from groq import Groq

from core.config import STT_TOKEN
from core.constants import HALLUCINATIONS

client = Groq(api_key=STT_TOKEN)




def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip().casefold()


async def stt(path: str) -> str:
    with open(path, "rb") as audio:
        result = client.audio.transcriptions.create(
            file=audio,
            model="whisper-large-v3",
            response_format="text",
            temperature=0
        )
    result = normalize(str(result))
    return result if result not in HALLUCINATIONS else '[тишина]'


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
