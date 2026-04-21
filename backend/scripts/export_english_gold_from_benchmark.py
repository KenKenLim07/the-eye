#!/usr/bin/env python3
"""
Export an English-only "gold" JSON set from a labeled benchmark CSV.

Goal:
- Build a cleaner, language-specific evaluation set for documentation when
  fine-tuning is not feasible.
- Output format is compatible with `scripts/evaluate_vader_ph_gold.py --file ...`

Example:
  cd backend
  python scripts/export_english_gold_from_benchmark.py \
    --file reports/benchmark_sample_2026-03-25_2026-03-31.csv \
    --out app/ml/distilbert_en_gold.v1.json \
    --tagalog-max 0.03 \
    --require-consensus on \
    --label-mode binary \
    --clean-text on \
    --exclude-noisy on
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _norm_label(s: str) -> str:
    raw = (s or "").strip().lower()
    if raw in {"pos", "positive"}:
        return "positive"
    if raw in {"neu", "neutral"}:
        return "neutral"
    if raw in {"neg", "negative"}:
        return "negative"
    return ""


def _safe_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an English-only gold set from a benchmark CSV.")
    parser.add_argument(
        "--file",
        default=str(BACKEND_ROOT / "reports" / "benchmark_sample_2026-03-25_2026-03-31.csv"),
        help="Input labeled CSV path.",
    )
    parser.add_argument(
        "--out",
        default=str(BACKEND_ROOT / "app" / "ml" / "distilbert_en_gold.v1.json"),
        help="Output gold JSON path.",
    )
    parser.add_argument(
        "--tagalog-max",
        type=float,
        default=0.03,
        help="Max tagalog_signal_ratio to be considered 'English-first' (default: 0.03).",
    )
    parser.add_argument(
        "--require-consensus",
        choices=["on", "off"],
        default="on",
        help="Keep only rows where label_a == label_b == label_final (default: on).",
    )
    parser.add_argument(
        "--label-mode",
        choices=["all", "binary"],
        default="binary",
        help="Label mode: all=pos/neu/neg, binary=pos/neg only (default: binary).",
    )
    parser.add_argument(
        "--clean-text",
        choices=["on", "off"],
        default="on",
        help="Apply conservative scraper-noise cleaning to exported text (default: on).",
    )
    parser.add_argument(
        "--exclude-noisy",
        choices=["on", "off"],
        default="on",
        help="Drop clearly broken/concatenated rows (default: on).",
    )
    parser.add_argument("--max-items", type=int, default=0, help="Max items to export (0=all).")
    parser.add_argument("--seed", type=int, default=13, help="Shuffle seed (default: 13).")
    args = parser.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    clean_text = args.clean_text == "on"
    exclude_noisy = args.exclude_noisy == "on"
    require_consensus = args.require_consensus == "on"

    from app.core.text_clean import clean_scraped_news_text  # noqa: WPS433

    rows: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(dict(row))

    if not rows:
        raise SystemExit("CSV is empty.")

    candidates: list[dict[str, Any]] = []
    for it in rows:
        title = str(it.get("title") or "").strip()
        content = str(it.get("content") or "").strip()
        if not (title or content):
            continue

        la = _norm_label(it.get("label_a", ""))
        lb = _norm_label(it.get("label_b", ""))
        lf = _norm_label(it.get("label_final", ""))
        if not lf:
            continue

        if require_consensus and not (la and lb and la == lb and lf == la):
            continue

        if args.label_mode == "binary" and lf not in {"positive", "negative"}:
            continue

        ratio = _safe_float(it.get("tagalog_signal_ratio", 0.0))
        if ratio > float(args.tagalog_max):
            continue

        raw_text = f"{title}\n\n{content}".strip()
        if clean_text:
            cleaned, meta = clean_scraped_news_text(raw_text, enabled=True)
            is_noisy = (
                (meta.input_len == 0)
                or (meta.output_len < 200)
                or bool(meta.truncated_at_second_dateline)
                or bool(meta.truncated_on_repeat_prefix)
                or bool(meta.truncated_at_inquirer_marker)
            )
            if exclude_noisy and is_noisy:
                continue
            text_out = cleaned
        else:
            text_out = raw_text

        candidates.append(
            {
                "text": text_out,
                "label": lf,
                "article_id": it.get("article_id"),
                "source": it.get("source"),
                "published_at": it.get("published_at"),
                "url": it.get("url"),
                "tagalog_signal_ratio": ratio,
            }
        )

    if not candidates:
        raise SystemExit("No rows matched filters. Try raising --tagalog-max or disabling --require-consensus.")

    random.Random(int(args.seed)).shuffle(candidates)
    if int(args.max_items) > 0:
        candidates = candidates[: int(args.max_items)]

    payload = {
        "version": "distilbert_en_gold.v1",
        "source_csv": str(csv_path),
        "filters": {
            "tagalog_max": float(args.tagalog_max),
            "require_consensus": bool(require_consensus),
            "label_mode": args.label_mode,
            "clean_text": bool(clean_text),
            "exclude_noisy": bool(exclude_noisy),
            "max_items": int(args.max_items),
            "seed": int(args.seed),
        },
        "items": candidates,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path} (n={len(candidates)})")


if __name__ == "__main__":
    main()

