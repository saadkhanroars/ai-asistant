"""
websites.py — Website resolver and search URL generation.

Website mapping:
  Known names (youtube, flipkart) -> home page URL.
  Unknown names -> https://www.<name>.com (best guess) or Google search.

Search URL generation:
  Each platform has a template with {query} placeholder.
  Unknown platform -> Google search.
"""

from __future__ import annotations

from urllib.parse import quote_plus

# Home pages — add any site here (data-driven, not hardcoded in logic)
WEBSITE_HOME: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "flipkart": "https://www.flipkart.com",
    "amazon": "https://www.amazon.in",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "netflix": "https://www.netflix.com",
}

# Search URL templates per platform
SEARCH_URL_TEMPLATES: dict[str, str] = {
    "google": "https://www.google.com/search?q={query}",
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "amazon": "https://www.amazon.in/s?k={query}",
    "flipkart": "https://www.flipkart.com/search?q={query}",
    "github": "https://github.com/search?q={query}",
    "reddit": "https://www.reddit.com/search/?q={query}",
}

DEFAULT_SEARCH_PLATFORM = "google"


def resolve_website(name: str) -> str:
    """
    Map a site name to a URL.
    Known -> home page; unknown -> https://www.<name>.com
    """
    key = name.lower().strip().replace(" ", "")
    if key in WEBSITE_HOME:
        return WEBSITE_HOME[key]
    # Already a URL?
    if name.startswith("http://") or name.startswith("https://"):
        return name
    return f"https://www.{key}.com"


def is_known_website(name: str) -> bool:
    key = name.lower().strip().replace(" ", "")
    return key in WEBSITE_HOME


def build_search_url(query: str, platform: str | None = None) -> str:
    """
    Build a platform search URL.
    Examples:
      physics, google -> Google search
      one piece, youtube -> YouTube results
    """
    plat = (platform or DEFAULT_SEARCH_PLATFORM).lower().strip()
    template = SEARCH_URL_TEMPLATES.get(plat, SEARCH_URL_TEMPLATES[DEFAULT_SEARCH_PLATFORM])
    return template.format(query=quote_plus(query))
