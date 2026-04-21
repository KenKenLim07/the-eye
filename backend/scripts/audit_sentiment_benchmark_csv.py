#!/usr/bin/env python3
"""
Audit a manual sentiment benchmark CSV for label consistency and data-quality issues.

This does NOT judge "ground truth" labels. It flags:
- label_a vs label_b disagreements
- label_final not matching either annotator
- empty/very short content
- likely boilerplate / duplicated text patterns from scrapers
- duplicate URLs / titles

Usage:
  cd backend
  python scripts/audit_sentiment_benchmark_csv.py --file reports/benchmark_sample_2026-03-25_2026-03-31.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LABELS = ("positive", "neutral", "negative")


def norm_label(v: Any) -> str:
    s = ("" if v is None else str(v)).strip().lower()
    if s in {"pos", "positive"}:
        return "positive"
    if s in {"neu", "neutral"}:
        return "neutral"
    if s in {"neg", "negative"}:
        return "negative"
    return ""


def count_substring(haystack: str, needle: str) -> int:
    if not haystack or not needle:
        return 0
    return haystack.count(needle)


@dataclass(frozen=True)
class Flags:
    empty_content: bool
    short_content: bool
    repeated_inquirer_privacy: bool
    repeated_read_more: bool
    many_datelines: bool
    looks_concatenated: bool


def flag_row(title: str, content: str) -> tuple[Flags, dict[str, int]]:
    t = (title or "").strip()
    c = (content or "").strip()
    text = f"{t}\n\n{c}".strip()

    privacy_hits = count_substring(text, "By providing an email address.")
    read_more_hits = count_substring(text, "READ:")
    manila_hits = count_substring(text, "MANILA")
    manila_dash_hits = count_substring(text, "MANILA —") + count_substring(text, "MANILA --")

    # Heuristics: these are intentionally simple.
    empty_content = len(c) == 0
    short_content = len(c) > 0 and len(c) < 200
    repeated_inquirer_privacy = privacy_hits >= 3
    repeated_read_more = read_more_hits >= 3
    many_datelines = manila_dash_hits >= 3
    looks_concatenated = (privacy_hits >= 2) or (read_more_hits >= 4) or (manila_hits >= 12) or (manila_dash_hits >= 4)

    return (
        Flags(
            empty_content=empty_content,
            short_content=short_content,
            repeated_inquirer_privacy=repeated_inquirer_privacy,
            repeated_read_more=repeated_read_more,
            many_datelines=many_datelines,
            looks_concatenated=looks_concatenated,
        ),
        {
            "privacy_hits": privacy_hits,
            "read_more_hits": read_more_hits,
            "manila_hits": manila_hits,
            "manila_dash_hits": manila_dash_hits,
            "content_len": len(c),
            "title_len": len(t),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit manual benchmark CSV for label/data quality issues.")
    parser.add_argument(
        "--file",
        default="reports/benchmark_sample_2026-03-25_2026-03-31.csv",
        help="Path to benchmark CSV.",
    )
    parser.add_argument("--show", type=int, default=20, help="How many examples to show per category.")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")

    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(dict(row))

    if not rows:
        raise SystemExit("CSV is empty.")

    dist_a = Counter()
    dist_b = Counter()
    dist_f = Counter()
    disagreements: list[dict[str, Any]] = []
    final_not_in_ab: list[dict[str, Any]] = []
    invalid_labels: list[dict[str, Any]] = []

    dup_url = Counter()
    dup_title = Counter()

    flag_counts = Counter()
    flagged_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for it in rows:
        aid = it.get("article_id")
        src = (it.get("source") or "").strip()
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        content = it.get("content") or ""

        la = norm_label(it.get("label_a"))
        lb = norm_label(it.get("label_b"))
        lf = norm_label(it.get("label_final"))

        if la:
            dist_a[la] += 1
        if lb:
            dist_b[lb] += 1
        if lf:
            dist_f[lf] += 1

        if (it.get("label_a") or it.get("label_b") or it.get("label_final")) and (not la or not lb or not lf):
            # Flag rows where any label field exists but failed normalization.
            if not (la and lb and lf):
                invalid_labels.append(
                    {
                        "article_id": aid,
                        "source": src,
                        "title": title[:140],
                        "label_a_raw": it.get("label_a"),
                        "label_b_raw": it.get("label_b"),
                        "label_final_raw": it.get("label_final"),
                    }
                )

        if la and lb and la != lb:
            disagreements.append(
                {
                    "article_id": aid,
                    "source": src,
                    "title": title[:140],
                    "label_a": la,
                    "label_b": lb,
                    "label_final": lf or "",
                }
            )

        if lf and la and lb and (lf != la and lf != lb):
            final_not_in_ab.append(
                {
                    "article_id": aid,
                    "source": src,
                    "title": title[:140],
                    "label_a": la,
                    "label_b": lb,
                    "label_final": lf,
                }
            )

        if url:
            dup_url[url] += 1
        if title:
            dup_title[title] += 1

        flags, feats = flag_row(title, str(content))
        for k, v in flags.__dict__.items():
            if v:
                flag_counts[k] += 1
                if len(flagged_examples[k]) < args.show:
                    flagged_examples[k].append(
                        {
                            "article_id": aid,
                            "source": src,
                            "title": title[:140],
                            "url": url[:120],
                            **feats,
                        }
                    )

    dup_urls = [(u, c) for u, c in dup_url.items() if c >= 2]
    dup_titles = [(t, c) for t, c in dup_title.items() if c >= 2]
    dup_urls.sort(key=lambda x: x[1], reverse=True)
    dup_titles.sort(key=lambda x: x[1], reverse=True)

    print("=== Benchmark CSV Audit ===")
    print(f"File: {path}")
    print(f"Rows: {len(rows)}")
    print()
    print("Label distributions (normalized):")
    print(f"- label_a: {dict(dist_a)}")
    print(f"- label_b: {dict(dist_b)}")
    print(f"- label_final: {dict(dist_f)}")
    print()
    print(f"Annotator disagreements (label_a != label_b): {len(disagreements)}")
    if disagreements:
        for ex in disagreements[: args.show]:
            print(f"  - {ex['article_id']} [{ex['source']}] {ex['label_a']} vs {ex['label_b']} (final={ex['label_final']}): {ex['title']}")
    print()
    print(f"Final label not matching either annotator: {len(final_not_in_ab)}")
    if final_not_in_ab:
        for ex in final_not_in_ab[: args.show]:
            print(f"  - {ex['article_id']} [{ex['source']}] a={ex['label_a']} b={ex['label_b']} final={ex['label_final']}: {ex['title']}")
    print()
    if invalid_labels:
        print(f"Rows with potentially invalid/unrecognized labels: {len(invalid_labels)}")
        for ex in invalid_labels[: args.show]:
            print(f"  - {ex['article_id']} [{ex['source']}] a={ex['label_a_raw']} b={ex['label_b_raw']} final={ex['label_final_raw']}: {ex['title']}")
        print()

    print("Data-quality flags (heuristic counts):")
    for k, c in flag_counts.most_common():
        print(f"- {k}: {c}")
    print()
    for k in ("empty_content", "short_content", "repeated_inquirer_privacy", "repeated_read_more", "many_datelines", "looks_concatenated"):
        examples = flagged_examples.get(k) or []
        if not examples:
            continue
        print(f"[{k}] examples:")
        for ex in examples[: args.show]:
            print(
                f"  - {ex['article_id']} [{ex['source']}] len={ex['content_len']} privacy={ex['privacy_hits']} read={ex['read_more_hits']} manila—={ex['manila_dash_hits']}: {ex['title']}"
            )
        print()

    print(f"Duplicate URLs (count>=2): {len(dup_urls)}")
    for u, c in dup_urls[: min(args.show, len(dup_urls))]:
        print(f"  - {c}x {u[:160]}")
    print()
    print(f"Duplicate titles (count>=2): {len(dup_titles)}")
    for t, c in dup_titles[: min(args.show, len(dup_titles))]:
        print(f"  - {c}x {t[:160]}")


if __name__ == "__main__":
    main()

