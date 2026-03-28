from typing import Optional

from fastapi import APIRouter

from app.cache import get_cached, set_cached
from app.core.supabase import get_supabase


router = APIRouter()


@router.get("/articles")
async def get_articles(
    limit: int = 50,
    offset: int = 0,
    source: Optional[str] = None,
    category: Optional[str] = None,
):
    sb = get_supabase()

    query = sb.table("articles").select("*")

    if source:
        query = query.eq("source", source)
    if category:
        query = query.eq("category", category)

    query = query.order("published_at", desc=True).range(offset, offset + limit - 1)

    try:
        result = query.execute()
        return {"articles": result.data, "count": len(result.data)}
    except Exception as e:
        return {"error": str(e), "articles": []}


@router.get("/articles/home-optimized")
async def get_home_articles(limit_per_source: int = 10, refresh: bool = False):
    """Optimized endpoint for home page - up to N articles per canonical source with caching."""
    # Generate cache key
    cache_key = f"home_articles:{limit_per_source}"
    last_good_key = f"home_articles:last_good:{limit_per_source}"

    # Check cache first
    if not refresh:
        cached_result = get_cached(cache_key)
        if cached_result:
            return cached_result

    sb = get_supabase()

    try:
        # Define canonical sources shown on the homepage.
        # ABS-CBN is optional because it is Akamai-sensitive (often blocked unless run in headed mode).
        required_sources = [
            "GMA",
            "Rappler",
            "Inquirer",
            "Manila Times",
            "Philstar",
            "Sunstar",
            "Manila Bulletin",
        ]
        optional_sources = [
            "ABS-CBN",
        ]
        sources = required_sources + optional_sources

        articles_by_source = {}
        source_errors = {}

        # Query per source with ordered limit for predictable results
        for src in sources:
            try:
                res = (
                    sb.table("articles")
                    .select("*")
                    .eq("source", src)
                    .order("published_at", desc=True)
                    .limit(limit_per_source)
                    .execute()
                )
                articles_by_source[src] = res.data or []
            except Exception as inner_e:
                # On per-source failure, continue with empty list
                articles_by_source[src] = []
                source_errors[src] = str(inner_e)

        total_found = sum(len(v or []) for v in articles_by_source.values())
        all_empty = total_found == 0
        missing_sources = [src for src in required_sources if not (articles_by_source.get(src) or [])]
        partial_empty = 0 < len(missing_sources) < len(required_sources)

        result_data = {"articles_by_source": articles_by_source}

        # If every source failed/empty, prefer returning a known good snapshot.
        if all_empty:
            last_good = get_cached(last_good_key)
            if last_good:
                # Keep short-lived cache to avoid hammering backend during transient failures.
                set_cached(cache_key, last_good, 60)
                return last_good
            # Don't cache all-empty results for long; they may be transient connectivity issues.
            set_cached(cache_key, result_data, 30)
            if source_errors:
                print(f"home-optimized all-empty with source errors: {source_errors}")
            return result_data

        # Partial-empty snapshots are often transient (one source lagging or timeout),
        # so keep them short-lived and avoid replacing the last known good cache.
        if partial_empty:
            set_cached(cache_key, result_data, 60)
            if source_errors:
                print(f"home-optimized partial-empty ({missing_sources}) with source errors: {source_errors}")
            else:
                print(f"home-optimized partial-empty ({missing_sources})")
            return result_data

        # Cache fully healthy result (e.g., 10 minutes) and save as last known good snapshot.
        set_cached(cache_key, result_data, 600)
        set_cached(last_good_key, result_data, 3600)
        return result_data

    except Exception as e:
        return {"error": str(e), "articles_by_source": {}}


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    sb = get_supabase()
    try:
        # supabase-py requires a select() before filters like eq()
        result = sb.table("articles").select("*").eq("id", article_id).execute()
        if result.data:
            return result.data[0]
        else:
            return {"error": "Article not found"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/articles/{article_id}/analysis")
async def get_article_analysis(article_id: int):
    sb = get_supabase()
    try:
        result = (
            sb.table("bias_analysis")
            .select("*")
            .eq("article_id", article_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]
        else:
            return {"error": "Analysis not found"}
    except Exception as e:
        return {"error": str(e)}
