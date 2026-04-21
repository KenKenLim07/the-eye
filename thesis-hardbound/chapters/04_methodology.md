# Design and Methodology

This chapter presents the methodology used to design, develop, and evaluate PH VibeCheck AI. It covers (1) the development process, (2) data collection and normalization, (3) the NLP analysis approach, and (4) evaluation procedures used to benchmark the hybrid sentiment engine in a Philippine news setting.

## Research Design

The study follows a **developmental and descriptive** research design: it designs and implements a working end-to-end system, then evaluates its behavior using controlled gold sets and a manually labeled benchmark on real news text. Quantitative results are reported as *signal-quality* metrics (accuracy, macro-F1, confusion patterns) rather than as definitive measures of media bias.

## Development Approach (Iterative SDLC)

PH VibeCheck AI was developed using an iterative, sprint-based approach. Iteration is essential for web-based news monitoring systems because source websites change layout and access patterns over time. Each iteration refined one or more modules (scrapers, preprocessing, ML scoring, storage, and dashboards), followed by verification on real collected articles.

*(Figure X: Iterative development approach used in the project (design → build → test → review → launch). Insert diagram here.)*

Figure X illustrates the iterative SDLC cycle used to guide development and refinement of the system. This approach supports rapid fixes when scraper behavior changes and provides a repeatable loop for validating output quality before deployment.

The sprint cycle can be summarized as:
1. **Design:** refine module boundaries, database interactions, API logic, and visualization requirements.
2. **Build:** implement or update scrapers, preprocessing routines, the hybrid sentiment engine, and dashboards.
3. **Test:** run targeted checks using recently collected articles and offline gold sets.
4. **Review:** inspect outputs (scraped text quality, sentiment behavior, and dashboard correctness).
5. **Launch:** deploy the updated version and monitor operational results to inform the next iteration.

## Data Sources and Inclusion Criteria

The system collects articles from a fixed set of Philippine news sources implemented as scraper modules in the backend. Sources are treated as the primary unit of comparison for outlet-level trends and correlation analysis. For evaluation reporting, this thesis follows the snapshot window used in the updated system artifact:
- **Observation window:** March 25, 2026 to March 31, 2026 (PH local time, Asia/Manila)

This fixed window supports consistent comparisons across sources and enables repeatable benchmark reporting.

The implemented sources are:
- ABS-CBN
- GMA News Online
- Inquirer
- Manila Bulletin
- Manila Times
- Philstar
- Rappler
- SunStar

## Collection and Normalization

Scrapers discover candidate article URLs, fetch article pages, and normalize extracted content into a consistent schema suitable for downstream NLP analysis. Normalization focuses on:
- capturing the canonical URL and source,
- extracting title and cleaned article content,
- retaining timestamps when available, and
- producing comparable text inputs across sources.

Where sources require dynamic rendering, headless browser automation can be used to render pages before extraction. The system is designed to remain resilient under source-specific layout changes by keeping scrapers modular and independently maintainable.

For analytics correctness, publication timestamps are normalized to timezone-aware UTC values before storage. When a source provides a timestamp without an explicit offset, the pipeline assumes Asia/Manila local time to avoid systematic day-bucket skew in trend aggregation.

## Conceptual Design and System Architecture

From a design perspective, PH VibeCheck AI follows a **pipeline** architecture: ingestion, analysis, storage, and visualization are separated into modules that can evolve independently. This separation is important for real-world news monitoring because failures are often source-specific (e.g., a single site changes layout), while the rest of the system should continue operating.

At a high level, the system’s block flow can be summarized as:
1. **Ingestion:** discover URLs per source, fetch content, normalize fields, and store articles.
2. **Analysis:** compute sentiment and extract entities asynchronously in the background.
3. **Persistence:** upsert analysis outputs with stable keys and maintain a public cache for the UI.
4. **Visualization:** query aggregated signals (trends, correlation, entities) and support drill-down to articles.

The detailed system diagram and the single-article lifecycle are presented in Chapter 3 (Technicality of the Project). In this chapter, the focus is on the methodological choices and procedures that govern how the pipeline is executed and evaluated.

To satisfy hardbound reporting conventions for software-development theses, the following diagrams will be included in the final manuscript:
- a **system block diagram** (module-level view of ingestion → analysis → storage → dashboards),
- an **algorithm/flow diagram** for the hybrid sentiment decision path (route → score → neutral handling), and
- an **evaluation workflow diagram** (gold sets → manual benchmark → drift checks).

## Algorithmic Procedures (Operational View)

Although the project integrates multiple components, its core behavior can be described as a small set of deterministic procedures that execute repeatedly during continuous runs and backfills.

