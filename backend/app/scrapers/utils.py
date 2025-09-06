import re
from typing import Optional
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

BLACKLIST_SEGMENTS = {"photo", "photos", "video", "videos", "about", "section", "tag", "author", "page"}


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