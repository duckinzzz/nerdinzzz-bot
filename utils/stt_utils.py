from groq import Groq

from core.bot_core import STT_TOKEN

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
