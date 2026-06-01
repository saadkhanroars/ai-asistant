"""Single Ollama adapter for semantic intent understanding."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from intent_schema import (
    IntentSchema,
    SEMANTIC_INTENTS,
    SEMANTIC_UNKNOWN,
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")
OLLAMA_TIMEOUT_SEC = float(os.getenv("OLLAMA_TIMEOUT_SEC", "2.5"))


def understand_intent(text: str) -> IntentSchema | None:
    """Ask Ollama for structured understanding. Return None on any failure."""
    prompt = _build_prompt(text)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SEC) as resp:
            outer = json.loads(resp.read().decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
        return None

    try:
        raw = outer.get("response") or "{}"
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return None

    return _schema_from_dict(data)


def _build_prompt(text: str) -> str:
    return (
        "Classify this Windows desktop assistant request. "
        "You only perform intent understanding, never execution. "
        "Return only JSON with keys: intent, target, query, platform, confidence. "
        "Allowed intent values: open_app, open_document, watch_media, "
        "search_web, play_media, unknown. "
        "Use search_web for web/video searches such as cat videos. "
        "Use watch_media for conversational watching requests. "
        "Use play_media for music/audio requests. "
        f"Request: {text!r}"
    )


def _schema_from_dict(data: dict) -> IntentSchema | None:
    intent = str(data.get("intent") or SEMANTIC_UNKNOWN).strip().lower()
    if intent not in SEMANTIC_INTENTS:
        intent = SEMANTIC_UNKNOWN
    try:
        confidence = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    return IntentSchema(
        intent=intent,
        target=str(data.get("target") or "").strip(),
        query=str(data.get("query") or "").strip(),
        platform=(str(data.get("platform")).strip().lower() or None)
        if data.get("platform") is not None
        else None,
        confidence=confidence,
        source="ollama",
    )
