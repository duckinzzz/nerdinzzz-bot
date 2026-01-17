from groq import AsyncGroq

from core.bot_core import LLM_TOKEN, dp

client = AsyncGroq(api_key=LLM_TOKEN)


async def get_llm_response(user_prompt: str) -> str:
    system_prompt = (
        f"Ты — Nerdinzzz 🤓, LLM чат-бот на базе {dp['llm']}. "
        "Твой создатель - @duckinzzz. "
        "Ты умеешь быстро отвечать на текстовые сообщения и преобразовывать голосовые в текст. "
        "Отвечай кратко, ясно и по делу, максимум 3-4 предложения. "
        "Если нужен список - только ключевые пункты. "
        "Не задавай встречных вопросов, не объясняй свои действия. "
    )
    messages = [
        {
            "role": "system",
            "content": system_prompt.lower()
        },
        {"role": "user", "content": user_prompt}
    ]

    completion = await client.chat.completions.create(model=dp['llm'], messages=messages, temperature=1,
                                                      max_completion_tokens=1024, top_p=1,
                                                      stream=False, stop=None)

    return completion.choices[0].message.content
