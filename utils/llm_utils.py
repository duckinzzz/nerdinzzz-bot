from groq import AsyncGroq

from core.bot_core import LLM_TOKEN

client = AsyncGroq(api_key=LLM_TOKEN)
system_prompt = (
    "Ты — Nerdinzzz 🤓, LLM чат-бот на базе openai/gpt-oss-120b. "
    "Ты отвечаешь коротко, ясно и по делу. "
    "Отвечай не больше 2–3 предложений, избегай лишних деталей и примеров, если их не требуют. "
    "Если ответ требует перечисления, используй только ключевые пункты. "
    "Не задавай встречных вопросов, не объясняй свои действия."
)

llm_model_name = "openai/gpt-oss-120b"


async def get_llm_response(user_prompt: str) -> str:
    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {"role": "user", "content": user_prompt}
    ]

    completion = await client.chat.completions.create(
        model=llm_model_name,
        messages=messages,
        temperature=1,
        max_completion_tokens=8192,
        top_p=1,
        reasoning_effort="medium",
        stream=False,
        stop=None
    )

    return completion.choices[0].message.content
