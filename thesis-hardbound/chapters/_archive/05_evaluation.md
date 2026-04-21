# Evaluation

This chapter evaluates the sentiment engine using two complementary strategies:
1. a small offline “gold” set designed for Taglish/Tagalog edge cases, and
2. a drift analysis on real collected news articles to measure how model changes affect production-like data.

The goal is not to claim perfect “ground truth” sentiment for news, but to provide thesis-defensible evidence that (a) the hybrid design improves robustness on code-switched text, and (b) model behavior changes are measurable, explainable, and reproducible.

## Benchmark Evaluation of the Sentiment Engine (Adapted from `hybrid.tex`)

This section adapts the benchmark reporting from the updated ACM artifact (`thesis latex/ACM_Hypertext_Conference_Template/hybrid.tex`). For the hardbound thesis:
- the dataset definitions and metrics are kept consistent, and
- the tables can be regenerated later if the lexicon patch or gold sets are updated.

## Evaluation Assets

### Offline Gold Set (Taglish/Tagalog Mini Dataset)

The project includes a hand-labeled gold set in:
- `backend/app/ml/vader_ph_eval.v1.json`

This file contains short Taglish/Tagalog sentences with expected labels:
`positive`, `neutral`, or `negative`. The dataset intentionally includes edge cases such as:
- Tagalog negation (“hindi”, “wala”, “huwag”),
- contrast constructions (“pero”, “ngunit”, “subalit”),
- common PH news tokens (crime/disaster/governance terms),
- mixed English + Tagalog phrasing typical of headlines and short descriptions.

As reported in `hybrid.tex`, the Taglish gold set has:
- $n=130$ items
- class distribution: 26 positive, 42 neutral, 62 negative

### Lexicon Patch Artifact (Versioned)

The PH VADER patch is stored in:
- `backend/app/ml/vader_ph_lexicon.v1.json`

It is versioned and applied deterministically. Patch status fields (version, enabled/applied, counts) are recorded in `model_metadata` so results can be traced to a specific patch version and configuration.

### English-Only Gold Set for the Transformer Baseline

To document DistilBERT behavior on formal English text (and to explicitly acknowledge that SST-2 is not trained with a neutral class), the project also includes:
- `backend/app/ml/distilbert_en_gold.v1.json` ($n=94$)

## Gold Set Evaluation Procedure

### Script and Modes

The gold set is evaluated using:
- `backend/scripts/evaluate_vader_ph_gold.py`

The script can evaluate:
- VADER (`--model vader`),
- DistilBERT SST-2 (`--model distilbert`),
- Hybrid router (`--model hybrid`).

It reports:
- overall accuracy,
- label distributions,
- confusion breakdown (true → predicted),
- and a list of the most informative misclassified examples.

### Parameter Sweeps (Thesis-Defensible Tuning)

To evaluate threshold and routing choices without code changes, the script supports runtime overrides:
- `--vader-neutral-band` → sets `VADER_NEUTRAL_BAND`
- `--tagalog-signal-threshold` → sets `TAGALOG_SIGNAL_THRESHOLD`
- `--distilbert-neutral-min-conf` → sets `DISTILBERT_NEUTRAL_MIN_CONF`

This allows controlled experiments such as widening the neutral band to reduce borderline false positives in factual news text.

## Reported Benchmark Results (from `hybrid.tex`)

### PH Patch Validation on the Taglish Gold Set (VADER)

The first benchmark isolates the impact of the PH lexicon/phrase patch on VADER using `backend/app/ml/vader_ph_eval.v1.json` ($n=130$).

Table 1: VADER patch validation on the Tagalog/Taglish gold set ($n=130$).

| Setting | Accuracy | Macro-F1 | F1 (Pos) | F1 (Neu) | F1 (Neg) |
|---|---:|---:|---:|---:|---:|
| VADER (patch off) | 0.369 | 0.350 | 0.435 | 0.441 | 0.174 |
| VADER + PH patch (on) | 0.908 | 0.905 | 0.943 | 0.838 | 0.932 |

Interpretation: baseline English VADER collapses toward the neutral class on Taglish/Tagalog inputs it does not recognize, while the PH patch restores three-class performance by adding locally frequent sentiment terms and phrase tokens.

### DistilBERT SST-2 on an English-Only Gold Set

