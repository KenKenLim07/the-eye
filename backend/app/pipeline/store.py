from typing import List
from app.core.supabase import get_supabase
from .normalize import NormalizedArticle
from app.scrapers.utils import normalize_source, normalize_category
import logging

logger = logging.getLogger(__name__)

def insert_articles(articles: List[NormalizedArticle]) -> dict:
    sb = get_supabase()
    # Filter out articles without URL (optional, but keeps DB clean)
    to_check = [a.url for a in articles if a.url]
    existing_urls: set[str] = set()
    if to_check:
        try:
            res = sb.table("articles").select("url").in_("url", to_check).execute()
            existing_urls = set((row.get("url") for row in (res.data or []) if row.get("url")))
        except Exception as e:
            logger.error(f"Error checking existing URLs: {e}")
            return {"checked": 0, "skipped": 0, "inserted": 0, "error": str(e), "inserted_ids": []}

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
    error_msg = None
    
    if rows:
        try:
            ins = sb.table("articles").insert(rows).select("id").execute()
            data = ins.data or []
            inserted = len(data)
            inserted_ids = [int(r.get("id")) for r in data if r.get("id") is not None]
            
            # Check for Supabase errors
            if hasattr(ins, 'error') and ins.error:
                error_msg = str(ins.error)
                logger.error(f"Supabase insert error: {error_msg}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error inserting articles: {error_msg}")
            inserted = 0
            inserted_ids = []

        # Fallback: if no IDs returned but we inserted articles, fetch them by URL
        if not inserted_ids and inserted > 0:
            try:
                urls_to_fetch = [r.get("url") for r in rows if r.get("url")]
                if urls_to_fetch:
                    fetch_res = sb.table("articles").select("id,url").in_("url", urls_to_fetch).execute()
                    inserted_ids = [int(r.get("id")) for r in (fetch_res.data or []) if r.get("id")]
            except Exception as e:
                logger.warning(f"Fallback ID fetch failed: {e}")

    result = {
        "checked": len(to_check),
        "skipped": len(articles) - len(rows),
        "inserted": inserted,
        "inserted_ids": inserted_ids,
    }
    
    if error_msg:
        result["error"] = error_msg
        
    return result
