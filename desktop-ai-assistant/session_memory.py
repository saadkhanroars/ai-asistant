"""
session_memory.py — Short-term session state for routing (not AI chat history).

Memory flow:
  1. Router completes an action (open, search, play, settings, …).
  2. SessionMemory.record_* updates structured fields.
  3. reference_resolver reads this state on the next user line.

Cleared when the assistant process exits. No long-term persistence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from debug_log import is_debug_enabled
from models import Candidate, ScoredCandidate, SearchItem

# What kind of thing the user last interacted with
ContextType = Literal[
    "none",
    "file",
    "folder",
    "media",
    "app",
    "search",
    "browser",
    "settings",
    "website",
    "disambiguation",
]

ActionType = Literal[
    "none",
    "open",
    "play",
    "search",
    "launch",
    "settings",
    "browser",
    "close",
    "select",
]


@dataclass
class MemoryItem:
    """One selectable item (file, app, folder, …)."""

    name: str
    path: str
    item_type: str
    score: float = 0.0

    @classmethod
    def from_search_item(cls, item: SearchItem, score: float = 0.0) -> MemoryItem:
        kind = (item.item_type or item.kind or "document").lower()
        return cls(name=item.name, path=item.path or item.name, item_type=kind, score=score)

    @classmethod
    def from_candidate(cls, cand: Candidate, score: float = 0.0) -> MemoryItem:
        return cls(
            name=cand.name,
            path=cand.path,
            item_type=cand.item_type,
            score=score,
        )


@dataclass
class SessionState:
    """All short-term fields used for reference resolution."""

    last_opened_item: MemoryItem | None = None
    last_search_results: list[MemoryItem] = field(default_factory=list)
    last_selected_result: MemoryItem | None = None
    last_browser: str | None = None
    last_action: ActionType = "none"
    current_context_type: ContextType = "none"
    last_search_query: str | None = None
    last_search_platform: str | None = None
    last_app_name: str | None = None
    last_folder_path: str | None = None
    last_settings_name: str | None = None


def _memory_log(tag: str, detail: str) -> None:
    if is_debug_enabled():
        print(f"[{tag}] {detail}")


class SessionMemory:
    """Singleton-style session store for the running assistant."""

    def __init__(self) -> None:
        self._state = SessionState()

    @property
    def state(self) -> SessionState:
        return self._state

    # --- Recording (called by router after each action) ---------------------

    def record_open(
        self,
        item: SearchItem | MemoryItem,
        *,
        score: float = 0.0,
        browser: str | None = None,
    ) -> None:
        mem = (
            item
            if isinstance(item, MemoryItem)
            else MemoryItem.from_search_item(item, score)
        )
        self._state.last_opened_item = mem
        self._state.last_selected_result = mem
        self._state.last_action = "open"
        ctx = _context_type_for_item(mem)
        self._state.current_context_type = ctx
        if ctx == "folder":
            self._state.last_folder_path = mem.path
        if browser:
            self.record_browser(browser)
        _memory_log("memory updated", f"open {mem.name!r} ({ctx})")
        _memory_log("context type", ctx)

    def record_play(self, item: SearchItem | MemoryItem, *, score: float = 0.0) -> None:
        mem = (
            item
            if isinstance(item, MemoryItem)
            else MemoryItem.from_search_item(item, score)
        )
        self._state.last_opened_item = mem
        self._state.last_selected_result = mem
        self._state.last_action = "play"
        self._state.current_context_type = "media"
        _memory_log("memory updated", f"play {mem.name!r}")
        _memory_log("context type", "media")

    def record_search_results(
        self,
        scored: list[ScoredCandidate] | list[Candidate],
        *,
        limit: int = 10,
    ) -> None:
        items: list[MemoryItem] = []
        for entry in scored[:limit]:
            if isinstance(entry, ScoredCandidate):
                items.append(MemoryItem.from_candidate(entry.candidate, entry.score))
            else:
                items.append(MemoryItem.from_candidate(entry))
        self._state.last_search_results = items
        self._state.last_action = "select"
        self._state.current_context_type = "disambiguation"
        if items:
            self._state.last_selected_result = items[0]
        _memory_log(
            "memory updated",
            f"search_results count={len(items)}",
        )
        _memory_log("context type", "disambiguation")

    def record_search(
        self,
        query: str,
        platform: str | None = None,
        *,
        browser: str | None = None,
    ) -> None:
        self._state.last_search_query = query
        self._state.last_search_platform = platform
        self._state.last_action = "search"
        self._state.current_context_type = "search"
        if browser:
            self.record_browser(browser)
        _memory_log("memory updated", f"search {query!r} on {platform or 'web'}")
        _memory_log("context type", "search")

    def record_browser(self, browser: str) -> None:
        self._state.last_browser = browser.lower().strip()
        _memory_log("memory updated", f"browser={self._state.last_browser}")

    def record_app(self, app_name: str) -> None:
        self._state.last_app_name = app_name
        self._state.last_action = "launch"
        self._state.current_context_type = "app"
        _memory_log("memory updated", f"app={app_name!r}")
        _memory_log("context type", "app")

    def record_settings(self, setting_name: str) -> None:
        self._state.last_settings_name = setting_name
        self._state.last_action = "settings"
        self._state.current_context_type = "settings"
        _memory_log("memory updated", f"settings={setting_name!r}")
        _memory_log("context type", "settings")

    def record_website(self, site: str, browser: str | None = None) -> None:
        self._state.last_action = "browser"
        self._state.current_context_type = "website"
        if browser:
            self.record_browser(browser)
        _memory_log("memory updated", f"website={site!r}")

    # --- Queries for resolver ------------------------------------------------

    def get_item_by_ordinal(self, index: int) -> MemoryItem | None:
        """1-based index into last_search_results."""
        results = self._state.last_search_results
        if not results or index < 1 or index > len(results):
            return None
        return results[index - 1]

    def get_primary_item(self) -> MemoryItem | None:
        """Best default target for it/that/this."""
        s = self._state
        if s.last_opened_item:
            return s.last_opened_item
        if s.last_selected_result:
            return s.last_selected_result
        if s.last_search_results:
            return s.last_search_results[0]
        return None

    def get_path_for_browser(self) -> str | None:
        item = self.get_primary_item()
        if item and item.path and os.path.isfile(item.path):
            return item.path
        return item.path if item else None

    def hint_folder_for_latest(self) -> str | None:
        return self._state.last_folder_path

    def clear(self) -> None:
        self._state = SessionState()


def _context_type_for_item(item: MemoryItem) -> ContextType:
    t = item.item_type.lower()
    if t == "folder":
        return "folder"
    if t in ("video", "audio"):
        return "media"
    if t in ("app", "system_app", "application", "shortcut"):
        return "app"
    if t == "image":
        return "file"
    return "file"


_session: SessionMemory | None = None


def get_session_memory() -> SessionMemory:
    global _session
    if _session is None:
        _session = SessionMemory()
    return _session
