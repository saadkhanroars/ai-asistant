"""
parser.py — Intent detection and target extraction.

Pipeline step after normalization:
  - Detect intent: open | launch | run | play | search
  - Extract target object, browser, platform, search query
  - Classify route type for execution

Examples:
  open youtube in brave   -> website + browser
  search physics on google -> web_search + platform
  play interstellar       -> local_media
  open downloads          -> local_folder
  launch photoshop        -> local_app
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from normalize import looks_like_ai_chat
from websites import is_known_website

# Supported intents
INTENTS = frozenset({"open", "launch", "start", "run", "play", "search"})
LAUNCH_INTENTS = frozenset({"launch", "start", "run"})
LOCAL_INTENTS = frozenset({"open", "launch", "run", "play"})

BROWSERS = frozenset({"brave", "chrome", "edge", "firefox", "msedge"})
PLATFORMS = frozenset({
    "google", "youtube", "amazon", "flipkart", "github", "reddit", "wikipedia",
})

# Route types used by router.execute
ROUTE_AI = "ai_chat"
ROUTE_WEB_SEARCH = "web_search"
ROUTE_WEBSITE = "website"
ROUTE_LOCAL_APP = "local_app"
ROUTE_LOCAL_MEDIA = "local_media"
ROUTE_LOCAL_FOLDER = "local_folder"
ROUTE_LOCAL_FILE = "local_file"
ROUTE_LOCAL_OPEN = "local_open"
ROUTE_WEB_FALLBACK = "web_fallback"


@dataclass
class ParsedCommand:
    """Structured result of parsing one user line."""

    raw: str
    normalized: str
    intent: str
    target: str
    route: str
    browser: str | None = None
    platform: str | None = None
    search_query: str | None = None
    website: str | None = None
    is_launcher_command: bool = False


def parse_command(user_text: str, normalized_text: str) -> ParsedCommand:
    """
    Intent detection + target extraction from normalized text.
    `normalized_text` comes from normalize.normalize_input().
    """
    raw = user_text.strip()
    text = normalized_text.strip()
    cmd = ParsedCommand(
        raw=raw,
        normalized=text,
        intent="open",
        target=text,
        route=ROUTE_LOCAL_OPEN,
    )
    if not text:
        return cmd

    work = text
    browser = _extract_browser(work)
    if browser:
        cmd.browser = browser
        work = _strip_browser_phrase(work, browser)

    platform = _extract_platform(work)
    if platform:
        cmd.platform = platform
        work = _strip_platform_phrase(work, platform)

    # "google quantum mechanics" / "youtube lofi"
    parts = work.split(None, 1)
    if parts and parts[0] in PLATFORMS and len(parts) > 1:
        cmd.intent = "search"
        cmd.platform = parts[0]
        cmd.search_query = parts[1].strip()
        cmd.target = cmd.search_query
        cmd.is_launcher_command = True
        cmd.route = ROUTE_WEB_SEARCH
        return cmd

    if not parts:
        cmd.target = work
        cmd.route = _classify_route(cmd)
        return cmd

    verb = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if verb == "search" and rest:
        cmd.intent = "search"
        cmd.is_launcher_command = True
        query, plat = _split_on_platform(rest)
        cmd.search_query = query
        cmd.target = query
        if plat:
            cmd.platform = plat
        elif not cmd.platform:
            cmd.platform = "google"
        cmd.route = ROUTE_WEB_SEARCH
        return cmd

    if verb in INTENTS:
        cmd.intent = verb
        cmd.is_launcher_command = True
        cmd.target = rest

        if verb == "search":
            cmd.search_query = rest
            if not cmd.platform:
                cmd.platform = "google"
            cmd.route = ROUTE_WEB_SEARCH
            return cmd

        if verb == "open" and _is_single_website(rest):
            cmd.website = _website_token(rest)
            cmd.route = ROUTE_WEBSITE
            return cmd

        cmd.route = _classify_route(cmd)
        return cmd

    # No leading verb
    cmd.intent = "open"
    cmd.target = work
    cmd.is_launcher_command = not looks_like_ai_chat(raw)
    cmd.route = _classify_route(cmd)
    return cmd


def classify_final_route(cmd: ParsedCommand, local_found: bool) -> str:
    """Adjust route after local search attempt."""
    if local_found:
        return cmd.route
    if cmd.route == ROUTE_WEBSITE:
        return ROUTE_WEBSITE
    if cmd.intent == "search" or cmd.search_query:
        return ROUTE_WEB_SEARCH
    if cmd.website or _is_single_website(cmd.target):
        return ROUTE_WEBSITE
    return ROUTE_WEB_FALLBACK


def _classify_route(cmd: ParsedCommand) -> str:
    """Map intent + target to execution route."""
    if cmd.intent == "search":
        return ROUTE_WEB_SEARCH
    if cmd.website or (cmd.intent == "open" and _is_single_website(cmd.target)):
        return ROUTE_WEBSITE
    if cmd.intent in LAUNCH_INTENTS or cmd.intent == "run":
        return ROUTE_LOCAL_APP
    if cmd.intent == "play":
        return ROUTE_LOCAL_MEDIA
    if _looks_like_folder_target(cmd.target):
        return ROUTE_LOCAL_FOLDER
    return ROUTE_LOCAL_OPEN


def _looks_like_folder_target(target: str) -> bool:
    from search_config import FOLDER_NICKNAMES

    token = target.strip().lower()
    if token in FOLDER_NICKNAMES:
        return True
    return bool(re.search(r"\b(folder|directory)\b", token))


def _is_single_website(text: str) -> bool:
    token = text.strip().lower()
    if not token or " " in token:
        return False
    return is_known_website(token.replace(" ", ""))


def _website_token(text: str) -> str:
    return text.strip().lower().replace(" ", "")


def _extract_browser(text: str) -> str | None:
    m = re.search(r"\s+in\s+(brave|chrome|edge|firefox|msedge)\s*$", text, re.I)
    if m:
        return _norm_browser(m.group(1))
    m = re.search(r"\s+on\s+(brave|chrome|edge|firefox|msedge)\s*$", text, re.I)
    if m:
        return _norm_browser(m.group(1))
    return None


def _norm_browser(name: str) -> str:
    n = name.lower()
    return "edge" if n == "msedge" else n


def _strip_browser_phrase(text: str, browser: str) -> str:
    text = re.sub(rf"\s+in\s+{browser}\s*$", "", text, flags=re.I)
    text = re.sub(r"\s+in\s+msedge\s*$", "", text, flags=re.I)
    text = re.sub(rf"\s+on\s+{browser}\s*$", "", text, flags=re.I)
    return text.strip()


def _extract_platform(text: str) -> str | None:
    m = re.search(
        r"\s+on\s+(google|youtube|amazon|flipkart|github|reddit|wikipedia)\s*$",
        text,
        re.I,
    )
    return m.group(1).lower() if m else None


def _strip_platform_phrase(text: str, platform: str) -> str:
    return re.sub(rf"\s+on\s+{platform}\s*$", "", text, flags=re.I).strip()


def _split_on_platform(rest: str) -> tuple[str, str | None]:
    m = re.search(
        r"^(.+?)\s+on\s+(google|youtube|amazon|flipkart|github|reddit|wikipedia)\s*$",
        rest,
        re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).lower()
    return rest.strip(), None
