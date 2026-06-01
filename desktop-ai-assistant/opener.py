"""
opener.py — Local execution step: search → rank → launch.

Returns (message, RankedMatch) only when match is reliable.
Otherwise None so router can try website/web fallback.
"""

from __future__ import annotations

from debug_log import is_debug_enabled
from launcher import launch_item
from normalize import build_search_query
from ranking import RankedMatch, find_best
from search import search_all
from search_config import MIN_MATCH_SCORE
from search_engine import get_last_search_stats


def try_local_open(
    target: str,
    intent: str = "open",
    route: str = "local_open",
) -> tuple[str | None, RankedMatch | None]:
    """
    Search disk, rank, open if reliable.
    Returns (status_message, match_info) or (None, None).
    """
    if not target.strip():
        return None, None

    parsed = build_search_query(target, intent=intent, route=route)
    items = search_all(parsed.normalized, parsed.tokens)

    if is_debug_enabled():
        stats = get_last_search_stats()
        print(
            f"[search] indexed={stats.total_indexed} "
            f"candidates={stats.candidates} time={stats.elapsed_ms}ms"
        )

    ranked = find_best(parsed, items, MIN_MATCH_SCORE)

    if ranked is None or not ranked.reliable:
        return None, None

    msg = launch_item(ranked.item, ranked.score)
    return msg, ranked
