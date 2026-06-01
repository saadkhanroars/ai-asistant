"""browser.py — Thin wrapper around browser_registry.py."""

from browser_registry import (
    detect_browsers,
    launch_url as open_url,
    list_available_browsers,
    normalize_browser as normalize_browser_name,
)

__all__ = ["open_url", "detect_browsers", "list_available_browsers", "normalize_browser_name"]
