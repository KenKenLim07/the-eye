#!/usr/bin/env python3
"""
ML Analysis Backfill Script

Purpose:
- Find recent articles that are missing sentiment analysis rows in `bias_analysis`
  (specifically `model_type='sentiment'`) and enqueue Celery tasks to analyze them.

Notes:
- The "Unscored" counts in the UI are based on missing sentiment rows, not merely
  missing *any* `bias_analysis` row. Many articles may have other model rows
  (e.g., political_bias) but still be missing sentiment, so this script targets
  the right gap.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
import logging
from typing import Iterable

# Allow running from repo root while importing backend package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.supabase import get_supabase  # noqa: E402
from app.workers.ml_tasks import analyze_articles_task  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _chunked(items: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _fetch_all_ids_recent_articles(since_iso: str, page_size: int = 1000) -> list[int]:
    sb = get_supabase()
    out: list[int] = []
    offset = 0
    while True:
        res = (
            sb.table("articles")
            .select("id")
            .gte("published_at", since_iso)
            .order("published_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break
        out.extend(int(r["id"]) for r in rows if r.get("id") is not None)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def _fetch_all_sentiment_analyzed_article_ids(since_iso: str, page_size: int = 1000) -> set[int]:
    """
    Fetch all article_ids that have *any* sentiment row created since `since_iso`.

    This avoids huge `article_id=in.(...)` URLs, and is accurate enough for backfilling
    recent data because sentiment rows for recent articles are also created recently.
    """
    sb = get_supabase()
    out: set[int] = set()
    offset = 0
    while True:
        res = (
            sb.table("bias_analysis")
            .select("article_id")
            .eq("model_type", "sentiment")
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break
        for r in rows:
            aid = r.get("article_id")
            if aid is not None:
                out.add(int(aid))
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def find_articles_missing_sentiment(since_days: int = 7) -> list[int]:
    """Return article IDs published in last `since_days` that lack sentiment rows."""
    # Use an explicit UTC timestamp for stable comparisons in PostgREST filters.
    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()

    # Fetch recent articles then subtract articles that already have sentiment rows.
    all_article_ids = _fetch_all_ids_recent_articles(since_date)
    if not all_article_ids:
        return []

    analyzed_ids = _fetch_all_sentiment_analyzed_article_ids(since_date)

    missing = [aid for aid in all_article_ids if aid not in analyzed_ids]
    logger.info("Found %d articles missing sentiment since %s.", len(missing), since_date)
    return missing


def backfill_analysis(article_ids: list[int], batch_size: int = 50) -> dict:
    """Enqueue Celery tasks to backfill ML analysis for article IDs."""
    if not article_ids:
        return {"queued": 0, "errors": [], "total_batches": 0}

    queued = 0
    errors: list[str] = []

    for idx, batch in enumerate(_chunked(article_ids, batch_size), start=1):
        try:
            task = analyze_articles_task.delay(batch)
            queued += len(batch)
            logger.info("Queued batch %d: %d articles (task: %s)", idx, len(batch), getattr(task, "id", "n/a"))
        except Exception as e:
            msg = f"Failed to queue batch {idx}: {e}"
            logger.error(msg)
            errors.append(msg)

    total_batches = (len(article_ids) + batch_size - 1) // batch_size
    return {"queued": queued, "errors": errors, "total_batches": total_batches}


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Backfill sentiment analysis for missed articles")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for queuing (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without queuing")
    args = parser.parse_args(argv[1:])

    logger.info("Scanning for articles missing sentiment analysis in the last %d days...", args.days)
    missing_ids = find_articles_missing_sentiment(args.days)

    if not missing_ids:
        logger.info("No missing sentiment analysis found.")
        return 0

    logger.info("Found %d articles missing sentiment analysis.", len(missing_ids))
    if args.dry_run:
        for i, aid in enumerate(missing_ids[:10], start=1):
            logger.info("  %d. Article ID: %d", i, aid)
        if len(missing_ids) > 10:
            logger.info("  ... and %d more", len(missing_ids) - 10)
        return 0

    result = backfill_analysis(missing_ids, args.batch_size)
    logger.info("Backfill queued: %d articles across %d batches.", result["queued"], result["total_batches"])
    if result["errors"]:
        logger.warning("Errors: %d", len(result["errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
