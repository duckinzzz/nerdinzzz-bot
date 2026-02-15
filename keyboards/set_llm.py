from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.constants import LLM_MODELS


def set_llm_kb(curr_llm):
    builder = InlineKeyboardBuilder()
    for tag, info in LLM_MODELS.items():
        builder.button(text=f"{'✅' if curr_llm == tag else ''}" + info["name"],
                       callback_data=f"sl:{tag}")

    builder.adjust(2)
    return builder.as_markup()
