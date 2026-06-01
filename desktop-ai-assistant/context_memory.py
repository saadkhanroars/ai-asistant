"""
context_memory.py — Backward-compatible facade over session_memory.

New code should use:
  session_memory.get_session_memory()
  reference_resolver.resolve_user_input()
"""

from __future__ import annotations

from models import SearchItem
from reference_resolver import hint_for_folder_latest, resolve_user_input
from session_memory import MemoryItem, SessionMemory, get_session_memory


class ContextMemory:
    """Thin wrapper; delegates to SessionMemory."""

    def __init__(self) -> None:
        self._session = get_session_memory()

    @property
    def context(self):
        return self._session.state

    def record_open_item(self, item: SearchItem, *, browser: str | None = None) -> None:
        self._session.record_open(item, browser=browser)

    def record_top_search_result(self, name: str, path: str, item_type: str) -> None:
        self._session.record_search_results(
            [MemoryItem(name=name, path=path, item_type=item_type)]
        )

    def record_browser(self, browser: str) -> None:
        self._session.record_browser(browser)

    def record_search(self, query: str, platform: str | None = None) -> None:
        self._session.record_search(query, platform)

    def record_app(self, app_name: str) -> None:
        self._session.record_app(app_name)

    def record_settings(self, setting_name: str) -> None:
        self._session.record_settings(setting_name)

    def get_last_path(self) -> str | None:
        return self._session.get_path_for_browser()

    def resolve_references(self, user_text: str) -> str:
        return resolve_user_input(user_text, self._session).text

    def hint_for_folder_latest(self, user_text: str) -> str | None:
        return hint_for_folder_latest(user_text, self._session)

    def clear(self) -> None:
        self._session.clear()


def get_context_memory() -> ContextMemory:
    return ContextMemory()
