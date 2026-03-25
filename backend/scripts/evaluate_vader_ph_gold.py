#!/usr/bin/env python3
"""
Evaluate VADER (baseline vs Taglish patched) on a small offline "gold" set.

Usage:
  cd backend
  python scripts/evaluate_vader_ph_gold.py --ph-patch off
  python scripts/evaluate_vader_ph_gold.py --ph-patch on
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Ensure `import app...` works when executed as a script (e.g., in Docker).
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Taglish VADER patch on an offline gold set.")
    parser.add_argument(
        "--ph-patch",
        choices=["auto", "on", "off"],
        default="auto",
        help="Control Taglish VADER patch via env var (default: auto/respect VADER_PH_PATCH).",
    )
    parser.add_argument(
        "--file",
        default=str(Path(__file__).resolve().parents[1] / "app" / "ml" / "vader_ph_eval.v1.json"),
        help="Path to the gold set JSON.",
    )
    parser.add_argument("--show", type=int, default=10, help="Show up to N misclassified examples.")
    args = parser.parse_args()

    if args.ph_patch == "on":
        os.environ["VADER_PH_PATCH"] = "1"
    elif args.ph_patch == "off":
        os.environ["VADER_PH_PATCH"] = "0"

    # Import after env var is set.
    from app.ml.bias import analyze_sentiment_vader_detailed  # noqa: WPS433

    with open(args.file, "r", encoding="utf-8") as f:
        payload = json.load(f) or {}
    items = payload.get("items") or []
    if not items:
        raise SystemExit("Gold set is empty.")

    correct = 0
    total = 0
    y_true = Counter()
    y_pred = Counter()
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    wrong: list[dict[str, str]] = []
    patch_meta_sample = None

    for it in items:
        text = str((it or {}).get("text") or "").strip()
        label = str((it or {}).get("label") or "").strip().lower()
        if not text or label not in {"positive", "neutral", "negative"}:
            continue
        score, pred, _, meta = analyze_sentiment_vader_detailed(text)
        if patch_meta_sample is None:
            patch_meta_sample = {
                "ph_patch_enabled": meta.get("ph_patch_enabled"),
                "ph_patch_applied": meta.get("ph_patch_applied"),
                "ph_patch_version": meta.get("ph_patch_version"),
                "ph_lexicon_terms_added": meta.get("ph_lexicon_terms_added"),
                "ph_lexicon_overrides": meta.get("ph_lexicon_overrides"),
                "ph_lexicon_skipped_existing": meta.get("ph_lexicon_skipped_existing"),
                "ph_phrases_enabled": meta.get("ph_phrases_enabled"),
                "ph_patch_error": meta.get("ph_patch_error"),
            }
        total += 1
        y_true[label] += 1
        y_pred[pred] += 1
        confusion[(label, pred)] += 1
        if pred == label:
            correct += 1
        else:
            wrong.append(
                {
                    "true": label,
                    "pred": pred,
                    "score": f"{score:.4f}",
                    "text": text[:160],
                }
            )

    acc = (correct / total) if total else 0.0
    print("=== VADER Gold Set Report ===")
    print(f"Items evaluated: {total}")
    print(f"Accuracy: {acc:.3f} ({correct}/{total})")
    if patch_meta_sample is not None:
        print()
        print("PH patch status (sample)")
        for k, v in patch_meta_sample.items():
            print(f"- {k}: {v}")
    print()
    print(f"True dist: {dict(y_true)}")
    print(f"Pred dist: {dict(y_pred)}")
    print()
    print("Confusion (true -> pred):")
    for t in ("positive", "neutral", "negative"):
        row = []
        for p in ("positive", "neutral", "negative"):
            row.append(f"{t}->{p}:{confusion[(t, p)]}")
        print("  " + " | ".join(row))

    if wrong and args.show:
        print()
        print(f"Misclassified (top {min(args.show, len(wrong))}):")
        for ex in wrong[: args.show]:
            print(f"- {ex['true']} -> {ex['pred']} (score={ex['score']}): {ex['text']}")


if __name__ == "__main__":
    main()
