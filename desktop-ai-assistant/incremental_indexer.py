"""
incremental_indexer.py — Update the index without full rescans.

Update flow:
  1. Filesystem event (watcher) or startup sync
  2. Decide: add / update / delete / rename
  3. Touch only affected rows in SQLite
  4. Patch in-memory search cache (search stays fast)

Synchronization logic (startup):
  - Load existing index
  - Remove DB entries whose files were deleted
  - Re-index entries whose mtime changed (batched, lightweight)
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

from database import (
    connect,
    delete_by_path,
    delete_under_prefix,
    fetch_all_paths,
    get_item_by_path,
    init_schema,
    update_item_count_meta,
    upsert_item,
)
from debug_log import is_debug_enabled
from indexer import row_from_path
from search_config import (
    ALL_SEARCH_EXTENSIONS,
    INDEX_DB_PATH,
    PROJECT_ROOT,
    STARTUP_SYNC_BATCH,
    all_search_locations,
    watch_paths,
)
from search_engine import patch_cache_item, remove_cache_path

_lock = threading.Lock()
_index_write_depth = 0

# Directory name segments to skip (anywhere in path)
IGNORE_DIR_NAMES = frozenset({
    "__pycache__", ".git", ".venv", "venv",
    "node_modules", ".cursor", ".idea", ".vscode",
    "__pypackages__", ".eggs", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".tox", "htmlcov",
    ".cache", "site-packages", "logs", "log", "tmp", "temp",
})

_PROJECT_ROOT_NORM = PROJECT_ROOT

# File extensions never indexed or watched
IGNORE_EXTENSIONS = frozenset({
    ".db", ".db-journal", ".db-wal", ".db-shm",
    ".log", ".tmp", ".temp", ".cache",
    ".pyc", ".pyo", ".pyd",
    ".swp", ".swo", ".lock",
})

# Basenames always ignored (assistant index + SQLite sidecars)
IGNORE_FILENAMES = frozenset({
    "desktop_index.db",
    "desktop_index.db-journal",
    "desktop_index.db-wal",
    "desktop_index.db-shm",
})

# Absolute paths derived from INDEX_DB_PATH (normalized at import)
_INDEX_DB_NORM = os.path.normcase(os.path.normpath(INDEX_DB_PATH))
_INDEX_DB_BASENAMES = frozenset(
    os.path.basename(p) for p in (
        _INDEX_DB_NORM,
        _INDEX_DB_NORM + "-journal",
        _INDEX_DB_NORM + "-wal",
        _INDEX_DB_NORM + "-shm",
    )
) | IGNORE_FILENAMES


def should_ignore_path(path: str) -> bool:
    """
    True if this path must never be watched or indexed.
    Prevents self-triggered loops from desktop_index.db and dev caches.
    """
    if not path:
        return True

    norm = os.path.normcase(os.path.normpath(path))
    base = os.path.basename(norm)

    # Never watch or index the assistant's own project tree
    if norm == _PROJECT_ROOT_NORM or norm.startswith(_PROJECT_ROOT_NORM + os.sep):
        return True

    if base in _INDEX_DB_BASENAMES:
        return True
    if norm == _INDEX_DB_NORM or norm.startswith(_INDEX_DB_NORM + "-"):
        return True

    parts = norm.split(os.sep)
    if any(part in IGNORE_DIR_NAMES for part in parts):
        return True

    if not os.path.isdir(norm):
        ext = Path(norm).suffix.lower()
        if ext in IGNORE_EXTENSIONS:
            return True
        # SQLite journal pattern: *.db-journal
        if ".db-" in base.lower():
            return True

    return False


def is_index_write_active() -> bool:
    """True while the assistant is writing to the index (ignore echo events)."""
    return _index_write_depth > 0


def should_index_path(path: str) -> bool:
    """
    True if this path belongs in the index.
    Watches user folders + Start Menu; skips unknown extensions for files.
    """
    path = os.path.normpath(path)
    if should_ignore_path(path):
        return False
    if not _under_watch_root(path):
        return False
    if os.path.isdir(path):
        return True
    ext = Path(path).suffix.lower()
    return ext in ALL_SEARCH_EXTENSIONS or ext in {".exe", ".lnk"}


def _under_watch_root(path: str) -> bool:
    path = os.path.normcase(os.path.normpath(path))
    for root in watch_paths():
        root_norm = os.path.normcase(os.path.normpath(root))
        if path == root_norm or path.startswith(root_norm + os.sep):
            return True
    return False


def find_source_root(path: str) -> str:
    path = os.path.normpath(path)
    best = ""
    for root in watch_paths():
        root = os.path.normpath(root)
        if path.startswith(root) and len(root) > len(best):
            best = root
    return best


def upsert_path(path: str) -> bool:
    """
    Add or update one file/folder in the index.
    Returns True if indexed.
    """
    path = os.path.normpath(path)
    if not should_index_path(path) or not os.path.exists(path):
        return False

    row = row_from_path(path, source_root=find_source_root(path))
    if not row:
        return False

    t0 = time.perf_counter()
    global _index_write_depth
    with _lock:
        _index_write_depth += 1
        try:
            conn = connect()
            init_schema(conn)
            upsert_item(conn, row)
            update_item_count_meta(conn)
            conn.close()
            patch_cache_item(row)
        finally:
            _index_write_depth -= 1

    if is_debug_enabled():
        ms = (time.perf_counter() - t0) * 1000
        print(f"[index+] updated {Path(path).name} ({ms:.1f} ms)")

    return True


def remove_path(path: str) -> None:
    """Remove one path from the index (delete or move away)."""
    path = os.path.normpath(path)
    t0 = time.perf_counter()
    deleted = 0
    global _index_write_depth
    with _lock:
        _index_write_depth += 1
        try:
            conn = connect()
            init_schema(conn)
            deleted = delete_by_path(conn, path)
            if not deleted:
                deleted = delete_under_prefix(conn, path)
            update_item_count_meta(conn)
            conn.close()
            remove_cache_path(path)
        finally:
            _index_write_depth -= 1

    if is_debug_enabled() and deleted:
        ms = (time.perf_counter() - t0) * 1000
        print(f"[index-] removed {path} ({deleted} rows, {ms:.1f} ms)")


def handle_move(src: str, dest: str) -> None:
    """Rename/move: drop old path, index new path."""
    if is_debug_enabled():
        print(f"[index~] move {src} -> {dest}")
    remove_path(src)
    if dest and os.path.exists(dest):
        upsert_path(dest)


def handle_filesystem_event(event_type: str, src: str, dest: str | None = None) -> None:
    """
    Entry point from watcher.py for create / modify / delete / move.
    """
    if is_index_write_active():
        return
    if should_ignore_path(src) or (dest and should_ignore_path(dest)):
        return

    if is_debug_enabled():
        print(f"[watch] {event_type}: {src}" + (f" -> {dest}" if dest else ""))

    if event_type == "moved" and dest:
        handle_move(src, dest)
        return
    if event_type == "deleted":
        remove_path(src)
        return
    if event_type in ("created", "modified"):
        if os.path.exists(src):
            upsert_path(src)
        else:
            remove_path(src)


def startup_sync() -> dict[str, Any]:
    """
    Startup synchronization:
      - Verify watched folders exist
      - Remove index rows for missing files (repair)
      - Re-index a batch of files whose mtime changed
    Does NOT rescan the whole PC.
    """
    t0 = time.perf_counter()
    removed = 0
    updated = 0
    checked = 0

    global _index_write_depth
    with _lock:
        _index_write_depth += 1
        try:
            conn = connect()
            init_schema(conn)
            paths = fetch_all_paths(conn)

            for path in paths:
                if should_ignore_path(path):
                    if os.path.isdir(path):
                        delete_under_prefix(conn, path)
                    else:
                        delete_by_path(conn, path)
                    remove_cache_path(path)
                    removed += 1
                    continue
                if not _under_watch_root(path):
                    continue
                checked += 1
                if not os.path.exists(path):
                    if os.path.isdir(path):
                        delete_under_prefix(conn, path)
                    else:
                        delete_by_path(conn, path)
                    remove_cache_path(path)
                    removed += 1
                    continue

                if updated < STARTUP_SYNC_BATCH:
                    try:
                        disk_mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    row = get_item_by_path(conn, path)
                    if row and abs(float(row["mtime"] or 0) - disk_mtime) > 1.0:
                        new_row = row_from_path(path, source_root=row["source_root"] or "")
                        if new_row:
                            upsert_item(conn, new_row)
                            patch_cache_item(new_row)
                            updated += 1

            update_item_count_meta(conn)
            conn.close()
        finally:
            _index_write_depth -= 1

    elapsed = time.perf_counter() - t0
    summary = {
        "sync_checked": checked,
        "removed": removed,
        "updated": updated,
        "elapsed_sec": round(elapsed, 2),
    }
    if is_debug_enabled():
        print(
            f"[sync] checked={checked} removed={removed} "
            f"updated={updated} ({elapsed:.2f}s)"
        )
    return summary


def incremental_refresh() -> dict[str, Any]:
    """
    Manual 'refresh index' — incremental sync only (no full rebuild).
    """
    summary = startup_sync()
    summary["refreshed"] = True
    summary["item_count"] = _count_items()
    return summary


def _count_items() -> int:
    from database import get_item_count, index_exists

    if not index_exists():
        return 0
    conn = connect()
    init_schema(conn)
    n = get_item_count(conn)
    conn.close()
    return n
