"""
Generate precision / recall / F1 visualisation charts from the benchmark JSON.

Usage (from repo root):
    python backend/scripts/plot_benchmark_metrics.py
    python backend/scripts/plot_benchmark_metrics.py --out backend/reports/charts

Outputs (saved to --out directory):
    recall_by_class.png      – grouped bar chart, recall per sentiment class per model
    precision_by_class.png   – same for precision
    f1_by_class.png          – same for F1
    precision_recall_f1.png  – combined 3-panel figure (good for thesis)
"""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless – no display required
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_JSON = (
    REPO_ROOT
    / "backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.json"
)
DEFAULT_OUT = REPO_ROOT / "backend/reports/charts"

CLASSES = ["positive", "neutral", "negative"]
CLASS_LABELS = ["Positive", "Neutral", "Negative"]

MODEL_DISPLAY = {
    "vader": "VADER (PH-patched)",
    "distilbert": "DistilBERT",
    "hybrid": "Hybrid",
}

COLORS = {
    "vader": "#4C72B0",
    "distilbert": "#DD8452",
    "hybrid": "#55A868",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_model_metrics(json_path: Path) -> dict:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    models_raw = data.get("models", {})
    out = {}
    for model, info in models_raw.items():
        pc = info.get("per_class", {})
        out[model] = {
            cls: {
                "precision": pc.get(cls, {}).get("precision", 0.0),
                "recall":    pc.get(cls, {}).get("recall",    0.0),
                "f1":        pc.get(cls, {}).get("f1",        0.0),
            }
            for cls in CLASSES
        }
        out[model]["_accuracy"] = info.get("accuracy", 0.0)
        out[model]["_macro_f1"] = info.get("macro_f1", 0.0)
    return out


def _grouped_bar(
    ax,
    models: list,
    metric: str,
    metrics: dict,
    title: str,
    ylabel: str,
):
    n_models = len(models)
    n_classes = len(CLASSES)
    x = np.arange(n_classes)
    width = 0.22
    offsets = np.linspace(-(n_models - 1) / 2, (n_models - 1) / 2, n_models) * width

    for offset, model in zip(offsets, models):
        values = [metrics[model][cls][metric] for cls in CLASSES]
        bars = ax.bar(
            x + offset,
            values,
            width,
            label=MODEL_DISPLAY.get(model, model),
            color=COLORS.get(model, "#999999"),
            edgecolor="white",
            linewidth=0.6,
        )
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.015,
                f"{val:.2f}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                fontweight="bold",
            )

    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_ylim(0, 1.12)
    ax.set_xticks(x)
    ax.set_xticklabels(CLASS_LABELS, fontsize=10)
    ax.legend(fontsize=9, loc="upper right")
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


# ---------------------------------------------------------------------------
# Single-metric charts
# ---------------------------------------------------------------------------

def plot_single(metric: str, title: str, ylabel: str, metrics: dict, out_dir: Path):
    models = list(metrics.keys())
    fig, ax = plt.subplots(figsize=(8, 5))
    _grouped_bar(ax, models, metric, metrics, title, ylabel)
    fig.tight_layout()
    path = out_dir / f"{metric}_by_class.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Combined 3-panel figure (the one to put in the thesis)
# ---------------------------------------------------------------------------

def plot_combined(metrics: dict, out_dir: Path):
    models = list(metrics.keys())
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))
    fig.suptitle(
        "Sentiment Classification – Precision, Recall & F1 by Class",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )

    _grouped_bar(axes[0], models, "precision", metrics, "Precision", "Precision")
    _grouped_bar(axes[1], models, "recall",    metrics, "Recall",    "Recall")
    _grouped_bar(axes[2], models, "f1",        metrics, "F1-Score",  "F1-Score")

    # Shared legend below the figure
    handles = [
        mpatches.Patch(color=COLORS.get(m, "#999"), label=MODEL_DISPLAY.get(m, m))
        for m in models
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=len(models),
        fontsize=10,
        bbox_to_anchor=(0.5, -0.06),
        frameon=False,
    )

    fig.tight_layout()
    path = out_dir / "precision_recall_f1.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Accuracy summary bar (bonus – shows overall accuracy side by side)
# ---------------------------------------------------------------------------

def plot_accuracy_summary(metrics: dict, out_dir: Path):
    models = list(metrics.keys())
    accuracies = [metrics[m]["_accuracy"] for m in models]
    macro_f1s  = [metrics[m]["_macro_f1"]  for m in models]

    x = np.arange(len(models))
    width = 0.35
    fig, ax = plt.subplots(figsize=(7, 4.5))

    b1 = ax.bar(x - width / 2, accuracies, width, label="Accuracy",
                color="#4C72B0", edgecolor="white")
    b2 = ax.bar(x + width / 2, macro_f1s,  width, label="Macro-F1",
                color="#55A868", edgecolor="white")

    for bars in (b1, b2):
        for bar in bars:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.012,
                f"{bar.get_height():.3f}",
                ha="center", va="bottom", fontsize=9, fontweight="bold",
            )

    ax.set_title("Overall Accuracy & Macro-F1 per Model", fontsize=13,
                 fontweight="bold", pad=10)
    ax.set_ylabel("Score", fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_DISPLAY.get(m, m) for m in models], fontsize=10)
    ax.legend(fontsize=9)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    path = out_dir / "accuracy_summary.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Plot benchmark precision/recall/F1 charts")
    parser.add_argument(
        "--json",
        default=str(DEFAULT_JSON),
        help="Path to benchmark JSON (default: latest benchmark report)",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Output directory for PNG files",
    )
    args = parser.parse_args()

    json_path = Path(args.json)
    out_dir   = Path(args.out)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON not found: {json_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = load_model_metrics(json_path)

    print(f"Models found: {list(metrics.keys())}")

    plot_single("recall",    "Recall by Sentiment Class",    "Recall",    metrics, out_dir)
    plot_single("precision", "Precision by Sentiment Class", "Precision", metrics, out_dir)
    plot_single("f1",        "F1-Score by Sentiment Class",  "F1-Score",  metrics, out_dir)
    plot_combined(metrics, out_dir)
    plot_accuracy_summary(metrics, out_dir)

    print("\nAll charts saved to:", out_dir)


if __name__ == "__main__":
    main()
