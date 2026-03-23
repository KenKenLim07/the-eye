#!/usr/bin/env python3
"""
Backfill `article_sentiment_public` from existing `bias_analysis` sentiment rows.

Why:
- The frontend "Coverage (7d)" metric uses `article_sentiment_public` because `bias_analysis`
  is usually not readable by anon clients (RLS).
- If you created `article_sentiment_public` later (or ML upserts were failing temporarily),
  many articles can have sentiment rows in `bias_analysis` but be missing the corresponding
  public cache row. That makes coverage look artificially low (e.g. 15%).

Run inside Docker (recommended):
  docker compose exec worker_ml python /app/scripts/backfill_article_sentiment_public.py --days 7 --dry-run
  docker compose exec worker_ml python /app/scripts/backfill_article_sentiment_public.py --days 7 --apply
"""

from __future__ import annotations

import os
import sys
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

# Allow running from repo root while importing backend package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from app.core.supabase import get_supabase  # noqa: E402
except ModuleNotFoundError as e:
    missing = getattr(e, "name", None) or str(e)
    raise SystemExit(
        "\n".join(
            [
                f"Missing Python dependency: {missing}",
                "",
                "Run this script inside Docker (recommended):",
                "  docker compose exec worker_ml python /app/scripts/backfill_article_sentiment_public.py --days 7 --dry-run",
                "",
            ]
        )
    ) from e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _chunked(items: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


@dataclass(frozen=True)
class SentRow:
    article_id: int
    sentiment_label: str | None
    sentiment_score: float | None
    created_at: str | None


def _fetch_article_ids_since(since_iso: str, page_size: int = 1000) -> list[int]:
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


def _latest_sentiment_rows_for_articles(article_ids: list[int]) -> list[SentRow]:
    """
    Return latest sentiment rows per article_id for the given ids.
    """
    if not article_ids:
        return []
    sb = get_supabase()
    # Pull rows newest-first; we'll keep the first row seen per article_id.
    res = (
        sb.table("bias_analysis")
        .select("article_id,sentiment_label,sentiment_score,created_at")
        .eq("model_type", "sentiment")
        .in_("article_id", article_ids)
        .order("created_at", desc=True)
        .execute()
    )
    seen: set[int] = set()
    out: list[SentRow] = []
    for r in (res.data or []):
        aid = r.get("article_id")
        if aid is None:
            continue
        try:
            aid_i = int(aid)
        except Exception:
            continue
        if aid_i in seen:
            continue
        seen.add(aid_i)
        out.append(
            SentRow(
                article_id=aid_i,
                sentiment_label=r.get("sentiment_label"),
                sentiment_score=r.get("sentiment_score"),
                created_at=r.get("created_at"),
            )
        )
    return out


def _count_public_rows(article_ids: list[int]) -> int:
    if not article_ids:
        return 0
    sb = get_supabase()
    total = 0
    for batch in _chunked(article_ids, 500):
        res = (
            sb.table("article_sentiment_public")
            .select("article_id", count="exact")
            .in_("article_id", batch)
            .limit(1)
            .execute()
        )
        total += res.count or 0
    return total


def backfill(*, days: int, apply: bool, batch_size: int) -> int:
    since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    all_ids = _fetch_article_ids_since(since_iso)
    if not all_ids:
        logger.info("No articles found in the last %d days.", days)
        return 0

    before = _count_public_rows(all_ids)
    logger.info("Articles last %dd: %d", days, len(all_ids))
    logger.info("Public sentiment rows present (before): %d", before)

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    upserted = 0

    for idx, batch in enumerate(_chunked(all_ids, batch_size), start=1):
        latest = _latest_sentiment_rows_for_articles(batch)
        if not latest:
            continue
        payload = [
            {
                "article_id": r.article_id,
                "sentiment_label": r.sentiment_label,
                "sentiment_score": r.sentiment_score,
                # Keep an explicit timestamp for cache freshness.
                "updated_at": now_iso,
            }
            for r in latest
        ]
        if not apply:
            upserted += len(payload)
            continue
        sb.table("article_sentiment_public").upsert(payload, on_conflict="article_id").execute()
        upserted += len(payload)
        if idx % 10 == 0:
            logger.info("Progress: processed %d batches...", idx)
        time.sleep(0.02)

    after = _count_public_rows(all_ids)
    logger.info("Public sentiment rows present (after): %d", after)
    logger.info("Would upsert %d rows." if not apply else "Upserted %d rows.", upserted)
    return upserted


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Backfill article_sentiment_public from bias_analysis")
    parser.add_argument("--days", type=int, default=7, help="Look back by published_at (default: 7)")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for Supabase queries (default: 500)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without writing")
    parser.add_argument("--apply", action="store_true", help="Apply upserts to article_sentiment_public")
    args = parser.parse_args(argv[1:])

    if not args.dry_run and not args.apply:
        args.dry_run = True

    backfill(days=args.days, apply=bool(args.apply), batch_size=args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

