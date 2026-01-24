import base64

import aiohttp
from aiogram.types import BufferedInputFile

from core.config import CF_ACCOUNT_ID, CF_API_TOKEN
from utils.logging_utils import log_error


async def generate_image(prompt: str) -> BufferedInputFile | None:
    """
    Generate image from text prompt using Cloudflare AI.
    Returns BufferedInputFile for sending via Telegram or None on error.
    """
    model = '@cf/black-forest-labs/flux-1-schnell'
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{model}"

    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "image_size": "512x512"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()

        img_b64 = data["result"]["image"]
        img_bytes = base64.b64decode(img_b64)

        return BufferedInputFile(img_bytes, filename="generated.png")

    except Exception as e:
        log_error(request_type='image_generation', user_prompt=prompt, error=e)
        return None
