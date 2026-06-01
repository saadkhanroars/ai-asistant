"""
type_mapper.py — Map index kinds to routing item types.

Types used for intent biasing in scoring_engine.py.
"""

from __future__ import annotations

import os
from pathlib import Path

from search_config import FOLDER_NICKNAMES

KIND_TO_TYPE: dict[str, str] = {
    "application": "app",
    "shortcut": "app",
    "folder": "folder",
    "video": "video",
    "audio": "audio",
    "image": "image",
    "document": "document",
    "code": "document",
    "archive": "document",
    "other": "document",
}

SYSTEM_APP_NAMES = frozenset({
    "calc", "calculator", "notepad", "paint", "mspaint", "cmd", "powershell",
    "settings", "control", "snipping", "explorer", "taskmgr", "task manager",
    "sticky notes", "onenote", "wordpad",
})


def map_kind_to_type(kind: str, path: str, name: str) -> str:
    """Return routing type: app | folder | document | video | …"""
    base = KIND_TO_TYPE.get(kind, "document")
    stem = Path(path).stem.lower() if path else name.lower()
    if base == "app" and stem in SYSTEM_APP_NAMES:
        return "system_app"
    return base


def attach_type_to_item(item) -> None:
    """Set item_type on SearchItem in place."""
    item.item_type = map_kind_to_type(item.kind, item.path, item.name)


def folder_nickname_type(name: str) -> str | None:
    if name.lower() in FOLDER_NICKNAMES:
        return "folder"
    return None
