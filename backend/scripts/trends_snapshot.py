#!/usr/bin/env python3
"""
Precompute sentiment trends snapshots into Supabase for frontend-only demos.

Writes to: public.sentiment_trends_snapshots
Reads from: public.articles, public.bias_analysis (model_type='sentiment')
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from supabase import Client, create_client
from supabase._sync.client import SupabaseException

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from snapshot_window import resolve_window  # noqa: E402

TZ_UTC = ZoneInfo("UTC")


def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    try:
        return create_client(url, key)
    except SupabaseException as e:
        raise RuntimeError(
            "Invalid Supabase API key. Ensure SUPABASE_SERVICE_ROLE_KEY is the full service_role key."
        ) from e


def fetch_articles_paginated(
    sb: Client,
    start_iso: str,
    end_iso: str,
    source: Optional[str],
    limit_per_batch: int = 1000,
) -> list[dict]:
    all_rows: list[dict] = []
    offset = 0
    while True:
        q = (
            sb.table("articles")
            .select("id,source,published_at")
            .gte("published_at", start_iso)
            .lte("published_at", end_iso)
            .order("published_at", desc=True)
            .range(offset, offset + limit_per_batch - 1)
        )
        if source:
            q = q.eq("source", source)
        res = q.execute()
        batch = res.data or []
        if not batch:
            break
        all_rows.extend(batch)
        offset += limit_per_batch
        if len(batch) < limit_per_batch:
            break
    return all_rows


def to_ph_date_str(ts: str) -> str:
    try:
        dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
        return dt.astimezone(TZ_PH).date().isoformat()
    except Exception:
        return (ts or "")[:10]


def snapshot_key(period: str, source: Optional[str], include_today: bool) -> str:
    src = "all" if not source else source
    return f"trends:period={period}:source={src}:include_today={'1' if include_today else '0'}"


def fetch_sentiment_rows(sb, article_ids: list[int]) -> list[dict]:
    # Keep chunks small to avoid PostgREST row caps.
    out: list[dict] = []
    batch_size = 250
    for i in range(0, len(article_ids), batch_size):
        batch_ids = article_ids[i : i + batch_size]
        res = (
            sb.table("bias_analysis")
            .select("article_id,sentiment_label,sentiment_score,created_at")
            .in_("article_id", batch_ids)
            .eq("model_type", "sentiment")
            .order("created_at", desc=True)
            .execute()
        )
        out.extend(res.data or [])
    return out


def dedupe_latest_by_article(rows: list[dict]) -> list[dict]:
    # Robust dedupe: keep the row with max created_at per article_id.
    best: dict[int, dict] = {}
    for r in rows:
        aid = r.get("article_id")
        if aid is None:
            continue
        aid_i = int(aid)
        created = (r.get("created_at") or "")[:32]
        prev = best.get(aid_i)
        if prev is None:
            best[aid_i] = r
            continue
        prev_created = (prev.get("created_at") or "")[:32]
        if created > prev_created:
            best[aid_i] = r
    return list(best.values())


def compute_trends(
    period: str,
    source: Optional[str],
    include_today: bool,
    *,
    anchor_latest: bool = False,
) -> dict:
    sb = get_supabase()
    start_date_str, end_date_str, note = resolve_window(
        sb, period, include_today=include_today, anchor_latest=anchor_latest
    )
    if note:
        print(f"[trends] {period}: {note}")
        print(f"[trends] window {start_date_str} .. {end_date_str}")

    articles = fetch_articles_paginated(sb, start_date_str, end_date_str, source=source, limit_per_batch=1000)

    daily_data: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []}
    )

    article_id_to_ph_date: dict[int, str] = {}
    for a in articles:
        aid = a.get("id")
        if aid is None:
            continue
        aid_i = int(aid)
        d = to_ph_date_str(a.get("published_at", ""))
        article_id_to_ph_date[aid_i] = d
        if d:
            daily_data[d]["total"] += 1

    article_ids = list(article_id_to_ph_date.keys())
    if not article_ids:
        return {
            "ok": True,
            "summary": {
                "period": period,
                "source": source,
                "total_articles": 0,
                "positive_pct": 0,
                "negative_pct": 0,
                "neutral_pct": 0,
                "avg_daily_articles": 0,
            },
            "timeline": [],
        }

    all_analysis = fetch_sentiment_rows(sb, article_ids)
    analysis_rows = dedupe_latest_by_article(all_analysis)

    for row in analysis_rows:
        aid = row.get("article_id")
        if aid is None:
            continue
        d = article_id_to_ph_date.get(int(aid))
        if not d:
            continue
        label = row.get("sentiment_label") or "neutral"
        score = row.get("sentiment_score")
        if score is not None:
            try:
                daily_data[d]["sentiment_scores"].append(float(score))
            except Exception:
                pass
        if label == "positive":
            daily_data[d]["positive"] += 1
        elif label == "negative":
            daily_data[d]["negative"] += 1
        else:
            daily_data[d]["neutral"] += 1

    timeline: list[dict] = []
    total_articles = 0
    total_positive = 0
    total_negative = 0
    total_neutral = 0

    for date_str in sorted(daily_data.keys()):
        data = daily_data[date_str]
        total = int(data["total"] or 0)
        positive = int(data["positive"] or 0)
        negative = int(data["negative"] or 0)
        neutral = int(data["neutral"] or 0)
        scores = data["sentiment_scores"] or []

        total_articles += total
        total_positive += positive
        total_negative += negative
        total_neutral += neutral

        avg_sentiment = (sum(scores) / len(scores)) if scores else 0
        timeline.append(
            {
                "date": date_str,
                "positive": positive,
                "negative": negative,
                "neutral": neutral,
                "total": total,
                "avg_sentiment": avg_sentiment,
                "positive_pct": round((positive / total * 100) if total > 0 else 0, 1),
                "negative_pct": round((negative / total * 100) if total > 0 else 0, 1),
                "neutral_pct": round((neutral / total * 100) if total > 0 else 0, 1),
            }
        )

    positive_pct = round((total_positive / total_articles * 100) if total_articles > 0 else 0, 1)
    negative_pct = round((total_negative / total_articles * 100) if total_articles > 0 else 0, 1)
    neutral_pct = round((total_neutral / total_articles * 100) if total_articles > 0 else 0, 1)
    avg_daily_articles = round(total_articles / len(timeline), 1) if timeline else 0

    return {
        "ok": True,
        "summary": {
            "period": period,
            "source": source,
            "total_articles": total_articles,
            "positive_pct": positive_pct,
            "negative_pct": negative_pct,
            "neutral_pct": neutral_pct,
            "avg_daily_articles": avg_daily_articles,
        },
        "timeline": timeline,
    }


def write_snapshot(
    period: str,
    source: Optional[str],
    include_today: bool,
    *,
    anchor_latest: bool = False,
    skip_empty: bool = False,
) -> Optional[str]:
    sb = get_supabase()
    payload = compute_trends(
        period=period,
        source=source,
        include_today=include_today,
        anchor_latest=anchor_latest,
    )
    summary = payload.get("summary") or {}
    timeline = payload.get("timeline") or []
    total = int(summary.get("total_articles") or 0)
    if skip_empty and total <= 0:
        print(f"Skip empty trends snapshot period={period} (would overwrite with no data)")
        return None

    key = snapshot_key(period, source, include_today)
    row = {
        "key": key,
        "period": period,
        "source": source,
        "include_today": include_today,
        "computed_at": datetime.now(TZ_UTC).isoformat(),
        "summary": summary,
        "timeline": timeline,
    }
    sb.table("sentiment_trends_snapshots").upsert(row).execute()
    return key


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Write sentiment trends snapshots into Supabase")
    ap.add_argument("period", choices=["7d", "30d"])
    ap.add_argument("--include-today", action="store_true", default=True)
    ap.add_argument("--no-include-today", dest="include_today", action="store_false")
    ap.add_argument(
        "--anchor-latest",
        action="store_true",
        help="End the window at the newest article published_at (portfolio freeze)",
    )
    ap.add_argument(
        "--skip-empty",
        action="store_true",
        help="Do not upsert if the computed window has zero articles",
    )
    args = ap.parse_args(argv[1:])

    key = write_snapshot(
        period=args.period,
        source=None,
        include_today=bool(args.include_today),
        anchor_latest=bool(args.anchor_latest),
        skip_empty=bool(args.skip_empty),
    )
    if key:
        print(f"Wrote trends snapshot {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
