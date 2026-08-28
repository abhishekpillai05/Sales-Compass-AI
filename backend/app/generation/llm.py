import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3-32b",
)

GENERATION_TEMPERATURE = float(
    os.getenv(
        "GENERATION_TEMPERATURE",
        "0.2",
    )
)

# Lazy singleton — created on first call so missing key doesn't crash startup.
_groq_client: Groq | None = None


def _get_client() -> Groq:
    """Return the Groq client, raising a clear error if the key is missing."""
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set in backend/.env. "
                "Add GROQ_API_KEY=<your-key> to enable response generation."
            )
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


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

    client = _get_client()

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