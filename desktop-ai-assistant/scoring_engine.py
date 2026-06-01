"""
scoring_engine.py — Weighted candidate scoring with type biasing.

Factors:
  - exact / fuzzy / keyword match
  - type compatibility with intent
  - alias expansion
  - recency (mtime)
  - path importance (Downloads/Desktop boost)
  - app/system boosts and noise/extension penalties
"""

from __future__ import annotations

import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

from alias_engine import canonical_token
from intent_engine import (
    INTENT_LAUNCH_APP,
    INTENT_OPEN_FILE,
    INTENT_OPEN_FOLDER,
    INTENT_PLAY_MEDIA,
    KNOWN_APP_TARGETS,
)
from system_apps import reserved_system_names
from models import Candidate, ScoreBreakdown, ScoredCandidate
from normalize import normalize_name
from scoring_config import (
    WEIGHT_ALIAS,
    WEIGHT_EXACT,
    WEIGHT_FUZZY,
    WEIGHT_KEYWORDS,
    WEIGHT_PATH,
    WEIGHT_RECENCY,
    WEIGHT_TYPE,
)

TYPE_BIAS: dict[str, set[str]] = {
    INTENT_PLAY_MEDIA: {"video", "audio"},
    INTENT_LAUNCH_APP: {"app", "system_app"},
    INTENT_OPEN_FOLDER: {"folder"},
    INTENT_OPEN_FILE: {"document", "image", "video", "audio"},
}

PATH_BOOST_FOLDERS = ("downloads", "desktop", "documents")

NOISE_NAME_PARTS = (
    "release_notes", "release notes", "readme", "changelog", "license",
    "copying", "third_party", "third party", "node_modules", "package-lock",
    "yarn.lock", ".min.", "vendor", "dist", "build", "cache",
    "debug_notes", "debug notes", "dev_notes", "dev notes",
    "todo", "todos", "contributing", "authors", "notice",
)

CONFIG_PATH_MARKERS = (
    "\\.vscode\\", "\\node_modules\\", "\\appdata\\roaming\\",
    "\\.config\\", "\\.cursor\\", "\\.git\\",
)

_RESERVED_SYSTEM_NAMES = reserved_system_names()


def score_candidates(
    candidates: list[Candidate],
    query_normalized: str,
    tokens: list[str],
    intent: str,
) -> list[ScoredCandidate]:
    """Score and sort all candidates (highest first)."""
    from semantic_intent import looks_like_settings_query

    # Settings-shaped queries must not lose to random indexed files
    if looks_like_settings_query(query_normalized):
        return []

    scored: list[ScoredCandidate] = []
    q_norm = normalize_name(query_normalized)

    for cand in candidates:
        bd = _score_one(cand, q_norm, tokens, intent)
        total = min(bd.total, 1.0)
        if total > 0:
            scored.append(ScoredCandidate(cand, total, bd))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def _score_one(
    cand: Candidate,
    q_norm: str,
    tokens: list[str],
    intent: str,
) -> ScoreBreakdown:
    names = [normalize_name(cand.name), cand.search_text or normalize_name(cand.name)]
    stem = normalize_name(Path(cand.path).stem)

    exact = max(_exact_score(q_norm, n, tokens) for n in names)
    fuzzy = max(_fuzzy_score(q_norm, n) for n in names)
    keywords = _keyword_score(tokens, " ".join(names))
    type_match = _type_score(cand.item_type, intent)
    alias = _alias_score(tokens, names)
    recency = _recency_score(cand.mtime)
    path_boost = _path_score(cand.path)

    boost = _compute_boost(cand, q_norm, tokens, intent, stem, names)
    penalty = _compute_penalty(cand, q_norm, tokens, intent, stem)

    return ScoreBreakdown(
        exact=WEIGHT_EXACT * exact,
        fuzzy=WEIGHT_FUZZY * fuzzy,
        keywords=WEIGHT_KEYWORDS * keywords,
        type_match=WEIGHT_TYPE * type_match,
        alias=WEIGHT_ALIAS * alias,
        recency=WEIGHT_RECENCY * recency,
        path_boost=WEIGHT_PATH * path_boost,
        boost=boost,
        penalty=penalty,
    )


def _compute_boost(
    cand: Candidate,
    q_norm: str,
    tokens: list[str],
    intent: str,
    stem: str,
    names: list[str],
) -> float:
    boost = 0.0

    if stem == q_norm or normalize_name(cand.name) == q_norm:
        boost += 0.12

    if cand.item_type in ("app", "system_app"):
        if intent in (INTENT_LAUNCH_APP, INTENT_OPEN_FILE):
            boost += 0.08
        if stem in KNOWN_APP_TARGETS or q_norm in KNOWN_APP_TARGETS:
            boost += 0.14

    if cand.item_type == "system_app":
        boost += 0.10

    if intent == INTENT_LAUNCH_APP and cand.item_type in ("app", "system_app"):
        boost += 0.06

    # Note-taking / notes queries: prefer apps and user documents over noise files
    if "notes" in tokens or q_norm == "notes":
        if cand.item_type in ("app", "system_app") and "note" in stem:
            boost += 0.10
        if cand.item_type == "document" and "note" in stem and "release" not in stem:
            boost += 0.05

    for t in tokens:
        c = canonical_token(t)
        if c != t.lower() and any(c == n or c in n for n in names):
            boost += 0.06

    return min(boost, 0.28)