Table 2 reports DistilBERT SST-2 on `backend/app/ml/distilbert_en_gold.v1.json` ($n=94$) as described in `hybrid.tex`. Under the baseline configuration used for this table, `DISTILBERT_NEUTRAL_MIN_CONF = 0.0`, so the neutral prediction rate is expected to be 0.000 (every input must be mapped to positive or negative).

Table 2: DistilBERT SST-2 on English-only gold set ($n=94$; binary positive vs. negative).

| Model | Accuracy | Macro-F1 (Pos/Neg) | Neutral-pred rate |
|---|---:|---:|---:|
| DistilBERT (SST-2) | 0.755 | 0.755 | 0.000 |

### Manual Benchmark on Real News Articles (3-Class)

To evaluate the end-to-end system on real collected articles, `hybrid.tex` reports a manual benchmark drawn from the seven-day observation window (2026-03-25 to 2026-03-31). A stratified sample of $n=200$ articles was labeled across seven outlets (ABS-CBN, GMA, Inquirer, Manila Bulletin, Manila Times, Philstar, Rappler), excluding SunStar due to frequent regional-language content.

Two annotators labeled each sampled article into three classes (positive, neutral, negative) based on overall news tone. Inter-annotator agreement was measured using Cohen’s kappa [@cohen1960kappa], and adjudication produced final labels with $\kappa=0.742$.

Table 3: Manual benchmark results on $n=200$ labeled news articles (3-class: Pos, Neu, Neg).

| Model | Accuracy | Macro-F1 | F1 (Pos) | F1 (Neu) | F1 (Neg) |
|---|---:|---:|---:|---:|---:|
| VADER + PH patch | 0.652 | 0.612 | 0.720 | 0.380 | 0.685 |
| DistilBERT (SST-2)\* | 0.625 | 0.535 | 0.745 | 0.160 | 0.700 |
| Hybrid router | **0.725** | **0.701** | **0.781** | **0.485** | **0.794** |

\* Utilizes confidence-based neutralization (`DISTILBERT_NEUTRAL_MIN_CONF = 0.60`).

### Manual Benchmark (Binary Subset)

Because SST-2 is trained as a binary classifier, `hybrid.tex` also reports a binary-only evaluation by excluding neutral ground-truth items.

Table 4: Binary benchmark results excluding neutral ground-truth.

| Model | Accuracy | Macro-F1 | Neutral-pred rate |
|---|---:|---:|---:|
| VADER + PH patch | 0.738 | 0.731 | 0.110 |
| DistilBERT (SST-2) | 0.793 | 0.802 | 0.045 |
| Hybrid router | **0.848** | **0.861** | 0.055 |

### Interpretation: The “Neutral Gap” in News

The manual benchmark highlights a neutral-handling gap for binary transformer models when applied to news text. Standalone DistilBERT achieves a low neutral F1 (0.160) in the 3-class benchmark because “neutral” is only produced indirectly via confidence thresholding. In contrast, the VADER path supports an explicit neutral band (e.g., `VADER_NEUTRAL_BAND=0.16`), improving neutral sensitivity.

The hybrid router combines:
- Tagalog-aware routing (to avoid applying an English-first model to Taglish-heavy inputs), and
- an abstention mechanism (confidence-based neutralization),
producing the best overall 3-class benchmark performance reported in `hybrid.tex`.

## Interpretation and Neutral Analysis (Expanded)

The benchmark results show a consistent pattern: “neutral” is the hardest class to model in a news domain. This is largely because many articles are written in an objective reporting style (e.g., dateline updates, announcements, and procedural reporting), where sentiment is present only implicitly. In this setting, a binary sentiment model tends to over-polarize unless an explicit abstention rule is introduced.

In the reported manual benchmark, the standalone DistilBERT SST-2 configuration attains a low neutral F1 ($\mathrm{F1}_{\mathrm{neu}} = 0.160$). This is expected because SST-2 is trained for binary polarity (positive vs. negative) rather than three-class sentiment. “Neutral” predictions in the system are therefore produced only by confidence-based thresholding (`DISTILBERT_NEUTRAL_MIN_CONF`) and optional neutralization of reporting-style prefaces, rather than by a learned neutral class.

By comparison, the rule-based VADER pathway can model neutrality explicitly via a configurable neutral band (`VADER_NEUTRAL_BAND`). With a wider neutral band (e.g., 0.16), the system can reduce false positives/negatives on borderline, factual statements. This explains why VADER+PH patch reaches a higher neutral F1 ($\mathrm{F1}_{\mathrm{neu}} = 0.380$) than the standalone transformer in the reported benchmark.

