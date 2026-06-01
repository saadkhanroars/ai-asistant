"""
intent_engine.py — Lightweight rule-based intent detection.

Maps verbs to semantic intents used for type biasing and routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Semantic intents (not just raw verbs)
INTENT_PLAY_MEDIA = "play_media"
INTENT_LAUNCH_APP = "launch_app"
INTENT_OPEN_FILE = "open_file"
INTENT_OPEN_FOLDER = "open_folder"  # open downloads, documents, …
INTENT_WEB_SEARCH = "web_search"
INTENT_OPEN_WEBSITE = "open_website"
INTENT_BROWSER_ACTION = "browser_action"  # forced browser URL/search
INTENT_CLOSE_APP = "close_app"
INTENT_FIND = "find"  # alias for search/open
INTENT_OPEN_SETTINGS = "open_settings"
INTENT_UNKNOWN = "unknown"

# Semantic settings match floor (short commands score higher)
_SETTINGS_CONFIDENCE_MIN = 0.45

VERB_TO_INTENT: dict[str, str] = {
    "open": INTENT_OPEN_FILE,
    "launch": INTENT_LAUNCH_APP,
    "start": INTENT_LAUNCH_APP,
    "run": INTENT_LAUNCH_APP,
    "play": INTENT_PLAY_MEDIA,
    "watch": INTENT_PLAY_MEDIA,
    "search": INTENT_WEB_SEARCH,
    "google": INTENT_WEB_SEARCH,
    "find": INTENT_FIND,
    "close": INTENT_CLOSE_APP,
    "kill": INTENT_CLOSE_APP,
}

LAUNCHER_VERBS = frozenset(VERB_TO_INTENT.keys()) | frozenset({"youtube"})

# Conversational starters to strip before intent detection
_CONVERSATIONAL_PREFIX_RE = re.compile(
    r"^(?:lets|let's|please|can\s+you|could\s+you|would\s+you|i\s+want\s+to)\s+",
    re.I,
)

# Targets that should prefer installed/system apps over files with the same name
def _known_app_targets() -> frozenset[str]:
    from system_apps import reserved_system_names

    return reserved_system_names() | frozenset({
        "control panel", "terminal", "explorer", "file explorer",
        "snipping tool", "word", "excel", "powerpoint", "outlook",
        "onenote", "sticky notes", "photos", "mail", "calendar", "store",
        "spotify", "discord", "slack", "teams", "zoom", "vlc", "obs", "steam",
    })


KNOWN_APP_TARGETS = _known_app_targets()


@dataclass
class IntentResult:
    raw_verb: str
    intent: str
    remainder: str
    is_launcher: bool
    setting_id: str | None = None
    semantic_confidence: float = 0.0


def detect_intent(user_text: str, normalized: str) -> IntentResult:
    """
    Detect intent from normalized text.
    Examples:
      play one piece -> play_media
      open physics notes -> open_file
      search quantum -> web_search
      close chrome -> close_app
      i want bluetooth -> open_settings
    """
    # Offline semantic layer (settings before file/app heuristics)
    from semantic_intent import resolve_settings_match

    sem = resolve_settings_match(user_text, normalized)
    if sem and sem.setting_id and sem.confidence >= _SETTINGS_CONFIDENCE_MIN:
        return IntentResult(
            "",
            INTENT_OPEN_SETTINGS,
            sem.canonical_target,
            True,
            setting_id=sem.setting_id,
            semantic_confidence=sem.confidence,
        )

    text = normalized.strip()

    # Strip conversational prefixes iteratively (e.g., "please can you open" -> "open")
    while True:
        new_text = _CONVERSATIONAL_PREFIX_RE.sub("", text).strip()
        if new_text == text:
            break
        text = new_text

    tokens = text.split()
    if not tokens:
        return IntentResult("", INTENT_UNKNOWN, "", False)

    # Find the first meaningful verb in the token stream
    verb = None
    rest = ""
    for i, token in enumerate(tokens):
        t_low = token.lower()
        if t_low in VERB_TO_INTENT or t_low == "youtube":
            verb = t_low
            rest = " ".join(tokens[i + 1:]).strip()
            break

    # "youtube one piece" -> web search on youtube
    if verb == "youtube" and rest:
        return IntentResult("youtube", INTENT_WEB_SEARCH, rest, True)

    if verb in VERB_TO_INTENT:
        intent = VERB_TO_INTENT[verb]
        if verb == "open" and _looks_like_folder(rest):
            intent = INTENT_OPEN_FOLDER
        elif verb in ("open", "launch", "start", "run") and _looks_like_app(rest):
            intent = INTENT_LAUNCH_APP
        if verb == "find":
            intent = INTENT_OPEN_FILE
        return IntentResult(verb, intent, rest, True)

    # Bare target: prefer app launch when it looks like an application name
    if _looks_like_app(text):
        return IntentResult("", INTENT_LAUNCH_APP, text, False)

    return IntentResult("", INTENT_OPEN_FILE, text, False)


def _looks_like_folder(target: str) -> bool:
    from search_config import FOLDER_NICKNAMES

    t = target.lower().strip()
    if t in FOLDER_NICKNAMES:
        return True
    return bool(re.search(r"\b(folder|directory|downloads|documents|desktop|pictures|music|videos)\b", t))


def _looks_like_app(target: str) -> bool:
    """True when the target is likely an installed/system app, not a file."""
    t = target.lower().strip()
    if not t:
        return False
    if t in KNOWN_APP_TARGETS:
        return True
    first = t.split(None, 1)[0]
    return first in KNOWN_APP_TARGETS and len(t.split()) == 1


def has_launcher_verb(text: str) -> bool:
    lower = text.lower()
    # Also strip prefixes here so router.py doesn't fallback to AI for "please open..."
    while True:
        new_text = _CONVERSATIONAL_PREFIX_RE.sub("", lower).strip()
        if new_text == lower:
            break
        lower = new_text
    return any(lower.startswith(v + " ") for v in LAUNCHER_VERBS)
