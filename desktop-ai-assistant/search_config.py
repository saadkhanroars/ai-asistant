"""
search_config.py — Paths, limits, file types, and index settings.
"""

import os
from urllib.parse import quote_plus

# Assistant install folder — never watch or index (prevents self-triggered loops)
PROJECT_ROOT = os.path.normcase(os.path.normpath(os.path.dirname(os.path.abspath(__file__))))

INDEX_DB_PATH = os.path.join(PROJECT_ROOT, "desktop_index.db")

MIN_MATCH_SCORE = 0.48
HIGH_CONFIDENCE_SCORE = 0.62
MIN_SCORE_GAP = 0.08

MAX_SEARCH_DEPTH = 8
MAX_PROGRAM_DEPTH = 3
MAX_INDEX_FILES = 50000

# Background index update settings (lightweight)
WATCH_DEBOUNCE_SEC = 1.0
POLL_INTERVAL_SEC = 45
STARTUP_SYNC_BATCH = 500

def _user_path(*parts: str) -> str:
    return os.path.join(os.environ["USERPROFILE"], *parts)


SEARCH_LOCATIONS: list[str] = [
    _user_path("Desktop"),
    _user_path("Downloads"),
    _user_path("Documents"),
    _user_path("Videos"),
    _user_path("Music"),
    _user_path("Pictures"),
]

CUSTOM_FOLDERS: list[str] = []

FOLDER_NICKNAMES: dict[str, str] = {
    "desktop": _user_path("Desktop"),
    "downloads": _user_path("Downloads"),
    "documents": _user_path("Documents"),
    "pictures": _user_path("Pictures"),
    "music": _user_path("Music"),
    "videos": _user_path("Videos"),
}

START_MENU_ROOTS: list[str] = [
    os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs",
    ),
    os.path.join(
        os.environ.get("PROGRAMDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs",
    ),
]

PROGRAM_ROOTS: list[str] = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
]

EXTENSIONS: dict[str, set[str]] = {
    "application": {".exe", ".bat", ".cmd", ".msi"},
    "shortcut": {".lnk"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"},
    "document": {
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
        ".xls", ".xlsx", ".ppt", ".pptx", ".csv",
    },
    "code": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".cs", ".json", ".md"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz"},
}

CATEGORY_LABELS: dict[str, str] = {
    "application": "executable",
    "shortcut": "shortcut",
    "folder": "folder",
    "video": "video",
    "audio": "audio",
    "image": "image",
    "document": "document",
    "code": "document",
    "archive": "document",
    "other": "document",
}

ALL_SEARCH_EXTENSIONS: set[str] = set()
for _exts in EXTENSIONS.values():
    ALL_SEARCH_EXTENSIONS.update(_exts)

BROWSER_SEARCH_URL = "https://www.google.com/search?q={query}"


def all_search_locations() -> list[str]:
    return [p for p in SEARCH_LOCATIONS + CUSTOM_FOLDERS if p and os.path.isdir(p)]


def all_index_roots() -> list[str]:
    roots = list(all_search_locations())
    for root in START_MENU_ROOTS + PROGRAM_ROOTS:
        if root and os.path.isdir(root) and root not in roots:
            roots.append(root)
    return roots


def watch_paths() -> list[str]:
    """
    Folders monitored by the background watcher.
    User folders + Start Menu (not entire Program Files — too heavy).
    """
    paths = list(all_search_locations())
    for root in START_MENU_ROOTS:
        if root and os.path.isdir(root) and root not in paths:
            paths.append(root)
    return paths


def make_browser_search_url(query: str) -> str:
    return BROWSER_SEARCH_URL.format(query=quote_plus(query))
