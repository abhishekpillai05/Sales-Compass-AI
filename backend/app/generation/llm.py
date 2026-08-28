import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3.6-27b",
)

GENERATION_TEMPERATURE = float(
    os.getenv(
        "GENERATION_TEMPERATURE",
        "0.2",
    )
)


if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is not set in .env"
    )


client = Groq(
    api_key=GROQ_API_KEY
)


def generate_llm_response(
    messages: list[dict],
    temperature: float | None = None,
) -> str:
    """
    Send messages to Groq and return
    the generated response.
    """

    if temperature is None:
        temperature = GENERATION_TEMPERATURE

    try:

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
        )

        return completion.choices[0].message.content

    except Exception as e:

        raise RuntimeError(
            f"Groq response generation failed: {str(e)}"
        ) from e