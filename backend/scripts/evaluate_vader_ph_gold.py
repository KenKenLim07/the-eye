#!/usr/bin/env python3
"""
Evaluate sentiment models on a small offline "gold" set.

Usage:
  cd backend
  python scripts/evaluate_vader_ph_gold.py --model vader --ph-patch on
  python scripts/evaluate_vader_ph_gold.py --model distilbert
  python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on
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

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

LABELS_3 = ["positive", "neutral", "negative"]
LABELS_BIN = ["positive", "negative"]


def _compute_metrics(y_true: list[str], y_pred: list[str], *, labels: list[str]) -> dict[str, object]:
    acc = float(accuracy_score(y_true, y_pred))
    pr, rc, f1, sup = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        zero_division=0,
    )
    macro_f1 = float(sum(f1) / len(f1)) if f1 is not None and len(f1) else 0.0
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    per_class: dict[str, dict[str, object]] = {}
    for i, lab in enumerate(labels):
        per_class[lab] = {
            "precision": float(pr[i]),
            "recall": float(rc[i]),
            "f1": float(f1[i]),
            "support": int(sup[i]),
        }
    return {"accuracy": acc, "macro_f1": macro_f1, "per_class": per_class, "labels": labels, "confusion": cm}


def _default_setting_name(model: str, ph_patch: str) -> str:
    if model == "vader":
        return "VADER+PH patch (on)" if ph_patch == "on" else "VADER (patch off)"
    if model == "distilbert":
        return "DistilBERT (SST-2)"
    if model == "hybrid":
        return "Hybrid router"
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Taglish VADER patch on an offline gold set.")
    parser.add_argument(
        "--model",
        choices=["vader", "distilbert", "hybrid"],
        default="vader",
        help="Which model to evaluate (default: vader).",
    )
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
    parser.add_argument(
        "--labels",
        choices=["auto", "3", "binary"],
        default="auto",
        help="Label set to score against: auto (infer), 3 (pos/neu/neg), binary (pos/neg).",
    )
    parser.add_argument(
        "--latex",
        choices=["off", "row"],
        default="off",
        help="Print a LaTeX table row (default: off).",
    )
    parser.add_argument(
        "--setting",
        default=None,
        help="Optional LaTeX row label (default: inferred from model + patch flag).",
    )
    parser.add_argument(
        "--vader-neutral-band",
        type=float,
        default=None,
        help="Set VADER_NEUTRAL_BAND for this run (e.g., 0.16).",
    )
    parser.add_argument(
        "--tagalog-signal-threshold",
        type=float,
        default=None,
        help="Set TAGALOG_SIGNAL_THRESHOLD for this run (hybrid routing).",
    )
    parser.add_argument(
        "--distilbert-neutral-min-conf",
        type=float,
        default=None,
        help="Set DISTILBERT_NEUTRAL_MIN_CONF for this run.",
    )
    parser.add_argument(
        "--vader-tl-but-words",
        choices=["auto", "on", "off"],
        default="auto",
        help="Control VADER_TL_BUT_WORDS (Tagalog contrast words in BUT_WORDS).",
    )
    parser.add_argument(
        "--vader-tl-but-normalize",
        choices=["auto", "on", "off"],
        default="auto",
        help="Control VADER_TL_BUT_NORMALIZE (normalize pero|ngunit|subalit → 'but').",
    )
    args = parser.parse_args()

    if args.ph_patch == "on":
        os.environ["VADER_PH_PATCH"] = "1"
    elif args.ph_patch == "off":
        os.environ["VADER_PH_PATCH"] = "0"
    if args.vader_neutral_band is not None:
        os.environ["VADER_NEUTRAL_BAND"] = str(args.vader_neutral_band)
    if args.tagalog_signal_threshold is not None:
        os.environ["TAGALOG_SIGNAL_THRESHOLD"] = str(args.tagalog_signal_threshold)
    if args.distilbert_neutral_min_conf is not None:
        os.environ["DISTILBERT_NEUTRAL_MIN_CONF"] = str(args.distilbert_neutral_min_conf)
    if args.vader_tl_but_words == "on":
        os.environ["VADER_TL_BUT_WORDS"] = "1"
    elif args.vader_tl_but_words == "off":
        os.environ["VADER_TL_BUT_WORDS"] = "0"
    if args.vader_tl_but_normalize == "on":
        os.environ["VADER_TL_BUT_NORMALIZE"] = "1"
    elif args.vader_tl_but_normalize == "off":
        os.environ["VADER_TL_BUT_NORMALIZE"] = "0"

    # Import after env var is set.
    from app.ml.bias import (  # noqa: WPS433
        analyze_sentiment_distilbert_detailed,
        analyze_sentiment_hybrid_detailed,
        analyze_sentiment_vader_detailed,
    )

    if args.model == "vader":
        scorer = analyze_sentiment_vader_detailed
    elif args.model == "distilbert":
        scorer = analyze_sentiment_distilbert_detailed
    else:
        scorer = analyze_sentiment_hybrid_detailed

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
    route_counts = Counter()
    y_true_list: list[str] = []
    y_pred_list: list[str] = []

    for it in items:
        text = str((it or {}).get("text") or "").strip()
        label = str((it or {}).get("label") or "").strip().lower()
        if not text or label not in {"positive", "neutral", "negative"}:
            continue
        score, pred, _, meta = scorer(text)
        route = ""
        route_reason = ""
        if args.model == "hybrid":
            route = str((meta or {}).get("route") or "")
            route_reason = str((meta or {}).get("route_reason") or "")
            if route:
                route_counts[route] += 1
        if patch_meta_sample is None:
            # VADER details are nested under route_metadata for hybrid.
            m = meta or {}
            if args.model == "hybrid":
                m = (m.get("route_metadata") or {}) if isinstance(m.get("route_metadata"), dict) else {}
            patch_meta_sample = {
                "ph_patch_enabled": m.get("ph_patch_enabled"),
                "ph_patch_applied": m.get("ph_patch_applied"),
                "ph_patch_version": m.get("ph_patch_version"),
                "ph_lexicon_terms_added": m.get("ph_lexicon_terms_added"),
                "ph_lexicon_overrides": m.get("ph_lexicon_overrides"),
                "ph_lexicon_skipped_existing": m.get("ph_lexicon_skipped_existing"),
                "ph_phrases_enabled": m.get("ph_phrases_enabled"),
                "ph_patch_error": m.get("ph_patch_error"),
            }
        total += 1
        y_true_list.append(label)
        y_pred_list.append(pred)
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
                    "route": route,
                    "route_reason": route_reason,
                }
            )

    acc = (correct / total) if total else 0.0
    if args.labels == "3":
        label_set = LABELS_3
    elif args.labels == "binary":
        label_set = LABELS_BIN
    else:
        # Auto: if the gold set has no neutral labels, score as binary.
        label_set = LABELS_BIN if ("neutral" not in set(y_true_list)) else LABELS_3

    metrics = _compute_metrics(y_true_list, y_pred_list, labels=label_set) if total else None
    neutral_pred_rate = (sum(1 for p in y_pred_list if p == "neutral") / total) if total else 0.0

    print("=== Sentiment Gold Set Report ===")
    print(f"Model: {args.model}")
    print(f"Items evaluated: {total}")
    if metrics:
        print(f"Accuracy: {metrics['accuracy']:.3f} ({correct}/{total})")
        print(f"Macro-F1: {metrics['macro_f1']:.3f} (labels={','.join(label_set)})")
        if label_set == LABELS_BIN:
            print(f"Neutral-pred rate: {neutral_pred_rate:.3f}")
    else:
        print(f"Accuracy: {acc:.3f} ({correct}/{total})")
    if patch_meta_sample is not None:
        print()
        print("PH patch status (sample)")
        for k, v in patch_meta_sample.items():
            print(f"- {k}: {v}")
    if args.model == "hybrid" and route_counts:
        print()
        print(f"Hybrid routes: {dict(route_counts)}")
    print()
    print(f"True dist: {dict(y_true)}")
    print(f"Pred dist: {dict(y_pred)}")
    print()
    if metrics:
        print("Confusion (rows=true, cols=pred):")
        labels = metrics["labels"]
        cm = metrics["confusion"]
        print("  labels:", ", ".join(str(x) for x in labels))
        for row in cm:
            print("  " + " ".join(f"{int(x):4d}" for x in row))
    else:
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
            route_bits = ""
            if args.model == "hybrid" and (ex.get("route") or ex.get("route_reason")):
                r = ex.get("route") or ""
                rr = ex.get("route_reason") or ""
                if r and rr:
                    route_bits = f" [{r}/{rr}]"
                elif r:
                    route_bits = f" [{r}]"
            print(f"- {ex['true']} -> {ex['pred']} (score={ex['score']}){route_bits}: {ex['text']}")

    if args.latex == "row" and metrics:
        setting = (args.setting or "").strip() or _default_setting_name(args.model, args.ph_patch)
        per = metrics["per_class"]
        if label_set == LABELS_3:
            row = (
                f"{setting} & {metrics['accuracy']:.3f} & {metrics['macro_f1']:.3f} & "
                f"{per['positive']['f1']:.3f} & {per['neutral']['f1']:.3f} & {per['negative']['f1']:.3f} \\\\"
            )
        else:
            row = f"{setting} & {metrics['accuracy']:.3f} & {metrics['macro_f1']:.3f} & {neutral_pred_rate:.3f} \\\\"
        print()
        print("=== LaTeX Row (copy/paste) ===")
        print(row)


if __name__ == "__main__":
    main()
