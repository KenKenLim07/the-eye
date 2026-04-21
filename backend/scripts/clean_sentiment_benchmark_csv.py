#!/usr/bin/env python3
"""
Create a cleaned copy of a manually labeled sentiment benchmark CSV.

This is intentionally conservative and targets scraper noise:
- Inquirer consent boilerplate paragraphs
- "READ:" / "READ MORE:" cross-links
- exact duplicate paragraphs (article repeated)
- obvious concatenation via repeated "MANILA —" datelines

Usage:
  cd backend
  python scripts/clean_sentiment_benchmark_csv.py \
    --in reports/benchmark_sample_2026-03-25_2026-03-31.csv \
    --out reports/benchmark_sample_2026-03-25_2026-03-31.cleaned.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean scraper-noise from a benchmark CSV (non-destructive).")
    parser.add_argument("--in", dest="in_file", required=True, help="Input CSV path (relative to backend/).")
    parser.add_argument("--out", dest="out_file", required=True, help="Output CSV path (relative to backend/).")
    args = parser.parse_args()

    in_path = (BACKEND_ROOT / args.in_file).resolve()
    out_path = (BACKEND_ROOT / args.out_file).resolve()

    if not in_path.exists():
        raise SystemExit(f"Input CSV not found: {in_path}")

    from app.core.text_clean import clean_scraped_news_text  # noqa: WPS433

    rows: list[dict[str, Any]] = []
    with open(in_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fieldnames = list(r.fieldnames or [])
        for row in r:
            rows.append(dict(row))

    if not rows:
        raise SystemExit("Input CSV is empty.")

    extra_cols = [
        "content_raw_len",
        "content_clean_len",
        "clean_removed_read_links",
        "clean_removed_boilerplate_paragraphs",
        "clean_removed_duplicate_paragraphs",
        "clean_truncated_at_second_dateline",
        "clean_truncated_on_repeat_prefix",
        "clean_truncated_at_inquirer_marker",
    ]
    out_fields = fieldnames + [c for c in extra_cols if c not in fieldnames]

    totals = Counter()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    final_out_path = out_path
    try:
        f = open(out_path, "w", encoding="utf-8", newline="")
    except PermissionError:
        # Common when the source CSV was created by a Docker container as a different UID.
        fallback = Path("/tmp") / out_path.name
        final_out_path = fallback
        f = open(fallback, "w", encoding="utf-8", newline="")
        print(f"Permission denied writing to: {out_path}")
        print(f"Writing cleaned CSV to fallback path: {fallback}")

    with f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for row in rows:
            content = str(row.get("content") or "")
            cleaned, meta = clean_scraped_news_text(content, enabled=True)

            totals["rows"] += 1
            totals["removed_read_links"] += int(meta.removed_read_links)
            totals["removed_boilerplate_paragraphs"] += int(meta.removed_boilerplate_paragraphs)
            totals["removed_duplicate_paragraphs"] += int(meta.removed_duplicate_paragraphs)
            totals["truncated_at_second_dateline"] += int(bool(meta.truncated_at_second_dateline))
            totals["truncated_on_repeat_prefix"] += int(bool(meta.truncated_on_repeat_prefix))
            totals["truncated_at_inquirer_marker"] += int(bool(meta.truncated_at_inquirer_marker))

            out = dict(row)
            out["content"] = cleaned
            out["content_raw_len"] = str(meta.input_len)
            out["content_clean_len"] = str(meta.output_len)
            out["clean_removed_read_links"] = str(meta.removed_read_links)
            out["clean_removed_boilerplate_paragraphs"] = str(meta.removed_boilerplate_paragraphs)
            out["clean_removed_duplicate_paragraphs"] = str(meta.removed_duplicate_paragraphs)
            out["clean_truncated_at_second_dateline"] = "1" if meta.truncated_at_second_dateline else "0"
            out["clean_truncated_on_repeat_prefix"] = "1" if meta.truncated_on_repeat_prefix else "0"
            out["clean_truncated_at_inquirer_marker"] = "1" if meta.truncated_at_inquirer_marker else "0"
            w.writerow(out)

    print("Wrote cleaned CSV:", final_out_path)
    print("Summary:", dict(totals))


if __name__ == "__main__":
    main()
