"""
watcher.py — Background filesystem watching for index updates.

Filesystem watching:
  - Preferred: watchdog library (OS-native events, low CPU)
  - Fallback: lightweight polling of index mtimes (no full rescan)

Update flow:
  event detected -> debounce -> incremental_indexer.handle_filesystem_event
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from debug_log import is_debug_enabled
from incremental_indexer import (
    handle_filesystem_event,
    is_index_write_active,
    should_ignore_path,
)
from search_config import POLL_INTERVAL_SEC, WATCH_DEBOUNCE_SEC, watch_paths

_observer = None
_polling_thread: threading.Thread | None = None
_running = False
_event_queue: deque[tuple[str, str, str | None]] = deque()
_queue_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_last_enqueue_at: float = 0.0


def start_background_watcher() -> str:
    """
    Start watching indexed folders in a background thread.
    Returns mode description: 'watchdog' or 'polling'.
    """
    global _running
    if _running:
        return "already running"

    _running = True
    _start_debounce_worker()

    if _try_watchdog():
        if is_debug_enabled():
            print(f"[watch] Started watchdog on {len(watch_paths())} folder(s)")
        return "watchdog"

    _start_polling()
    if is_debug_enabled():
        print(f"[watch] Watchdog unavailable — polling every {POLL_INTERVAL_SEC}s")
    return "polling"


def stop_background_watcher() -> None:
    """Stop watcher on assistant exit."""
    global _running, _observer, _polling_thread
    _running = False

    if _observer is not None:
        try:
            _observer.stop()
            _observer.join(timeout=2)
        except Exception:
            pass
        _observer = None

    if _polling_thread is not None:
        _polling_thread.join(timeout=2)
        _polling_thread = None


def _start_debounce_worker() -> None:
    global _worker_thread

    def worker() -> None:
        while _running:
            time.sleep(0.25)
            if is_index_write_active():
                continue

            with _queue_lock:
                if not _event_queue:
                    continue
                quiet_for = time.monotonic() - _last_enqueue_at
                if quiet_for < WATCH_DEBOUNCE_SEC:
                    continue
                batch: list[tuple[str, str, str | None]] = []
                while _event_queue:
                    batch.append(_event_queue.popleft())

            # Coalesce: last event per path wins
            by_path: dict[str, tuple[str, str, str | None]] = {}
            for ev in batch:
                by_path[ev[1]] = ev
            for event_type, src, dest in by_path.values():
                try:
                    handle_filesystem_event(event_type, src, dest)
                except Exception as err:
                    if is_debug_enabled():
                        print(f"[watch] error: {err}")

    _worker_thread = threading.Thread(target=worker, daemon=True, name="index-debounce")
    _worker_thread.start()


def _should_watch_path(path: str) -> bool:
    """Filter events before they enter the debounce queue."""
    if not path or should_ignore_path(path):
        return False
    if is_index_write_active():
        return False
    return True


def _enqueue(event_type: str, src: str, dest: str | None = None) -> None:
    global _last_enqueue_at
    if not _should_watch_path(src):
        return
    if dest and not _should_watch_path(dest):
        dest = None
    with _queue_lock:
        _event_queue.append((event_type, src, dest))
        _last_enqueue_at = time.monotonic()


def _try_watchdog() -> bool:
    global _observer
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return False

    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                if _ok_dir(event.src_path):
                    _enqueue("created", event.src_path)
                return
            if _should_watch_path(event.src_path):
                _enqueue("created", event.src_path)

        def on_modified(self, event):
            # Directory mtime changes fire constantly; only track file edits.
            if event.is_directory:
                return
            if _should_watch_path(event.src_path):
                _enqueue("modified", event.src_path)

        def on_deleted(self, event):
            if _should_watch_path(event.src_path):
                _enqueue("deleted", event.src_path)

        def on_moved(self, event):
            if _should_watch_path(event.src_path) or (
                event.dest_path and _should_watch_path(event.dest_path)
            ):
                _enqueue("moved", event.src_path, event.dest_path)

    _observer = Observer()
    handler = Handler()
    for path in watch_paths():
        if os.path.isdir(path):
            _observer.schedule(handler, path, recursive=True)

    _observer.start()
    return True


def _ok_dir(path: str) -> bool:
    """Index new folders when created under watch roots (not ignored)."""
    return _should_watch_path(path)


def _start_polling() -> None:
    """
    Fallback polling: compare mtime of paths already in the index.
    No recursive directory walk — keeps CPU usage low.
    """
    global _polling_thread

    def poll_loop() -> None:
        from database import connect, fetch_all_paths, get_item_by_path, init_schema
        from incremental_indexer import remove_path, should_ignore_path, upsert_path

        while _running:
            time.sleep(POLL_INTERVAL_SEC)
            if is_index_write_active():
                continue
            try:
                conn = connect()
                init_schema(conn)
                paths = fetch_all_paths(conn)
                conn.close()
                for path in paths:
                    if not _running:
                        break
                    if should_ignore_path(path):
                        continue
                    if not os.path.exists(path):
                        remove_path(path)
                        continue
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    conn = connect()
                    row = get_item_by_path(conn, path)
                    conn.close()
                    if row and abs(float(row["mtime"] or 0) - mtime) > 1.0:
                        upsert_path(path)
            except Exception as err:
                if is_debug_enabled():
                    print(f"[poll] error: {err}")

    _polling_thread = threading.Thread(target=poll_loop, daemon=True, name="index-poll")
    _polling_thread.start()
