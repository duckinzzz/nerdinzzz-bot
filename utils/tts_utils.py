import ffmpeg
import imageio_ffmpeg as iio
from groq import Groq

from core.config import TTS_TOKEN

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


async def generate_voice(prompt: str):
    response = client.audio.speech.create(
        model="canopylabs/orpheus-v1-english",
        voice="daniel",
        response_format="wav",
        input=prompt,
    )
    wav_bytes = response.read()
    ogg_bytes = wav_to_ogg(wav_bytes)

    return ogg_bytes
