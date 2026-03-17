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


def get_all_bias_analysis_paginated(
    sb,
    start_date,
    model_type: str = "political_bias",
    limit_per_batch: int = 1000,
):
    """Get ALL bias_analysis records with proper pagination to bypass 1000-row limit."""
    all_analysis = []
    offset = 0

    while True:
        query = (
            sb.table("bias_analysis")
            .select("*, articles(*)")
            .eq("model_type", model_type)
            .gte("created_at", start_date)
            .order("created_at", desc=True)
        )

        result = query.range(offset, offset + limit_per_batch - 1).execute()
        analysis_batch = result.data or []

        if not analysis_batch:
            break

        all_analysis.extend(analysis_batch)
        offset += limit_per_batch

        if len(analysis_batch) < limit_per_batch:
            break

    return all_analysis

