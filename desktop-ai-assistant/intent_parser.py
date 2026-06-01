"""Semantic intent understanding for ambiguous desktop requests."""

from __future__ import annotations

import re

from intent_schema import (
    IntentSchema,
    SEMANTIC_OPEN_APP,
    SEMANTIC_OPEN_DOCUMENT,
    SEMANTIC_PLAY_MEDIA,
    SEMANTIC_SEARCH_WEB,
    SEMANTIC_UNKNOWN,
    SEMANTIC_WATCH_MEDIA,
)
from normalize import normalize_input
from ollama_adapter import understand_intent
from parser import parse_command
from system_apps import resolve_system_app

_MEDIA_WORDS = frozenset({
    "video", "videos", "movie", "movies", "show", "shows", "episode",
    "episodes", "anime", "watch", "fun",
})
_MUSIC_WORDS = frozenset({"music", "song", "songs", "audio", "playlist"})
_DOC_WORDS = frozenset({"note", "notes", "pdf", "document", "documents", "chemistry"})
_NONSENSE_RE = re.compile(r"^[a-z]{7,}$")


def parse_intent(text: str) -> IntentSchema:
    """
    Return structured understanding only.

    Ollama is tried first through ollama_adapter. If unavailable or uncertain,
    deterministic local heuristics provide a safe fallback.
    """
    llm = understand_intent(text)
    if llm and llm.normalized_intent() != SEMANTIC_UNKNOWN and llm.confidence >= 0.55:
        return llm
    return _heuristic_intent(text)


def _heuristic_intent(text: str) -> IntentSchema:
    normalized = normalize_input(text)
    cmd = parse_command(text, normalized)
    target = cmd.target or normalized
    tokens = set(re.findall(r"[a-z0-9]+", normalized))

    if resolve_system_app(target):
        return IntentSchema(SEMANTIC_OPEN_APP, target=target, confidence=0.95)

    if _looks_like_nonsense(normalized):
        return IntentSchema(SEMANTIC_UNKNOWN, query=normalized, confidence=0.1)

    if cmd.intent == "search" or cmd.search_query:
        query = cmd.search_query or target
        return IntentSchema(
            SEMANTIC_SEARCH_WEB,
            query=query,
            platform=cmd.platform,
            confidence=0.9,
        )

    if tokens & _MUSIC_WORDS:
        return IntentSchema(
            SEMANTIC_PLAY_MEDIA,
            target=_strip_light_verbs(target),
            query=_strip_light_verbs(target),
            confidence=0.82,
        )

    if tokens & _MEDIA_WORDS:
        query = _strip_light_verbs(target) or target
        intent = SEMANTIC_WATCH_MEDIA if "watch" in tokens or "fun" in tokens else SEMANTIC_SEARCH_WEB
        return IntentSchema(
            intent,
            target=query,
            query=query,
            platform="youtube" if "video" in tokens or "videos" in tokens else None,
            confidence=0.78,
        )

    if tokens & _DOC_WORDS:
        return IntentSchema(
            SEMANTIC_OPEN_DOCUMENT,
            target=target,
            query=target,
            confidence=0.72,
        )

    return IntentSchema(SEMANTIC_UNKNOWN, query=target, confidence=0.2)


def _looks_like_nonsense(text: str) -> bool:
    compact = text.replace(" ", "")
    if not _NONSENSE_RE.match(compact):
    if len(compact) < 4:
        return False
    if not _NONSENSE_RE.match(compact) and len(compact) > 7:
        # High length without spaces and no vowels/strange pattern
        vowels = sum(1 for ch in compact if ch in "aeiou")
        if vowels == 0: return True

    vowels = sum(1 for ch in compact if ch in "aeiou")
    return vowels == 0 or vowels / max(len(compact), 1) < 0.2


def _strip_light_verbs(text: str) -> str:
    return re.sub(
        r"^(?:lets|let s|let's|please|play|watch|open|search)\s+",
        "",
        text.strip(),
        flags=re.I,
    ).strip()
