# Appendix C — Relevant Source Code (Index and Selected Excerpts)

This appendix provides a concise index of the most relevant source-code modules used to implement PH VibeCheck AI, together with short excerpts for the core methodology-critical components. The full source code is available in the project repository; the goal of this appendix is to make the implementation traceable and defensible without printing the entire codebase.

## Source code index (by subsystem)

| Subsystem | Key paths (repo-relative) | Purpose |
|---|---|---|
| API (backend) | `backend/app/main.py`, `backend/app/api/` | FastAPI entrypoint and REST routes (health, scraping triggers, ML analytics endpoints). |
| Scrapers | `backend/app/scrapers/` | Per-source scrapers (ABS-CBN, GMA, Inquirer, Rappler, etc.), plus shared utilities. |
| ML sentiment + bias | `backend/app/ml/bias.py` | Hybrid sentiment router, VADER path (incl. long-form weighting), and row-building for database writes. |
| Transformer sentiment | `backend/app/ml/sentiment_transformer.py` | DistilBERT SST-2 CPU inference with bounded input and neutralization rules. |
| Evaluation assets | `backend/app/ml/vader_ph_eval.v1.json`, `backend/app/ml/distilbert_en_gold.v1.json` | Gold sets used in offline evaluation. |
| Evaluation scripts | `backend/scripts/` | Gold-set evaluation, manual benchmark evaluation, drift checks, export tooling. |
| Celery workers | `backend/app/workers/` | Background tasks for ML analysis and cache backfills. |
| Storage client | `backend/app/core/supabase.py` | Supabase (PostgreSQL) API client wrapper used by workers and scripts. |
| Supabase type safety | `src/types/database.ts`, `src/lib/supabase/{client,server,admin}.ts` | TypeScript database types and typed Supabase clients used by the frontend. |
| Frontend (dashboards) | `src/app/`, `src/components/`, `src/lib/` | UI pages and components for Trends/Correlation/Entities and article drill-down. |

## Supabase type safety (TypeScript)

The frontend uses Supabase’s generated TypeScript types (`src/types/database.ts`) to provide compile-time checks for the core tables represented in the file. Typed clients are created in `src/lib/supabase/client.ts` and `src/lib/supabase/server.ts` via `createClient<Database>(...)`.

Some database objects used for demos or experimental snapshot workflows may not be represented in `src/types/database.ts`. For these cases, the codebase also provides untyped Supabase clients (`supabaseUntyped`, `supabaseServerUntyped`, `getSupabaseAdminUntyped`) to avoid spreading unsafe `as any` casts.

## Selected excerpts (methodology-critical)

### Hybrid sentiment routing (Tagalog-signal heuristic → VADER or DistilBERT)

File: `backend/app/ml/bias.py`

```python
def _tagalog_signal(text: str) -> dict[str, Any]:
    raw = (text or "").strip().lower()
    tokens = re.findall(r"[a-zñ]+", raw, flags=re.IGNORECASE)
    if not tokens:
        return {"tokens": 0, "hits": 0, "ratio": 0.0}
    hits = 0
    for t in tokens:
        tl = t.lower()
        if tl in _TAGALOG_FUNCTION_WORDS or tl in _TAGALOG_SIGNAL_TOKENS:
            hits += 1
    return {"tokens": len(tokens), "hits": hits, "ratio": (hits / max(1, len(tokens)))}


def analyze_sentiment_hybrid_detailed(text: str) -> Tuple[float, str, float, Dict[str, Any]]:
    threshold = _get_env_float("TAGALOG_SIGNAL_THRESHOLD", 0.06)
    threshold = max(0.0, min(1.0, threshold))
    sig = _tagalog_signal(text)
    route = "vader" if float(sig.get("ratio") or 0.0) >= threshold else "distilbert"
    route_reason = "tagalog_signal"

    if route == "distilbert" and _looks_like_reporting_preface(text):
        route = "vader"
        route_reason = "reporting_preface"

    if route == "vader":
        try:
            compound, label, elapsed_ms, meta = analyze_sentiment_vader_detailed(text)
            return compound, label, elapsed_ms, {
                "library": "hybrid",
                "engine": "vader_or_distilbert",
                "route": "vader",
                "route_reason": route_reason,
                "tagalog_signal_threshold": threshold,
                "tagalog_signal_ratio": sig.get("ratio"),
                "tagalog_signal_hits": sig.get("hits"),
                "tagalog_signal_tokens": sig.get("tokens"),
                "route_metadata": meta,
            }
        except Exception as e:
            compound, label, elapsed_ms, meta = analyze_sentiment_distilbert_detailed(text)
            return compound, label, elapsed_ms, {
                "library": "hybrid",
                "engine": "vader_or_distilbert",
                "route": "distilbert_fallback",
                "route_reason": route_reason,
                "tagalog_signal_threshold": threshold,
                "tagalog_signal_ratio": sig.get("ratio"),
                "tagalog_signal_hits": sig.get("hits"),
                "tagalog_signal_tokens": sig.get("tokens"),
                "route_metadata": meta,
                "vader_error": str(e),
            }

    compound, label, elapsed_ms, meta = analyze_sentiment_distilbert_detailed(text)
    if meta.get("error"):
        v_compound, v_label, v_elapsed, v_meta = analyze_sentiment_vader_detailed(text)
        return v_compound, v_label, v_elapsed, {
            "library": "hybrid",
            "engine": "vader_or_distilbert",
            "route": "vader_fallback",
            "route_reason": route_reason,
            "tagalog_signal_threshold": threshold,
            "tagalog_signal_ratio": sig.get("ratio"),
            "tagalog_signal_hits": sig.get("hits"),
            "tagalog_signal_tokens": sig.get("tokens"),
            "route_metadata": v_meta,
            "distilbert_error": meta.get("error"),
        }

    return compound, label, elapsed_ms, {
        "library": "hybrid",
        "engine": "vader_or_distilbert",
        "route": "distilbert",
        "route_reason": route_reason,
        "tagalog_signal_threshold": threshold,
        "tagalog_signal_ratio": sig.get("ratio"),
        "tagalog_signal_hits": sig.get("hits"),
        "tagalog_signal_tokens": sig.get("tokens"),
        "route_metadata": meta,
    }
```

