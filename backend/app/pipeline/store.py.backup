from typing import List
from app.core.supabase import get_supabase
from .normalize import NormalizedArticle
from app.scrapers.utils import normalize_source, normalize_category


def insert_articles(articles: List[NormalizedArticle]) -> dict:
    sb = get_supabase()
    # Filter out articles without URL (optional, but keeps DB clean)
    to_check = [a.url for a in articles if a.url]
    existing_urls: set[str] = set()
    if to_check:
        res = sb.table("articles").select("url").in_("url", to_check).execute()
        existing_urls = set((row.get("url") for row in (res.data or []) if row.get("url")))

    rows = [
        {
            "source": normalize_source(a.source) or a.source,
            "category": normalize_category(a.category) if a.category else None,
            "raw_category": getattr(a, "raw_category", None),
            "title": a.title,
            "url": a.url,
            "content": a.content,
            "published_at": a.published_at,
        }
        for a in articles
        if (not a.url) or (a.url not in existing_urls)
    ]

    inserted = 0
    inserted_ids: list[int] = []
    if rows:
        ins = sb.table("articles").insert(rows).execute()
        data = ins.data or []
        inserted = len(data)
        inserted_ids = [int(r.get("id")) for r in data if r.get("id") is not None]

    return {
        "checked": len(to_check),
        "skipped": len(articles) - len(rows),
        "inserted": inserted,
        "inserted_ids": inserted_ids,
    } 