def _compute_penalty(
    cand: Candidate,
    q_norm: str,
    tokens: list[str],
    intent: str,
    stem: str,
) -> float:
    penalty = 0.0
    name_lower = normalize_name(cand.name)
    path_lower = cand.path.lower()

    from semantic_intent import looks_like_settings_query, SHORT_SETTING_COMMANDS

    if looks_like_settings_query(q_norm) or q_norm in SHORT_SETTING_COMMANDS:
        penalty += 0.50

    # Short semantic commands (bluetooth, sound, wifi) — deprioritize unrelated files
    q_tokens = set(re.findall(r"[a-z]+", q_norm))
    if q_tokens & set(SHORT_SETTING_COMMANDS.keys()) and len(q_tokens) <= 3:
        if cand.item_type not in ("app", "system_app"):
            penalty += 0.35

    for noise in NOISE_NAME_PARTS:
        if noise in name_lower and noise not in q_norm:
            penalty += 0.22
            break

    if "release" in name_lower and "notes" in tokens and "release" not in q_norm:
        penalty += 0.20

    # "open notes" — penalize changelog/debug/readme noise
    if "notes" in tokens or q_norm in ("notes", "note"):
        noise_bits = ("release", "changelog", "debug", "dev", "readme", "todo")
        if any(n in name_lower for n in noise_bits) and "note" in name_lower:
            if not any(n in q_norm for n in noise_bits):
                penalty += 0.24

    for marker in CONFIG_PATH_MARKERS:
        if marker in path_lower:
            penalty += 0.18
            break

    ext = Path(cand.path).suffix.lower()
    if ext and not any(t.endswith(ext.lstrip(".")) for t in tokens):
        if intent in (INTENT_LAUNCH_APP,) or q_norm in KNOWN_APP_TARGETS:
            if ext in (".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".log"):
                penalty += 0.25
            elif ext in (".md", ".txt") and stem != q_norm:
                penalty += 0.12

    if intent == INTENT_LAUNCH_APP and cand.item_type == "document":
        penalty += 0.15

    # Reserved Windows system names: never prefer a loose file match
    if q_norm in _RESERVED_SYSTEM_NAMES or stem in _RESERVED_SYSTEM_NAMES:
        if cand.item_type in ("document", "folder", "image", "video", "audio"):
            penalty += 0.35
        if cand.item_type in ("document",) and stem == q_norm:
            penalty += 0.25

    if intent == INTENT_OPEN_FOLDER and cand.item_type != "folder":
        penalty += 0.10

    # Intent-aware: launching apps — deprioritize non-app files
    if intent == INTENT_OPEN_FILE and q_norm in KNOWN_APP_TARGETS:
        if cand.item_type not in ("app", "system_app") and cand.item_type != "folder":
            penalty += 0.12

    # Partial token buried in long unrelated filenames (e.g. release_notes)
    if tokens and len(tokens) == 1 and len(stem) > len(tokens[0]) + 6:
        t = tokens[0]
        if t in name_lower and stem != q_norm and t not in stem.split():
            penalty += 0.14

    return min(penalty, 0.40)


def _exact_score(q: str, name: str, tokens: list[str]) -> float:
    if q == name:
        return 1.0
    if q in name:
        return 0.95
    if tokens and all(re.search(rf"\b{re.escape(t)}\b", name) for t in tokens if len(t) >= 2):
        return 0.9
    return 0.0


def _fuzzy_score(q: str, name: str) -> float:
    if not q or not name:
        return 0.0
    if q in name:
        return 0.95
    q_us = q.replace(" ", "_")
    return max(
        SequenceMatcher(None, q, name).ratio(),
        SequenceMatcher(None, q_us, name).ratio(),
    )


def _keyword_score(tokens: list[str], name: str) -> float:
    if not tokens:
        return 0.0
    meaningful = [t for t in tokens if len(t) >= 2 or t.isdigit()]
    if not meaningful:
        meaningful = tokens
    hits = sum(1 for t in meaningful if re.search(rf"\b{re.escape(t)}\b", name))
    partial = sum(1 for t in meaningful if t in name and not re.search(rf"\b{re.escape(t)}\b", name))
    score = hits / len(meaningful)
    if partial and not hits:
        score = (partial / len(meaningful)) * 0.45
    return score


def _type_score(item_type: str, intent: str) -> float:
    preferred = TYPE_BIAS.get(intent, TYPE_BIAS[INTENT_OPEN_FILE])
    if item_type in preferred:
        return 1.0
    if intent == INTENT_PLAY_MEDIA and item_type == "folder":
        return 0.1
    if intent == INTENT_LAUNCH_APP:
        if item_type in ("document", "video", "image", "folder"):
            return 0.2
        return 0.35
    if intent == INTENT_OPEN_FILE:
        if item_type in ("app", "system_app"):
            return 0.55
        if item_type == "folder":
            return 0.4
    if intent == INTENT_OPEN_FOLDER and item_type != "folder":
        return 0.15
    return 0.45


def _alias_score(tokens: list[str], names: list[str]) -> float:
    for t in tokens:
        c = canonical_token(t)
        if c != t and any(c in n for n in names):
            return 1.0
    return 0.0


def _recency_score(mtime: float) -> float:
    if mtime <= 0:
        return 0.0
    days = (time.time() - mtime) / 86400
    if days < 1:
        return 1.0
    if days < 7:
        return 0.7
    if days < 30:
        return 0.4
    return 0.1


def _path_score(path: str) -> float:
    lower = path.lower()
    for part in PATH_BOOST_FOLDERS:
        if part in lower:
            return 0.8
    return 0.3
