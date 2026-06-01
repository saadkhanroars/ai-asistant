"""
database.py — Lightweight SQLite index storage.

Stores one row per file/folder/app with searchable metadata.
The search engine reads from here instead of scanning disk each time.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from search_config import INDEX_DB_PATH

# Row shape: name, path, extension, kind, category, search_text, mtime, source_root
CREATE_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    extension TEXT,
    kind TEXT,
    category TEXT,
    search_text TEXT,
    mtime REAL,
    source_root TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_search ON items(search_text);
CREATE INDEX IF NOT EXISTS idx_items_kind ON items(kind);
"""

CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(INDEX_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(CREATE_ITEMS + CREATE_META)
    conn.commit()


def index_exists() -> bool:
    return Path(INDEX_DB_PATH).is_file()


def clear_items(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM items")
    conn.commit()


def insert_items(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    """Batch insert indexed entries. Returns count inserted."""
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT OR REPLACE INTO items
        (name, path, extension, kind, category, search_text, mtime, source_root)
        VALUES (:name, :path, :extension, :kind, :category, :search_text, :mtime, :source_root)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def get_item_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM items").fetchone()
    return int(row["c"]) if row else 0


def fetch_all_items(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM items"))


def fetch_by_token_prefix(
    conn: sqlite3.Connection, tokens: list[str], limit: int = 8000
) -> list[sqlite3.Row]:
    """
    Fast SQL pre-filter: any token appears in search_text or name.
    If no tokens, return all (capped).
    """
    if not tokens:
        return list(conn.execute("SELECT * FROM items LIMIT ?", (limit,)))

    clauses = []
    params: list[str] = []
    for token in tokens:
        if len(token) < 2 and not token.isdigit():
            continue
        pattern = f"%{token}%"
        clauses.append("(search_text LIKE ? OR name LIKE ?)")
        params.extend([pattern, pattern])

    if not clauses:
        return list(conn.execute("SELECT * FROM items LIMIT ?", (limit,)))

    where = " OR ".join(clauses)
    sql = f"SELECT * FROM items WHERE {where} LIMIT ?"
    params.append(str(limit))
    return list(conn.execute(sql, params))


def save_build_metadata(conn: sqlite3.Connection, roots: list[str], count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    set_meta(conn, "built_at", now)
    set_meta(conn, "item_count", str(count))
    set_meta(conn, "indexed_roots", "|".join(roots))


def upsert_item(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    """Insert or replace a single indexed entry (incremental update)."""
    conn.execute(
        """
        INSERT OR REPLACE INTO items
        (name, path, extension, kind, category, search_text, mtime, source_root)
        VALUES (:name, :path, :extension, :kind, :category, :search_text, :mtime, :source_root)
        """,
        row,
    )
    conn.commit()


def delete_by_path(conn: sqlite3.Connection, path: str) -> int:
    """Remove one entry. Returns rows deleted."""
    cur = conn.execute("DELETE FROM items WHERE path = ?", (path,))
    conn.commit()
    return cur.rowcount


def delete_under_prefix(conn: sqlite3.Connection, dir_path: str) -> int:
    """Remove entries inside a deleted folder."""
    prefix = os.path.normpath(dir_path)
    if not prefix.endswith(os.sep):
        prefix += os.sep
    cur = conn.execute(
        "DELETE FROM items WHERE path = ? OR path LIKE ?",
        (os.path.normpath(dir_path), prefix + "%"),
    )
    conn.commit()
    return cur.rowcount


def fetch_all_paths(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT path FROM items").fetchall()
    return [r["path"] for r in rows]


def get_item_by_path(conn: sqlite3.Connection, path: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM items WHERE path = ?", (path,)).fetchone()


def update_item_count_meta(conn: sqlite3.Connection) -> None:
    set_meta(conn, "item_count", str(get_item_count(conn)))
    set_meta(conn, "last_incremental", datetime.now(timezone.utc).isoformat())


def get_index_stats() -> dict[str, str]:
    if not index_exists():
        return {"exists": "false", "item_count": "0"}
    conn = connect()
    init_schema(conn)
    stats = {
        "exists": "true",
        "item_count": str(get_item_count(conn)),
        "built_at": get_meta(conn, "built_at", "unknown"),
        "indexed_roots": get_meta(conn, "indexed_roots", ""),
    }
    conn.close()
    return stats
