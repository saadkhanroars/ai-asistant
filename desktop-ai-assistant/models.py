"""models.py — Shared types for index, routing, and scoring."""

from __future__ import annotations

from dataclasses import dataclass, field


# Indexed item kinds (internal) -> routing types (user-facing categories)
ITEM_TYPES = frozenset({
    "app",
    "folder",
    "document",
    "image",
    "video",
    "audio",
    "website",
    "system_app",
})


@dataclass
class SearchItem:
    """One row from the SQLite index."""

    name: str
    path: str
    kind: str
    mtime: float
    search_text: str
    item_type: str = "document"


@dataclass
class Candidate:
    """One possible action target before scoring."""

    name: str
    path: str
    item_type: str
    source: str  # index | website | browser
    mtime: float = 0.0
    search_text: str = ""


@dataclass
class ScoreBreakdown:
    exact: float = 0.0
    fuzzy: float = 0.0
    keywords: float = 0.0
    type_match: float = 0.0
    alias: float = 0.0
    recency: float = 0.0
    path_boost: float = 0.0
    boost: float = 0.0
    penalty: float = 0.0

    @property
    def total(self) -> float:
        return max(
            0.0,
            self.exact + self.fuzzy + self.keywords + self.type_match
            + self.alias + self.recency + self.path_boost
            + self.boost - self.penalty,
        )


@dataclass
class ScoredCandidate:
    candidate: Candidate
    score: float
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)


@dataclass
class RoutingDecision:
    """Result of confidence evaluation."""

    action: str  # open | ask_user | browser | web_search | close | ai | none
    message: str = ""
    chosen: ScoredCandidate | None = None
    top_candidates: list[ScoredCandidate] = field(default_factory=list)
    confidence: float = 0.0
