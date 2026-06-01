"""
router.py — Deterministic multi-stage routing engine.

Pipeline:
  query -> normalize -> intent -> entities -> candidates -> scoring
        -> confidence -> action

Preserves: SQLite index, watchdog, launcher, browser registry.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from alias_engine import expand_aliases
from browser_registry import launch_url
from candidate_generator import generate_index_candidates
from confidence_engine import evaluate
from debug_log import RouteDebug, is_debug_enabled
from entity_extractor import Entities, extract_entities
from reference_resolver import hint_for_folder_latest, resolve_user_input
from session_memory import get_session_memory
from intent_engine import (
    IntentResult,
    INTENT_CLOSE_APP,
    INTENT_LAUNCH_APP,
    INTENT_OPEN_FILE,
    INTENT_OPEN_SETTINGS,
    INTENT_OPEN_WEBSITE,
    INTENT_PLAY_MEDIA,
    INTENT_UNKNOWN,
    INTENT_WEB_SEARCH,
    detect_intent,
    has_launcher_verb,
)
from intent_parser import parse_intent
from intent_schema import (
    IntentSchema,
    SEMANTIC_OPEN_APP,
    SEMANTIC_OPEN_DOCUMENT,
    SEMANTIC_PLAY_MEDIA,
    SEMANTIC_SEARCH_WEB,
    SEMANTIC_WATCH_MEDIA,
)
from semantic_intent import resolve_settings_match, should_skip_file_search
from settings_router import launch_settings, resolve_settings
from launcher import launch_item, launch_system_app
from system_apps import resolve_system_app, user_wants_explicit_local
from models import Candidate, ScoredCandidate, SearchItem
from normalize import build_search_query, looks_like_ai_chat, normalize_input
from scoring_engine import score_candidates
from websites import build_search_url, is_known_website, resolve_website

# Pending disambiguation (user picks 1, 2, 3…)
_pending_choices: list[ScoredCandidate] = []

_CHOICE_RE = re.compile(r"^(?:open|choose|pick|select)\s+(\d+)$", re.I)


def handle_request(user_text: str) -> str | None:
    """Run routing pipeline. None -> AI fallback in main.py."""
    global _pending_choices
    dbg = RouteDebug()
    text = user_text.strip()
    dbg.input_text = text

    if not text:
        return "Please type a command or question."

    # Short-term memory: resolve it/that/first one/open latest …
    session = get_session_memory()
    resolved = resolve_user_input(text, session)
    text = resolved.text

    # Ordinal from memory ("open the first one") when list still pending
    if resolved.ordinal is not None:
        if _pending_choices and resolved.ordinal <= len(_pending_choices):
            return _resolve_numeric_choice(resolved.ordinal, dbg)
        item = session.get_item_by_ordinal(resolved.ordinal)
        if item and not _pending_choices:
            return _open_memory_item(item, dbg, session)

    # Numeric pick from previous list: "1", "open 2", "choose 3"
    choice_n = _parse_choice_number(text)
    if choice_n is not None and _pending_choices:
        return _resolve_numeric_choice(choice_n, dbg)

    _pending_choices = []

    if looks_like_ai_chat(text) and not has_launcher_verb(text):
        dbg.route = "ai_chat"
        dbg.fallback_reason = "question -> AI"
        dbg.flush()
        return None

    # 1. Normalize
    normalized = normalize_input(text)
    normalized = expand_aliases(normalized)
    dbg.normalized_text = normalized

    # 1b. Settings priority — before file index (sound settings, bluetooth, wifi, …)
    settings_msg = _try_settings_route(normalized, text, dbg, session)
    if settings_msg is not None:
        return settings_msg

    # 2. Intent
    intent_result = detect_intent(text, normalized)
    semantic_result = _semantic_from_deterministic(intent_result)

    if intent_result.intent == INTENT_UNKNOWN or not intent_result.raw_verb:
        # 2b. Semantic understanding only; deterministic router still executes.
        try:
            semantic_result = parse_intent(text)
    # Try semantic understanding to refine intent, even if rule-based verb exists
    try:
        parsed_semantic = parse_intent(text)
        if parsed_semantic and parsed_semantic.confidence > 0.6:
            semantic_result = parsed_semantic
            mapped = _intent_from_semantic(semantic_result)
            if mapped is not None:
            if mapped:
                intent_result = mapped
        except Exception as err:
            if is_debug_enabled():
                dbg.extra["semantic_error"] = str(err)
    except Exception as err:
        if is_debug_enabled():
            dbg.extra["semantic_error"] = str(err)

    dbg.intent = intent_result.intent

    # 3. Entities
    entities = extract_entities(
        text, normalized, intent_result.intent, intent_result.remainder
    )
    dbg.target = entities.target
    dbg.browser = entities.browser
    dbg.platform = entities.platform
    dbg.search_query = entities.search_query
    if semantic_result and semantic_result.platform:
        entities.platform = semantic_result.platform
        dbg.platform = entities.platform

    # --- Explicit browser / web search (skip local index) -------------------
    if _should_browser_shortcut(intent_result.intent, entities):
        dbg.route = "browser_action"
        if entities.local_path and entities.browser:
            result = _action_local_in_browser(entities)
        else:
            result = _action_browser(entities, intent_result.intent)
        dbg.fallback_reason = "explicit web/browser intent"
        dbg.flush()
        return result

    if intent_result.intent == INTENT_CLOSE_APP:
        dbg.route = "close_app"
        result = _action_close(entities.target)
        dbg.flush()
        return result

    # --- Windows Settings (intent path; early route may have handled already) ---
    if intent_result.intent == INTENT_OPEN_SETTINGS and intent_result.setting_id:
        settings_msg = _launch_settings_by_id(
            intent_result.setting_id,
            intent_result.semantic_confidence,
            dbg,
            session,
        )
        if settings_msg is not None:
            dbg.flush()
            return settings_msg

    # --- Windows system apps (override index unless explicit file/folder) ---
    if not user_wants_explicit_local(text):
        sys_app = resolve_system_app(entities.target)
        if sys_app:
            dbg.route = "SYSTEM_APP"
            dbg.match_name = sys_app.display_name
            dbg.match_kind = "SYSTEM_APP"
            dbg.fallback_reason = "resolved as SYSTEM_APP"
            dbg.extra["system_app_command"] = sys_app.command
            session.record_app(sys_app.display_name)
            result = launch_system_app(sys_app)
            dbg.flush()
            return result

    # 4. Candidate generation (index) - skip when query is a settings command
    if should_skip_file_search(text, normalized):
        settings_msg = _try_settings_route(normalized, text, dbg, session)
        if settings_msg is not None:
            return settings_msg
        return (
            "That looks like a Windows settings request, but I couldn't match a "
            "specific page. Try: sound settings, bluetooth, wifi settings, display."
        )

    route = _route_for_intent(intent_result.intent)
    folder_hint = hint_for_folder_latest(text, session)
    candidates, search_meta = generate_index_candidates(
        entities.target, intent_result.intent, route, folder_hint=folder_hint
    )
    dbg.index_candidates = search_meta.get("candidates")
    dbg.index_total = search_meta.get("total_indexed")
    dbg.search_ms = search_meta.get("elapsed_ms")
    dbg.extra["candidate_count"] = len(candidates)
    dbg.extra["candidate_categories"] = _category_summary(candidates)

    # 5. Scoring
    parsed = build_search_query(entities.target, intent_result.intent, route)
    scored = score_candidates(
        candidates, parsed.normalized, parsed.tokens, intent_result.intent
    )

    _attach_score_debug(dbg, scored)

    # 6. Confidence
    decision = evaluate(scored)
    dbg.extra["confidence"] = f"{decision.confidence:.2f}"
    dbg.route = decision.action

    # 7. Action
    if scored:
        session.record_search_results(scored)

    semantic_fallback = _try_semantic_low_confidence_fallback(
        semantic_result, decision, entities, intent_result.intent
    )
    if semantic_fallback is not None:
        dbg.route = "browser_action"
        dbg.fallback_reason = "semantic low-confidence local match -> web"
        dbg.flush()
        return semantic_fallback

    result = _execute_decision(
        decision, entities, dbg, text, session, intent_result.intent
    )
    dbg.flush()
    return result

def _try_settings_route(
    normalized: str,
    user_text: str,
    dbg: RouteDebug,
    session,
) -> str | None:
    """Strong settings priority: ms-settings before indexed file search."""
    if user_wants_explicit_local(user_text):
        return None
    match = resolve_settings_match(user_text, normalized)
    if not match or not match.setting_id:
        return None
    return _launch_settings_by_id(match.setting_id, match.confidence, dbg, session)


def _launch_settings_by_id(
    setting_id: str,
    confidence: float,
    dbg: RouteDebug,
    session,
) -> str | None:
    target = resolve_settings(setting_id)
    if not target:
        return None
    dbg.route = "settings"
    dbg.match_name = target.display_name
    dbg.match_kind = "SETTINGS"
    dbg.extra["confidence"] = f"{confidence:.2f}"
    dbg.fallback_reason = "settings priority (ms-settings)"
    session.record_settings(target.display_name)
    return launch_settings(target)


def _intent_from_semantic(semantic: IntentSchema) -> IntentResult | None:
    target = semantic.target or semantic.query
    if semantic.intent == SEMANTIC_OPEN_APP and target:
        return IntentResult("semantic", INTENT_LAUNCH_APP, target, True)
    if semantic.intent == SEMANTIC_OPEN_DOCUMENT and target:
        return IntentResult("semantic", INTENT_OPEN_FILE, target, True)
    if semantic.intent in (SEMANTIC_WATCH_MEDIA, SEMANTIC_PLAY_MEDIA) and target:
        return IntentResult("semantic", INTENT_PLAY_MEDIA, target, True)
    if semantic.intent == SEMANTIC_SEARCH_WEB and (semantic.query or target):
        return IntentResult("semantic", INTENT_WEB_SEARCH, semantic.query or target, True)
    return None


def _semantic_from_deterministic(intent_result: IntentResult) -> IntentSchema | None:
    if intent_result.intent == INTENT_PLAY_MEDIA and intent_result.remainder:
        return IntentSchema(
            SEMANTIC_PLAY_MEDIA,
            target=intent_result.remainder,
            query=intent_result.remainder,
            platform="youtube",
            confidence=0.75,
            source="deterministic",
        )
    if intent_result.intent == INTENT_OPEN_FILE and intent_result.remainder:
        tokens = set(re.findall(r"[a-z0-9]+", intent_result.remainder.lower()))
        if tokens & {"season", "episode", "movie", "movies", "video", "videos", "anime"}:
            return IntentSchema(
                SEMANTIC_WATCH_MEDIA,
                target=intent_result.remainder,
                query=intent_result.remainder,
                platform="youtube",
                confidence=0.72,
                source="deterministic",
            )
        if tokens & {"note", "notes", "pdf", "document", "documents"}:
            return IntentSchema(
                SEMANTIC_OPEN_DOCUMENT,
                target=intent_result.remainder,
                query=intent_result.remainder,
                confidence=0.72,
                source="deterministic",
            )
    return None


def _try_semantic_low_confidence_fallback(
    semantic: IntentSchema | None,
    decision,
    entities: Entities,
    route_intent: str,
) -> str | None:
    if semantic is None or decision.action != "clarify":
        return None
    if semantic.intent not in (
        SEMANTIC_OPEN_DOCUMENT,
        SEMANTIC_WATCH_MEDIA,
        SEMANTIC_PLAY_MEDIA,
    ):
        return None
    query = semantic.query or semantic.target or entities.target
    if not query:
        return None
    platform = semantic.platform
    if not platform and route_intent == INTENT_PLAY_MEDIA:
        platform = "youtube"
    fallback_entities = Entities(
        raw=entities.raw,
        target=query,
        search_query=query,
        platform=platform or "google",
        browser=entities.browser,
        force_browser=True,
    )
    return _action_browser(fallback_entities, INTENT_WEB_SEARCH)


def _should_browser_shortcut(intent: str, entities: Entities) -> bool:
    """Web/browser path when explicitly requested — includes local file in browser."""
    if entities.local_path and entities.browser:
        return True
    if intent == INTENT_WEB_SEARCH and entities.search_query:
        return True
    if entities.website and entities.browser:
        return True
    if entities.force_browser and entities.browser and entities.search_query:
        return True
    return False


def _execute_decision(
    decision,
    entities: Entities,
    dbg: RouteDebug,
    user_text: str = "",
    session=None,
    route_intent: str = "",
) -> str | None:
    if session is None:
        session = get_session_memory()
    if decision.action == "open" and decision.chosen:
        c = decision.chosen.candidate
        if not user_wants_explicit_local(user_text):
            sys_app = resolve_system_app(entities.target)
            if sys_app and c.item_type not in ("app", "system_app"):
                dbg.route = "SYSTEM_APP"
                dbg.match_name = sys_app.display_name
                dbg.match_kind = "SYSTEM_APP"
                dbg.fallback_reason = "resolved as SYSTEM_APP (over file match)"
                session.record_app(sys_app.display_name)
                return launch_system_app(sys_app)
        item = _candidate_to_search_item(c)
        msg = launch_item(item, decision.chosen.score)
        if route_intent == INTENT_PLAY_MEDIA or c.item_type in ("video", "audio"):
            session.record_play(item, score=decision.chosen.score)
        else:
            session.record_open(item, score=decision.chosen.score, browser=entities.browser)
        dbg.fallback_reason = "auto-open (high confidence)"
        return msg

    if decision.action == "clarify":
        dbg.fallback_reason = "low confidence — ask clarification"
        return decision.message

    if decision.action == "ask_user":
        global _pending_choices
        _pending_choices = decision.top_candidates
        session.record_search_results(decision.top_candidates)
        dbg.fallback_reason = "ambiguous — ask user"
        return decision.message

    # Safe website fallback: only when no strong local match
    web = _try_website_fallback(entities)
    if web:
        dbg.route = "browser_action"
        dbg.fallback_reason = "no strong local match -> website"
        return web

    dbg.fallback_reason = "no local match -> AI"
    return None


def _try_website_fallback(entities: Entities) -> str | None:
    token = entities.target.strip().lower().replace(" ", "")
    if not token or not is_known_website(token):
        return None
    url = resolve_website(token)
    return f"{launch_url(url, entities.browser)} Site: {token}"


def _action_local_in_browser(entities: Entities) -> str:
    """Open a local file URI in the chosen browser."""
    path = entities.local_path
    if not path or not os.path.isfile(path):
        return "No file to open in the browser."
    url = Path(path).resolve().as_uri()
    browser = entities.browser
    session = get_session_memory()
    session.record_open(
        SearchItem(
            name=os.path.basename(path),
            path=path,
            kind="document",
            mtime=0,
            search_text="",
            item_type="document",
        ),
        browser=browser,
    )
    return f"{launch_url(url, browser)} File: {os.path.basename(path)}"


def _action_browser(entities: Entities, intent: str) -> str:
    session = get_session_memory()
    if entities.website:
        url = resolve_website(entities.website)
        session.record_website(entities.website, entities.browser)
        return f"{launch_url(url, entities.browser)} Site: {entities.website}"

    query = entities.search_query or entities.target
    platform = entities.platform or "google"
    url = build_search_url(query, platform)
    session.record_search(query, platform, browser=entities.browser)
    return f"{launch_url(url, entities.browser)} Searching {platform} for: {query}"


def _action_close(target: str) -> str:
    name = target.strip().lower()
    if not name:
        return "Say which app to close, e.g. close chrome"
    exe = name if name.endswith(".exe") else f"{name}.exe"
    try:
        subprocess.run(
            ["taskkill", "/IM", exe, "/F"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return f"Tried to close {name}."
    except Exception as err:
        return f"Could not close {name}: {err}"


def _parse_choice_number(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    m = _CHOICE_RE.match(text.strip())
    return int(m.group(1)) if m else None


def _resolve_numeric_choice(n: int, dbg: RouteDebug) -> str:
    global _pending_choices
    count = len(_pending_choices)
    if n < 1 or n > count:
        _pending_choices = []
        return f"Pick a number between 1 and {count}." if count else "No pending choices."
    chosen = _pending_choices[n - 1]
    _pending_choices = []
    item = _candidate_to_search_item(chosen.candidate)
    dbg.route = "open (user choice)"
    dbg.match_name = chosen.candidate.name
    dbg.match_score = chosen.score
    dbg.fallback_reason = f"user selected option {n}"
    dbg.flush()
    session = get_session_memory()
    if chosen.candidate.item_type in ("video", "audio"):
        session.record_play(item, score=chosen.score)
    else:
        session.record_open(item, score=chosen.score)
    return launch_item(item, chosen.score)


def _open_memory_item(item, dbg: RouteDebug, session) -> str:
    """Open an item resolved from session memory (ordinal without pending list)."""
    search_item = SearchItem(
        name=item.name,
        path=item.path,
        kind=item.item_type,
        mtime=0,
        search_text="",
        item_type=item.item_type,
    )
    dbg.route = "open (memory reference)"
    dbg.match_name = item.name
    dbg.fallback_reason = "resolved from session memory"
    dbg.flush()
    session.record_open(search_item)
    return launch_item(search_item, item.score)


def _candidate_to_search_item(c: Candidate):
    from models import SearchItem

    return SearchItem(
        name=c.name,
        path=c.path,
        kind=c.item_type,
        mtime=c.mtime,
        search_text=c.search_text,
        item_type=c.item_type,
    )


def _route_for_intent(intent: str) -> str:
    if intent == INTENT_LAUNCH_APP:
        return "local_app"
    if intent == INTENT_PLAY_MEDIA:
        return "local_media"
    from intent_engine import INTENT_OPEN_FOLDER

    if intent == INTENT_OPEN_FOLDER:
        return "local_folder"
    return "local_open"


def _category_summary(candidates: list[Candidate]) -> str:
    counts: dict[str, int] = {}
    for c in candidates:
        counts[c.item_type] = counts.get(c.item_type, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def _attach_score_debug(dbg: RouteDebug, scored: list[ScoredCandidate]) -> None:
    if not scored:
        return
    top = scored[0]
    dbg.match_name = top.candidate.name
    dbg.match_kind = top.candidate.item_type
    dbg.match_score = top.score
    b = top.breakdown
    dbg.extra["score_breakdown"] = (
        f"exact={b.exact:.2f} fuzzy={b.fuzzy:.2f} kw={b.keywords:.2f} "
        f"type={b.type_match:.2f} boost={b.boost:.2f} penalty={b.penalty:.2f} "
        f"total={top.score:.2f}"
    )
    if is_debug_enabled():
        lines = []
        for i, sc in enumerate(scored[:5], 1):
            c = sc.candidate
            lines.append(f"{i}. {c.name} [{c.item_type}] {sc.score:.2f}")
        dbg.extra["top_ranked"] = " | ".join(lines)
