# Technicality of the Project

This chapter discusses the technical complexity of PH VibeCheck AI as an end-to-end pipeline for continuously collecting Philippine online news, processing it with NLP, and presenting the outputs through interactive dashboards. The technicality of the project lies not in a single algorithm, but in the coordination of multiple subsystems that must operate reliably under real-world constraints (dynamic websites, changing page structures, continuous scheduling, and reproducible storage). In practical terms, the system transforms unstructured, web-delivered articles into structured analytical outputs (sentiment and entity signals) that can be queried, aggregated, and verified through an interactive interface.

## End-to-End Architecture (Pipeline View)

PH VibeCheck AI is implemented as a pipeline for continuous news collection, processing, and visualization. The frontend is a Next.js web application deployed on Vercel. The backend exposes a REST API using FastAPI and is deployed via Docker. Background work (scraping and ML processing) is orchestrated with Celery using Redis as broker/cache. Articles and analysis outputs are stored in a Supabase-managed PostgreSQL database.

![PH VibeCheck AI architecture: Next.js frontend (Vercel), FastAPI backend (Docker), Celery worker/beat with Redis, Supabase (PostgreSQL) storage, and external news sources.](figures/system-flowchart.png){#fig:architecture}

At a high level:
- The frontend provides dashboards (Home, Search, Trends, Correlation, Entities) for monitoring and exploration.
- The backend handles application logic and analytics endpoints and persists data in Supabase.
- Celery Beat schedules scraping tasks; Celery workers execute scraping and NLP processing asynchronously and write outputs to the database.

In deployment, these components are run as separate containers (API, scraping worker, ML worker, scheduler/beat, and Redis), which isolates failure domains and allows each workload to be tuned independently (e.g., higher concurrency for scraping vs. conservative CPU bounds for transformer inference).

## Technology Stack Roles (Subsystem View)

The system uses a modular stack where each technology plays a specific role in the pipeline:
- **Web/API layer:** FastAPI exposes REST endpoints for dashboards and operational routes (e.g., manual scrape triggers).
- **Containerized deployment:** Docker provides a consistent runtime for the API, workers, scheduler, and supporting services.
- **Task scheduling and background execution:** Celery workers execute scraping and ML analysis asynchronously, while Celery Beat maintains periodic schedules per source.
- **Queueing and caching:** Redis serves as the broker/result backend for Celery and can also be used as a lightweight cache for repeated analytics queries.
- **Relational storage:** Supabase-managed PostgreSQL stores normalized articles and analysis outputs with stable upsert keys that support rescoring without duplication.
- **Frontend analytics interface:** a Next.js application provides interactive dashboards and drill-down navigation for verification workflows.

To align with capstone constraints (limited compute and real-world sources), the overall design prioritizes separation of concerns: ingestion, ML, storage, and visualization are decoupled so changes in one subsystem (e.g., a scraper breaking due to layout changes) do not require redesigning the entire platform.

## Single-Article Pipeline Flow (From URL to Dashboards)

While the architecture is multi-component, the system can be understood most concretely as the lifecycle of a single article. A flow diagram for this section will be added in the final manuscript (e.g., Mermaid-based) to visualize each stage.

1. **Discovery (per source):** the scraper seeds candidate URLs (HTTP section pages, RSS feeds, or JSON endpoints depending on the outlet), then canonicalizes and de-duplicates the URL set.
2. **DB preflight de-duplication:** candidate URLs are checked against existing rows in the `articles` table so that already-ingested URLs are skipped early during continuous runs.
3. **Content extraction (fast-path → fallback):** the scraper attempts network-first extraction (structured data / site JSON payloads). If content is incomplete or blocked, the scraper falls back to Playwright rendering and then extracts the final text.
4. **Normalization and storage:** the extracted article is normalized into a consistent schema (source/category fields, content cleaning, and timezone-aware `published_at`), then inserted into Supabase (PostgreSQL). URL canonicalization and insertion safeguards prevent duplicate rows from silently accumulating.
5. **Asynchronous ML enqueue:** after storage, the pipeline enqueues analysis for new article IDs on the ML queue, decoupling heavy NLP work from scraping and from API response latency.
6. **Sentiment + entity extraction:** the ML worker fetches the stored article text and runs (a) hybrid sentiment scoring and (b) named entity recognition, producing per-article outputs plus metadata that supports auditing and reproducibility.
7. **Upsert analysis outputs:** analysis rows are upserted into `bias_analysis` using a stable uniqueness key so re-scoring overwrites rather than duplicates. A public-facing cache table (`article_sentiment_public`) is also upserted to support lightweight frontend display and fast reads.
8. **Aggregation and visualization:** API endpoints compute trend/correlation/entity summaries from stored outputs (with optional Redis caching for repeated queries), and the frontend renders the results as dashboards for monitoring and drill-down.

## Web Scraping Under Real-World Website Constraints

Modern news sites vary in how content is delivered: some pages can be discovered and parsed reliably via HTTP requests, while others require additional steps due to dynamically rendered content, anti-bot protections, or frequent layout changes. For these reasons, scraper implementation must be resilient and modular.

The system implements multiple news sources as separate scraper modules (`backend/app/scrapers/`), enabling per-source adaptation without destabilizing the overall pipeline. Where necessary, headless browser automation can be used to render dynamic pages before extraction. This flexibility is important for long-running monitoring systems because website structures evolve continuously.

### Discovery and extraction strategy (network-first with browser fallback)

To improve throughput and reliability, the scraping layer is designed around a “network-first, browser-fallback” strategy:
- **Network-first discovery:** attempt to seed candidate article URLs using lightweight sources such as section listing pages fetched over HTTP, RSS feeds, or public JSON list endpoints. This stage aims to avoid launching a full browser unless necessary.
- **Network-first extraction:** when an article is discovered, attempt to extract full content from HTML using structured metadata (e.g., JSON-LD `NewsArticle`) or site-provided JSON payloads. This improves speed and reduces the chance of timeouts on long backfill runs.
- **Playwright fallback:** when network-first extraction fails (blocked pages, partial excerpts, hydration delays, missing structured data), fall back to Playwright to render the page and extract the final text.

Across sources, candidate URLs are canonicalized and de-duplicated early. A database “preflight” step checks which URLs already exist in the `articles` table so that workers do not repeatedly scrape or insert duplicates during continuous runs.

### ABS-CBN: API and RSS discovery, Playwright fallback for Akamai-sensitive pages

ABS-CBN poses a practical constraint for long-running scrapers: some pages can be sensitive to bot detection and browser automation fingerprints. To reduce load and avoid unnecessary browser rendering, ABS-CBN uses a multi-stage discovery approach:
- **JSON API discovery:** discover fresh links using ABS-CBN’s OneDomain content API list endpoints (fast, JSON response).
- **RSS discovery:** supplement discovery using RSS feeds when additional URLs are needed.
- **Content fast-paths:** attempt to scrape via HTTP + structured data (JSON-LD) where available, and fall back to Playwright when the extracted body is missing or too short.

When Playwright is used, the implementation focuses on resource control and stability: optional resource blocking (images/fonts/media/trackers) reduces bandwidth and speeds up page load, and optional “headed mode” routing can be enabled via configuration for cases where headless browsing becomes unreliable on bot-protected routes.

### GMA: HTTP discovery and story-API fast-paths before Playwright

For GMA News Online, the scraper prioritizes low-latency discovery and extraction:
- **HTTP section discovery:** seed article URLs by fetching GMA section pages over HTTP (e.g., `/news/topstories/`, `/news/money/`) and extracting candidate links.
- **Story API extraction:** for many articles, the page references a compact story payload hosted on `data.gmanetwork.com`; when detected, the scraper fetches this JSON directly (often containing the full story body) and converts it to plain text.
- **Playwright fallback:** if content remains incomplete (e.g., excerpt-only bodies) or if discovery yields insufficient URLs, the scraper falls back to Playwright rendering and extraction.

This layered design is especially important during catch-up runs: network-first methods allow large windows of news to be processed without opening a browser for every item, while still retaining browser rendering as a correctness fallback.

## Asynchronous Processing and Scheduling

One of the key technical design choices is separating scraping and NLP analysis from the API request–response path. Running heavy operations synchronously (e.g., extracting many articles or scoring long articles with NLP models) would degrade responsiveness. Instead, the system uses Celery workers to perform scraping and ML processing asynchronously, with Redis providing broker/cache support.

Scheduling via Celery Beat enables continuous ingestion: tasks run periodically per source, and workers process new data in the background. This design supports steady-state operation and allows the platform to provide an “always-updating” view without requiring manual runs.

In addition, the task system is structured around **separate queues**: scraping tasks run on a scrape queue, while sentiment/entity processing runs on an ML queue. This separation prevents ML workloads (e.g., scoring long-form articles) from blocking ingestion, and it enables different concurrency and restart policies per worker process.

Operationally, scraping schedules are configured per source to balance freshness with site politeness. For example, high-frequency sources run on roughly hourly intervals, while more sensitive sources (e.g., ABS-CBN) can be scheduled more gently and optionally routed to a dedicated “headed” scrape queue when required by changes in anti-bot behavior.

From a system-operations standpoint, asynchronous execution also enables resilience: if a batch of articles contains timeouts or a source temporarily fails, the worker can retry without blocking other sources, and the API can remain responsive because it reads already-stored rows rather than waiting for scraping/ML to finish.

## Storage, Upserts, and “One Active Sentiment Row per Article”

Operational stability depends on predictable storage semantics. Articles are stored as normalized records in Supabase (PostgreSQL). Sentiment outputs are written using upsert semantics so that re-scoring does not create duplicate rows that skew analytics.

The system writes sentiment analysis rows into `bias_analysis` keyed by `(article_id, model_version, model_type='sentiment')`, and maintains a public cache table `article_sentiment_public` used by the frontend for coverage and lightweight display. This two-table strategy supports security (internal analysis rows can be protected by RLS) while keeping the UI responsive and consistent.

At the storage boundary, the pipeline enforces additional “production hardening” details that matter for trend analytics:
- **URL canonicalization:** URLs are normalized before insertion so that trivial variants (e.g., tracking parameters) do not create duplicate rows.
- **Duplicate pre-check and safe insertion:** batches perform best-effort duplicate checks against existing URLs; when pre-checks are unavailable (e.g., transient network failures), the system can fall back to upsert behavior to avoid hard-failing ingestion.
- **Timestamp normalization:** when sources provide timestamps without explicit timezone offsets, the pipeline normalizes publication time to UTC using an Asia/Manila assumption to prevent systematic day-bucket skew in trend views.

To avoid “double counting” sentiment in analytics, the system also uses a single active `model_version` for production writes (e.g., `sentiment_hybrid_v1`). This practice ensures that model experiments can be recorded without unintentionally skewing dashboard aggregation queries.

## Supabase query performance and indexing (news-scale analytics)

Because the dashboards execute repeated queries over growing article tables, the system includes database indexing steps designed for news-style workloads:
- **Full-text search (FTS):** a `search_tsv` column and trigger-maintained `tsvector` enable faster search than naive substring scans, using a language-agnostic `simple` configuration suitable for mixed Tagalog/English content.
- **Trigram indexes (optional):** GIN trigram indexes can accelerate `ILIKE %query%` searches when substring semantics are required, at the cost of larger index size.
- **Correlation and aggregation indexes:** composite indexes support common analytics patterns such as “latest sentiment per article” and date-range filtering by source for trends/correlation views.

These indexing steps are captured as executable SQL artifacts (`backend/scripts/create_article_search_fts.sql`, `backend/scripts/create_article_search_trgm.sql`, and `backend/scripts/create_correlation_indexes.sql`) to support reproducibility and easier database tuning across environments.

## Hybrid Sentiment Engine (Implementation Technicalities)

PH VibeCheck AI uses a hybrid sentiment engine to address multilingual and code-switched Philippine news text. The hybrid design combines:
- a lexicon-based sentiment analyzer (VADER) [@hutto2014vader], extended with a Philippine Tagalog/Taglish patch, and
- a lightweight transformer classifier (DistilBERT) [@sanh2019distilbert; @devlin2018bert] fine-tuned on SST-2 [@socher2013sst], implemented using a standard transformer runtime.

### VADER: Long-Form Weighting for Articles

VADER was designed for short social text; when applied to long articles, sentiment can be diluted. To mitigate this, the implementation applies a long-form weighting strategy:
- split input into title and body (when a title/body separator is provided),
- segment the body into sentence-based chunks,
- compute compound sentiment for title, lead chunks, and body chunks, and
- aggregate with fixed weights to produce a single article-level compound score in $[-1,1]$.

Labels (positive/neutral/negative) are derived using a configurable neutral band (`VADER_NEUTRAL_BAND`) to reduce false polarity on factual reporting text.

### PH Tagalog/Taglish Lexicon Patch

The PH patch is a versioned JSON artifact (`backend/app/ml/vader_ph_lexicon.v1.json`) that extends VADER with:
- Tagalog/Taglish sentiment terms,
- conservative negations and boosters, and
- multi-word expressions collapsed into single tokens for deterministic scoring (e.g., phrase normalization).

Patch application is designed to be safe in Celery workers: it is applied once per process and its status/version is recorded in `model_metadata` to maintain transparency and reproducibility.

### DistilBERT: CPU Inference with Truncation and Neutralization

The transformer path uses DistilBERT SST-2 to score English-heavy text efficiently on CPU. To keep runtime bounded for long articles, the system enforces:
- character clipping (`DISTILBERT_MAX_CHARS`) and
- token truncation (`DISTILBERT_MAX_LENGTH`).

Because SST-2 is binary, neutrality is introduced through confidence-based thresholding (`DISTILBERT_NEUTRAL_MIN_CONF`): low-confidence predictions are treated as neutral to reduce over-polarization of objective reporting language.

### Hybrid Router

The hybrid router selects the VADER+PH path or the DistilBERT path per article using a lightweight Tagalog-signal heuristic. Taglish-heavy or linguistically ambiguous inputs are routed to the VADER+PH path, while English-heavy inputs are routed to DistilBERT. Routing decisions and sub-model metadata are persisted so that the system’s behavior can be audited and defended in evaluation.

## Dashboard Layer (Exploration and Verification)

The dashboard layer provides interactive views for monitoring and analysis:
- Home (latest feed + KPI snapshot),
- Search (keyword queries + pagination),
- Trends (sentiment over time),
- Correlation (cross-source alignment via daily averages), and
- Entities (frequency and associated sentiment).

These dashboards are designed to support exploratory analysis and to encourage qualitative verification by enabling navigation from aggregated summaries to individual articles.
