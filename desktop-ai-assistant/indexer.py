"""
indexer.py — Filesystem indexer (build the searchable "map").

Indexing pipeline:
  scan folders
    → extract metadata (name, path, ext, mtime)
    → categorize (app, folder, video, …)
    → normalize searchable text
    → save to SQLite (database.py)

On startup: load existing index; build only if missing.
Manual: refresh index / rebuild index commands.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from database import (
    clear_items,
    connect,
    get_item_count,
    index_exists,
    init_schema,
    insert_items,
    save_build_metadata,
)
from debug_log import is_debug_enabled
from normalize import normalize_name
from search_config import (
    ALL_SEARCH_EXTENSIONS,
    CATEGORY_LABELS,
    EXTENSIONS,
    FOLDER_NICKNAMES,
    MAX_INDEX_FILES,
    MAX_PROGRAM_DEPTH,
    MAX_SEARCH_DEPTH,
    PROGRAM_ROOTS,
    START_MENU_ROOTS,
    all_index_roots,
    all_search_locations,
)


def ensure_index() -> dict[str, Any]:
    """
    Startup behavior:
      - If index missing -> full rebuild
      - Else -> load index + incremental startup_sync (repair stale rows)
    """
    if not index_exists():
        if is_debug_enabled():
            print("[index] No index found — building first-time index…")
        return rebuild_index()

    stats = _stats_dict()
    if is_debug_enabled():
        print(
            f"[index] Loaded existing index: {stats['item_count']} items "
            f"(built {stats.get('built_at', '?')})"
        )

    from incremental_indexer import startup_sync

    sync = startup_sync()
    stats["startup_sync"] = sync
    return stats


def rebuild_index() -> dict[str, Any]:
    """Full rescan and replace database contents."""
    t0 = time.perf_counter()
    conn = connect()
    init_schema(conn)
    clear_items(conn)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    roots_indexed: list[str] = []

    # Well-known folder nicknames (downloads, desktop, …)
    for nickname, path in FOLDER_NICKNAMES.items():
        if os.path.isdir(path):
            row = row_from_path(path, display_name=nickname, source_root="nicknames")
            if row and _add_row(rows, seen, row):
                roots_indexed.append(path)

    # User + custom folders (recursive)
    for root in all_search_locations():
        if os.path.isdir(root):
            roots_indexed.append(root)
            _scan_tree(root, root, rows, seen, MAX_SEARCH_DEPTH, include_folders=True)

    # Start Menu apps
    for root in START_MENU_ROOTS:
        if root and os.path.isdir(root):
            roots_indexed.append(root)
            _scan_tree(
                root, root, rows, seen, MAX_SEARCH_DEPTH,
                extensions={".lnk", ".exe"},
            )

    # Program Files (shallow exe)
    for root in PROGRAM_ROOTS:
        if os.path.isdir(root):
            roots_indexed.append(root)
            _scan_tree(
                root, root, rows, seen, MAX_PROGRAM_DEPTH,
                extensions={".exe"},
            )

    insert_items(conn, rows)
    count = get_item_count(conn)
    save_build_metadata(conn, roots_indexed, count)
    conn.close()

    from search_engine import invalidate_cache, load_index_cache

    invalidate_cache()
    load_index_cache()

    elapsed = time.perf_counter() - t0
    summary = {
        "item_count": count,
        "elapsed_sec": round(elapsed, 2),
        "roots": roots_indexed,
        "rebuilt": True,
    }
    if is_debug_enabled():
        print(f"[index] Rebuilt: {count} items in {elapsed:.2f}s")
    return summary


def refresh_index() -> dict[str, Any]:
    """Manual refresh — incremental sync only (no full rescan)."""
    from incremental_indexer import incremental_refresh

    return incremental_refresh()


def show_indexed_folders() -> str:
    """Human-readable list of configured and indexed roots."""
    lines = ["Indexed / configured folders:"]
    for root in all_index_roots():
        tag = "OK" if os.path.isdir(root) else "MISSING"
        lines.append(f"  [{tag}] {root}")
    stats = _stats_dict()
    lines.append(f"\nDatabase: {stats.get('item_count', 0)} items")
    lines.append(f"Last built: {stats.get('built_at', 'never')}")
    return "\n".join(lines)


def _stats_dict() -> dict[str, Any]:
    from database import get_index_stats

    return get_index_stats()


def _scan_tree(
    root: str,
    current: str,
    rows: list[dict],
    seen: set[str],
    max_depth: int,
    extensions: set[str] | None = None,
    include_folders: bool = False,
) -> None:
    if len(rows) >= MAX_INDEX_FILES:
        return
    root = os.path.normpath(root)

    from incremental_indexer import IGNORE_DIR_NAMES, should_ignore_path

    for dirpath, dirnames, filenames in os.walk(current):
        if len(rows) >= MAX_INDEX_FILES:
            return
        depth = _depth(root, dirpath)
        if depth >= max_depth:
            dirnames.clear()

        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORE_DIR_NAMES and not d.startswith(".")
        ]

        if include_folders:
            for name in dirnames:
                full = os.path.join(dirpath, name)
                row = row_from_path(full, source_root=root)
                _add_row(rows, seen, row)

        use_ext = extensions if extensions is not None else ALL_SEARCH_EXTENSIONS
        for filename in filenames:
            if len(rows) >= MAX_INDEX_FILES:
                return
            ext = Path(filename).suffix.lower()
            if use_ext and ext not in use_ext:
                continue
            full = os.path.join(dirpath, filename)
            if should_ignore_path(full):
                continue
            row = row_from_path(full, source_root=root)
            _add_row(rows, seen, row)


def row_from_path(
    path: str,
    display_name: str | None = None,
    source_root: str = "",
) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    kind = categorize(path)
    name = display_name or Path(path).stem or Path(path).name
    ext = Path(path).suffix.lower() if not os.path.isdir(path) else ""
    search_text = normalize_name(name)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    category = CATEGORY_LABELS.get(kind, "document")
    return {
        "name": name,
        "path": path,
        "extension": ext,
        "kind": kind,
        "category": category,
        "search_text": search_text,
        "mtime": mtime,
        "source_root": source_root,
    }


def categorize(path: str) -> str:
    """Map path to kind: folder, shortcut, application, video, …"""
    if os.path.isdir(path):
        return "folder"
    ext = Path(path).suffix.lower()
    for kind, exts in EXTENSIONS.items():
        if ext in exts:
            return kind
    return "other"


def _add_row(rows: list, seen: set[str], row: dict | None) -> bool:
    if not row:
        return False
    key = os.path.normcase(row["path"])
    if key in seen:
        return False
    seen.add(key)
    rows.append(row)
    return True


def _depth(root: str, dirpath: str) -> int:
    rel = os.path.relpath(dirpath, root)
    if rel == ".":
        return 0
    return rel.count(os.sep) + 1
