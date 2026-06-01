"""
reference_resolver.py — Map pronouns and ordinals to session memory.

Runs at the start of each router request, before intent detection.
Uses generalized patterns (not per-command hardcoding).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from debug_log import is_debug_enabled
from session_memory import MemoryItem, SessionMemory

# Ordinal words -> 1-based index
_ORDINAL_MAP: dict[str, int] = {
    "first": 1,
    "1st": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
    "fifth": 5,
    "5th": 5,
    "five": 5,
}

# open/play/choose the <ordinal> [one|result|option]
_ORDINAL_COMMAND_RE = re.compile(
    r"^(?P<verb>open|launch|start|run|play|watch|choose|pick|select|view|show)"
    r"\s+(?:the\s+)?(?P<ord>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|one|two|three|four|five)"
    r"(?:\s+(?:one|result|option|match))?\s*$",
    re.I,
)

# open latest [type hint]
_LATEST_TYPE_RE = re.compile(
    r"^(?:open|launch|view|show)\s+(?:the\s+)?latest\s+(\w+)\s*$",
    re.I,
)

_LATEST_ALONE_RE = re.compile(
    r"^(?:open|launch|view|show)\s+(?:the\s+)?latest\s*$",
    re.I,
)

# open previous [type]
_PREVIOUS_RE = re.compile(
    r"^(?:open|launch|view|show|play)\s+(?:the\s+)?previous\s+(\w+)?\s*$",
    re.I,
)

# open that <type>  /  open that pdf
_THAT_TYPE_RE = re.compile(
    r"^(?P<verb>open|launch|play|view|show)\s+(?:the\s+)?that\s+(\w+)\s*$",
    re.I,
)

# open/play/close/search ... it|that|this ...
_PRONOUN_VERB_RE = re.compile(
    r"^(?P<verb>open|launch|start|run|play|watch|close|kill|search|google|find|view|show)"
    r"\s+(?P<ref>it|that|this|them)\b(?P<rest>.*)$",
    re.I,
)

# search it [on|in] <platform|browser>
_SEARCH_IT_RE = re.compile(
    r"^search\s+(?:it|that|this)\s+(?:on|in)\s+(\w+)\s*$",
    re.I,
)

# open X in browser
_OPEN_IN_BROWSER_RE = re.compile(
    r"^(?:open|launch|view|show)\s+"
    r"(?:it|that|this|the\s+(?:file|image|video|item)|latest)\s+"
    r"(?:in|on|with)\s+(\w+)\s*$",
    re.I,
)

_LATEST_IN_PHRASE_RE = re.compile(
    r"\b(?:latest|newest|most\s+recent|last)\s+(\w+)\b",
    re.I,
)

_TYPE_HINTS = frozenset({
    "image", "photo", "picture", "video", "movie", "audio", "song", "music",
    "pdf", "document", "doc", "file", "folder", "app",
})


@dataclass
class ResolveResult:
    """Output of reference resolution."""

    text: str
    ordinal: int | None = None  # pick from last_search_results (1-based)
    changed: bool = False
    resolved_from: str = ""


def _log_resolved(original: str, result: str, detail: str) -> None:
    if is_debug_enabled() and original != result:
        print(f"[reference resolved] {detail}")
        print(f"  before: {original!r}")
        print(f"  after:  {result!r}")


def resolve_user_input(user_text: str, memory: SessionMemory) -> ResolveResult:
    """
    Resolve references in the user line using session memory.
    Returns possibly rewritten text and/or an ordinal for ranked lists.
    """
    text = user_text.strip()
    if not text:
        return ResolveResult(text=text)

    # Ordinal: "open the first one"
    m = _ORDINAL_COMMAND_RE.match(text)
    if m:
        ord_word = m.group("ord").lower()
        idx = _ORDINAL_MAP.get(ord_word)
        if idx is not None:
            item = memory.get_item_by_ordinal(idx)
            verb = m.group("verb").lower()
            if item:
                rewritten = _command_for_item(verb, item)
                _log_resolved(text, rewritten, f"ordinal #{idx} -> {item.name}")
                return ResolveResult(
                    text=rewritten,
                    ordinal=idx,
                    changed=True,
                    resolved_from="ordinal",
                )
            _log_resolved(text, text, f"ordinal #{idx} (no list in memory)")
            return ResolveResult(text=text, ordinal=idx, resolved_from="ordinal")

    # search it on youtube / in brave
    m = _SEARCH_IT_RE.match(text)
    if m:
        target = m.group(1).lower()
        query = memory.state.last_search_query
        if not query:
            item = memory.get_primary_item()
            if item and memory.state.current_context_type == "search":
                query = item.name
        if query:
            new_text = f"search {query} on {target}"
            _log_resolved(text, new_text, "search-it -> last query")
            return ResolveResult(text=new_text, changed=True, resolved_from="search_it")

    # open it in brave
    m = _OPEN_IN_BROWSER_RE.match(text)
    if m:
        browser = m.group(1)
        path = memory.get_path_for_browser()
        item = memory.get_primary_item()
        if path:
            new_text = f"open {path} in {browser}"
            _log_resolved(text, new_text, "open-in-browser path")
            return ResolveResult(text=new_text, changed=True, resolved_from="browser_path")
        if item:
            new_text = f"open {item.name} in {browser}"
            _log_resolved(text, new_text, "open-in-browser name")
            return ResolveResult(text=new_text, changed=True, resolved_from="browser_name")

    # open latest image / open latest pdf
    m = _LATEST_TYPE_RE.match(text)
    if m:
        type_hint = m.group(1).lower()
        item = _find_by_type_hint(memory, type_hint)
        if item:
            new_text = f"open {item.path if item.path else item.name}"
            _log_resolved(text, new_text, f"latest-{type_hint}")
            return ResolveResult(text=new_text, changed=True, resolved_from="latest_type")
        new_text = f"open latest {type_hint}"
        return ResolveResult(text=new_text, resolved_from="latest_type_query")

    if _LATEST_ALONE_RE.match(text):
        item = memory.get_primary_item()
        if item:
            target = item.path or item.name
            new_text = f"open {target}"
            _log_resolved(text, new_text, "latest -> last item")
            return ResolveResult(text=new_text, changed=True, resolved_from="latest")

    # open previous image
    m = _PREVIOUS_RE.match(text)
    if m:
        item = memory.get_primary_item()
        if item:
            new_text = f"open {item.path or item.name}"
            _log_resolved(text, new_text, "previous")
            return ResolveResult(text=new_text, changed=True, resolved_from="previous")

    # open that pdf
    m = _THAT_TYPE_RE.match(text)
    if m:
        type_hint = m.group(2).lower()
        item = _find_by_type_hint(memory, type_hint)
        verb = m.group(1).lower()
        if item:
            new_text = _command_for_item(verb, item)
            _log_resolved(text, new_text, f"that-{type_hint}")
            return ResolveResult(text=new_text, changed=True, resolved_from="that_type")

    # Verb + pronoun: open it, play that, close it, search it ...
    m = _PRONOUN_VERB_RE.match(text)
    if m:
        verb = m.group("verb").lower()
        rest = m.group("rest") or ""
        item = _resolve_pronoun_target(memory, verb)
        if item:
            if verb in ("close", "kill"):
                new_text = f"close {item.name}"
            elif verb in ("search", "google", "find"):
                q = memory.state.last_search_query or item.name
                plat = rest.strip().lstrip("on ").strip() if rest else "google"
                new_text = f"search {q} on {plat}" if plat else f"search {q}"
            else:
                new_text = _command_for_item(verb, item) + rest
            _log_resolved(text, new_text, f"pronoun-{verb}")
            return ResolveResult(text=new_text, changed=True, resolved_from="pronoun")

    # Inline pronoun replacement (fallback)
    if re.search(r"\b(it|that|this)\b", text, re.I):
        item = memory.get_primary_item()
        if item:
            replacement = item.path if item.path and len(item.path) > 1 else item.name
            new_text = re.sub(
                r"\b(it|that|this)\b",
                replacement,
                text,
                count=1,
                flags=re.I,
            )
            if new_text != text:
                _log_resolved(text, new_text, "inline pronoun")
                return ResolveResult(text=new_text, changed=True, resolved_from="inline")

    return ResolveResult(text=text)


def hint_for_folder_latest(user_text: str, memory: SessionMemory) -> str | None:
    """Folder scope for 'open latest X' when user recently opened a folder."""
    if not _LATEST_IN_PHRASE_RE.search(user_text.lower()):
        return None
    return memory.hint_folder_for_latest()


def _command_for_item(verb: str, item: MemoryItem) -> str:
    target = item.path if item.path and os.path.isfile(item.path) else item.name
    if verb in ("play", "watch"):
        return f"play {target}"
    return f"open {target}"


def _resolve_pronoun_target(memory: SessionMemory, verb: str) -> MemoryItem | None:
    s = memory.state
    if verb in ("search", "google", "find") and s.last_search_query:
        return memory.get_primary_item()
    if verb in ("close", "kill") and s.last_app_name:
        return MemoryItem(s.last_app_name, s.last_app_name, "app")
    return memory.get_primary_item()


def _find_by_type_hint(memory: SessionMemory, type_hint: str) -> MemoryItem | None:
    """Pick best match from last results or last opened by type/extension."""
    hint = type_hint.lower()
    if hint not in _TYPE_HINTS and hint not in ("pdf", "png", "jpg", "mp4", "mkv"):
        ext = f".{hint}"
    else:
        ext = f".{hint}" if hint in ("pdf", "png", "jpg", "jpeg", "mp4", "mkv", "doc", "docx") else None

    for pool in (memory.state.last_search_results, _items_pool(memory)):
        for item in pool:
            name_lower = item.name.lower()
            itype = item.item_type.lower()
            if ext and name_lower.endswith(ext):
                return item
            if hint in ("image", "photo", "picture") and itype == "image":
                return item
            if hint in ("video", "movie") and itype == "video":
                return item
            if hint in ("audio", "song", "music") and itype == "audio":
                return item
            if hint in ("pdf", "document", "doc") and (
                itype == "document" or name_lower.endswith(".pdf")
            ):
                return item
            if hint == "folder" and itype == "folder":
                return item
    return None


def _items_pool(memory: SessionMemory) -> list[MemoryItem]:
    out: list[MemoryItem] = []
    if memory.state.last_opened_item:
        out.append(memory.state.last_opened_item)
    return out
