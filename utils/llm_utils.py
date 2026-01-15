from groq import AsyncGroq

from core.bot_core import LLM_TOKEN

client = AsyncGroq(api_key=LLM_TOKEN)
llm_model_name = "OpenAI/GPT-OSS-120b"

system_prompt = (
    f"Ты — Nerdinzzz 🤓, LLM чат-бот на базе {llm_model_name}. "
    "Твой создатель - @duckinzzz. "
    "Ты умеешь быстро отвечать на текстовые сообщения и преобразовывать голосовые в текст. "
    "Отвечай кратко, ясно и по делу, максимум 3-4 предложения. "
    "Если нужен список - только ключевые пункты. "
    "Не задавай встречных вопросов, не объясняй свои действия."
)


async def get_llm_response(user_prompt: str) -> str:
    messages = [
        {
            "role": "system",
            "content": system_prompt.lower()
        },
        {"role": "user", "content": user_prompt}
    ]

    completion = await client.chat.completions.create(model=llm_model_name, messages=messages, temperature=1,
                                                      max_completion_tokens=8192, top_p=1, reasoning_effort="medium",
                                                      stream=False, stop=None)

    return completion.choices[0].message.content
