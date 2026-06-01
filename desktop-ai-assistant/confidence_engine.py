"""
confidence_engine.py — Decide auto-open vs ask user vs fallback.

Low confidence -> do NOT open random files.
Ambiguous top scores -> show numbered list.
"""

from __future__ import annotations

from models import RoutingDecision, ScoredCandidate
from scoring_config import (
    AMBIGUITY_GAP,
    AUTO_OPEN_THRESHOLD,
    CLARIFY_THRESHOLD,
    MAX_CHOICES_SHOWN,
    MEDIUM_CONFIDENCE_THRESHOLD,
    MIN_CANDIDATE_THRESHOLD,
    STRONG_MATCH_THRESHOLD,
)


def evaluate(
    scored: list[ScoredCandidate],
    *,
    allow_ask: bool = True,
) -> RoutingDecision:
    """
    Confidence tiers:
      high   -> auto open
      medium -> numbered options (ask_user)
      low    -> clarification (no random guess)
    """
    if not scored:
        return RoutingDecision(
            action="clarify",
            confidence=0.0,
            message=_clarify_message(),
        )

    top = scored[0]
    second = scored[1] if len(scored) > 1 else None
    second_score = second.score if second else 0.0
    gap = top.score - second_score

    viable = [s for s in scored if s.score >= MIN_CANDIDATE_THRESHOLD]

    # Low confidence — do not open or list weak guesses
    if top.score < CLARIFY_THRESHOLD:
        return RoutingDecision(
            action="clarify",
            confidence=top.score,
            message=_clarify_message(),
        )

    # Multiple strong matches with small gap -> ask, never guess
    if (
        allow_ask
        and second
        and top.score >= STRONG_MATCH_THRESHOLD
        and second_score >= STRONG_MATCH_THRESHOLD
        and gap < AMBIGUITY_GAP
    ):
        return RoutingDecision(
            action="ask_user",
            confidence=top.score,
            top_candidates=viable[:MAX_CHOICES_SHOWN],
            message=_format_choices(viable[:MAX_CHOICES_SHOWN]),
        )

    # Strong winner -> auto open
    if top.score >= AUTO_OPEN_THRESHOLD and gap >= AMBIGUITY_GAP:
        return RoutingDecision(
            action="open",
            chosen=top,
            confidence=top.score,
            top_candidates=scored[:MAX_CHOICES_SHOWN],
        )

    # Clear gap between #1 and #2
    if top.score >= MIN_CANDIDATE_THRESHOLD and gap >= AMBIGUITY_GAP:
        return RoutingDecision(
            action="open",
            chosen=top,
            confidence=top.score,
            top_candidates=scored[:MAX_CHOICES_SHOWN],
        )

    # High score but close second -> ask user
    if top.score >= AUTO_OPEN_THRESHOLD and allow_ask and viable:
        return RoutingDecision(
            action="ask_user",
            confidence=top.score,
            top_candidates=viable[:MAX_CHOICES_SHOWN],
            message=_format_choices(viable[:MAX_CHOICES_SHOWN]),
        )

    # Medium confidence — show numbered options
    if allow_ask and viable and top.score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return RoutingDecision(
            action="ask_user",
            confidence=top.score,
            top_candidates=viable[:MAX_CHOICES_SHOWN],
            message=_format_choices(viable[:MAX_CHOICES_SHOWN]),
        )

    # Weak viable set — clarify instead of guessing
    if top.score < MEDIUM_CONFIDENCE_THRESHOLD:
        return RoutingDecision(
            action="clarify",
            confidence=top.score,
            message=_clarify_message(),
        )

    return RoutingDecision(action="clarify", confidence=top.score, message=_clarify_message())


def _clarify_message() -> str:
    return (
        "I'm not sure what to open. Try being more specific, for example:\n"
        "  • open bluetooth settings\n"
        "  • open downloads\n"
        "  • open latest image\n"
        "  • launch chrome\n"
        "Or pick from a numbered list when I show matches."
    )


def _format_choices(choices: list[ScoredCandidate]) -> str:
    lines = ["I found:"]
    for i, sc in enumerate(choices, 1):
        c = sc.candidate
        lines.append(f"  {i}. {c.name} ({c.item_type}, {sc.score:.0%})")
    lines.append("Reply with a number (e.g. 1) or: open 2 / choose 3")
    return "\n".join(lines)
