#!/usr/bin/env python3
"""
Precompute correlation snapshots into Supabase for frontend-only demos.

Writes to: public.correlation_snapshots
Reads from: public.articles, public.bias_analysis (model_type='sentiment')
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Optional
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


def snapshot_key(period: str, include_today: bool) -> str:
    return f"corr:period={period}:sources=all:include_today={'1' if include_today else '0'}"


def pearson_r(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for x, y in zip(xs, ys):
        dx = x - mean_x
        dy = y - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy
    if den_x <= 0 or den_y <= 0:
        return None
    return num / sqrt(den_x * den_y)


def fetch_sentiment_rows(sb, article_ids: list[int]) -> list[dict]:
    out: list[dict] = []
    batch_size = 250
    for i in range(0, len(article_ids), batch_size):
        batch_ids = article_ids[i : i + batch_size]
        res = (
            sb.table("bias_analysis")
            .select("article_id,sentiment_score,created_at")
            .in_("article_id", batch_ids)
            .eq("model_type", "sentiment")
            .order("created_at", desc=True)
            .execute()
        )
        out.extend(res.data or [])
    return out


def dedupe_latest_by_article(rows: list[dict]) -> list[dict]:
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


def compute_correlation(
    period: str,
    include_today: bool,
    *,
    anchor_latest: bool = False,
) -> dict:
    sb = get_supabase()
    start_date_str, end_date_str, note = resolve_window(
        sb, period, include_today=include_today, anchor_latest=anchor_latest
    )
    if note:
        print(f"[correlation] {period}: {note}")
        print(f"[correlation] window {start_date_str} .. {end_date_str}")

    articles = fetch_articles_paginated(sb, start_date_str, end_date_str, source=None, limit_per_batch=1000)
    if not articles:
        return {"ok": True, "period": period, "include_today": include_today, "sources": [], "matrix": [], "p_values": []}

    id_to_meta: dict[int, tuple[str, str]] = {}
    article_ids: list[int] = []
    for a in articles:
        aid = a.get("id")
        if aid is None:
            continue
        aid_i = int(aid)
        article_ids.append(aid_i)
        src = (a.get("source") or "unknown").strip() or "unknown"
        d = to_ph_date_str(a.get("published_at", ""))
        id_to_meta[aid_i] = (src, d)

    all_analysis = fetch_sentiment_rows(sb, article_ids)
    analysis_rows = dedupe_latest_by_article(all_analysis)

    per_source_date_scores = defaultdict(lambda: defaultdict(list))
    for row in analysis_rows:
        aid = row.get("article_id")
        score = row.get("sentiment_score")
        if aid is None or score is None:
            continue
        meta = id_to_meta.get(int(aid))
        if not meta:
            continue
        src, d = meta
        if not d:
            continue
        try:
            per_source_date_scores[src][d].append(float(score))
        except Exception:
            continue

    per_source_series = defaultdict(dict)
    for src, dmap in per_source_date_scores.items():
        for d, vals in dmap.items():
            if not vals:
                continue
            per_source_series[src][d] = float(sum(vals) / len(vals))

    src_names = sorted(per_source_series.keys())
    n = len(src_names)
    if n == 0:
        return {"ok": True, "period": period, "include_today": include_today, "sources": [], "matrix": [], "p_values": []}

    matrix: list[list[Optional[float]]] = [[None for _ in range(n)] for _ in range(n)]
    pvals: list[list[Optional[float]]] = [[None for _ in range(n)] for _ in range(n)]

    for i in range(n):
        a = src_names[i]
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            b = src_names[j]
            da = per_source_series[a]
            db = per_source_series[b]
            common_dates = sorted(set(da.keys()) & set(db.keys()))
            xs = [da[d] for d in common_dates]
            ys = [db[d] for d in common_dates]
            r = pearson_r(xs, ys)
            matrix[i][j] = r
            matrix[j][i] = r

    return {"ok": True, "period": period, "include_today": include_today, "sources": src_names, "matrix": matrix, "p_values": pvals}


def write_snapshot(
    period: str,
    include_today: bool,
    *,
    anchor_latest: bool = False,
    skip_empty: bool = False,
) -> Optional[str]:
    sb = get_supabase()
    payload = compute_correlation(
        period=period,
        include_today=include_today,
        anchor_latest=anchor_latest,
    )
    sources = payload.get("sources") or []
    if skip_empty and not sources:
        print(f"Skip empty correlation snapshot period={period} (would overwrite with no data)")
        return None

    key = snapshot_key(period, include_today)
    row = {
        "key": key,
        "period": period,
        "include_today": include_today,
        "computed_at": datetime.now(TZ_UTC).isoformat(),
        "sources": sources,
        "matrix": payload.get("matrix") or [],
        "p_values": payload.get("p_values") or [],
    }
    sb.table("correlation_snapshots").upsert(row).execute()
    return key


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Write correlation snapshots into Supabase")
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
        help="Do not upsert if the computed window has no sources/data",
    )
    args = ap.parse_args(argv[1:])

    key = write_snapshot(
        period=args.period,
        include_today=bool(args.include_today),
        anchor_latest=bool(args.anchor_latest),
        skip_empty=bool(args.skip_empty),
    )
    if key:
        print(f"Wrote correlation snapshot {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv))
