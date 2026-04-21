#!/usr/bin/env python3
"""
Export a stratified sample of real news articles for manual sentiment benchmarking.

This script is intended for thesis documentation. It produces a CSV that can be
manually labeled by two annotators (label_a, label_b) and adjudicated (label_final).

Usage:
  cd backend
  python scripts/export_sentiment_benchmark_sample.py \
    --start-local 2026-03-25 --end-local 2026-03-31 \
    --n 200 --min-per-source 20 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TZ_PH = ZoneInfo("Asia/Manila")
TZ_UTC = ZoneInfo("UTC")

DEFAULT_SOURCES = [
    "ABS-CBN",
    "GMA",
    "Inquirer",
    "Manila Bulletin",
    "Manila Times",
    "Philstar",
    "Rappler",
]


def _parse_local_date(d: str) -> date:
    return date.fromisoformat(d)


def _ph_local_window_to_utc(start_local: str, end_local: str) -> tuple[str, str]:
    s = datetime.combine(_parse_local_date(start_local), time(0, 0, 0), tzinfo=TZ_PH).astimezone(TZ_UTC)
    e = datetime.combine(_parse_local_date(end_local), time(23, 59, 59, 999999), tzinfo=TZ_PH).astimezone(TZ_UTC)
    return s.isoformat(), e.isoformat()


def _fetch_articles_meta(sb, *, start_utc: str, end_utc: str, batch_size: int = 1000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        res = (
            sb.table("articles")
            .select("id,source,published_at,url,title")
            .gte("published_at", start_utc)
            .lte("published_at", end_utc)
            .neq("source", "Sunstar")
            .order("published_at", desc=False)
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        batch = res.data or []
        if not batch:
            break
        out.extend(batch)
        offset += batch_size
        if len(batch) < batch_size:
            break
    return out


def _fetch_articles_full(sb, ids: list[int], *, batch_size: int = 200) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for i in range(0, len(ids), batch_size):
        chunk = ids[i : i + batch_size]
        res = (
            sb.table("articles")
            .select("id,source,published_at,url,title,content")
            .in_("id", chunk)
            .execute()
        )
        for r in (res.data or []):
            try:
                rid = int(r.get("id"))
            except Exception:
                continue
            out[rid] = r
    return out


def _largest_remainder_alloc(need: int, weights: dict[str, int]) -> dict[str, int]:
    if need <= 0:
        return {k: 0 for k in weights}
    total = sum(max(0, int(v)) for v in weights.values())
    if total <= 0:
        return {k: 0 for k in weights}

    raw: dict[str, float] = {k: (need * (max(0, int(v)) / total)) for k, v in weights.items()}
    base: dict[str, int] = {k: int(raw[k]) for k in raw}
    rem = need - sum(base.values())
    if rem <= 0:
        return base

    frac_sorted = sorted(((k, raw[k] - base[k]) for k in raw), key=lambda x: x[1], reverse=True)
    for k, _ in frac_sorted:
        if rem <= 0:
            break
        base[k] += 1
        rem -= 1
    return base


def _sample_stratified(
    rng: random.Random,
    by_source: dict[str, list[dict[str, Any]]],
    *,
    n: int,
    min_per_source: int,
    sources: list[str],
) -> list[int]:
    selected: set[int] = set()
    chosen: list[int] = []

    for src in sources:
        pool = by_source.get(src) or []
        if not pool:
            continue
        k = min(min_per_source, len(pool))
        picks = rng.sample(pool, k=k) if len(pool) > k else list(pool)
        for p in picks:
            pid = int(p["id"])
            if pid in selected:
                continue
            selected.add(pid)
            chosen.append(pid)

    if len(chosen) >= n:
        return chosen[:n]

    remaining_needed = n - len(chosen)
    remaining_by_source: dict[str, list[dict[str, Any]]] = {}
    remaining_counts: dict[str, int] = {}
    for src in sources:
        pool = by_source.get(src) or []
        rest = [p for p in pool if int(p["id"]) not in selected]
        remaining_by_source[src] = rest
        remaining_counts[src] = len(rest)

    alloc = _largest_remainder_alloc(remaining_needed, remaining_counts)

    # Respect availability; if any source is over-allocated, cap and redistribute.
    extra: dict[str, int] = {k: min(int(alloc.get(k, 0)), remaining_counts.get(k, 0)) for k in sources}
    deficit = remaining_needed - sum(extra.values())
    if deficit > 0:
        # Greedy redistribute to sources with remaining capacity.
        capacity = {k: remaining_counts.get(k, 0) - extra.get(k, 0) for k in sources}
        for src in sorted(capacity, key=lambda s: capacity[s], reverse=True):
            if deficit <= 0:
                break
            if capacity[src] <= 0:
                continue
            add = min(deficit, capacity[src])
            extra[src] += add
            deficit -= add

    for src in sources:
        k = int(extra.get(src, 0))
        if k <= 0:
            continue
        pool = remaining_by_source.get(src) or []
        picks = rng.sample(pool, k=k) if len(pool) > k else list(pool)
        for p in picks:
            pid = int(p["id"])
            if pid in selected:
                continue
            selected.add(pid)
            chosen.append(pid)
            if len(chosen) >= n:
                return chosen

    return chosen


def _chunks(xs: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(xs), size):
        yield xs[i : i + size]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export stratified benchmark sample (manual labeling).")
    parser.add_argument("--start-local", required=True, help="Start date (PH local), YYYY-MM-DD")
    parser.add_argument("--end-local", required=True, help="End date (PH local), YYYY-MM-DD")
    parser.add_argument("--n", type=int, default=200, help="Total sample size (default: 200)")
    parser.add_argument("--min-per-source", type=int, default=20, help="Minimum per source (default: 20)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help=f"Comma-separated sources (default: {','.join(DEFAULT_SOURCES)})",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path (default: backend/reports/benchmark_sample_<start>_<end>.csv)",
    )
    parser.add_argument(
        "--with-model-outputs",
        action="store_true",
        help="Include baseline model outputs (slower; requires transformer model availability).",
    )
    args = parser.parse_args()

    if args.n <= 0:
        raise SystemExit("--n must be > 0")
    if args.min_per_source < 0:
        raise SystemExit("--min-per-source must be >= 0")

    sources = [s.strip() for s in (args.sources or "").split(",") if s.strip()]
    if not sources:
        raise SystemExit("No sources provided.")

    start_utc, end_utc = _ph_local_window_to_utc(args.start_local, args.end_local)

    from app.core.supabase import get_supabase  # noqa: WPS433

    sb = get_supabase()
    meta_rows = _fetch_articles_meta(sb, start_utc=start_utc, end_utc=end_utc)
    if not meta_rows:
        raise SystemExit("No articles found for the selected window.")

    by_source: dict[str, list[dict[str, Any]]] = {}
    for r in meta_rows:
        src = str(r.get("source") or "").strip()
        if not src:
            continue
        by_source.setdefault(src, []).append(r)

    rng = random.Random(args.seed)
    chosen_ids = _sample_stratified(rng, by_source, n=args.n, min_per_source=args.min_per_source, sources=sources)
    if len(chosen_ids) < args.n:
        print(f"Warning: only sampled {len(chosen_ids)} articles (target was {args.n}).", file=sys.stderr)

    full = _fetch_articles_full(sb, chosen_ids)
    missing = [i for i in chosen_ids if i not in full]
    if missing:
        print(f"Warning: {len(missing)} sampled ids could not be fetched (skipped).", file=sys.stderr)

    # Ensure patch env is set before importing model code (when model outputs are requested).
    if args.with_model_outputs:
        os.environ.setdefault("VADER_PH_PATCH", "1")

    from app.ml.bias import (  # noqa: WPS433
        _tagalog_signal,
        analyze_sentiment_distilbert_detailed,
        analyze_sentiment_hybrid_detailed,
        analyze_sentiment_vader_detailed,
    )

    rows_out: list[dict[str, Any]] = []
    for aid in chosen_ids:
        r = full.get(aid)
        if not r:
            continue
        title = str(r.get("title") or "").strip()
        content = str(r.get("content") or "").strip()
        text = f"{title}\n\n{content}".strip()
        sig = _tagalog_signal(text)
        tagalog_ratio = float(sig.get("ratio") or 0.0)

        out_row: dict[str, Any] = {
            "article_id": int(r.get("id")),
            "source": str(r.get("source") or "").strip(),
            "published_at": str(r.get("published_at") or ""),
            "url": str(r.get("url") or ""),
            "title": title,
            "content": content,
            "tagalog_signal_ratio": f"{tagalog_ratio:.6f}",
            "label_a": "",
            "label_b": "",
            "label_final": "",
            "vader_label": "",
            "distilbert_label": "",
            "hybrid_label": "",
            "hybrid_route": "",
        }

        if args.with_model_outputs:
            try:
                _, v_label, _, _ = analyze_sentiment_vader_detailed(text)
                out_row["vader_label"] = v_label
            except Exception:
                pass
            try:
                _, d_label, _, _ = analyze_sentiment_distilbert_detailed(text)
                out_row["distilbert_label"] = d_label
            except Exception:
                pass
            try:
                _, h_label, _, meta = analyze_sentiment_hybrid_detailed(text)
                out_row["hybrid_label"] = h_label
                out_row["hybrid_route"] = str((meta or {}).get("route") or "")
            except Exception:
                pass

        rows_out.append(out_row)

    rows_out.sort(key=lambda x: (str(x.get("source") or ""), str(x.get("published_at") or "")))

    default_out = BACKEND_ROOT / "reports" / f"benchmark_sample_{args.start_local}_{args.end_local}.csv"
    out_path = Path(args.out) if args.out else default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    if not fieldnames:
        raise SystemExit("No rows to write.")

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {out_path}")
    print(f"Window (PH): {args.start_local} → {args.end_local}")
    print(f"Window (UTC): {start_utc} → {end_utc}")
    print(f"Sources: {', '.join(sources)} (Sunstar excluded by design)")


if __name__ == "__main__":
    main()
