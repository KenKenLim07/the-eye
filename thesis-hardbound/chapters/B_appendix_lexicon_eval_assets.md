# Appendix B — Evaluation Datasets and Lexicon Patch

This appendix documents the PH lexicon patch and benchmark assets used by the hybrid sentiment engine. These artifacts are versioned to support reproducibility and thesis-defensible evaluation.

## PH VADER Lexicon Patch

### Source of truth

Patch file:
- `backend/app/ml/vader_ph_lexicon.v1.json`

This JSON is loaded and applied by `backend/app/ml/bias.py` when `VADER_PH_PATCH=1` (truthy). Patch application is designed to be safe for Celery workers:
- it is applied **once per process** (module-level “applied” flag),
- patch status (enabled/applied/version and counts) is emitted into `model_metadata`.

### File structure

The patch file contains:
- `version` (string): patch version identifier (e.g., `ph_taglish_v1`)
- `lexicon` (object): token → valence score (float), roughly in the VADER scale
- `negations` (array): conservative Tagalog negations to add to VADER’s negation set
- `boosters` (object): intensifiers/dampeners token → scalar
- `phrases` (object): multi-word phrase → `{ "token": "...", "valence": ... }`
- `but_words` (array): Tagalog contrast words (e.g., equivalents of “but”)
- `override_existing_allowlist` (array, optional): tokens allowed to override base VADER entries when collisions occur

### Phrase normalization

When the PH patch is enabled, `_preprocess_for_vader()` applies deterministic phrase substitutions:
- known multi-word expressions are replaced with their configured single token (e.g., `"sana all"` → `sana_all`)
- the phrase token is present in the merged lexicon so VADER can score it

This prevents inconsistent scoring caused by splitting multi-word expressions into separate tokens.

### Contrast (“but”) handling and controls

The patch optionally supports Tagalog contrast handling in two ways:
1. **BUT_WORDS injection** into VADER constants (when available), controlled by:
   - `VADER_TL_BUT_WORDS` (unset → enabled by default; set `0` to disable)
2. **Contrast word normalization** in preprocessing (replacing Tagalog contrast words with `"but"`), controlled by:
   - `VADER_TL_BUT_NORMALIZE` (unset → enabled by default; set `0` to disable)

These options exist because contrast weighting can over-polarize mixed sentences in news text (e.g., “X pero Y”) depending on how the sentence is written.

## Gold Sets (Offline Benchmarks)

### Taglish/Tagalog gold set

File:
- `backend/app/ml/vader_ph_eval.v1.json`

Shape:
- `version` (string)
- `items` (array): `{ "text": "...", "label": "positive|neutral|negative" }`

This set is designed to stress:
- Tagalog negation and contrast,
- common Taglish sentiment terms,
- PH news tokens (crime/disaster/governance),
- mixed language short sentences similar to headline + lead snippets.

### English-only gold set (DistilBERT baseline)

File:
- `backend/app/ml/distilbert_en_gold.v1.json`

This subset is used to document DistilBERT SST-2 behavior on formal English text, and to explicitly acknowledge that SST-2 is binary unless neutralization is introduced via confidence thresholding.

## Manual Benchmark Assets (Real News)

The study also includes a manually labeled benchmark sample exported from the database for the fixed observation window:
- Sample CSV (labeling worksheet): `backend/reports/benchmark_sample_2026-03-25_2026-03-31.csv`
- Labeling protocol: `docs/sentiment_benchmark_labeling.md`

After labeling and adjudication, benchmark evaluation produces versioned reports under `backend/reports/`, including:
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.json` (primary thesis-report JSON used for tables in Chapter 5)
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.raw.json` (pre-cleaning run, if generated)
- `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.cleaned.json` (post-cleaning run, if generated)

During threshold tuning, intermediate summaries may also be stored as JSON (e.g., `backend/reports/sentiment_benchmark_tuning.json`) to track improvements and trade-offs across neutral-band and routing settings.

## Evaluation scripts

Gold set runner:
- `backend/scripts/evaluate_vader_ph_gold.py`
  - supports `--model {vader,distilbert,hybrid}`
  - supports toggling the PH patch and overriding key thresholds at runtime

Real-news drift runner:
- `backend/scripts/evaluate_vader_longform.py`
  - compares legacy single-pass VADER vs the selected “new path” model on sampled real articles

Manual benchmark evaluator:
- `backend/scripts/evaluate_sentiment_benchmark.py`
  - reads the labeled CSV
  - optionally cleans scraped text
  - outputs a JSON report and prints LaTeX-ready tables for thesis reporting

## Safe update workflow (recommended)

1. **Edit one artifact at a time** (lexicon patch or gold set), and bump its `version`.
2. Run `evaluate_vader_ph_gold.py` (baseline vs patched vs hybrid) and record results.
3. Run `evaluate_vader_longform.py` drift checks to ensure changes are explainable on real news.
4. If you rescore production rows, use a stable `SENTIMENT_MODEL_VERSION` (e.g., `sentiment_hybrid_v1`) so analytics are not skewed by duplicate experimental rows.
