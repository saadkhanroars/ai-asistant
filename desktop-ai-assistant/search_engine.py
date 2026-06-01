"""
search_engine.py — Fast search against the SQLite index.

Search flow (no live disk walk):
  1. Load / cache index rows from database
  2. SQL pre-filter by query tokens (optional)
  3. Convert rows -> SearchItem
  4. ranking.py scores and picks the best match

Debug: logs candidate count and search time.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from database import connect, fetch_all_items, fetch_by_token_prefix, index_exists, init_schema
from debug_log import is_debug_enabled
from normalize import NormalizedQuery
from models import SearchItem


@dataclass
class SearchStats:
    """Debug info for one search."""

    candidates: int = 0
    total_indexed: int = 0
    elapsed_ms: float = 0.0


_cache: list[SearchItem] | None = None
_last_stats = SearchStats()


def invalidate_cache() -> None:
    """Call after full rebuild so next search reloads DB."""
    global _cache
    _cache = None


def patch_cache_item(row: dict) -> None:
    """
    Update one entry in memory after incremental index change.
    Search keeps working without reloading the whole index.
    """
    global _cache
    if _cache is None:
        return
    path = os.path.normcase(row["path"])
    item = _dict_to_item(row)
    for i, existing in enumerate(_cache):
        if os.path.normcase(existing.path) == path:
            _cache[i] = item
            return
    _cache.append(item)


def remove_cache_path(path: str) -> None:
    """Remove one path from memory cache."""
    global _cache
    if _cache is None:
        return
    key = os.path.normcase(path)
    _cache = [i for i in _cache if os.path.normcase(i.path) != key]
    # Also drop children if folder removed
    prefix = key + os.sep
    _cache = [i for i in _cache if not os.path.normcase(i.path).startswith(prefix)]


def _dict_to_item(row: dict) -> SearchItem:
    return SearchItem(
        name=row["name"],
        path=row["path"],
        kind=row["kind"],
        mtime=float(row.get("mtime") or 0),
        search_text=row.get("search_text") or "",
    )


def load_index_cache() -> int:
    """Load all items into memory for instant repeated searches."""
    global _cache
    if not index_exists():
        _cache = []
        return 0

    conn = connect()
    init_schema(conn)
    rows = fetch_all_items(conn)
    conn.close()

    _cache = [_row_to_item(r) for r in rows]
    return len(_cache)


def get_last_search_stats() -> SearchStats:
    return _last_stats


def search_index(parsed: NormalizedQuery) -> list[SearchItem]:
    """
    Search the index for matches to normalized query tokens.
    Returns candidate list for ranking.py.
    """
    global _last_stats
    t0 = time.perf_counter()

    if _cache is None:
        load_index_cache()

    total = len(_cache or [])
    if total == 0:
        _last_stats = SearchStats(0, 0, 0.0)
        return []

    # Token pre-filter via SQL when index is large; else filter in memory
    if total > 3000 and parsed.tokens:
        candidates = _sql_prefilter(parsed.tokens)
    else:
        candidates = _memory_filter(_cache or [], parsed.tokens)

    elapsed = (time.perf_counter() - t0) * 1000
    _last_stats = SearchStats(
        candidates=len(candidates),
        total_indexed=total,
        elapsed_ms=round(elapsed, 2),
    )

    if is_debug_enabled():
        print(
            f"[search] {len(candidates)} candidates from {total} indexed "
            f"({elapsed:.1f} ms)"
        )

    return candidates


def _sql_prefilter(tokens: list[str]) -> list[SearchItem]:
    conn = connect()
    init_schema(conn)
    rows = fetch_by_token_prefix(conn, tokens)
    conn.close()
    return [_row_to_item(r) for r in rows]


def _memory_filter(items: list[SearchItem], tokens: list[str]) -> list[SearchItem]:
    if not tokens:
        return items
    out: list[SearchItem] = []
    for item in items:
        text = (item.search_text + " " + item.name).lower()
        if any(t in text for t in tokens if len(t) >= 2 or t.isdigit()):
            out.append(item)
    return out


def _row_to_item(row) -> SearchItem:
    from type_mapper import map_kind_to_type

    kind = row["kind"]
    path = row["path"]
    item_type = row["category"] if row["category"] else map_kind_to_type(kind, path, row["name"])
    return SearchItem(
        name=row["name"],
        path=path,
        kind=kind,
        mtime=float(row["mtime"] or 0),
        search_text=row["search_text"] or "",
        item_type=item_type,
    )
