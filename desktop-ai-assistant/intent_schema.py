"""Structured semantic intent returned by understanding layers."""

from __future__ import annotations

from dataclasses import dataclass


SEMANTIC_OPEN_APP = "open_app"
SEMANTIC_OPEN_DOCUMENT = "open_document"
SEMANTIC_WATCH_MEDIA = "watch_media"
SEMANTIC_SEARCH_WEB = "search_web"
SEMANTIC_PLAY_MEDIA = "play_media"
SEMANTIC_UNKNOWN = "unknown"

SEMANTIC_INTENTS = frozenset({
    SEMANTIC_OPEN_APP,
    SEMANTIC_OPEN_DOCUMENT,
    SEMANTIC_WATCH_MEDIA,
    SEMANTIC_SEARCH_WEB,
    SEMANTIC_PLAY_MEDIA,
    SEMANTIC_UNKNOWN,
})


@dataclass(frozen=True)
class IntentSchema:
    """LLM/semantic understanding only; router remains authoritative."""

    intent: str
    target: str = ""
    query: str = ""
    platform: str | None = None
    confidence: float = 0.0
    source: str = "heuristic"

    def normalized_intent(self) -> str:
        return self.intent if self.intent in SEMANTIC_INTENTS else SEMANTIC_UNKNOWN
