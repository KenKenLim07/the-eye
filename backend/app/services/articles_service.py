from __future__ import annotations


def get_all_articles_paginated(
    sb,
    start_date,
    source=None,
    end_date=None,
    limit_per_batch: int = 1000,
    select_fields: str = "*",
):
    """Get ALL articles with proper pagination to bypass Supabase 1000-row limit.

    Args:
        select_fields: Fields to select (default '*', but can be 'id,source,published_at' for performance)
    """
    all_articles = []
    offset = 0

    while True:
        query = (
            sb.table("articles")
            .select(select_fields)
            .gte("published_at", start_date)
            .order("published_at", desc=True)
        )

        if end_date:
            query = query.lte("published_at", end_date)

        if source:
            query = query.eq("source", source)

        result = query.range(offset, offset + limit_per_batch - 1).execute()
        articles = result.data or []

        if not articles:
            break

        all_articles.extend(articles)
        offset += limit_per_batch

        # Safety check to prevent infinite loops
        if len(articles) < limit_per_batch:
            break

    return all_articles
