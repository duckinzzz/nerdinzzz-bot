import base64
import json

import aiohttp
from aiogram.types import BufferedInputFile

from core.config import CF_ACCOUNT_ID, CF_API_TOKEN
from utils.logging_utils import log_error

# Cloudflare AI error code: the generated image was rejected by the output filter
MODERATION_ERROR_CODE = 3030


class ImageFlagged(Exception):
    """Cloudflare moderation flagged the generated image."""


def _is_flagged(body: str) -> bool:
    """True if the Cloudflare error body reports an output moderation rejection."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return False
    return any(err.get('code') == MODERATION_ERROR_CODE for err in data.get('errors', []))


async def generate_image(prompt: str) -> BufferedInputFile | None:
    """
    Generate image from text prompt using Cloudflare AI.
    Returns BufferedInputFile for sending via Telegram or None on error.
    Raises ImageFlagged when moderation rejects the result — the prompt itself is fine.
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
                    if _is_flagged(body):
                        raise ImageFlagged
                    return None
                data = json.loads(body)

        img_b64 = data["result"]["image"]
        img_bytes = base64.b64decode(img_b64)

        return BufferedInputFile(img_bytes, filename="generated.png")

    except ImageFlagged:
        # Already logged as an HTTP error, and the handler shows its own message
        raise
    except Exception as e:
        log_error(request_type='image_generation', user_prompt=prompt, error=e)
        return None
