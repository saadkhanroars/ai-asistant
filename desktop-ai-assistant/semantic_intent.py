"""
semantic_intent.py — Offline-first semantic intent layer (no embeddings/APIs).

Uses aliases, synonym maps, keyword groups, phrase matching, and scoring
to understand natural variations before any AI call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from alias_engine import expand_aliases
from normalize import normalize_input

INTENT_OPEN_SETTINGS = "open_settings"
INTENT_TOGGLE_SETTING = "toggle_setting"  # turn on wifi, enable bluetooth
INTENT_UNKNOWN = "unknown"

# Minimum score to route (short commands and "X settings" use higher floors)
_SETTINGS_ROUTE_MIN = 0.45
_SHORT_COMMAND_CONFIDENCE = 0.96
_SETTINGS_PHRASE_CONFIDENCE = 0.94

# Keywords that strongly imply Windows Settings (bypass file index)
SETTINGS_PRIORITY_KEYWORDS = frozenset({
    "settings", "setting", "bluetooth", "wifi", "wi", "fi", "wlan", "wireless",
    "display", "screen", "brightness", "sound", "audio", "volume", "speaker",
    "battery", "storage", "network", "ethernet", "update", "night", "nightlight",
})

# Bare one-word commands -> setting id (high confidence)
SHORT_SETTING_COMMANDS: dict[str, str] = {
    "bluetooth": "bluetooth",
    "bt": "bluetooth",
    "wifi": "wifi",
    "wlan": "wifi",
    "display": "display",
    "screen": "display",
    "sound": "sound",
    "audio": "sound",
    "volume": "sound",
    "battery": "battery",
    "storage": "storage",
    "network": "network",
    "update": "windows_update",
    "nightlight": "night_light",
    "night": "night_light",
}

# Explicit multi-word settings phrases
SETTINGS_PHRASES: dict[str, str] = {
    "sound settings": "sound",
    "audio settings": "sound",
    "volume settings": "sound",
    "volume controls": "sound",
    "wifi settings": "wifi",
    "wi fi settings": "wifi",
    "bluetooth settings": "bluetooth",
    "display settings": "display",
    "screen settings": "display",
    "brightness settings": "display",
    "battery settings": "battery",
    "battery options": "battery",
    "storage settings": "storage",
    "network settings": "network",
    "windows update": "windows_update",
    "night light": "night_light",
    "night mode": "night_light",
    "open settings": "settings",  # general — handled via keyword fallback
}

# Canonical setting id -> synonym tokens (matched as whole words or phrases)
SETTING_SYNONYMS: dict[str, tuple[str, ...]] = {
    "bluetooth": (
        "bluetooth", "bt", "blue tooth", "pair device", "pairing",
        "connect headphones", "connect headset", "connect earbuds",
        "wireless headphones", "bluetooth device",
    ),
    "wifi": (
        "wifi", "wifi settings", "wi fi", "wi-fi", "wireless", "wlan",
        "internet connection", "turn on wifi", "enable wifi", "connect wifi",
    ),
    "network": ("network", "ethernet", "proxy", "vpn settings"),
    "display": (
        "display", "screen", "monitor", "brightness", "resolution",
        "brightness settings", "screen brightness",
    ),
    "sound": (
        "sound", "sound settings", "audio", "audio settings", "speaker",
        "volume", "volume controls", "volume control", "volume settings",
        "mute", "headphones output",
    ),
    "battery": ("battery", "power saver", "battery saver", "battery options"),
    "night_light": (
        "night light", "nightlight", "night mode", "blue light",
        "eye comfort", "night shift",
    ),
    "storage": ("storage", "disk space", "free space", "storagesense"),
    "windows_update": (
        "windows update", "system update", "update windows", "os update",
    ),
}

# Phrases that imply Settings even without the word "settings"
SETTINGS_CUE_WORDS = frozenset({
    "settings", "setting", "options", "option", "preferences", "preference",
    "controls", "control", "panel", "configuration", "configure",
})

# Verbs stripped before matching setting targets
_ACTION_PREFIXES = re.compile(
    r"^(?:please\s+)?(?:"
    r"i\s+want|i\s+need|show\s+me|take\s+me\s+to|go\s+to|"
    r"open|launch|start|run|go|turn\s+on|turn\s+off|enable|disable|"
    r"connect|pair|adjust|change|set|view|see"
    r")\s+",
    re.I,
)

_SETTINGS_TAIL = re.compile(
    r"\s+(?:in\s+)?(?:windows\s+)?settings(?:\s+app)?\s*$",
    re.I,
)


@dataclass
class SemanticMatch:
    intent: str
    setting_id: str | None
    confidence: float
    canonical_target: str
    matched_phrase: str = ""


def looks_like_settings_query(text: str) -> bool:
    """True when query should not compete with indexed files."""
    norm = expand_aliases(normalize_input(text))
    if not norm:
        return False
    tokens = set(re.findall(r"[a-z0-9]+", norm))
    if tokens & SETTINGS_PRIORITY_KEYWORDS:
        return resolve_settings_match(text, norm) is not None
    return False


def should_skip_file_search(text: str, normalized: str | None = None) -> bool:
    """Skip index search when a settings route is available."""
    norm = normalized or normalize_input(text)
    return looks_like_settings_query(text) or resolve_settings_match(text, norm) is not None


def resolve_settings_match(
    user_text: str,
    normalized: str | None = None,
) -> SemanticMatch | None:
    """
    Strong settings resolver: short commands, explicit phrases, then synonym scan.
    Used by router BEFORE indexed search.
    """
    text = (normalized or normalize_input(user_text)).strip()
    text = expand_aliases(text)
    if not text:
        return None

    # Explicit file extension — user wants a file, not Settings
    if re.search(r"\.[a-z0-9]{2,5}\b", text):
        return None

    work = _strip_action_prefix(text)
    work = _SETTINGS_TAIL.sub("", work).strip()
    work = re.sub(r"\s+", " ", work)
    compact = work.strip()

    # 1. Explicit phrases ("sound settings", "wifi settings")
    for phrase, setting_id in sorted(SETTINGS_PHRASES.items(), key=lambda x: -len(x[0])):
        if phrase in text or phrase in compact or compact == phrase:
            if setting_id == "settings":
                continue
            return _make_match(setting_id, _SETTINGS_PHRASE_CONFIDENCE, phrase, text)

    # 2. Short bare commands ("bluetooth", "sound", "wifi")
    tokens = compact.split()
    if len(tokens) == 1 and tokens[0] in SHORT_SETTING_COMMANDS:
        sid = SHORT_SETTING_COMMANDS[tokens[0]]
        return _make_match(sid, _SHORT_COMMAND_CONFIDENCE, tokens[0], text)

    # 3. Two tokens: "<setting> settings" / "settings <setting>"
    if len(tokens) == 2:
        a, b = tokens[0], tokens[1]
        if b in ("settings", "setting", "options", "controls") and a in SHORT_SETTING_COMMANDS:
            sid = SHORT_SETTING_COMMANDS[a]
            return _make_match(sid, _SETTINGS_PHRASE_CONFIDENCE, f"{a} {b}", text)
        if a in ("settings", "setting") and b in SHORT_SETTING_COMMANDS:
            sid = SHORT_SETTING_COMMANDS[b]
            return _make_match(sid, _SETTINGS_PHRASE_CONFIDENCE, f"{a} {b}", text)

    # 4. Synonym / phrase scoring (original logic, lower threshold)
    best = _score_synonym_matches(work, text)
    if best and best.confidence >= _SETTINGS_ROUTE_MIN:
        return best
    return None


def detect_semantic_intent(user_text: str, normalized: str | None = None) -> SemanticMatch | None:
    """Score user text against offline semantic patterns."""
    return resolve_settings_match(user_text, normalized)


def _make_match(
    setting_id: str,
    confidence: float,
    phrase: str,
    text: str,
) -> SemanticMatch:
    intent = INTENT_OPEN_SETTINGS
    if re.search(r"\b(turn\s+on|turn\s+off|enable|disable)\b", text):
        intent = INTENT_TOGGLE_SETTING
    return SemanticMatch(
        intent=intent,
        setting_id=setting_id,
        confidence=confidence,
        canonical_target=setting_id,
        matched_phrase=phrase,
    )


def _score_synonym_matches(work: str, text: str) -> SemanticMatch | None:
    best: SemanticMatch | None = None
    for setting_id, phrases in SETTING_SYNONYMS.items():
        for phrase in phrases:
            score = _phrase_score(work, text, phrase)
            if score <= 0:
                continue
            if _has_settings_cue(text) or _implies_settings_page(phrase, work):
                score = min(1.0, score + 0.18)
            if len(work.split()) <= 2:
                score = min(1.0, score + 0.10)
            match = _make_match(setting_id, score, phrase, text)
            if best is None or match.confidence > best.confidence:
                best = match
    return best


def _strip_action_prefix(text: str) -> str:
    prev = None
    work = text
    while work != prev:
        prev = work
        work = _ACTION_PREFIXES.sub("", work).strip()
    return work


def _has_settings_cue(text: str) -> bool:
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    return bool(tokens & SETTINGS_CUE_WORDS)


def _implies_settings_page(phrase: str, work: str) -> bool:
    """Brightness/volume/bluetooth-style queries usually mean Settings."""
    setting_keywords = (
        "bluetooth", "wifi", "display", "brightness", "volume", "sound",
        "battery", "night", "storage", "update",
    )
    blob = f"{phrase} {work}".lower()
    return any(k in blob for k in setting_keywords)


def _phrase_score(work: str, full: str, phrase: str) -> float:
    """Token overlap + substring phrase match scoring."""
    phrase = phrase.lower().strip()
    if not phrase:
        return 0.0

    if phrase in work or phrase in full:
        base = 0.88 if phrase == work.strip() else 0.78
    else:
        ptoks = set(re.findall(r"[a-z0-9]+", phrase))
        wtoks = set(re.findall(r"[a-z0-9]+", work))
        if not ptoks:
            return 0.0
        overlap = len(ptoks & wtoks) / len(ptoks)
        if overlap < 0.5:
            return 0.0
        base = 0.55 + 0.35 * overlap

    # Prefer longer, more specific phrase matches
    if len(phrase.split()) >= 2:
        base = min(1.0, base + 0.06)
    return base


def extract_setting_target(text: str) -> str | None:
    """Return canonical setting id if text clearly names one setting."""
    m = resolve_settings_match(text)
    return m.setting_id if m else None
