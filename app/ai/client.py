from openai import AsyncOpenAI
from app.ai.config import OPENAI_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def generate_response(messages: list):

    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS
    )

    return response.choices[0].message.content