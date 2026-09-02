import base64
import json

import aiohttp
from aiogram.types import BufferedInputFile

from core.config import CF_ACCOUNT_ID, CF_API_TOKEN
from utils.logging_utils import log_error


async def generate_image(prompt: str) -> BufferedInputFile | None:
    """
    Generate image from text prompt using Cloudflare AI.
    Returns BufferedInputFile for sending via Telegram or None on error.
    """
    model = '@cf/black-forest-labs/flux-2-klein-4b'
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{model}"

    # flux-2-dev requires multipart/form-data, even for a prompt-only request
    form = aiohttp.FormData()
    form.add_field("prompt", prompt)

    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=form) as response:
                body = await response.text()
                if not response.ok:
                    log_error(
                        request_type='image_generation',
                        user_prompt=prompt,
                        error=f"HTTP {response.status}: {body[:1000]}",
                    )
                    return None
                data = json.loads(body)

        img_b64 = data["result"]["image"]
        img_bytes = base64.b64decode(img_b64)

        return BufferedInputFile(img_bytes, filename="generated.png")

    except Exception as e:
        log_error(request_type='image_generation', user_prompt=prompt, error=e)
        return None
