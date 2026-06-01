"""
memory.py — Keeps chat history for the current terminal session.

Each user message and assistant reply is stored so the AI can see
context from earlier in the same run. History is cleared when you exit.
"""


class SessionMemory:
    """Simple in-memory list of OpenAI-style chat messages."""

    def __init__(self) -> None:
        # Each item: {"role": "user" | "assistant", "content": "..."}
        self._messages: list[dict[str, str]] = []

    def add_user(self, text: str) -> None:
        """Remember something the user said."""
        self._messages.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        """Remember something the assistant replied."""
        self._messages.append({"role": "assistant", "content": text})

    def get_messages(self) -> list[dict[str, str]]:
        """Return a copy of the conversation (safe to pass to the API)."""
        return list(self._messages)

    def clear(self) -> None:
        """Wipe history — useful for a future 'reset' command."""
        self._messages.clear()

    def message_count(self) -> int:
        """How many messages are stored (for debugging or UI later)."""
        return len(self._messages)

    # Future ideas:
    # - save/load history to a JSON file
    # - limit history length to save tokens
    # - add a system prompt stored at index 0
