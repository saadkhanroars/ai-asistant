"""
alias_engine.py — Expand abbreviations before matching.

Data-driven map: alias -> canonical phrase.
Add entries to ALIAS_MAP to extend (yt, vscode, docs, pics, …).
"""

from __future__ import annotations

import re

# alias -> canonical replacement (applied to full query, longest first)
ALIAS_MAP: dict[str, str] = {
    "yt": "youtube",
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "vsc": "visual studio code",
    "docs": "documents",
    "pics": "pictures",
    "dl": "downloads",
    "calc": "calculator",
    "ps": "photoshop",
    "ff": "firefox",
    "win settings": "settings",
    "windows settings": "settings",
    "bt": "bluetooth",
    "wi-fi": "wifi",
    "night mode": "night light",
    "volume": "sound",
    "brightness": "display",
}

_INDEX: dict[str, str] = {}


def _build_index() -> None:
    global _INDEX
    if _INDEX:
        return
    for alias, canonical in ALIAS_MAP.items():
        _INDEX[alias.lower()] = canonical.lower()


def expand_aliases(text: str) -> str:
    """Replace known aliases in the query string."""
    _build_index()
    lower = text.lower()
    for alias in sorted(_INDEX, key=len, reverse=True):
        pattern = _alias_pattern(alias)
        lower = pattern.sub(_INDEX[alias], lower)
    return lower


def canonical_token(token: str) -> str:
    _build_index()
    return _INDEX.get(token.lower(), token.lower())


def _alias_pattern(alias: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in alias.split()]
    body = r"\s+".join(parts)
    return re.compile(rf"(?<!\w){body}(?!\w)")
