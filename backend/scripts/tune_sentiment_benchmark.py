#!/usr/bin/env python3
"""
Grid-search tuner for the manual sentiment benchmark.

IMPORTANT: A naive grid that re-runs transformers for every trial is extremely slow.
This script uses a two-phase approach:
  1) Precompute model "raw" outputs once per text (and per MAX_CHARS setting).
  2) Apply thresholds/routing in pure Python for each trial.

Goal: pick defensible threshold values (instead of guessing) that maximize
either accuracy or macro-F1 on your labeled benchmark.

This tuner DOES NOT change labels; it only sweeps env vars that affect inference:
  - TAGALOG_SIGNAL_THRESHOLD
  - VADER_NEUTRAL_BAND
  - DISTILBERT_NEUTRAL_MIN_CONF
  - DISTILBERT_MAX_CHARS
  - (optional) DISTILBERT_NEUTRALIZE_REPORTING (0/1)

Usage (inside worker_ml):
  cd backend
  python scripts/tune_sentiment_benchmark.py --file reports/benchmark_sample_2026-03-25_2026-03-31.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

LABELS = ["positive", "neutral", "negative"]


def _norm_label(s: Any) -> str:
    raw = ("" if s is None else str(s)).strip().lower()
    if raw in {"pos", "positive"}:
        return "positive"
    if raw in {"neu", "neutral"}:
        return "neutral"
    if raw in {"neg", "negative"}:
        return "negative"
    return ""


def _compute_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    acc = float(accuracy_score(y_true, y_pred))
    pr, rc, f1, sup = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    macro_f1 = float(sum(f1) / len(f1)) if len(f1) else 0.0
    cm = confusion_matrix(y_true, y_pred, labels=LABELS).tolist()
    per = {}
    for i, lab in enumerate(LABELS):
        per[lab] = {"precision": float(pr[i]), "recall": float(rc[i]), "f1": float(f1[i]), "support": int(sup[i])}
    return {"accuracy": acc, "macro_f1": macro_f1, "per_class": per, "confusion_matrix": cm}


def _parse_floats(csv_list: str) -> list[float]:
    out: list[float] = []
    for part in (csv_list or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out


def _parse_ints(csv_list: str) -> list[int]:
    out: list[int] = []
    for part in (csv_list or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


@dataclass(frozen=True)
class Trial:
    tagalog_threshold: float
    vader_neutral_band: float
    distilbert_neutral_min_conf: float
    distilbert_max_chars: int
    neutralize_reporting: int
    hybrid_distilbert_route_min_conf: float


def _iter_trials(
    tagalog_thresholds: Iterable[float],
    vader_bands: Iterable[float],
    neutral_confs: Iterable[float],
    max_chars: Iterable[int],
    neutralize_reporting: Iterable[int],
    hybrid_route_min_confs: Iterable[float],
) -> list[Trial]:
    trials: list[Trial] = []
    for t in tagalog_thresholds:
        for vb in vader_bands:
            for nc in neutral_confs:
                for mc in max_chars:
                    for nr in neutralize_reporting:
                        for hr in hybrid_route_min_confs:
                            trials.append(
                                Trial(
                                    tagalog_threshold=float(t),
                                    vader_neutral_band=float(vb),
                                    distilbert_neutral_min_conf=float(nc),
                                    distilbert_max_chars=int(mc),
                                    neutralize_reporting=int(nr),
                                    hybrid_distilbert_route_min_conf=float(hr),
                                )
                            )
    return trials


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune sentiment benchmark thresholds via grid search.")
    parser.add_argument("--file", default="reports/benchmark_sample_2026-03-25_2026-03-31.csv")
    parser.add_argument("--clean-text", choices=["on", "off"], default="on")
    parser.add_argument("--model", choices=["hybrid", "vader", "distilbert"], default="hybrid")
    parser.add_argument("--optimize", choices=["accuracy", "macro_f1"], default="macro_f1")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--out", default="reports/sentiment_benchmark_tuning.json")

    # Keep the default grid modest; you can expand it once the workflow is proven.
    parser.add_argument("--tagalog-thresholds", default="0.03,0.06,0.10,0.15")
    parser.add_argument("--vader-neutral-bands", default="0.12,0.14,0.16,0.18")
    parser.add_argument("--distilbert-neutral-min-confs", default="0.55,0.60,0.65,0.70,0.75,0.80,0.85")
    parser.add_argument("--distilbert-max-chars", default="800,1200,2000")
    parser.add_argument("--distilbert-neutralize-reporting", default="1")
    parser.add_argument(
        "--hybrid-distilbert-route-min-confs",
        default="0.0,0.65,0.70,0.75,0.80",
        help="If >0, fall back to VADER when DistilBERT raw score is below this threshold (hybrid only).",
    )
    parser.add_argument("--progress-every", type=int, default=50, help="Print progress every N trials.")

    args = parser.parse_args()

    csv_path = (BACKEND_ROOT / args.file).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    from app.core.text_clean import clean_scraped_news_text  # noqa: WPS433
    from app.ml.bias import analyze_sentiment_vader_detailed  # noqa: WPS433
    from app.ml.sentiment_transformer import analyze_sentiment_distilbert_detailed  # noqa: WPS433
    import app.ml.bias as bias_mod  # noqa: WPS433
    # NOTE: we avoid calling internal transformer heuristics per trial for speed.

    clean_text = args.clean_text == "on"

    items: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            items.append(dict(row))
    if not items:
        raise SystemExit("CSV is empty.")

    y_true: list[str] = []
    texts: list[str] = []
    for it in items:
        lf = _norm_label(it.get("label_final"))
        title = str(it.get("title") or "").strip()
        content = str(it.get("content") or "").strip()
        if not lf or not (title or content):
            continue
        raw = f"{title}\n\n{content}".strip()
        if clean_text:
            raw, _ = clean_scraped_news_text(raw, enabled=True)
        y_true.append(lf)
        texts.append(raw)

    tagalog_thresholds = _parse_floats(args.tagalog_thresholds)
    vader_bands = _parse_floats(args.vader_neutral_bands)
    neutral_confs = _parse_floats(args.distilbert_neutral_min_confs)
    max_chars = _parse_ints(args.distilbert_max_chars)
    neutralize_reporting = _parse_ints(args.distilbert_neutralize_reporting)
    hybrid_route_min_confs = _parse_floats(args.hybrid_distilbert_route_min_confs)

    trials = _iter_trials(tagalog_thresholds, vader_bands, neutral_confs, max_chars, neutralize_reporting, hybrid_route_min_confs)
    if not trials:
        raise SystemExit("No trials: check your grid args.")

    # ---- Phase 1: precompute per-text features + raw model outputs ----
    print("Precomputing features + raw model outputs...")

    # For routing/reporting neutralization heuristics, use the same regex logic as the app.
    looks_preface = [bool(bias_mod._looks_like_reporting_preface(t)) for t in texts]  # type: ignore[attr-defined]
    tag_sig_ratio = [float((bias_mod._tagalog_signal(t) or {}).get("ratio") or 0.0) for t in texts]  # type: ignore[attr-defined]

    # VADER compound is independent of the neutral band; compute once.
    vader_compound: list[float] = []
    for i, text in enumerate(texts, start=1):
        comp, _, _, _ = analyze_sentiment_vader_detailed(text)
        vader_compound.append(float(comp))
        if i % 50 == 0:
            print(f"  VADER precompute: {i}/{len(texts)}")

    # DistilBERT raw outputs depend on MAX_CHARS (because the input is clipped).
    # Disable reporting-neutralization during precompute so we always get raw score + raw label.
    distilbert_raw_by_max_chars: dict[int, list[dict[str, Any]]] = {}
    os.environ["DISTILBERT_NEUTRALIZE_REPORTING"] = "0"
    os.environ["DISTILBERT_NEUTRAL_MIN_CONF"] = "0.0"
    for mc in max_chars:
        os.environ["DISTILBERT_MAX_CHARS"] = str(mc)
        arr: list[dict[str, Any]] = []
        for i, text in enumerate(texts, start=1):
            _, _, _, meta = analyze_sentiment_distilbert_detailed(text)
            arr.append(
                {
                    "score_raw": float((meta or {}).get("transformer_score_raw") or 0.0),
                    "label_raw": str((meta or {}).get("label_unthresholded") or "neutral"),
                }
            )
            if i % 50 == 0:
                print(f"  DistilBERT precompute (max_chars={mc}): {i}/{len(texts)}")
        distilbert_raw_by_max_chars[int(mc)] = arr

    # ---- Phase 2: grid search in pure Python ----
    def vader_label_from_compound(compound: float, band: float) -> str:
        if abs(compound) < band:
            return "neutral"
        return "positive" if compound > 0 else "negative"

    scored: list[dict[str, Any]] = []
    total_trials = len(trials)
    for idx, tr in enumerate(trials, start=1):
        y_pred: list[str] = []

        if args.model == "vader":
            for comp in vader_compound:
                y_pred.append(vader_label_from_compound(comp, tr.vader_neutral_band))
        elif args.model == "distilbert":
            # Apply reporting-neutralization + confidence-to-neutral threshold on precomputed raw.
            raw = distilbert_raw_by_max_chars[int(tr.distilbert_max_chars)]
            for is_preface, raw_item in zip(looks_preface, raw):
                if tr.neutralize_reporting and is_preface:
                    # Conservative approximation: treat reporting-preface texts as neutral.
                    y_pred.append("neutral")
                    continue
                score_raw = float(raw_item["score_raw"])
                base = str(raw_item["label_raw"] or "neutral")
                if score_raw < tr.distilbert_neutral_min_conf:
                    y_pred.append("neutral")
                else:
                    y_pred.append(base)
        else:
            # Hybrid: route via tagalog signal OR reporting preface; then apply per-engine thresholds.
            raw = distilbert_raw_by_max_chars[int(tr.distilbert_max_chars)]
            for is_preface, ratio, comp, raw_item in zip(looks_preface, tag_sig_ratio, vader_compound, raw):
                if is_preface:
                    y_pred.append(vader_label_from_compound(comp, tr.vader_neutral_band))
                    continue
                if ratio >= tr.tagalog_threshold:
                    y_pred.append(vader_label_from_compound(comp, tr.vader_neutral_band))
                    continue
                score_raw = float(raw_item["score_raw"])
                base = str(raw_item["label_raw"] or "neutral")
                # Confidence-gated fallback to VADER (new hybrid behavior).
                if tr.hybrid_distilbert_route_min_conf > 0.0 and score_raw and score_raw < tr.hybrid_distilbert_route_min_conf:
                    y_pred.append(vader_label_from_compound(comp, tr.vader_neutral_band))
                    continue
                if score_raw < tr.distilbert_neutral_min_conf:
                    y_pred.append("neutral")
                else:
                    y_pred.append(base)

        m = _compute_metrics(y_true, y_pred)
        score = float(m[args.optimize])
        scored.append(
            {
                "trial": {
                    "TAGALOG_SIGNAL_THRESHOLD": tr.tagalog_threshold,
                    "VADER_NEUTRAL_BAND": tr.vader_neutral_band,
                    "DISTILBERT_NEUTRAL_MIN_CONF": tr.distilbert_neutral_min_conf,
                    "DISTILBERT_MAX_CHARS": tr.distilbert_max_chars,
                    "DISTILBERT_NEUTRALIZE_REPORTING": tr.neutralize_reporting,
                    "HYBRID_DISTILBERT_ROUTE_MIN_CONF": tr.hybrid_distilbert_route_min_conf,
                },
                "metrics": m,
                "score": score,
            }
        )

        if args.progress_every and idx % int(args.progress_every) == 0:
            best_so_far = max(scored, key=lambda x: float(x.get("score") or 0.0))
            print(f"Trials: {idx}/{total_trials} best_{args.optimize}={best_so_far['score']:.4f}")

    scored.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    top = scored[: max(1, int(args.top_k))]

    out_path = (BACKEND_ROOT / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ok": True,
                "input_csv": str(csv_path),
                "model": args.model,
                "optimize": args.optimize,
                "clean_text": clean_text,
                "grid_sizes": {
                    "tagalog_thresholds": len(tagalog_thresholds),
                    "vader_neutral_bands": len(vader_bands),
                    "distilbert_neutral_min_confs": len(neutral_confs),
                    "distilbert_max_chars": len(max_chars),
                    "distilbert_neutralize_reporting": len(neutralize_reporting),
                    "trials_total": len(trials),
                },
                "top": top,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    best = top[0]
    print("=== Tuning Results ===")
    print("Model:", args.model)
    print("Optimize:", args.optimize)
    print("Clean text:", "on" if clean_text else "off")
    print("Trials:", len(trials))
    print("Best score:", best["score"])
    print("Best trial env:")
    for k, v in (best["trial"] or {}).items():
        print(f"- {k}={v}")
    bm = best["metrics"]
    print(f"Best metrics: accuracy={bm['accuracy']:.3f} macro_f1={bm['macro_f1']:.3f}")
    print("Wrote:", out_path)


if __name__ == "__main__":
    main()
