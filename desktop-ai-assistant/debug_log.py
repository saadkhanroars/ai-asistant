"""
debug_log.py — Router debug output (no extra dependencies).

Set environment variable ASSISTANT_DEBUG=1 to enable.
Shows intent, target, route, match, and fallback reasons.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def is_debug_enabled() -> bool:
    return os.environ.get("ASSISTANT_DEBUG", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


@dataclass
class RouteDebug:
    """Collects routing decisions for one user line."""

    input_text: str = ""
    normalized_text: str = ""
    intent: str = ""
    route: str = ""
    target: str = ""
    browser: str | None = None
    platform: str | None = None
    search_query: str | None = None
    match_name: str | None = None
    match_score: float | None = None
    match_kind: str | None = None
    search_ms: float | None = None
    index_candidates: int | None = None
    index_total: int | None = None
    fallback_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def set(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra[key] = value

    def flush(self) -> None:
        """Print debug lines to the terminal."""
        if not is_debug_enabled():
            return
        print("--- Router debug ---")
        print(f"  input:      {self.input_text!r}")
        if self.normalized_text:
            print(f"  normalized: {self.normalized_text!r}")
        print(f"  intent:     {self.intent or '(none)'}")
        print(f"  target:     {self.target!r}")
        if self.browser:
            print(f"  browser:    {self.browser}")
        if self.platform:
            print(f"  platform:   {self.platform}")
        if self.search_query:
            print(f"  search_q:   {self.search_query!r}")
        print(f"  route:      {self.route or '(pending)'}")
        if self.index_total is not None:
            print(
                f"  index:      {self.index_candidates or 0} candidates "
                f"/ {self.index_total} total"
            )
        if self.search_ms is not None:
            print(f"  search_ms:  {self.search_ms}")
        if self.match_name:
            score_txt = (
                f"{self.match_score:.2f}" if self.match_score is not None else "?"
            )
            print(
                f"  match:      {self.match_name} "
                f"({self.match_kind}, score={score_txt})"
            )
        if self.fallback_reason:
            print(f"  fallback:   {self.fallback_reason}")
        for key, value in self.extra.items():
            label = key.replace("_", " ")
            print(f"  {label}: {value}")
        print("--------------------")
