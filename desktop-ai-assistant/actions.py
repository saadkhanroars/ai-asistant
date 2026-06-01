"""
actions.py — Send every user line to the intent router first.

The router handles local + web actions. None = AI fallback in main.py.
"""

from router import handle_request


def try_run_action(user_text: str) -> str | None:
    """Return a message if handled locally; None if AI should answer."""
    return handle_request(user_text.strip())
