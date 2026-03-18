import re
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup

CANONICAL_CATEGORIES = {
    "headlines": "Headlines",
    "news": "News",
    "nation": "Nation",
    "business": "Business",
    "sports": "Sports",
    "technology": "Technology",
    "tech": "Technology",
    "world": "World",
    "entertainment": "Entertainment",
    "lifestyle": "Lifestyle",
    "opinion": "Opinion",
    "cebu": "Cebu",
    "davao": "Davao",
    "manila": "Manila",
    "bohol": "Bohol",
    "pampanga": "Pampanga",
    "baguio": "Baguio",
    "zamboanga": "Zamboanga",
    "iloilo": "Iloilo",
    "tacloban": "Tacloban",
    "general-santos": "General Santos",
}

# Canonical source display names
CANONICAL_SOURCES: Dict[str, str] = {
    "gma": "GMA",
    "manila bulletin": "Manila Bulletin",
    "sunstar": "Sunstar",
    "inquirer": "Inquirer",
    "rappler": "Rappler",
    "philstar": "Philstar",
    "manila times": "Manila Times",
    "abs-cbn": "ABS-CBN",
}

BLACKLIST_SEGMENTS = {"photo", "photos", "video", "videos", "about", "section", "tag", "author", "page"}


def normalize_source(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower()
    return CANONICAL_SOURCES.get(key) or raw.strip().title()


def normalize_category(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower().replace("_", "-")
    return CANONICAL_CATEGORIES.get(key) or raw.strip().title()


def extract_category_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        segments = [s for s in (parsed.path or "").split('/') if s]
        for seg in segments:
            if seg.lower() in BLACKLIST_SEGMENTS:
                continue
            canon = normalize_category(seg)
            if canon in CANONICAL_CATEGORIES.values():
                return canon
        # Heuristics for year-based paths like /2025/09/05/...
        if segments and re.match(r"^20\d{2}$", segments[0]):
            # Look backward for a known segment
            for seg in segments:
                canon = normalize_category(seg)
                if canon in CANONICAL_CATEGORIES.values():
                    return canon
    except Exception:
        return None
    return None


def extract_category_from_html(soup: Optional[BeautifulSoup]) -> Optional[str]:
    if soup is None:
        return None
    # OpenGraph / meta tags
    meta_candidates = [
        ("property", "article:section"),
        ("name", "section"),
        ("name", "category"),
    ]
    for attr, value in meta_candidates:
        tag = soup.find("meta", {attr: value})
        if tag and tag.get("content"):
            cat = normalize_category(tag.get("content"))
            if cat:
                return cat
    # Breadcrumbs
    for selector in [
        "nav.breadcrumb a", 
        ".breadcrumb a", 
        ".breadcrumbs a", 
        "ul.breadcrumb li a",
        "#breadcrumb a",
    ]:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            cat = normalize_category(el.get_text(strip=True))
            if cat:
                return cat
    # Structured data
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            import json
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                section = data.get("articleSection")
                if isinstance(section, str):
                    cat = normalize_category(section)
                    if cat:
                        return cat
        except Exception:
            continue
    return None


def resolve_category(url: Optional[str], soup: Optional[BeautifulSoup]) -> str:
    # Prefer explicit HTML signals, then URL, then fallback
    cat = extract_category_from_html(soup)
    if not cat:
        cat = extract_category_from_url(url)
    return cat or "General" 


def resolve_category_pair(url: Optional[str], soup: Optional[BeautifulSoup]) -> tuple[str, Optional[str]]:
    raw = extract_category_from_html(soup) or extract_category_from_url(url)
    normalized = normalize_category(raw) if raw else None
    return (normalized or "General", raw)


# Content validation utilities

def validate_article_content(content: str, min_length: int = 50) -> bool:
    if not content:
        return False
    return len(content.strip()) >= min_length


def is_video_content(url: str) -> bool:
    video_patterns = ["/videos/", "/video/", "/watch/", "/play/", "/stream/"]
    return any(pattern in (url or "").lower() for pattern in video_patterns)


def should_skip_article(url: str, content: str, min_content_length: int = 50) -> tuple[bool, str]:
    """Return (should_skip, reason)."""
    if is_video_content(url):
        return True, "video content"
    if not validate_article_content(content, min_content_length):
        return True, "insufficient content"
    return False, ""


def log_skipped_article(source: str, url: str, reason: str) -> None:
    import logging

    logger = logging.getLogger(__name__)
    logger.info("%s: skipping article (%s) - %s", source, reason, url)


def is_valid_news_url(url: str, base_domain: str) -> bool:
    """Advanced URL validation for news articles."""
    try:
        parsed = urlparse(url)

        if not parsed.netloc.endswith(base_domain):
            return False

        path_lower = (parsed.path or "").lower()
        segments = [s for s in (parsed.path or "").split("/") if s]

        # reject pagination/listing URLs
        if any(s == "page" for s in segments):
            return False
        if re.search(r"/page/\\d+/?$", path_lower, re.IGNORECASE):
            return False
        listing_roots = ["/latest/", "/section/", "/tag/", "/author/", "/topics/"]
        if any(path_lower.rstrip("/") == root.rstrip("/") for root in listing_roots):
            return False

        blocked_patterns = [
            "lotto",
            "swertres",
            "stl",
            "pcso",
            "gambling",
            "betting",
            "photo",
            "photos",
            "video",
            "videos",
            "modal",
            "popup",
            "advertisement",
            "ad",
            "promo",
            "promotion",
            "results",
            "draw",
            "winning",
            "numbers",
            "play",
            "ticket",
            "/wp-content/",
            "/wp-",
            "/tachyon/",
        ]
        if any(pattern in path_lower for pattern in blocked_patterns):
            return False

        # require at least 3 segments, e.g. /philippines/politics/slug
        if len(segments) < 3:
            return False

        return True
    except Exception:
        return False


# Re-export scraping 'stealth' helpers from dedicated modules to keep imports stable.
# New code should import from app.scrapers.support.* (kept in utils for backward compat).
from app.scrapers.support.http_client import stealth_request  # noqa: E402
from app.scrapers.support.playwright_stealth import (  # noqa: E402
    create_stealth_browser_context,
    setup_stealth_page,
    simulate_human_behavior,
)
from app.scrapers.support.stealth_profile import (  # noqa: E402
    get_advanced_stealth_headers,
    get_human_like_delay,
    get_random_language,
    get_random_proxy,
    get_random_timezone,
    get_random_user_agent,
    get_random_viewport,
    get_retry_delay,
)
