"""
ranking.py — Score and select the best local match.

Ranking priority (combined score):
  1. Exact normalized match (strong boost)
  2. Partial / keyword overlap
  3. Fuzzy similarity (typos, spacing)
  4. Intent/route compatibility:
     - launch/run/start -> executables & shortcuts
     - play -> video/audio
     - folder route -> directories
  5. Number/pattern tokens (s01e01, years)

Result selection:
  - Must meet MIN_MATCH_SCORE
  - Reliable if HIGH_CONFIDENCE or clear gap to second-best
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from alias_engine import canonical_token as canonical_for
from normalize import NormalizedQuery, normalize_name
from parser import (
    ROUTE_LOCAL_APP,
    ROUTE_LOCAL_FOLDER,
    ROUTE_LOCAL_MEDIA,
)
from models import SearchItem
from search_config import HIGH_CONFIDENCE_SCORE, MIN_MATCH_SCORE, MIN_SCORE_GAP

W_EXACT = 0.22
W_FUZZY = 0.28
W_KEYWORDS = 0.28
W_NUMBERS = 0.08
W_PATTERNS = 0.08
W_INTENT = 0.18

TIE_MARGIN = 0.04


@dataclass
class RankedMatch:
    item: SearchItem
    score: float
    reliable: bool


def find_best(
    parsed: NormalizedQuery, items: list[SearchItem], min_score: float = MIN_MATCH_SCORE
) -> RankedMatch | None:
    """Return best match if score is reliable enough."""
    if not items:
        return None

    scored: list[tuple[float, SearchItem]] = []
    for item in items:
        s = score_item(parsed, item)
        if s > 0:
            scored.append((s, item))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)

    if parsed.wants_latest:
        latest = _pick_latest(parsed, scored, min_score)
        if latest:
            s = score_item(parsed, latest)
            if s >= min_score:
                return RankedMatch(latest, s, _is_reliable(s, scored, latest))

    best_score, best_item = _resolve_winner(parsed, scored)
    if best_score < min_score:
        return None

    reliable = _is_reliable(best_score, scored, best_item)
    return RankedMatch(best_item, best_score, reliable)


def _is_reliable(
    best_score: float,
    scored: list[tuple[float, SearchItem]],
    best_item: SearchItem,
) -> bool:
    if best_score >= HIGH_CONFIDENCE_SCORE:
        return True
    if best_score < MIN_MATCH_SCORE:
        return False
    second = next((s for s, i in scored if i.path != best_item.path), None)
    if second is None:
        return best_score >= MIN_MATCH_SCORE
    return (best_score - second) >= MIN_SCORE_GAP


def score_item(parsed: NormalizedQuery, item: SearchItem) -> float:
    names = _item_names(item)
    exact = max(_exact_score(parsed, n) for n in names)
    fuzzy = max(_fuzzy_score(parsed.normalized, n) for n in names)
    keywords = max(_keyword_score(parsed.tokens, n) for n in names)
    numbers = _number_score(parsed.numbers, item.name)
    patterns = _pattern_score(parsed, item.name)
    intent = _route_intent_score(parsed, item)

    total = (
        W_EXACT * exact
        + W_FUZZY * fuzzy
        + W_KEYWORDS * keywords
        + W_NUMBERS * numbers
        + W_PATTERNS * patterns
        + W_INTENT * intent
    )
    total += _type_hint_boost(parsed, item)
    total += _recency_boost(item.mtime)
    return min(total, 1.0)


def _recency_boost(mtime: float) -> float:
    """Small boost for recently modified files (latest-screenshot style queries)."""
    if mtime <= 0:
        return 0.0
    import time

    age_days = (time.time() - mtime) / 86400
    if age_days < 1:
        return 0.06
    if age_days < 7:
        return 0.04
    if age_days < 30:
        return 0.02
    return 0.0


def _exact_score(parsed: NormalizedQuery, name: str) -> float:
    q = parsed.normalized.strip()
    if not q:
        return 0.0
    if q == name:
        return 1.0
    # token-exact: all query tokens present as whole words
    if parsed.tokens and all(
        re.search(rf"\b{re.escape(t)}\b", name) for t in parsed.tokens if len(t) >= 2
    ):
        return 0.92
    return 0.0


def _route_intent_score(parsed: NormalizedQuery, item: SearchItem) -> float:
    """Route-aware intent: launch->apps, play->media, folder route->dirs."""
    kind = item.kind
    route = parsed.route
    intent = parsed.intent

    apps = {"application", "shortcut"}
    media = {"video", "audio"}

    if route == ROUTE_LOCAL_APP or intent in ("launch", "run", "start"):
        if kind in apps:
            return 1.0
        if kind == "folder":
            return 0.25
        return 0.45

    if route == ROUTE_LOCAL_MEDIA or intent == "play":
        if kind in media:
            return 1.0
        if kind == "folder":
            return 0.12
        if kind in apps:
            return 0.15
        return 0.35

    if route == ROUTE_LOCAL_FOLDER:
        if kind == "folder":
            return 1.0
        return 0.4

    if parsed.type_hint and kind == parsed.type_hint:
        return 1.0
    return 0.72


def _item_names(item: SearchItem) -> list[str]:
    stem = normalize_name(item.name)
    canonical = canonical_for(stem)
    names = [stem, normalize_name(Path(item.path).stem)]
    if canonical != stem:
        names.append(canonical)
    return names


def _resolve_winner(
    parsed: NormalizedQuery, scored: list[tuple[float, SearchItem]]
) -> tuple[float, SearchItem]:
    best_score, best_item = scored[0]
    best_file = next(((s, i) for s, i in scored if i.kind != "folder"), None)
    best_folder = next(((s, i) for s, i in scored if i.kind == "folder"), None)

    if best_file and best_folder:
        fs, fi = best_file
        fos, foi = best_folder
        if abs(fs - fos) <= TIE_MARGIN and _folder_should_win(parsed, fi, foi):
            return fos, foi
    return best_score, best_item


def _folder_should_win(
    parsed: NormalizedQuery, file_item: SearchItem, folder_item: SearchItem
) -> bool:
    if parsed.route == ROUTE_LOCAL_FOLDER:
        return True
    if parsed.type_hint == "folder":
        return True
    if parsed.type_hint and parsed.type_hint != "folder":
        return False
    fn = normalize_name(file_item.name)
    fon = normalize_name(folder_item.name)
    fh = sum(1 for t in parsed.tokens if t in fn)
    dh = sum(1 for t in parsed.tokens if t in fon)
    return dh > fh


def _pick_latest(
    parsed: NormalizedQuery,
    scored: list[tuple[float, SearchItem]],
    min_score: float,
) -> SearchItem | None:
    hint = parsed.type_hint or "image"
    pool = [
        (s, i)
        for s, i in scored
        if s >= min_score and i.kind == hint and not os.path.isdir(i.path)
    ]
    if not pool:
        pool = [(s, i) for s, i in scored if s >= min_score and not os.path.isdir(i.path)]
    if not pool:
        return None
    pool.sort(key=lambda x: x[1].mtime, reverse=True)
    return pool[0][1]


def _fuzzy_score(query: str, name: str) -> float:
    q, n = query.strip(), name.strip()
    if not q or not n:
        return 0.0
    if q in n:
        return 0.95
    q_us = q.replace(" ", "_")
    return max(
        SequenceMatcher(None, q, n).ratio(),
        SequenceMatcher(None, q_us, n).ratio(),
        SequenceMatcher(
            None, " ".join(sorted(q.split())), " ".join(sorted(n.split()))
        ).ratio(),
    )


def _keyword_score(tokens: list[str], name: str) -> float:
    if not tokens:
        return 0.0
    meaningful = [t for t in tokens if len(t) >= 2 or t.isdigit()]
    if not meaningful:
        meaningful = tokens
    hits = sum(1 for t in meaningful if t in name)
    return hits / len(meaningful)


def _number_score(numbers: list[str], name: str) -> float:
    if not numbers:
        return 0.0
    lower = name.lower()
    return sum(1 for n in numbers if n in lower) / len(numbers)


def _pattern_score(parsed: NormalizedQuery, name: str) -> float:
    n = name.lower()
    parts = hit = 0
    if parsed.season:
        parts += 1
        if re.search(rf"s0?{int(parsed.season)}", n):
            hit += 1
    if parsed.episode:
        parts += 1
        if re.search(rf"e0?{int(parsed.episode)}", n):
            hit += 1
    if parsed.version:
        parts += 1
        if re.search(rf"\bv{parsed.version}\b", n):
            hit += 1
    return hit / parts if parts else 0.0


def _type_hint_boost(parsed: NormalizedQuery, item: SearchItem) -> float:
    if parsed.type_hint and item.kind == parsed.type_hint:
        return 0.1
    if parsed.extension and item.path.lower().endswith(parsed.extension):
        return 0.12
    return 0.0