![Hybrid sentiment procedure: compute Tagalog-signal, route to VADER+PH vs DistilBERT SST-2, apply bounded-input constraints and neutral handling, then persist outputs and routing metadata.](figures/method-hybrid-sentiment-flow.png){#fig:method-hybrid-flow}

Figure X summarizes the operational decision path used in the hybrid sentiment engine. Articles with stronger Tagalog/Taglish signals are routed to the localized VADER pathway, while English-heavy articles are routed to the DistilBERT (SST-2) pathway; both paths apply conservative bounding/neutral handling before producing a final label and score.

For auditability and reproducibility, the system records the selected route and key routing/model metadata together with the stored sentiment outputs, enabling later inspection of why a particular pathway was used for an article.

### Scraping procedure (network-first → browser fallback)

For each source, the scraper follows a layered strategy:
1. **Seed URL candidates** from lightweight endpoints (HTTP section listings, RSS, or JSON list endpoints).
2. **Canonicalize and de-duplicate** URLs before scraping.
3. **DB preflight**: check which URLs already exist and skip them early.
4. **Extract content via network-first parsing** (structured metadata / site JSON payloads / HTML parsing).
5. **Fallback to Playwright rendering** when the extracted body is missing/incomplete or blocked, then re-extract text.
6. **Normalize and store** the article (title, cleaned content, timestamps) for downstream analysis.

This strategy improves throughput during catch-up windows by avoiding browser rendering for every item, while still retaining a correctness fallback for dynamic or bot-protected pages.

### Hybrid sentiment procedure (route → score → neutral handling)

The sentiment engine uses two scoring pathways and an explicit routing decision:
1. Compute a lightweight **Tagalog-signal ratio** on the input text (based on a fixed set of Tagalog/Taglish tokens and patterns).
2. **Route** the article to the most appropriate engine:
   - Tagalog/Taglish-heavy → VADER + PH patch [@hutto2014vader]
   - English-heavy → DistilBERT SST-2 polarity scoring [@sanh2019distilbert; @devlin2018bert; @socher2013sst]
3. Apply **bounded-input constraints** for long-form stability (truncation/clipping for transformer inputs; chunk/weight strategy for long articles).
4. Map raw model outputs to a three-class label set using:
   - a neutral band around zero for VADER, and
   - confidence-based abstention into neutral for the binary SST-2 transformer baseline.

Routing decisions and key sub-model metadata are persisted so model behavior can be audited and explained in evaluation.

### Entity extraction procedure (entity-centric aggregation)

Entity extraction is applied per stored article:
1. Run NER to extract entity spans and labels (PERSON/ORG/GPE) [@nadeau2007ner].
2. Normalize and store extracted entities in a queryable representation.
3. Compute aggregates for dashboards such as top entities by frequency and average sentiment of associated articles.

### Storage semantics (upsert to avoid double counting)

To ensure stable analytics across rescoring and backfills:
1. Articles are stored with canonical URLs to prevent duplicate rows caused by trivial URL variants.
2. Analysis outputs are written with upsert semantics using stable uniqueness keys (so re-runs overwrite instead of duplicating).
3. A public cache table is maintained for fast UI reads (latest sentiment per article) while preserving richer internal metadata for audit and evaluation.

## NLP Analysis Method (Hybrid Sentiment + NER)

Sentiment is computed using a hybrid engine that combines a Tagalog/Taglish-extended VADER pathway [@hutto2014vader] with a DistilBERT SST-2 transformer pathway [@sanh2019distilbert; @devlin2018bert; @socher2013sst]. A lightweight language-signal heuristic routes each article to the most appropriate pathway (Taglish-heavy → VADER+PH; English-heavy → DistilBERT).

Named Entity Recognition (NER) is applied to extract persons, organizations, and locations (PERSON/ORG/GPE), enabling entity-level frequency ranking and associated sentiment summaries [@nadeau2007ner]. Entity outputs are used as exploratory signals to guide qualitative review rather than as definitive judgments.

As a preprocessing principle, the system avoids aggressive “cleaning” that could change meaning (e.g., stripping punctuation globally). Instead, it applies only limited deterministic normalization where it is needed for model behavior (e.g., VADER phrase substitution and contrast handling in the Taglish patch), and otherwise relies on the underlying tokenizers (VADER rules and transformer tokenization) to handle punctuation and whitespace.

## Evaluation Procedures

Evaluation is designed to be thesis-defensible and reproducible, and to reflect two realities of Philippine news text: (1) code-switching and locally frequent expressions, and (2) long-form, factual reporting where neutrality must be handled carefully. To address these, the study uses three complementary evaluation strategies:
1. **Offline gold sets** to validate specific linguistic edge cases under controlled settings.
2. **Manual benchmark on real news** to measure end-to-end accuracy on authentic article text with human labels.
3. **Drift checks on recent real articles** to ensure model updates produce explainable, inspectable changes in production-like data.

*(Figure X: Evaluation workflow (gold sets → manual benchmark with two annotators + adjudication + kappa → drift checks → reports/tables). Insert diagram here.)*

Figure X summarizes the evaluation workflow from controlled tests to real-news benchmarking and operational drift checks. Using multiple evaluation layers reduces the risk of overfitting to a small gold set while ensuring that changes observed on production-like data remain explainable.

Across evaluations, the core quantitative metrics are accuracy and confusion matrices. For the manual benchmark, the study also reports macro-averaged precision/recall/F1 across the three sentiment classes and measures inter-annotator agreement using Cohen’s kappa [@cohen1960kappa].

### Offline Gold Sets (Definition)

The project includes:
- **Taglish/Tagalog gold set:** `backend/app/ml/vader_ph_eval.v1.json` ($n=130$; 3-class: positive/neutral/negative).
- **English-only gold set (transformer baseline):** `backend/app/ml/distilbert_en_gold.v1.json` ($n=94$; binary positive/negative).

These sets are intended to stress key phenomena relevant to Philippine news: code-switching, Tagalog negation, contrast constructions, and PH news tokens.

### Gold Set Evaluation Procedure

Gold set evaluation is run using `backend/scripts/evaluate_vader_ph_gold.py`, which supports evaluating VADER, DistilBERT, and the hybrid router on a fixed labeled set. The script reports:
- overall accuracy,
- label distributions (true vs predicted),
- a 3×3 confusion summary (positive/neutral/negative),
- and a short list of misclassified examples for qualitative inspection.

The script supports evaluating VADER, DistilBERT, and the hybrid router under controlled configurations. Key tunable parameters include:
- `VADER_NEUTRAL_BAND` (neutral zone width for VADER label mapping),
- `TAGALOG_SIGNAL_THRESHOLD` (routing threshold for hybrid selection),
- `DISTILBERT_NEUTRAL_MIN_CONF` (confidence threshold for abstaining into neutral).

In addition, the evaluation harness can enable or disable specific Tagalog contrast handling behaviors (e.g., mapping contrast words such as *pero* into VADER’s contrast logic) to quantify their effect under identical data and thresholds.

### Manual Benchmark Protocol (Real News, 3-Class)

To evaluate end-to-end behavior on real articles, the study constructs a manually labeled benchmark from the same observation window. The benchmark is exported from the database as a stratified sample using `backend/scripts/export_sentiment_benchmark_sample.py`, with a target sample size of $n=200$ and a minimum per-source quota (default 20) to ensure multi-source coverage. The export window is specified in PH local dates and converted to UTC for database filtering.

Because some outlets can contain regional-language content that is not consistently handled by English-only sentiment baselines, the benchmark export excludes SunStar by default for label consistency (while SunStar remains supported by the system for live ingestion and dashboard views).

#### Annotation workflow

The labeling workflow follows the protocol documented in `docs/sentiment_benchmark_labeling.md`:
1. **Two annotators label independently** using three classes (positive/neutral/negative).
2. Each annotator writes their decision into separate columns (`label_a`, `label_b`).
3. **Adjudication** resolves disagreements into a final label (`label_final`) used as the reference label for model evaluation.

Inter-annotator agreement is measured using Cohen’s kappa on `label_a` versus `label_b` [@cohen1960kappa].

#### Model evaluation on the benchmark sample

Benchmark evaluation is run using `backend/scripts/evaluate_sentiment_benchmark.py`. The script:
- reads the labeled CSV (title + body text),
- optionally applies conservative scraper-noise cleaning before inference (to remove repeated boilerplate and obvious concatenation artifacts),
- computes accuracy, macro-F1, per-class precision/recall/F1, and confusion matrices for each model variant (VADER, DistilBERT, Hybrid),
- reports hybrid route counts and route-level accuracy (e.g., VADER route vs DistilBERT route), and
- outputs a JSON report and pre-formatted LaTeX tables for thesis reporting.

The results used in Chapter 5 are taken from the generated JSON report under `backend/reports/` (e.g., `backend/reports/sentiment_benchmark_2026-03-25_2026-03-31.json`).

Because SST-2 is a binary objective, the benchmark tool also reports an additional “binary subset” evaluation where neutral ground-truth rows are excluded and neutral predictions are treated as errors. This makes abstention behavior visible while allowing a direct positive-vs-negative comparison when needed.

### Drift Checks on Real Articles

Offline gold sets are limited in size and coverage; therefore, the project also runs drift evaluation on sampled real articles stored in the database. Drift checks are run using:
- `backend/scripts/evaluate_vader_longform.py`

This script compares a legacy baseline (single-pass VADER over full text) against a selected “new path” model (VADER long-form, DistilBERT, or hybrid), reporting:
- score drift statistics and mean absolute delta,
- label distribution shifts and percent changed labels,
- and the most-changed examples to support qualitative inspection.

The drift perspective is a safety mechanism: it reduces the risk that an update improves a small benchmark but causes unexpected behavior across real news text.

Importantly, drift results are not treated as “accuracy” outcomes; rather, they function as an operational sanity check that surfaces large changes for audit and explanation.

## Reproducibility and Offline Operation

To keep evaluation repeatable across machines and networks, the system supports:
- **Dockerized execution** of evaluation scripts inside the ML worker container, ensuring consistent dependencies and model code paths.
- **Offline transformer loading** when the Hugging Face model weights are cached locally (via `HF_HOME` cache directory and `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`), reducing reliance on network availability during thesis runs.
- **Configurable thresholds via environment variables** (e.g., neutral bands and routing thresholds) so that reported results can be reproduced by re-running the same commands with the same settings (see Appendix A).