### DistilBERT SST-2 inference (bounded input + confidence-to-neutral)

File: `backend/app/ml/sentiment_transformer.py`

```python
def analyze_sentiment_distilbert_detailed(text: str) -> tuple[float, str, float, dict[str, Any]]:
    start = time.time()
    raw = (text or "").strip()

    model_id = (os.getenv("DISTILBERT_MODEL_ID") or "").strip() or "distilbert-base-uncased-finetuned-sst-2-english"
    max_length = _get_env_int("DISTILBERT_MAX_LENGTH", 512)
    max_chars = _get_env_int("DISTILBERT_MAX_CHARS", 2000)
    neutral_min_conf = _get_env_float("DISTILBERT_NEUTRAL_MIN_CONF", 0.60)

    clipped = raw[:max_chars]
    if not clipped:
        elapsed_ms = (time.time() - start) * 1000.0
        return 0.0, "neutral", elapsed_ms, {"error": None}

    pipe = _get_pipeline()
    out = pipe(clipped, truncation=True, max_length=max_length)
    item = out[0] if isinstance(out, list) and out else (out or {})

    label_raw = str((item or {}).get("label") or "").upper()
    score_raw = float((item or {}).get("score") or 0.0)

    is_positive = "POS" in label_raw
    base_label = "positive" if is_positive else "negative"
    compound = score_raw if is_positive else -score_raw

    if score_raw < neutral_min_conf:
        elapsed_ms = (time.time() - start) * 1000.0
        return 0.0, "neutral", elapsed_ms, {"transformer_label_raw": label_raw, "transformer_score_raw": score_raw, "error": None}

    elapsed_ms = (time.time() - start) * 1000.0
    return compound, base_label, elapsed_ms, {"transformer_label_raw": label_raw, "transformer_score_raw": score_raw, "error": None}
```

### ML worker task (fetch articles → analyze → upsert results)

File: `backend/app/workers/ml_tasks.py`

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_articles_task(self, article_ids: list[int]):
    # Fetch articles (chunked to avoid massive `id=in.(...)` URLs and timeouts).
    rows: list[dict] = []
    for batch in _chunked(article_ids, fetch_chunk):
        res = sb.table("articles").select("*").in_("id", batch).execute()
        rows.extend(res.data or [])

    out_rows: list[dict] = []
    for r in rows:
        article_id = r.get("id")
        text = f"{str(r.get('title') or '').strip()}\\n\\n{str(r.get('content') or '').strip()}".strip()
        out_rows.extend(build_comprehensive_bias_analysis(int(article_id), text))

    # Chunked upsert avoids very large payloads/timeouts.
    for batch in _chunked(out_rows, upsert_chunk):
        sb.table("bias_analysis").upsert(batch, on_conflict="article_id,model_version,model_type").execute()

    # Public sentiment cache (latest sentiment per article for fast UI reads).
    now_iso = datetime.now(timezone.utc).isoformat()
    sent_rows = [
        {"article_id": int(r["article_id"]), "sentiment_label": r.get("sentiment_label"), "sentiment_score": r.get("sentiment_score"), "updated_at": now_iso}
        for r in out_rows
        if (r.get("model_type") or "").strip() == "sentiment"
    ]
    for batch in _chunked(sent_rows, upsert_chunk):
        sb.table("article_sentiment_public").upsert(batch, on_conflict="article_id").execute()
```

Note: code excerpts above are shortened to highlight the controlling logic and database write semantics; refer to the full files for complete error handling and metadata fields.
