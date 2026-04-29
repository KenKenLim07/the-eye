# Appendix D — Evaluation Tools and Test Documents

This appendix lists the evaluation scripts, datasets, and documentation used to benchmark the sentiment models and to support reproducibility of the reported results.

## Evaluation datasets (inputs)

**Gold sets (offline):**
- `backend/app/ml/vader_ph_eval.v1.json` — Taglish/Tagalog gold set ($n=130$, 3-class).
- `backend/app/ml/distilbert_en_gold.v1.json` — English-only gold set ($n=94$, binary).

**Manual benchmark sample (real news CSV):**
- `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv` — stratified sample exported from the database with labeling columns (`label_a`, `label_b`, `label_final`) and model-output columns.

**Labeling protocol document:**
- `docs/sentiment_benchmark_labeling.md` — annotation instructions, definitions, and adjudication guidance.

## Evaluation scripts (tools)

**Gold-set evaluator:**
- `backend/scripts/evaluate_vader_ph_gold.py`
  - evaluates `--model {vader,distilbert,hybrid}`
  - supports threshold overrides (`--vader-neutral-band`, `--tagalog-signal-threshold`, `--distilbert-neutral-min-conf`)

**Manual benchmark evaluator (real-news, end-to-end):**
- `backend/scripts/evaluate_sentiment_benchmark.py`
  - reads labeled benchmark CSV
  - computes accuracy, macro-F1, per-class metrics, confusion matrices, and hybrid routing summaries
  - emits a JSON report used for Chapter 5 tables

**Drift checker (real articles):**
- `backend/scripts/evaluate_vader_longform.py`
  - compares an old baseline path vs a selected new path on sampled recent articles
  - reports label drift %, score drift, and most-changed examples for audit

**Benchmark sample export tool:**
- `backend/scripts/export_sentiment_benchmark_sample.py`
  - exports a stratified real-news sample from Supabase for the specified observation window

## Supporting evaluation documentation

The following documents provide step-by-step run commands and interpretation notes:
- `docs/ACCURACY_EVALUATION.md`
- `docs/FINAL_ACCURACY_EVALUATION.md`

## Evaluation outputs (reports)

Primary report used in Chapter 5:
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.json`

Optional intermediate reports (if generated):
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.raw.json`
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.cleaned.json`
- `backend/reports/sentiment_benchmark_tuning.json`

