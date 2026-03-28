from __future__ import annotations

import json
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup


def _normalize_type(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for v in value:
            if isinstance(v, str) and v:
                return v
    return ""


def _iter_jsonld_objects(payload: Any):
    """
    Yield dict objects that might represent a NewsArticle/Article.

    Handles:
    - dict payload
    - list payload
    - @graph payloads
    """
    if isinstance(payload, dict):
        # common pattern: {"@context":..., "@graph":[...]}
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict):
                    yield item
        yield payload
        return
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item


def extract_json_ld_newsarticle(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """
    Extract the first JSON-LD object that looks like a NewsArticle.

    Returns a dict containing keys we care about:
      - headline
      - articleBody
      - datePublished
      - articleSection (optional)
    """
    if soup is None:
        return None

    scripts = soup.select('script[type="application/ld+json"]')
    if not scripts:
        return None

    accepted = {"NewsArticle", "Article", "BlogPosting"}

    for script in scripts:
        raw = script.string or script.get_text(strip=True) or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        for obj in _iter_jsonld_objects(payload):
            t = _normalize_type(obj.get("@type"))
            if not t or t not in accepted:
                continue

            headline = obj.get("headline")
            article_body = obj.get("articleBody")
            date_published = obj.get("datePublished")
            article_section = obj.get("articleSection")

            # Some sites store body in other fields; we keep v1 strict to avoid false positives.
            out: Dict[str, Any] = {}
            if isinstance(headline, str) and headline.strip():
                out["headline"] = headline.strip()
            if isinstance(article_body, str) and article_body.strip():
                out["articleBody"] = article_body.strip()
            if isinstance(date_published, str) and date_published.strip():
                out["datePublished"] = date_published.strip()
            if isinstance(article_section, str) and article_section.strip():
                out["articleSection"] = article_section.strip()

            if out:
                return out

    return None

