"""
entity_extractor.py — Extract target, browser, platform, website from query.

Critical rule: "search X on brave" -> browser action, NOT local file search.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from browser_registry import is_browser_name, normalize_browser
from intent_engine import INTENT_OPEN_FILE, INTENT_WEB_SEARCH
from websites import is_known_website

PLATFORMS = frozenset({
    "google", "youtube", "amazon", "flipkart", "github", "reddit", "wikipedia",
})


@dataclass
class Entities:
    raw: str
    target: str
    browser: str | None = None
    platform: str | None = None
    search_query: str | None = None
    website: str | None = None
    force_browser: bool = False
    local_path: str | None = None  # absolute path when opening a file in browser


def extract_entities(user_text: str, normalized: str, intent: str, remainder: str) -> Entities:
    work = remainder.strip() or normalized.strip()
    ent = Entities(raw=user_text, target=work)

    if intent == INTENT_WEB_SEARCH:
        work = _parse_web_search_phrases(work, ent)

    # --- "in brave" / "on chrome" (browser) vs "on google" (platform) ---
    browser = _extract_browser_phrase(work)
    if browser:
        ent.browser = browser
        work = _strip_trailing_browser(work, browser)
        ent.force_browser = True

    platform = _extract_platform_phrase(work)
    if platform:
        ent.platform = platform
        work = _strip_trailing_platform(work, platform)

    # "search laptops on flipkart" -> query + platform mid-string
    query, mid_plat = _split_search_on_platform(work)
    if mid_plat:
        ent.platform = mid_plat
        work = query
        ent.search_query = query
        ent.target = query

    ent.target = work

    # Resolved context path: open C:\...\file.png in brave
    if work and os.path.isfile(work):
        ent.local_path = os.path.normpath(work)
        ent.target = os.path.basename(work)

    if intent == INTENT_WEB_SEARCH or ent.search_query:
        ent.search_query = ent.search_query or work
        if not ent.platform:
            ent.platform = "google"

    if ent.browser:
        ent.force_browser = True

    # Known website token — defer to local index unless browser is explicit
    if intent == INTENT_OPEN_FILE and _is_website_token(work):
        ent.website = work.lower().replace(" ", "")
        if ent.browser:
            ent.force_browser = True

    # Browser + web search intent => never local index
    if ent.browser and (ent.search_query or intent == INTENT_WEB_SEARCH):
        ent.force_browser = True

    # Local file opened in a specific browser
    if ent.browser and ent.local_path:
        ent.force_browser = True

    if ent.browser and not ent.platform and intent == INTENT_WEB_SEARCH:
        ent.platform = "google"

    return ent


def _parse_web_search_phrases(work: str, ent: Entities) -> str:
    """Parse: search youtube for physics in brave"""
    m = re.match(
        rf"^({'|'.join(PLATFORMS)})\s+for\s+(.+)$",
        work,
        re.I,
    )
    if not m:
        return work

    ent.platform = m.group(1).lower()
    rest = m.group(2).strip()

    browser = _extract_browser_phrase(rest)
    if browser:
        ent.browser = browser
        rest = _strip_trailing_browser(rest, browser)
        ent.force_browser = True

    ent.search_query = rest
    ent.target = rest
    return rest


def _extract_browser_phrase(text: str) -> str | None:
    m = re.search(r"\s+in\s+(\w+)\s*$", text, re.I)
    if m and is_browser_name(m.group(1)):
        return normalize_browser(m.group(1))
    m = re.search(r"\s+on\s+(\w+)\s*$", text, re.I)
    if m and is_browser_name(m.group(1)):
        return normalize_browser(m.group(1))
    return None


def _extract_platform_phrase(text: str) -> str | None:
    m = re.search(r"\s+on\s+(\w+)\s*$", text, re.I)
    if m:
        word = m.group(1).lower()
        if word in PLATFORMS:
            return word
    return None


def _strip_trailing_browser(text: str, browser: str) -> str:
    text = re.sub(rf"\s+in\s+{re.escape(browser)}\s*$", "", text, flags=re.I)
    text = re.sub(rf"\s+on\s+{re.escape(browser)}\s*$", "", text, flags=re.I)
    return text.strip()


def _strip_trailing_platform(text: str, platform: str) -> str:
    return re.sub(rf"\s+on\s+{re.escape(platform)}\s*$", "", text, flags=re.I).strip()


def _split_search_on_platform(rest: str) -> tuple[str, str | None]:
    m = re.search(
        r"^(.+?)\s+on\s+(google|youtube|amazon|flipkart|github|reddit|wikipedia)\s*$",
        rest,
        re.I,
    )
    if m:
        return m.group(1).strip(), m.group(2).lower()
    return rest.strip(), None


def _is_website_token(text: str) -> bool:
    token = text.strip().lower()
    return bool(token) and " " not in token and is_known_website(token)
