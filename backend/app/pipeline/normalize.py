from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

@dataclass
class NormalizedArticle:
    source: str
    category: Optional[str]
    raw_category: Optional[str]
    title: str
    url: Optional[str]
    content: Optional[str]
    published_at: Optional[str]


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_article(source: str, title: str, url: Optional[str], content: Optional[str], category: Optional[str] = None, published_at: Optional[str] = None, raw_category: Optional[str] = None) -> NormalizedArticle:
    return NormalizedArticle(
        source=source,
        category=category,
        raw_category=raw_category,
        title=title.strip(),
        url=url,
        content=(content or "").strip() or None,
        published_at=published_at or iso_now(),
    ) 