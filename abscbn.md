# ABS‑CBN Scraper: From Blocked Headless Playwright → Fast API‑First Ingestion

This document explains the ABS‑CBN breakthrough and how to replicate the same “pro” debugging workflow on other publishers:
- Why the old approach was fragile (Akamai + headless detection + heavy pages).
- How we found a stable **public JSON content API** already used by the site.
- How we redesigned the scraper to be **incremental**, **canonical‑first**, and mostly **browser‑free**.

Primary implementation: `backend/app/scrapers/abs_cbn.py`.

---

## 1) The Original Problem (Why ABS‑CBN was “special”)

### Symptoms you saw
- Headless Playwright runs frequently failed with “blocked / all landing pages blocked”.
- Headed mode (Xvfb) could work, but was **slow** and **RAM‑heavy** (Chromium + a virtual display).
- Even when it “worked”, it wasted time re‑scraping duplicates because it discovered links the same way each run.

### Root cause (the key constraint)
ABS‑CBN’s public HTML pages (e.g. `https://news.abs-cbn.com/news/...`) are protected (Akamai / bot mitigation).
That means:
- **Direct HTTP fetch** (`requests.get(article_url)`) often returns `403`.
- “HTTP + JSON‑LD” fast‑paths (like what we used for GMA) are **not reliable** on ABS‑CBN.

So the winning approach wasn’t “make Playwright stealthier forever” — it was: **stop depending on protected HTML**.

---

## 2) The Senior‑Dev Debugging Playbook We Used

### Step A — Prove the HTML is blocked (so we don’t chase the wrong fix)
Run this inside your worker container so you match the same environment:

```bash
docker compose exec worker sh -lc "python - <<'PY'
import requests
url='https://news.abs-cbn.com/news/business/2026/3/28/statement-of-the-members-of-the-abs-cbn-board-of-directors-2051'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'},timeout=25)
print('status=',r.status_code,'bytes=',len(r.text))
PY"
```

If you get `403`, that confirms: “HTTP‑first HTML parsing is a dead end”.

### Step B — Use Playwright only as a network microscope (not as the extractor)
Enable network debug while loading a real article. This logs JSON/XHR endpoints observed during navigation.

```bash
docker compose exec worker_headed sh -lc \
  "ABS_CBN_NETWORK_DEBUG=1 ABS_CBN_API_CONTENT_FASTPATH=0 ABS_CBN_DISABLE_DELAY=1 USE_HUMAN_DELAY=0 xvfb-run -a \
   python -c 'from app.scrapers.abs_cbn import ABSCBNScraper; ABSCBNScraper().scrape_latest(max_articles=1)'"
```

Note: you won’t “see a browser window” because:
- `xvfb-run` uses a **virtual** display inside the container, not your desktop display.

### Step C — Take any “real looking JSON” endpoint and test it without a browser
One endpoint family stood out and was reliably accessible:

- `https://od2-content-api.abs-cbn.com/prod/list/id/...`

Test it directly (fast, repeatable, no Chromium):

```bash
docker compose exec worker sh -lc "python - <<'PY'
import requests
u='https://od2-content-api.abs-cbn.com/prod/list/id/news?limit=3&offset=0'
r=requests.get(u,timeout=20)
print('status',r.status_code,'len',len(r.text))
j=r.json()
it=(j.get('listItem') or [None])[0]
print('keys',list(it.keys())[:12] if isinstance(it,dict) else None)
extra=(it.get('extra') or {}) if isinstance(it,dict) else {}
print('has_body_html', isinstance(it,dict) and isinstance(it.get('body_html'),str))
print('has_slug', isinstance(extra.get('slugline_url'),str) or isinstance(it.get('slugline_url'),str))
PY"
```

Breakthrough fields:
- `body_html` → full article body (HTML)
- `extra.slugline_url` (or `slugline_url`) → canonical URL path for the public site

This is the “GMA story payload” equivalent for ABS‑CBN — but *not* tied to protected HTML.

---

## 3) The New Architecture (Incremental + Canonical‑First)

ABS‑CBN now behaves like a “good citizen” scraper:

1) **Discover candidates without a browser**
   - API discovery: pull list pages from `od2-content-api.../list/id/*`
   - Optional RSS discovery: `https://news.abs-cbn.com/rss`

2) **Canonicalize + dedupe early**
   - Every URL is normalized via `app.core.url.canonicalize_url`.
   - Dedup happens during discovery, not only at DB insert time.

3) **DB preflight (big performance win)**
   - One Supabase query to check which candidate URLs already exist in `public.articles`.
   - Don’t open pages / don’t process items that are already in DB.

4) **API content fast‑path (the default)**
   - Convert `body_html` → clean text paragraphs.
   - Populate `title`, `content`, `category`, `published_at`.
   - Enforce a minimum content length (`ABS_CBN_API_MIN_BODY_CHARS`) and apply `SCRAPER_CONTENT_MAX_CHARS` truncation consistently.

5) **Playwright fallback (rare)**
   - Only used when the API payload is missing/too short, or when a format changes.
   - You can force this for debugging via env flags.

Result:
- Most runs are **headless + no browser** (low RAM, fast).
- Headed/Xvfb is kept as a fallback tool, not the default production dependency.

---

## 4) Implementation Map (Where to Look in the Code)

