"""
normalize.py — Text normalization only (no routing).

Handles generic rules:
  - spacing, capitalization, punctuation
  - abbreviations via aliases.py
  - word numbers, season/episode patterns
  - type hints for ranking (folder, video, image, …)

For intent/target parsing see parser.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from alias_engine import expand_aliases as apply_aliases

WORD_TO_NUM: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20",
    "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
}

TYPE_HINT_KEYWORDS: dict[str, str] = {
    "screenshot": "image",
    "photo": "image",
    "picture": "image",
    "image": "image",
    "video": "video",
    "movie": "video",
    "film": "video",
    "song": "audio",
    "music": "audio",
    "audio": "audio",
    "document": "document",
    "pdf": "document",
    "folder": "folder",
    "directory": "folder",
    "project": "folder",
    "app": "application",
    "application": "application",
    "program": "application",
}

FILLER_WORDS = frozenset({"my", "the", "a", "an", "me", "please", "of"})


@dataclass
class NormalizedQuery:
    """Normalized target string for local search + ranking."""

    raw: str
    intent: str
    route: str
    normalized: str
    tokens: list[str] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)
    season: str | None = None
    episode: str | None = None
    version: str | None = None
    extension: str | None = None
    wants_latest: bool = False
    type_hint: str | None = None


def normalize_input(text: str) -> str:
    """
    First pipeline step: clean user text for parsing.
    - lowercase
    - collapse spaces
    - apply aliases
    - strip punctuation at edges
    """
    t = text.strip().lower()
    t = re.sub(r"[^\w\s.\-:/\\]", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = apply_aliases(t)
    return t.strip()


def normalize_name(text: str) -> str:
    """Flatten a filename for comparison."""
    t = text.lower()
    t = re.sub(r"[\s._\-]+", " ", t)
    return " ".join(t.split())


def build_search_query(target: str, intent: str, route: str) -> NormalizedQuery:
    """Build ranking query from extracted target + route."""
    raw = target.strip()
    text = apply_aliases(raw.lower())
    text = _words_to_numbers(text)
    text = _normalize_season_episode_phrases(text)

    wants_latest = any(w in text for w in ("latest", "newest", "most recent", "last"))
    if wants_latest:
        text = re.sub(r"\b(latest|newest|most recent|last)\b", " ", text)
        text = " ".join(text.split())

    type_hint = _detect_type_hint(text)
    if route == "local_folder":
        type_hint = "folder"
    elif route == "local_media":
        type_hint = type_hint or "video"

    extension = _parse_extension(text)
    season, episode = _parse_season_episode_codes(text)
    version = _parse_version(text)

    tokens = re.findall(r"[a-z0-9]+", text)
    numbers = re.findall(r"\d+", text)
    tokens = [t for t in tokens if t not in FILLER_WORDS]

    return NormalizedQuery(
        raw=raw,
        intent=intent,
        route=route,
        normalized=text,
        tokens=tokens,
        numbers=numbers,
        season=season,
        episode=episode,
        version=version,
        extension=extension,
        wants_latest=wants_latest,
        type_hint=type_hint,
    )


def looks_like_ai_chat(text: str) -> bool:
    """True when the line should skip web fallback and use AI."""
    lower = text.lower().strip()
    if lower.endswith("?"):
        return True
    starters = (
        "what ", "why ", "how ", "who ", "when ", "where ",
        "explain ", "tell me ", "describe ", "can you ",
        "help me understand", "write a ", "create a ",
    )
    return any(lower.startswith(s) for s in starters)


def _words_to_numbers(text: str) -> str:
    for word, digit in WORD_TO_NUM.items():
        text = re.sub(rf"\b{word}\b", digit, text)
    return text


def _normalize_season_episode_phrases(text: str) -> str:
    def season_repl(m: re.Match) -> str:
        return f"s{int(m.group(1)):02d}"
        return f" s{int(m.group(1)):02d} "

    def episode_repl(m: re.Match) -> str:
        return f"e{int(m.group(1)):02d}"
        return f" e{int(m.group(1)):02d} "

    text = re.sub(r"\bseason\s+(\d{1,2})\b", season_repl, text)
    text = re.sub(r"\bepisode\s+(\d{1,2})\b", episode_repl, text)
    return text
    text = re.sub(r"\bseason\s*(\d{1,2})\b", season_repl, text, flags=re.I)
    text = re.sub(r"\b(?:episode|ep|e)\s*(\d{1,2})\b", episode_repl, text, flags=re.I)
    text = re.sub(r"\bs\s*(\d{1,2})\b", season_repl, text, flags=re.I)
    return " ".join(text.split())


def _detect_type_hint(text: str) -> str | None:
    for word, hint in TYPE_HINT_KEYWORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return hint
    return None


def _parse_extension(text: str) -> str | None:
    m = re.search(r"\.([a-z0-9]{2,5})\b", text)
    return f".{m.group(1)}" if m else None


def _parse_season_episode_codes(text: str) -> tuple[str | None, str | None]:
    m = re.search(r"s(\d{1,2})\s*e(?:p)?\s*(\d{1,2})", text)
    if m:
        return m.group(1).zfill(2), m.group(2).zfill(2)
    m = re.search(r"(\d{1,2})\s*x\s*(\d{1,2})", text)
    if m:
        return m.group(1).zfill(2), m.group(2).zfill(2)
    season = episode = None
    m = re.search(r"\bs(\d{2})\b", text)
    if m:
        season = m.group(1)
    m = re.search(r"\be(\d{2})\b", text)
    if m:
        episode = m.group(1)
    return season, episode


def _parse_version(text: str) -> str | None:
    m = re.search(r"\bv(\d+)\b", text)
    return m.group(1) if m else None
