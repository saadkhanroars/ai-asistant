"""
aliases.py — Map many names to one canonical search name.

How it works:
  1. You define CANONICAL_ALIASES: one real name -> list of alternate names.
  2. apply_aliases() rewrites the user's query before matching.
  3. Works for any app/file nickname — add rows as you discover them.

Windows system apps (settings, notepad, calc, …) live in system_apps.py
with launch commands and routing priority — not in this file.
"""

from __future__ import annotations

# canonical name (lowercase) -> alternate names users might say
CANONICAL_ALIASES: dict[str, list[str]] = {
    "visual studio code": ["vscode", "vs code", "vsc"],
    "google chrome": ["chrome", "google chrome browser"],
    "microsoft edge": ["edge", "msedge"],
    "adobe photoshop": ["photoshop", "ps"],
    "blender": ["blender 3d"],
    "spotify": ["spotify music"],
    "vlc": ["vlc media player"],
}

# Built automatically: alias -> canonical
_ALIAS_TO_CANONICAL: dict[str, str] = {}


def _build_alias_index() -> None:
    global _ALIAS_TO_CANONICAL
    if _ALIAS_TO_CANONICAL:
        return
    for canonical, aliases in CANONICAL_ALIASES.items():
        c = canonical.lower().strip()
        _ALIAS_TO_CANONICAL[c] = c
        for alias in aliases:
            _ALIAS_TO_CANONICAL[alias.lower().strip()] = c


def apply_aliases(text: str) -> str:
    """
    Replace known aliases in the query with their canonical form.
    "launch vscode" -> "launch visual studio code"
    """
    _build_alias_index()
    lower = text.lower()
    # Longest aliases first so "vs code" wins over "vs"
    for alias in sorted(_ALIAS_TO_CANONICAL, key=len, reverse=True):
        if alias in lower:
            canonical = _ALIAS_TO_CANONICAL[alias]
            lower = lower.replace(alias, canonical)
    return lower


def canonical_for(name: str) -> str:
    """Return canonical name if this string is a known alias."""
    _build_alias_index()
    key = name.lower().strip()
    return _ALIAS_TO_CANONICAL.get(key, key)


def register_alias(canonical: str, alias: str) -> None:
    """Add one alias at runtime (optional extension hook)."""
    _build_alias_index()
    c = canonical.lower().strip()
    a = alias.lower().strip()
    CANONICAL_ALIASES.setdefault(c, []).append(a)
    _ALIAS_TO_CANONICAL[a] = c