All in: `backend/app/scrapers/abs_cbn.py`

Key pieces:
- API discovery:
  - `ABS_CBN_API_DISCOVERY`
  - `ABS_CBN_API_LIST_URLS`
  - `_extract_api_item_url()` supports both `slugline_url` and `extra.slugline_url`
- API content fast‑path:
  - `ABS_CBN_API_CONTENT_FASTPATH`
  - `ABS_CBN_API_MIN_BODY_CHARS`
  - `_article_from_api_item()` (uses `body_html`)
- DB preflight + canonical dedupe:
  - `backend/app/scrapers/support/db_dedupe.py`
  - `filter_existing_article_urls(...)`
  - `unique_canonical_urls(...)`
- Safety/quality guardrails:
  - `_validate_url()` is **segment‑based** to avoid substring false positives (e.g. `stl` matching `mostly`).
  - Blocks obvious non‑articles (galleries/videos/tags/search/lotto, file extensions).
- Playwright performance knobs (only relevant for fallback):
  - Resource blocking envs: `ABS_CBN_BLOCK_IMAGES`, `ABS_CBN_BLOCK_FONTS`, `ABS_CBN_BLOCK_MEDIA`, `ABS_CBN_BLOCK_TRACKERS`, `ABS_CBN_BLOCK_STYLESHEETS`
  - Hydration wait tuning: `ABS_CBN_HYDRATION_TIMEOUT_MS`, `ABS_CBN_HYDRATION_MIN_PARAS`
- Debugging:
  - `ABS_CBN_NETWORK_DEBUG=1` logs JSON/XHR endpoints during a Playwright run

Routing:
- `backend/app/workers/celery_app.py`
  - ABS‑CBN routes to the normal `scrape` queue by default.
  - Force headed only when needed: `ABS_CBN_FORCE_HEADED=1`.
- `backend/app/api/scrape_router.py`
  - ABS‑CBN is no longer hard‑wired to a headed queue; it follows the routing above.

---

## 5) Recommended Env Defaults (Copy/Paste)

API‑first defaults (recommended):

```bash
ABS_CBN_API_DISCOVERY=1
ABS_CBN_API_CONTENT_FASTPATH=1
ABS_CBN_API_MIN_BODY_CHARS=600
ABS_CBN_RSS_DISCOVERY=1
ABS_CBN_FORCE_HEADED=0
```

List endpoints (comma‑separated):

```bash
ABS_CBN_API_LIST_URLS="https://od2-content-api.abs-cbn.com/prod/list/id/news?limit=60&offset=0,https://od2-content-api.abs-cbn.com/prod/list/id/business?limit=60&offset=0,https://od2-content-api.abs-cbn.com/prod/list/id/technology?limit=60&offset=0,https://od2-content-api.abs-cbn.com/prod/list/id/sports?limit=60&offset=0,https://od2-content-api.abs-cbn.com/prod/list/id/entertainment?limit=60&offset=0"
```

---

## 6) How to Test It (Quick Checks)

### A) Pure API run (no Xvfb, no browser)
```bash
docker compose exec worker sh -lc \
  "PLAYWRIGHT_HEADLESS=true ABS_CBN_API_DISCOVERY=1 ABS_CBN_API_CONTENT_FASTPATH=1 ABS_CBN_RSS_DISCOVERY=0 \
   python -c 'from app.scrapers.abs_cbn import ABSCBNScraper; r=ABSCBNScraper().scrape_latest(max_articles=3); print(r.metadata); print(\"articles=\",len(r.articles)); print(\"errors=\",r.errors);'"
```

Expected:
- `headless_mode: True`
- `articles` should be >0 when ABS‑CBN has new posts

### B) End‑to‑end queue test (API → insert into Supabase)
Queue a scrape:

```bash
curl -sS -X POST "http://localhost:8000/scrape/run" \
  -H "Content-Type: application/json" \
  -d '{"source":"abs_cbn"}'
```

Then follow the normal worker logs:

```bash
docker compose logs -f worker
```

Tip: if `inserted=0` but `skipped>0`, that’s usually **duplicates** (already in DB), not a scraper failure.

### C) Canary check (detect API shape changes early)
```bash
python backend/scripts/abs_cbn_api_canary.py
```

---

## 7) Ops Notes (RAM + What To Do With `worker_headed`)

### Why `worker_headed` uses so much RAM
Even when idle, a headed/Xvfb + Chromium‑ready environment can sit in the hundreds of MB to >1GB range (depends on concurrency and how the container is configured).

### Do we still need it?
Not for normal scraping anymore.
Keep `worker_headed` for:
- debugging (`ABS_CBN_NETWORK_DEBUG=1`)
- emergency fallback when ABS‑CBN changes the API and you need temporary “DOM fallback”

If you want to free RAM right now, stop it:
- `docker compose stop worker_headed`

---

## 8) Why This Approach Scales (Repeatable Pattern)

This ABS‑CBN work is the template:
1) Identify which **structured payload** the site uses (JSON‑LD, REST, GraphQL, `.gz` story blobs).
2) Make that the fast‑path (HTTP‑first, minimal parsing).
3) Preflight the DB to avoid wasting compute on duplicates.
4) Keep Playwright as a fallback + debugging tool, not the primary data path.
