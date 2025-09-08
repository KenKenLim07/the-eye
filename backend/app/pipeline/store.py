from typing import List
from app.core.supabase import get_supabase
from .normalize import NormalizedArticle


def insert_articles(articles: List[NormalizedArticle]) -> dict:
    sb = get_supabase()
    # Filter out articles without URL (optional, but keeps DB clean)
    to_check = [a.url for a in articles if a.url]

    rows = [
        {
            "source": a.source,
            "category": a.category,
            "raw_category": getattr(a, "raw_category", None),
            "title": a.title,
            "url": a.url,
            "content": a.content,
            "published_at": a.published_at,
        }
        for a in articles
        if a.url
    ]

    inserted = 0
    if rows:
        # Use upsert to avoid duplicate key violations on url
        res = sb.table("articles").upsert(rows, on_conflict="url").execute()
        inserted = len(res.data or [])

    # We cannot know exact skipped count from upsert response reliably; estimate
    skipped = max(0, len(to_check) - inserted)
    return {"checked": len(to_check), "skipped": skipped, "inserted": inserted} 