#!/usr/bin/env python3
"""
Evaluate sentiment models on a manually labeled benchmark CSV.

Expected CSV columns:
  - title, content
  - label_a, label_b, label_final

Optional columns (kept/ignored):
  - article_id, source, published_at, url, tagalog_signal_ratio, ...

Usage:
  cd backend
  python scripts/evaluate_sentiment_benchmark.py --file reports/benchmark_sample_2026-03-25_2026-03-31.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sklearn.metrics import (
    accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

LABELS = ["positive", "neutral", "negative"]


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


def _latex_escape(s: str) -> str:
    return (
        (s or "")
        .replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _make_latex_table(metrics: dict[str, Any]) -> str:
    rows = []
    for model in ("vader", "distilbert", "hybrid"):
        m = metrics.get("models", {}).get(model) or {}
        acc = _safe_float(m.get("accuracy"))
        macro_f1 = _safe_float(m.get("macro_f1"))
        per = m.get("per_class") or {}
        f1_pos = _safe_float((per.get("positive") or {}).get("f1"))
        f1_neu = _safe_float((per.get("neutral") or {}).get("f1"))
        f1_neg = _safe_float((per.get("negative") or {}).get("f1"))
        rows.append((model, acc, macro_f1, f1_pos, f1_neu, f1_neg))

    lines = []
    lines.append("\\begin{table}[h]")
    lines.append("\\caption{Manual benchmark results (overall tone classification).}")
    lines.append("\\label{tab:benchmark}")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\begin{tabular}{lrrrrr}")
    lines.append("\\toprule")
    lines.append("Model & Accuracy & Macro-F1 & F1 (Pos) & F1 (Neu) & F1 (Neg) \\\\")
    lines.append("\\midrule")
    for model, acc, macro_f1, f1_pos, f1_neu, f1_neg in rows:
        name = {"vader": "VADER+PH", "distilbert": "DistilBERT", "hybrid": "Hybrid"}.get(model, model)
        lines.append(f"{_latex_escape(name)} & {acc:.3f} & {macro_f1:.3f} & {f1_pos:.3f} & {f1_neu:.3f} & {f1_neg:.3f} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def _make_latex_table_binary(metrics: dict[str, Any]) -> str:
    """
    Binary subset table (exclude neutral ground-truth rows).
    """
    rows = []
    for model in ("vader", "distilbert", "hybrid"):
        b = (metrics.get("binary_subset") or {}).get(model) or {}
        if not b.get("ok"):
            continue
        rows.append((model, _safe_float(b.get("accuracy")), _safe_float(b.get("macro_f1")), _safe_float(b.get("neutral_pred_rate"))))

    lines = []
    lines.append("\\begin{table}[h]")
    lines.append("\\caption{Binary benchmark results excluding neutral ground-truth (positive vs. negative).}")
    lines.append("\\label{tab:benchmark-binary}")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\begin{tabular}{lrrr}")
    lines.append("\\toprule")
    lines.append("Model & Accuracy & Macro-F1 & Neutral-pred rate \\\\")
    lines.append("\\midrule")
    for model, acc, macro_f1, neu_rate in rows:
        name = {"vader": "VADER+PH", "distilbert": "DistilBERT", "hybrid": "Hybrid"}.get(model, model)
        lines.append(f"{_latex_escape(name)} & {acc:.3f} & {macro_f1:.3f} & {neu_rate:.3f} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)

def _compute_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    acc = accuracy_score(y_true, y_pred)
    pr, rc, f1, sup = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=LABELS,
        zero_division=0,
    )
    macro_f1 = float(sum(f1) / len(f1)) if f1 is not None and len(f1) else 0.0
    cm = confusion_matrix(y_true, y_pred, labels=LABELS).tolist()
    per_class = {}
    for i, lab in enumerate(LABELS):
        per_class[lab] = {
            "precision": float(pr[i]),
            "recall": float(rc[i]),
            "f1": float(f1[i]),
            "support": int(sup[i]),
        }
    return {
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "per_class": per_class,
        "confusion_matrix_labels": LABELS,
        "confusion_matrix": cm,
    }


def _compute_binary_subset_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    """
    Binary evaluation on the subset where ground truth is clearly valenced:
    keep only rows with y_true in {positive, negative}. Neutral predictions are treated as errors.

    We also report a 2x3 confusion matrix (true: pos/neg; pred: pos/neg/neu) to
    make "neutral-as-abstain" behavior visible.
    """
    keep_idx = [i for i, t in enumerate(y_true) if t in {"positive", "negative"}]
    if not keep_idx:
        return {"ok": False, "n": 0}

    yt = [y_true[i] for i in keep_idx]
    yp = [y_pred[i] for i in keep_idx]

    labels_bin = ["positive", "negative"]
    acc = accuracy_score(yt, yp)
    pr, rc, f1, sup = precision_recall_fscore_support(
        yt,
        yp,
        labels=labels_bin,
        zero_division=0,
    )
    macro_f1 = float(sum(f1) / len(f1)) if f1 is not None and len(f1) else 0.0

    # Manual 2x3 confusion: rows=true(pos/neg), cols=pred(pos/neg/neu/other)
    cols = ["positive", "negative", "neutral", "other"]
    cm = [[0, 0, 0, 0], [0, 0, 0, 0]]
    for t, p in zip(yt, yp):
        r = 0 if t == "positive" else 1
        if p == "positive":
            c = 0
        elif p == "negative":
            c = 1
        elif p == "neutral":
            c = 2
        else:
            c = 3
        cm[r][c] += 1

    per_class = {}
    for i, lab in enumerate(labels_bin):
        per_class[lab] = {
            "precision": float(pr[i]),
            "recall": float(rc[i]),
            "f1": float(f1[i]),
            "support": int(sup[i]),
        }

    neutral_pred_rate = float(sum(1 for p in yp if p == "neutral") / len(yp))
    other_pred_rate = float(sum(1 for p in yp if p not in {"positive", "negative", "neutral"}) / len(yp))

    return {
        "ok": True,
        "n": len(yt),
        "labels_true": labels_bin,
        "labels_pred": cols,
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "per_class": per_class,
        "confusion_matrix": cm,
        "neutral_pred_rate": neutral_pred_rate,
        "other_pred_rate": other_pred_rate,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate sentiment models on a manual benchmark CSV.")
    parser.add_argument(
        "--file",
        default=str(BACKEND_ROOT / "reports" / "benchmark_sample_2026-03-25_2026-03-31.csv"),
        help="Path to labeled CSV.",
    )
    parser.add_argument(
        "--clean-text",
        choices=["on", "off"],
        default="on",
        help="Apply conservative scraper-noise cleaning before model inference (default: on).",
    )
    parser.add_argument(
        "--exclude-noisy",
        choices=["on", "off"],
        default="off",
        help="Exclude clearly scraper-broken rows (empty/boilerplate/concatenated) from evaluation (default: off).",
    )
    parser.add_argument(
        "--models",
        default="vader,distilbert,hybrid",
        help="Comma-separated models to evaluate: vader, distilbert, hybrid.",
    )
    parser.add_argument(
        "--ph-patch",
        choices=["on", "off"],
        default="on",
        help="Enable Taglish VADER patch for evaluation (default: on).",
    )
    parser.add_argument(
        "--out",
        default=str(BACKEND_ROOT / "reports" / "sentiment_benchmark_2026-03-25_2026-03-31.json"),
        help="Output JSON path.",
    )
    args = parser.parse_args()

    csv_path = Path(args.file)
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    models = [m.strip().lower() for m in (args.models or "").split(",") if m.strip()]
    unknown = [m for m in models if m not in {"vader", "distilbert", "hybrid"}]
    if unknown:
        raise SystemExit(f"Unknown model(s): {unknown}")

    if args.ph_patch == "on":
        os.environ["VADER_PH_PATCH"] = "1"
    else:
        os.environ["VADER_PH_PATCH"] = "0"

    clean_text = args.clean_text == "on"
    exclude_noisy = args.exclude_noisy == "on"

    # Record key runtime settings for reproducibility (especially when running outside worker_ml).
    runtime_settings = {
        "VADER_PH_PATCH": os.getenv("VADER_PH_PATCH"),
        "VADER_NEUTRAL_BAND": os.getenv("VADER_NEUTRAL_BAND"),
        "TAGALOG_SIGNAL_THRESHOLD": os.getenv("TAGALOG_SIGNAL_THRESHOLD"),
        "HYBRID_STRATEGY": os.getenv("HYBRID_STRATEGY"),
        "HYBRID_DISTILBERT_ROUTE_MIN_CONF": os.getenv("HYBRID_DISTILBERT_ROUTE_MIN_CONF"),
        "HYBRID_VADER_GATE_NEUTRAL_BAND": os.getenv("HYBRID_VADER_GATE_NEUTRAL_BAND"),
        "HYBRID_V2_OVERRIDE_MIN_CONF": os.getenv("HYBRID_V2_OVERRIDE_MIN_CONF"),
        "DISTILBERT_MODEL_ID": os.getenv("DISTILBERT_MODEL_ID"),
        "DISTILBERT_MAX_LENGTH": os.getenv("DISTILBERT_MAX_LENGTH"),
        "DISTILBERT_MAX_CHARS": os.getenv("DISTILBERT_MAX_CHARS"),
        "DISTILBERT_NEUTRAL_MIN_CONF": os.getenv("DISTILBERT_NEUTRAL_MIN_CONF"),
        "DISTILBERT_NEUTRALIZE_REPORTING": os.getenv("DISTILBERT_NEUTRALIZE_REPORTING"),
        "DISTILBERT_TEXT_NORMALIZE": os.getenv("DISTILBERT_TEXT_NORMALIZE"),
        "DISTILBERT_NORMALIZE_PRESERVE_NEWLINES": os.getenv("DISTILBERT_NORMALIZE_PRESERVE_NEWLINES"),
        "TRANSFORMER_LABEL_MAP": os.getenv("TRANSFORMER_LABEL_MAP"),
        "HF_HOME": os.getenv("HF_HOME"),
        "TRANSFORMERS_CACHE": os.getenv("TRANSFORMERS_CACHE"),
        "HF_HUB_CACHE": os.getenv("HF_HUB_CACHE"),
        "BENCHMARK_TEXT_CLEAN": "on" if clean_text else "off",
        "BENCHMARK_EXCLUDE_NOISY": "on" if exclude_noisy else "off",
    }

    from app.ml.bias import (  # noqa: WPS433
        analyze_sentiment_distilbert_detailed,
        analyze_sentiment_hybrid_detailed,
        analyze_sentiment_vader_detailed,
    )
    from app.core.text_clean import clean_scraped_news_text  # noqa: WPS433

    items: list[dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            items.append(dict(row))

    if not items:
        raise SystemExit("CSV is empty.")

    # Agreement (kappa) over rows that have both label_a and label_b.
    a_labels: list[str] = []
    b_labels: list[str] = []
    for it in items:
        la = _norm_label(it.get("label_a", ""))
        lb = _norm_label(it.get("label_b", ""))
        if la and lb:
            a_labels.append(la)
            b_labels.append(lb)
    kappa = float(cohen_kappa_score(a_labels, b_labels, labels=LABELS)) if a_labels else None

    # Simple human baselines vs final labels (not a "ground truth", but useful ceiling context).
    human_a_true: list[str] = []
    human_a_pred: list[str] = []
    human_b_true: list[str] = []
    human_b_pred: list[str] = []
    agree_true: list[str] = []
    agree_pred: list[str] = []
    for it in items:
        la = _norm_label(it.get("label_a", ""))
        lb = _norm_label(it.get("label_b", ""))
        lf = _norm_label(it.get("label_final", ""))
        if lf and la:
            human_a_true.append(lf)
            human_a_pred.append(la)
        if lf and lb:
            human_b_true.append(lf)
            human_b_pred.append(lb)
        if lf and la and lb and la == lb:
            agree_true.append(lf)
            agree_pred.append(la)

    # Final labels (required for model evaluation).
    y_true: list[str] = []
    texts: list[str] = []
    meta_rows: list[dict[str, Any]] = []
    skipped = 0
    excluded_noisy = 0
    clean_totals = Counter()
    for it in items:
        lf = _norm_label(it.get("label_final", ""))
        title = str(it.get("title") or "").strip()
        content = str(it.get("content") or "").strip()
        if not lf or not (title or content):
            skipped += 1
            continue
        y_true.append(lf)
        raw_text = f"{title}\n\n{content}".strip()
        if clean_text:
            cleaned_text, meta = clean_scraped_news_text(raw_text, enabled=True)
            is_noisy = (
                (meta.input_len == 0)
                or (meta.output_len < 200)
                or bool(meta.truncated_at_second_dateline)
                or bool(meta.truncated_on_repeat_prefix)
                or bool(meta.truncated_at_inquirer_marker)
            )
            if exclude_noisy and is_noisy:
                excluded_noisy += 1
                # Undo the earlier append to y_true since we are skipping this row.
                y_true.pop()
                continue
            texts.append(cleaned_text)
            clean_totals["removed_read_links"] += int(meta.removed_read_links)
            clean_totals["removed_boilerplate_paragraphs"] += int(meta.removed_boilerplate_paragraphs)
            clean_totals["removed_duplicate_paragraphs"] += int(meta.removed_duplicate_paragraphs)
            clean_totals["truncated_at_second_dateline"] += int(bool(meta.truncated_at_second_dateline))
            clean_totals["truncated_on_repeat_prefix"] += int(bool(meta.truncated_on_repeat_prefix))
            clean_totals["truncated_at_inquirer_marker"] += int(bool(meta.truncated_at_inquirer_marker))
        else:
            texts.append(raw_text)
        meta_rows.append(
            {
                "article_id": it.get("article_id"),
                "source": it.get("source"),
                "published_at": it.get("published_at"),
                "url": it.get("url"),
            }
        )

    if not y_true:
        raise SystemExit("No usable rows: ensure label_final is filled and title/content are present.")

    results: dict[str, Any] = {
        "ok": True,
        "input_csv": str(csv_path),
        "items_total": len(items),
        "items_used": len(y_true),
        "items_skipped": skipped,
        "items_excluded_noisy": excluded_noisy,
        "label_set": LABELS,
        "kappa": kappa,
        "kappa_n": len(a_labels),
        "human_baselines": {
            "annotator_a_vs_final": _compute_metrics(human_a_true, human_a_pred) if human_a_true else None,
            "annotator_b_vs_final": _compute_metrics(human_b_true, human_b_pred) if human_b_true else None,
            "agreement_subset_n": len(agree_true),
            "agreement_subset_vs_final": _compute_metrics(agree_true, agree_pred) if agree_true else None,
        },
        "runtime_settings": runtime_settings,
        "text_cleaning_summary": dict(clean_totals) if clean_text else None,
        "models": {},
    }

    # Evaluate models.
    route_counts = Counter()
    route_correct = defaultdict(int)
    route_total = defaultdict(int)
    preds_by_model: dict[str, list[str]] = {}

    for model in models:
        y_pred: list[str] = []
        for text, true_lab in zip(texts, y_true):
            if model == "vader":
                _, pred, _, _ = analyze_sentiment_vader_detailed(text)
                y_pred.append(pred)
            elif model == "distilbert":
                _, pred, _, _ = analyze_sentiment_distilbert_detailed(text)
                y_pred.append(pred)
            else:
                _, pred, _, meta = analyze_sentiment_hybrid_detailed(text)
                y_pred.append(pred)
                route = str((meta or {}).get("route") or "")
                if route:
                    route_counts[route] += 1
                    route_total[route] += 1
                    if pred == true_lab:
                        route_correct[route] += 1

        preds_by_model[model] = y_pred
        results["models"][model] = _compute_metrics(y_true, y_pred)

    if "hybrid" in models:
        results["hybrid_routes"] = {
            "counts": dict(route_counts),
            "accuracy_by_route": {
                r: (route_correct[r] / route_total[r]) if route_total[r] else None for r in route_total
            },
        }

    # Binary subset (exclude neutral ground truth) for SST-2-aligned comparability.
    results["binary_subset"] = {m: _compute_binary_subset_metrics(y_true, preds_by_model[m]) for m in models}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("=== Manual Benchmark Report ===")
    print(f"Input: {csv_path}")
    print(f"Used: {len(y_true)} / {len(items)} (skipped={skipped})")
    print("Runtime settings:", {k: v for k, v in runtime_settings.items() if v})
    if clean_text:
        print("Text cleaning summary:", dict(clean_totals))
    if kappa is not None:
        print(f"Cohen's kappa: {kappa:.3f} (n={len(a_labels)})")
    else:
        print("Cohen's kappa: N/A (label_a/label_b not filled)")
    print()

    hb = results.get("human_baselines") or {}
    if hb.get("annotator_a_vs_final"):
        ha = hb["annotator_a_vs_final"]
        print(f"[human_a] accuracy={ha['accuracy']:.3f} macro_f1={ha['macro_f1']:.3f} (vs label_final)")
    if hb.get("annotator_b_vs_final"):
        hb2 = hb["annotator_b_vs_final"]
        print(f"[human_b] accuracy={hb2['accuracy']:.3f} macro_f1={hb2['macro_f1']:.3f} (vs label_final)")
    if hb.get("agreement_subset_vs_final"):
        hs = hb["agreement_subset_vs_final"]
        print(f"[human_agree_subset] n={hb.get('agreement_subset_n')} accuracy={hs['accuracy']:.3f} macro_f1={hs['macro_f1']:.3f} (where label_a==label_b)")
    print()

    for model in models:
        m = results["models"][model]
        print(f"[{model}] accuracy={m['accuracy']:.3f} macro_f1={m['macro_f1']:.3f}")
        cm = m["confusion_matrix"]
        print("Confusion (rows=true, cols=pred; order: positive, neutral, negative):")
        for row in cm:
            print("  " + " ".join(f"{int(x):4d}" for x in row))
        print()

    if "hybrid" in models and route_counts:
        print("Hybrid route counts:", dict(route_counts))
        print("Hybrid accuracy by route:", results.get("hybrid_routes", {}).get("accuracy_by_route"))
        print()

    print("=== Binary Subset (Pos/Neg only; neutral GT excluded) ===")
    for model in models:
        b = (results.get("binary_subset") or {}).get(model) or {}
        if not b.get("ok"):
            print(f"[{model}] N/A")
            continue
        print(
            f"[{model}] n={b['n']} accuracy={b['accuracy']:.3f} macro_f1={b['macro_f1']:.3f} "
            f"(neutral_pred_rate={b['neutral_pred_rate']:.3f})"
        )
        print("Confusion (rows=true pos/neg; cols=pred pos,neg,neu,other):")
        for row in b["confusion_matrix"]:
            print("  " + " ".join(f"{int(x):4d}" for x in row))
        print()

    print(f"Wrote JSON: {out_path}")
    print()
    print("=== LaTeX Table (copy/paste) ===")
    print(_make_latex_table(results))
    print()
    print("=== LaTeX Table (Binary subset; copy/paste) ===")
    print(_make_latex_table_binary(results))


if __name__ == "__main__":
    main()
