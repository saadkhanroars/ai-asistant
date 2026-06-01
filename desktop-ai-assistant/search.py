"""
search.py — Public search API (queries the index via search_engine).

Live disk scanning was replaced by indexer + database + search_engine.
"""

from __future__ import annotations

from models import SearchItem
from normalize import NormalizedQuery
from search_engine import search_index

__all__ = ["SearchItem", "search_all"]


def search_all(query_normalized: str, tokens: list[str]) -> list[SearchItem]:
    """Search the local index for candidates matching the query."""
    parsed = NormalizedQuery(
        raw=query_normalized,
        intent="open",
        route="local_open",
        normalized=query_normalized,
        tokens=tokens,
    )
    return search_index(parsed)
