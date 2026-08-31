import re
import secrets

from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from core.config import BOT_USERNAME
from utils import tti_utils
from utils.db_utils import get_last_messages
from utils.llm_utils import generate_summary, make_prompt
from utils.logging_utils import log_message, log_error

summary_router = Router()

# Store summaries temporarily so a long summary fits in a short callback token
summary_store: dict[str, str] = {}

# Instruction for rendering a summary as a scene, not a chat digest
SUMMARY_IMAGE_INSTRUCTION = """
Transform the chat summary below into ONE vivid, cohesive narrative scene to draw.
Do NOT depict it as a chat digest, a list of topics, or a recap of a conversation.
Weave the people, events and details described into a single lively story moment or atmosphere.
Return only the image generation prompt. ENGLISH ONLY. No violence.
"""


def _clean_summary_for_image(summary: str) -> str:
    """Strip markdown links and leading boilerplate so only the content remains."""
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', summary)
    lines = [ln.strip() for ln in text.splitlines()]
    # Skip leading greeting/header lines until the first topic marker or bullet
    marker_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("🔸") or ln.startswith("-")),
        0
    )
    return "\n".join(lines[marker_idx:]).strip()


@summary_router.message(Command("summary"))
async def summary_handler(message: Message, bot: Bot):
    """Handle /summary: generate a summary of recent chat messages."""
    chat_id = message.chat.id

    if message.chat.type not in ("group", "supergroup"):
        return await message.answer(
            "❌ Команда /summary доступна только в групповых чатах"
        )

    status_msg = await message.reply("⏳ Анализирую историю чата...")

    try:
        messages = await get_last_messages(chat_id)

        if len(messages) < 2:
            await status_msg.delete()
            await message.reply(
                "❌ Недостаточно сообщений для саммари.\n"
                f"Найдено всего: {len(messages)}"
            )
            return

        messages_json = [
            {
                "message_id": msg.message_id,
                "user_id": msg.user_id,
                "username": msg.username,
                "first_name": msg.first_name,
                "text": msg.text
            }
            for msg in messages
        ]

        summary = await generate_summary(
            messages_json=messages_json,
            chat_id=chat_id,
            total_count=len(messages),
            bot_username=BOT_USERNAME
        )

        await status_msg.delete()
        log_message(
            request_type='summary',
            message=message,
            messages_count=len(messages),
            chat_id=chat_id
        )
        token = secrets.token_hex(8)
        summary_store[token] = summary
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🎨 Визуализировать", callback_data=f"viz_{token}")
            ]]
        )
        await message.reply(summary, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        await status_msg.delete()
        log_error(request_type='summary', message=message, error=e, chat_id=chat_id)
        await message.reply("❌ Ошибка при генерации саммари. Попробуйте позже.")


@summary_router.callback_query(F.data.startswith("viz_"))
async def visualize_summary_handler(callback: CallbackQuery, bot: Bot):
    """Handle "visualize" button: generate an image from the summary text."""
    token = callback.data.removeprefix("viz_")
    summary = summary_store.pop(token, None)

    if not summary:
        # Summary already used or expired: just remove the button from the message
        await callback.answer()
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await callback.answer()
    status_msg = await callback.message.answer("🖌️ Рисую...")

    try:
        cleaned_summary = _clean_summary_for_image(summary)
        llm_prompt = await make_prompt(cleaned_summary, system_instruction=SUMMARY_IMAGE_INSTRUCTION)
        if not llm_prompt:
            await status_msg.delete()
            await callback.message.answer("❌ Не получилось обработать промпт")
            return

        image = await tti_utils.generate_image(llm_prompt)
        await status_msg.delete()
        if image:
            log_message(request_type='image_generation', message=callback.message, llm_prompt=llm_prompt)
            await callback.message.answer_photo(photo=image)
            # Hide the button once the image was sent successfully
            await callback.message.edit_reply_markup(reply_markup=None)
        else:
            await callback.message.answer("❌ Не получилось сгенерировать изображение")
    except Exception as e:
        try:
            await status_msg.delete()
        except Exception:
            pass
        log_error(request_type='image_generation', error=e)
        await callback.message.answer("❌ Ошибка при генерации изображения")
