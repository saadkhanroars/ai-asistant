"""
launcher.py — Open the winning search result on Windows.

Launcher logic by type:
  - application / shortcut / exe -> os.startfile (Windows finds the app)
  - folder -> File Explorer
  - video / audio / image / document / code -> default app via os.startfile
Media files use the system default player (no hardcoded VLC, etc.).
Web/browser actions are handled by router.py + browser.py.
"""

from __future__ import annotations

import os

from models import SearchItem


def launch_system_app(app) -> str:
    """Launch a reserved Windows system application (see system_apps.py)."""
    from system_apps import launch_system_app as _launch

    return _launch(app)


def launch_item(item: SearchItem, score: float) -> str:
    """Open one SearchItem and return a status message."""
    if not os.path.exists(item.path):
        return f"Not found anymore: {item.path}"

    try:
        os.startfile(item.path)
    except OSError as err:
        return f"Could not open {item.name}: {err}"

    label = _kind_label(item.kind)
    detail = f" ({score:.0%} match)" if score < 1.0 else ""
    return f"Opened {label}: {item.name}{detail}"


def _kind_label(kind: str) -> str:
    labels = {
        "application": "app",
        "shortcut": "app",
        "folder": "folder",
        "video": "video",
        "audio": "audio",
        "image": "image",
        "document": "document",
        "code": "file",
    }
    return labels.get(kind, "item")
