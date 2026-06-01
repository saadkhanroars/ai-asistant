"""
ai.py — Talks to OpenAI and returns assistant replies.

Uses environment variables for the API key and model name.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

# Load variables from .env in the project folder
load_dotenv()

# Low-cost model; override with OPENAI_MODEL in .env if you prefer
DEFAULT_MODEL = "gpt-4.1-mini"


def has_api_key() -> bool:
    """True when a usable OpenAI API key is configured."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(api_key) and api_key != "your_api_key_here"


def get_client() -> OpenAI:
    """Create an OpenAI client. Raises a clear error if the key is missing."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not has_api_key():
        raise ValueError(
            "OPENAI_API_KEY is missing or still set to the placeholder.\n"
            "Copy .env.example to .env and add your real API key.\n"
            "Local search and settings routing work without a key."
        )
    return OpenAI(api_key=api_key)


def get_model_name() -> str:
    """Model from .env or the default."""
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def offline_ai_message() -> str:
    """Friendly reply when AI is unavailable (no API key)."""
    return (
        "AI chat is optional and not configured (no OPENAI_API_KEY). "
        "I can still open apps, files, folders, Windows settings, and search the web. "
        "Try: open bluetooth settings, open downloads, launch chrome, search cats on brave."
    )


def ask_ai(messages: list[dict[str, str]]) -> str:
    """
    Send conversation history to OpenAI and return the assistant text.

    messages: list like [{"role": "user", "content": "..."}, ...]
    """
    if not has_api_key():
        return offline_ai_message()

    client = get_client()
    model = get_model_name()

    # Optional system message — customize personality here later
    api_messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful desktop assistant. "
                "Keep answers concise and friendly."
            ),
        },
        *messages,
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=api_messages,
        )
        choice = response.choices[0].message.content
        return (choice or "").strip() or "(No response from the model.)"
    except Exception as err:
        # Beginner-friendly error instead of a long stack trace
        return f"AI error: {err}"

    # Future ideas:
    # - streaming responses (print tokens as they arrive)
    # - retry on rate limits
    # - token usage logging
