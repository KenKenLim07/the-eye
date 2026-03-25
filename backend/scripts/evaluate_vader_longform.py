#!/usr/bin/env python3
"""
Compare legacy single-pass VADER vs new long-form weighted VADER on real articles.

Usage:
  cd backend
  # Baseline (no PH patch)
  python scripts/evaluate_vader_longform.py --days 30 --limit 300 --ph-patch off

  # Patched (Taglish lexicon enabled)
  python scripts/evaluate_vader_longform.py --days 30 --limit 300 --ph-patch on
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

# Ensure `import app...` works when executed as a script (e.g., in Docker).
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.supabase import get_supabase


def label_from_compound(compound: float, pos_threshold: float = 0.05, neg_threshold: float = -0.05) -> str:
    if compound >= pos_threshold:
        return "positive"
    if compound <= neg_threshold:
        return "negative"
    return "neutral"


def fetch_recent_articles(days: int, limit: int, source: str | None) -> list[dict[str, Any]]:
    sb = get_supabase()
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = (
        sb.table("articles")
        .select("id,title,content,source,published_at")
        .gte("published_at", start)
        .order("published_at", desc=True)
        .limit(limit)
    )
    if source:
        q = q.eq("source", source)
    res = q.execute()
    return res.data or []


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate VADER long-form aggregation vs legacy single-pass.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days (default: 30)")
    parser.add_argument("--limit", type=int, default=300, help="Max articles to sample (default: 300)")
    parser.add_argument("--source", type=str, default=None, help="Optional source filter (e.g., Rappler)")
    parser.add_argument("--top", type=int, default=10, help="Top changed examples to print")
    parser.add_argument(
        "--ph-patch",
        choices=["auto", "on", "off"],
        default="auto",
        help="Control Taglish VADER patch via env var (default: auto/respect VADER_PH_PATCH).",
    )
    args = parser.parse_args()

    if args.ph_patch == "on":
        os.environ["VADER_PH_PATCH"] = "1"
    elif args.ph_patch == "off":
        os.environ["VADER_PH_PATCH"] = "0"

    # Import after setting env so VADER is initialized with the intended patch state.
    from app.ml.bias import analyze_sentiment_vader_detailed, _ensure_vader  # noqa: WPS433

    rows = fetch_recent_articles(days=args.days, limit=args.limit, source=args.source)
    if not rows:
        print("No articles found in selected window.")
        return

    sia = _ensure_vader()
    total = len(rows)
    changed = 0
    abs_diffs: list[float] = []
    old_scores: list[float] = []
    new_scores: list[float] = []
    old_labels = Counter()
    new_labels = Counter()
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    changed_examples: list[dict[str, Any]] = []
    patch_meta_sample: dict[str, Any] | None = None

    for r in rows:
        title = str(r.get("title") or "").strip()
        content = str(r.get("content") or "").strip()

        # Legacy path (before long-form upgrade): full text single-pass.
        legacy_text = f"{title} {content}".strip()
        old_compound = float(sia.polarity_scores(legacy_text).get("compound", 0.0))
        old_label = label_from_compound(old_compound)

        # New path: title/body-aware weighted aggregation.
        upgraded_text = f"{title}\n\n{content}".strip()
        new_compound, new_label, _, details = analyze_sentiment_vader_detailed(upgraded_text)
        if patch_meta_sample is None:
            patch_meta_sample = {
                "ph_patch_enabled": details.get("ph_patch_enabled"),
                "ph_patch_applied": details.get("ph_patch_applied"),
                "ph_patch_version": details.get("ph_patch_version"),
                "ph_lexicon_terms_added": details.get("ph_lexicon_terms_added"),
                "ph_lexicon_overrides": details.get("ph_lexicon_overrides"),
                "ph_lexicon_skipped_existing": details.get("ph_lexicon_skipped_existing"),
                "ph_phrases_enabled": details.get("ph_phrases_enabled"),
                "ph_patch_error": details.get("ph_patch_error"),
            }

        old_scores.append(old_compound)
        new_scores.append(new_compound)
        abs_diffs.append(abs(new_compound - old_compound))
        old_labels[old_label] += 1
        new_labels[new_label] += 1
        confusion[(old_label, new_label)] += 1

        if old_label != new_label:
            changed += 1
            changed_examples.append(
                {
                    "id": r.get("id"),
                    "source": r.get("source"),
                    "published_at": str(r.get("published_at") or "")[:10],
                    "title": title[:120],
                    "old_label": old_label,
                    "new_label": new_label,
                    "old_score": round(old_compound, 4),
                    "new_score": round(new_compound, 4),
                    "delta": round(new_compound - old_compound, 4),
                    "chunks": details.get("chunks_analyzed", 0),
                }
            )

    changed_examples.sort(key=lambda x: abs(float(x["delta"])), reverse=True)

    print("=== VADER Comparison Report ===")
    print(f"Window: last {args.days} days")
    print(f"Source: {args.source or 'ALL'}")
    print(f"Sampled articles: {total}")
    if patch_meta_sample is not None:
        print()
        print("PH patch status (sample)")
        for k in (
            "ph_patch_enabled",
            "ph_patch_applied",
            "ph_patch_version",
            "ph_lexicon_terms_added",
            "ph_lexicon_overrides",
            "ph_lexicon_skipped_existing",
            "ph_phrases_enabled",
            "ph_patch_error",
        ):
            print(f"- {k}: {patch_meta_sample.get(k)}")
    print()
    print("Score drift")
    print(f"- Mean old score: {mean(old_scores):.4f}")
    print(f"- Mean new score: {mean(new_scores):.4f}")
    print(f"- Mean absolute delta: {mean(abs_diffs):.4f}")
    print()
    print("Label distribution")
    print(f"- Old: {dict(old_labels)}")
    print(f"- New: {dict(new_labels)}")
    print()
    print("Label changes")
    print(f"- Changed labels: {changed}/{total} ({(changed / total) * 100:.1f}%)")
    print("- Confusion (old -> new):")
    for o in ("positive", "neutral", "negative"):
        row_bits = []
        for n in ("positive", "neutral", "negative"):
            row_bits.append(f"{o}->{n}:{confusion[(o, n)]}")
        print(f"  {' | '.join(row_bits)}")

    if changed_examples:
        print()
        print(f"Top {min(args.top, len(changed_examples))} changed examples by score delta")
        for ex in changed_examples[: args.top]:
            print(
                f"- [{ex['id']}] {ex['source']} {ex['published_at']} | "
                f"{ex['old_label']}({ex['old_score']}) -> {ex['new_label']}({ex['new_score']}) | "
                f"delta={ex['delta']} chunks={ex['chunks']} | {ex['title']}"
            )


if __name__ == "__main__":
    main()
