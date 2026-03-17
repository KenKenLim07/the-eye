from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from app.cache import get_cached, set_cached
from app.core.supabase import get_supabase
from app.services.articles_service import get_all_bias_analysis_paginated


router = APIRouter()


@router.get("/bias/summary")
async def bias_summary(days: int = Query(default=30, ge=1, le=180)):
    """OPTIMIZED: Get political bias summary with trends-style caching"""
    cache_key = f"bias_summary:{days}"

    # Try cache first (like trends)
    cached_data = get_cached(cache_key)
    if cached_data:
        return cached_data

    sb = get_supabase()
    try:
        # Calculate date range
        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        # OPTIMIZED: Single query with JOIN instead of N+1
        # SENIOR APPROACH: Use pagination function like trends endpoint

        all_analysis = get_all_bias_analysis_paginated(sb, start_date, "political_bias")

        if not all_analysis:
            empty_response = {
                "ok": True,
                "daily_buckets": [],
                "distribution": {},
                "top_sources": [],
                "top_categories": [],
                "recent_examples": [],
            }
            # Cache empty result for 1 minute (like trends)
            set_cached(cache_key, empty_response, 60)
            return empty_response

        # Calculate distribution
        distribution = {}
        for item in all_analysis:
            direction = item.get("model_metadata", {}).get("direction", "unknown")
            distribution[direction] = distribution.get(direction, 0) + 1

        # Calculate daily buckets
        daily_buckets = {}
        for item in all_analysis:
            date = item.get("created_at", "")[:10]
            if date not in daily_buckets:
                daily_buckets[date] = {"total": 0, "by_direction": {}}

            direction = item.get("model_metadata", {}).get("direction", "unknown")
            daily_buckets[date]["total"] += 1
            daily_buckets[date]["by_direction"][direction] = daily_buckets[date]["by_direction"].get(
                direction, 0
            ) + 1

        # Convert to list format
        daily_buckets_list = []
        for date in sorted(daily_buckets.keys(), reverse=True):
            data = daily_buckets[date]
            daily_buckets_list.append({"date": date, "total": data["total"], "by_direction": data["by_direction"]})

        # Calculate top sources from articles
        source_counts = {}
        for item in all_analysis:
            article = item.get("articles", {})
            source = article.get("source", "Unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Calculate top categories from articles
        category_counts = {}
        for item in all_analysis:
            article = item.get("articles", {})
            category = article.get("category", "Unknown")
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1

        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Get recent examples
        recent_examples = []
        for item in all_analysis[:5]:
            article = item.get("articles", {})
            recent_examples.append(
                {
                    "id": article.get("id", 0),
                    "title": article.get("title", ""),
                    "source": article.get("source", "Unknown"),
                    "published_at": article.get("published_at", ""),
                }
            )

        response = {
            "ok": True,
            "daily_buckets": daily_buckets_list,
            "distribution": distribution,
            "top_sources": [{"source": k, "count": v} for k, v in top_sources],
            "top_categories": [{"category": k, "count": v} for k, v in top_categories],
            "recent_examples": recent_examples,
        }

        # Cache for 5 minutes (like trends)
        set_cached(cache_key, response, 300)
        return response

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "daily_buckets": [],
            "distribution": {},
            "top_sources": [],
            "top_categories": [],
            "recent_examples": [],
        }


@router.get("/bias/explain/{article_id}")
async def bias_explain(article_id: int):
    """Return detailed bias analysis (latest) for a specific article, with keyword matches and components."""
    sb = get_supabase()
    try:
        result = (
            sb.table("bias_analysis")
            .select("*, articles(*)")
            .eq("article_id", article_id)
            .eq("model_type", "political_bias")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"ok": False, "error": "No political_bias analysis found for article"}
        row = rows[0]
        md = row.get("model_metadata") or {}
        return {
            "ok": True,
            "article": row.get("articles", {}),
            "direction": md.get("direction"),
            "keyword_matches": md.get("keyword_matches", {}),
            "analysis_components": md.get("analysis_components", {}),
            "political_bias_score": row.get("political_bias_score"),
            "confidence_score": row.get("confidence_score"),
            "created_at": row.get("created_at"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/bias/source_summary")
async def bias_source_summary(days: int = Query(default=30, ge=1, le=180)):
    """Return per-source distribution of political_bias directions within the time window."""
    sb = get_supabase()
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        all_analysis = get_all_bias_analysis_paginated(sb, start_date, "political_bias")
        if not all_analysis:
            return {"ok": True, "by_source": {}}
        by_source = {}
        for item in all_analysis:
            article = item.get("articles", {})
            source = article.get("source", "Unknown")
            direction = item.get("model_metadata", {}).get("direction", "unknown")
            if source not in by_source:
                by_source[source] = {}
            by_source[source][direction] = by_source[source].get(direction, 0) + 1
        return {"ok": True, "by_source": by_source}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/bias/articles")
async def bias_articles(
    direction: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    sb = get_supabase()
    try:
        # Get articles with political bias analysis
        query = (
            sb.table("bias_analysis")
            .select("*, articles(*)")
            .eq("model_type", "political_bias")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if direction:
            query = query.eq("model_metadata->direction", direction)

        result = query.execute()

        return {"ok": True, "items": result.data or [], "total": len(result.data or [])}

    except Exception as e:
        return {"ok": False, "error": str(e), "items": [], "total": 0}
