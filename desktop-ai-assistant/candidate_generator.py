"""
candidate_generator.py — Build candidate list from the SQLite index.

Does not rescan disk — uses search_engine (indexed data only).
"""

from __future__ import annotations

import re

from models import Candidate
from normalize import NormalizedQuery, build_search_query
from search import search_all
from search_engine import get_last_search_stats
from type_mapper import attach_type_to_item
from websites import is_known_website


def generate_index_candidates(
    target: str,
    intent: str,
    route: str,
    *,
    folder_hint: str | None = None,
) -> tuple[list[Candidate], dict]:
    """Load candidates from index; return (candidates, search_stats_dict)."""
    parsed = build_search_query(target, intent=intent, route=route)
    items = search_all(parsed.normalized, parsed.tokens)

    # Session context: "open latest image" after opening a folder
    if folder_hint and parsed.wants_latest:
        hint_norm = folder_hint.lower()
        in_folder = [i for i in items if hint_norm in i.path.lower()]
        if in_folder:
            items = in_folder

    for item in items:
        attach_type_to_item(item)

    candidates = [
        Candidate(
            name=item.name,
            path=item.path,
            item_type=item.item_type,
            source="index",
            mtime=item.mtime,
            search_text=item.search_text,
        )
        for item in items
    ]

    stats = get_last_search_stats()
    meta = {
        "candidates": stats.candidates,
        "total_indexed": stats.total_indexed,
        "elapsed_ms": stats.elapsed_ms,
    }
    return candidates, meta


def website_candidate(name: str) -> Candidate | None:
    token = name.lower().replace(" ", "")
    if not is_known_website(token):
        return None
    return Candidate(
        name=token,
        path=token,
        item_type="website",
        source="website",
    )
