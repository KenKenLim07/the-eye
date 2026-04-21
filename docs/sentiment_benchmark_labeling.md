# Sentiment Benchmark Labeling Guide (PH VibeCheck AI)

This guide defines a lightweight, thesis-friendly protocol for manually labeling a small benchmark set of Philippine news articles, then evaluating sentiment models (VADER+PH patch, DistilBERT, Hybrid).

## Label Set (3-class)
Use exactly one label per article:

- `positive`: overall tone is favorable/optimistic/supportive.
- `neutral`: primarily factual reporting; mixed tone without a clear valence; announcements/updates; balanced pros/cons.
- `negative`: overall tone is unfavorable/alarming/critical; harm, conflict, loss, fear, or strong criticism dominates.

## What to label (news tone)
Label the **overall tone of the article text** (title + body) as read by a typical audience. For straight reporting without explicit affect, default to `neutral`.

Examples (rule of thumb):
- “Confirmed: no injuries” → usually `neutral` (informational).
- “Victim killed in…” → usually `negative` (harm dominates).
- “Community celebrates…” → usually `positive`.

## Common edge cases
- **Mixed valence** (e.g., good news + concerns): choose `neutral` unless one valence clearly dominates the framing.
- **Policy/economic reports**: focus on the overall framing (benefit vs burden). If unclear, choose `neutral`.
- **Quotations**: the article can inherit tone from quoted statements; still label the overall piece.

## Annotation workflow (two annotators)
1) Export the sample CSV using:
   - `docker compose exec worker_ml python scripts/export_sentiment_benchmark_sample.py --start-local 2026-03-25 --end-local 2026-03-31 --n 200 --min-per-source 20`
2) Each annotator labels independently:
   - Annotator A fills `label_a`
   - Annotator B fills `label_b`
3) Adjudication:
   - For disagreements, the author reviews and writes the final decision into `label_final`.

## Agreement + reporting
- Compute inter-annotator agreement using **Cohen’s kappa** on `label_a` vs `label_b`.
- Report model performance using **accuracy**, **macro-F1**, per-class precision/recall/F1, and the confusion matrix.

## Recommended evaluation command (consistent settings + cached weights)
Run evaluation inside `worker_ml` so the environment variables match the deployed hybrid pipeline (e.g., Taglish VADER patch, routing threshold), and so Hugging Face weights can be reused from the host cache mount:

- `docker compose exec worker_ml python scripts/evaluate_sentiment_benchmark.py --file reports/benchmark_sample_2026-03-25_2026-03-31.csv`

## Data handling / copyright note
Do not publish full article text in the thesis or public repo artifacts. Keep the CSV private; only report aggregate metrics and brief excerpts if needed and allowed by fair use.