The hybrid router combines these complementary behaviors and produces the best overall three-class performance (accuracy 0.725; neutral F1 0.485) by:
- routing Taglish-heavy or linguistically ambiguous text through the PH-extended VADER pathway, and
- allowing the transformer pathway to abstain (neutralize) under low confidence rather than forcing a polar label.

In the binary-only subset (where neutral ground truth is removed), the hybrid model achieves the highest macro-F1 (0.861). The non-zero neutral prediction rate in this binary view reflects the system’s deliberate abstention design: it outputs neutral when confidence thresholds are not satisfied, prioritizing precision over forced polarity.

## Real-World News Complexity and Model Limitations (Evaluation Perspective)

The gap between controlled gold-set performance and the manual news benchmark highlights the difficulty of sentiment labeling for real articles. Unlike sentence-level benchmarks, full articles contain longer context, mixed language (Taglish), and a high proportion of objective reporting. These properties introduce ambiguity that increases annotation difficulty and makes “neutral” detection especially challenging.

Additionally, DistilBERT SST-2 is optimized for binary polarity classification, and its neutral behavior in this project is derived from confidence thresholding rather than explicit training. The VADER component, while more transparent and tunable, depends on the completeness of the PH lexicon patch and may miss emerging slang or domain-specific polarity shifts.

Finally, the hybrid router is heuristic: it can misroute highly mixed-language items, and it does not explicitly model languages beyond English and Tagalog (e.g., Cebuano). These limitations motivate (a) continued lexicon expansion, (b) multilingual transformer upgrades, and (c) drift monitoring on real news (next section) to ensure changes remain explainable and operationally stable.

## Real-News Drift Evaluation (Production-Like Behavior)

Gold sets are necessary but small; they cannot capture the full diversity of real news. Therefore, the project also uses a drift evaluation on real stored articles:
- `backend/scripts/evaluate_vader_longform.py`

This script samples recent articles from the `articles` table and compares:
- **Legacy baseline:** single-pass VADER over full concatenated text
vs.
- **New path:** one of `{vader, distilbert, hybrid}` (selected by `--model`)

It reports:
- mean score drift and mean absolute delta,
- label distribution shifts,
- percent of changed labels,
- and the top changed examples (largest score deltas) to support qualitative inspection.

This “drift” perspective is important for system safety: a sentiment update that improves gold-set accuracy might still cause unexpected flips across real news if it overreacts to domain-specific phrases.

## Benchmark Sampling and Manual Labeling Protocol

For reproducibility and qualitative analysis, the repo includes:
- a labeling protocol: `docs/sentiment_benchmark_labeling.md`
- example benchmark sample CSV(s): `backend/reports/benchmark_sample_*.csv`

These assets support manual review and make evaluation steps auditable for a hardbound thesis.

## What We Benchmark (and Why)

The evaluation benchmarks three properties:
1. **Taglish robustness:** Does the model handle Tagalog/Taglish cues (negation, contrast, slang, PH news tokens) better than English-only baselines?
2. **Neutral handling:** Does it avoid over-polarizing factual reporting language common in news?
3. **Operational stability:** Do parameter changes (lexicon patch, neutral band, routing threshold) produce measurable but explainable drift instead of chaotic label flips?

## Reproducible Commands (Docker)

The scripts are designed to run inside the Docker environment used by the ML worker. Example commands (adjust to your deployment setup):

```bash
# Gold set (hybrid)
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_ph_gold.py --model hybrid --ph-patch on"

# Real-news drift (last 7 days; compare baseline vs hybrid)
docker compose exec worker_ml sh -lc "cd /app/backend && python scripts/evaluate_vader_longform.py --days 7 --limit 300 --model hybrid --ph-patch on"
```

When operating in offline mode for Hugging Face model loading, set:
`HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, and ensure the model is present in the configured HF cache directory (see `thesis-hardbound/SYSTEM_FACTS.md`).

## Limitations of the Evaluation

Sentiment for news is inherently ambiguous: news writing includes factual reporting, irony, and culturally specific framing. The gold set is small and cannot represent all domains; DistilBERT SST-2 is trained on general sentiment (reviews) and may misinterpret domain-specific news language; and the hybrid router can misroute heavily mixed-language articles. These limitations are mitigated through transparent metadata logging, parameterized evaluation scripts, and drift-based sanity checks on real news data.
