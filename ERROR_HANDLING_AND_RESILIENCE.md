# Error Handling and Website Structure Change Resilience

## Overview

The scraping system implements multi-layered error handling and structure change resilience through:

1. **Multi-tier retry logic** at both Celery task level and scraper level
2. **Exponential backoff** with randomized delays
3. **Selector fallback chains** for handling HTML structure changes
4. **Structured data extraction** (JSON-LD) as primary source with CSS selector fallbacks
5. **Graceful degradation** when extraction fails

---

## 1. Error Handling: Connection Loss & Network Failures

### 1.1 Multi-Layer Retry Architecture

#### **Layer 1: Celery Task-Level Retries**

All scraping tasks are configured with automatic retry on failure:

- **Max retries:** 3 attempts per task
- **Default retry delay:** 60 seconds base
- **Exponential backoff formula:** `countdown = 60 * (2 ** attempt_number)`
  - Attempt 1: 60 seconds
  - Attempt 2: 120 seconds
  - Attempt 3: 240 seconds

**Implementation:**

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_rappler_task(self):
    try:
        # Scraping logic
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {"ok": False, "error": str(e), "retries_exhausted": True}
```

#### **Layer 2: Scraper-Level Request Retries**

Each scraper implements its own retry logic for individual HTTP requests:

**Sunstar Scraper:**

- **Max retries:** 3 attempts per URL
- **Progressive delay:** `delay = random_delay * (attempt + 1)`
  - First attempt: 5-12 seconds random delay
  - Retry 1: 10-24 seconds (2x multiplier)
  - Retry 2: 15-36 seconds (3x multiplier)
- **Special handling for HTTP 429 (Rate Limiting):**
  - Additional wait: 5-10 seconds random
  - Continues retry loop without incrementing attempt counter

**Manila Times Scraper:**

- **Exponential backoff with jitter:** `wait_time = (2 ** attempt) + random.uniform(1, 3)`
  - Attempt 1: 2-5 seconds
  - Attempt 2: 4-7 seconds
  - Attempt 3: 8-11 seconds
- **Special handling for HTTP 502 (Bad Gateway):**
  - Recognizes 502 as transient error
  - Applies exponential backoff specifically for 502 errors

**Enhanced Retry Mixin (Advanced):**

- **Circuit breaker pattern:** Tracks failures per domain
- **Exponential backoff with randomization:**
  - `wait_time = (2 ** attempt) + random.uniform(2, 8)` for timeouts
  - `wait_time = (2 ** attempt) + random.uniform(1, 5)` for HTTP errors
- **Specific exception handling:**
  - `httpx.TimeoutException`: Exponential backoff
  - `httpx.HTTPStatusError`: Retryable status codes (5xx, 429)
  - `httpx.RequestError`: Generic network errors with retry
  - **Max retries:** 5 attempts (most conservative)

### 1.2 Network Error Handling

#### **Connection Timeout Handling**

- **Playwright timeouts:**
  - Default navigation timeout: 25,000ms (25 seconds)
  - Default operation timeout: 30,000ms (30 seconds)
  - Fallback strategy: If `domcontentloaded` fails, attempts full `load` with reduced timeout (15 seconds)

#### **Connection Loss Recovery**

- **Playwright page failures:**

  - Attempts retry with different wait strategy
  - Closes context and recreates browser context on persistent failure
  - Maximum 2 attempts per article before giving up

- **HTTPX request failures:**
  - Catches `httpx.RequestError` (connection refused, DNS failure, etc.)
  - Applies exponential backoff before retry
  - Rotates User-Agent between retries to avoid fingerprinting

#### **HTTP Status Code Handling**

**HTTP 200:** Success, returns response

**HTTP 429 (Rate Limited):**

- Special handling: Waits 10-20 seconds (randomized)
- Continues retry loop without counting as failure
- Rotates headers/User-Agent on next attempt

**HTTP 502/503/504 (Server Errors):**

- Treated as transient errors
- Applies exponential backoff
- Retries up to max attempts
- Rappler scraper: Specifically detects 502/503 and applies 5-12 second random delay

**HTTP 403 (Forbidden):**

- Rappler scraper: Raises custom exception `rappler_cooldown`
- Task-level retry will catch and retry after exponential backoff
- May indicate temporary IP block (handled by Celery retry)

**HTTP 5xx (Server Errors):**

- All 5xx errors trigger retry with backoff
- Considered transient failures
- Maximum retries applied

### 1.3 Error Logging & Monitoring

- **Error collection:** Each scraper maintains an `errors` list
- **Performance tracking:** Records duration, articles scraped, candidates found
- **Task status logging:** Celery tasks log to database via `finalize_run()` with status "error"
- **Structured error messages:** Format: `"{source}: {error_type}: {details}"`

---

## 2. Website Structure Change Resilience

### 2.1 Multi-Tier Selector Fallback System

#### **Tier 1: Structured Data Extraction (JSON-LD)**

**Primary extraction method** - Most reliable when available:

- Extracts from `<script type="application/ld+json">` tags
- Looks for `NewsArticle`, `Article`, or `BlogPosting` schema types
- Extracts: `headline`, `datePublished`, `articleBody`
- **Advantages:**
  - Structured, standardized format
  - Less likely to change with CSS/styling updates
  - Higher accuracy

**Implementation (Rappler/Manila Bulletin):**

```python
json_ld = self._extract_json_ld(soup)
title = json_ld.get("headline") or fallback_selectors or ""
content = json_ld.get("articleBody") or fallback_selectors or ""
```

#### **Tier 2: CSS Selector Fallback Chains**

Each scraper defines **ordered lists of selectors** for each element type, tried in sequence until one succeeds:

**Title Extraction (Inquirer):**

```python
"title": [
    "h1.entry-title",      # Most specific
    "h1",                  # Generic h1
    ".entry-title",        # Class-based
    "title"                # HTML title tag (last resort)
]
```

**Content Extraction (Inquirer):**

```python
"content": [
    ".entry-content .entry-body p",  # Most specific nested
    ".entry-content p",               # Parent container
    ".entry-body p",                 # Alternative container
    "article .entry-content p",      # Article-scoped
    ".post-content p",                # Generic post content
    ".article-content p",            # Generic article content
    ".content p",                     # Generic content
    "article p",                      # Article paragraphs
    "p"                               # All paragraphs (last resort)
]
```

**Published Date (PhilStar):**

```python
"published_date": [
    "time.article__date",    # Semantic HTML5
    ".article__date",         # Class-based
    "time",                   # Generic time element
    ".date"                   # Generic date class
]
```

#### **Tier 3: Extraction Method with Fallbacks**

Each scraper implements `_extract_with_fallbacks()` method:

**Implementation Pattern:**

```python
def _extract_with_fallbacks(self, soup: BeautifulSoup, selector_list: List[str]) -> Optional[str]:
    """Try each selector in order until one succeeds."""
    for selector in selector_list:
        try:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text:  # Valid non-empty result
                    return self._sanitize_text(text)
        except Exception:
            continue  # Try next selector
    return None  # All selectors failed
```

### 2.2 Content Extraction Resilience

#### **Multiple Extraction Strategies**

**Strategy 1: JSON-LD First (Rappler/Manila Bulletin)**

```python
title = json_ld.get("headline") or selector_fallback or ""
```

**Strategy 2: Selector Chain with Validation (Inquirer)**

- Tries selectors in order
- Validates extracted text (non-empty, minimum length)
- Sanitizes output (removes scripts, normalizes whitespace)

**Strategy 3: Content Container Filtering (Rappler)**

- Removes unwanted elements first:
  - `nav`, `footer`, `aside`, `.share`, `.social`, `.related`
  - `.newsletter`, `.subscribe`, `.ad`, `.advertisement`
  - `.comments`, `.author-info`, `.tags`, `.breadcrumbs`
- Then applies selector chain
- Filters boilerplate text (mentions of "subscribe", "newsletter", etc.)

**Strategy 4: Playwright Content Waiting (Manila Bulletin/Rappler)**

- Waits for content selectors to appear: `"article, .entry-content, .post-content"`
- Uses short timeout (5 seconds) - doesn't block if absent
- Falls back to immediate parsing if selectors don't appear

### 2.3 URL Validation & Filtering

#### **Multi-Level URL Validation**

Prevents scraping non-article pages even if structure changes:

**Level 1: Domain Validation**

```python
if not parsed.netloc.endswith('inquirer.net'):
    return False
```

**Level 2: Path Pattern Matching**

- Requires date patterns: `/20\d{2}/` (year)
- Requires valid section paths: `/news/`, `/nation/`, `/business/`
- Rejects section landing pages: `/latest/`, `/section/`, `/tag/`

**Level 3: Structural Validation**

- Minimum path segments (at least 2)
- Requires article-like slugs (hyphenated, >8 chars)
- Rejects utility pages: `/contact/`, `/about/`, `/search`

**Level 4: Blacklist Patterns**

```python
blacklist_patterns = [
    r"/feed/", r"/search", r"/tag/", r"/author/",
    r"/newsletter", r"/subscribe", r"/login",
    r"/wp-", r"/page/\d+/?$", r"/latest/$"
]
```

### 2.4 Playwright Navigation Resilience

#### **Multi-Strategy Page Loading**

When website structure changes affect loading:

**Strategy 1: Fast Loading (Primary)**

```python
page.goto(url, wait_until="domcontentloaded")
```

- Waits only for DOM to be ready
- Faster, less likely to timeout

**Strategy 2: Fallback Loading**

```python
try:
    page.goto(url, wait_until="domcontentloaded")
except Exception:
    page.goto(url)  # Default wait (load event)
    page.wait_for_load_state("domcontentloaded", timeout=15_000)
```

- If first attempt fails, tries default navigation
- Then explicitly waits for DOM with shorter timeout

**Strategy 3: Content Waiting**

```python
page.wait_for_selector("article, .entry-content, .post-content", timeout=5_000)
```

- Waits for content containers to appear
- Short timeout prevents blocking
- Continues even if selectors absent (graceful degradation)

### 2.5 Error Handling for Structure Changes

#### **Graceful Degradation**

- If title extraction fails: Article is skipped (logged as error)
- If content extraction fails: Article is skipped (logged as error)
- If date extraction fails: Uses current timestamp as fallback
- **Result:** System continues scraping other articles instead of crashing

#### **Error Logging for Monitoring**

- Logs selector failures at debug level
- Logs extraction failures with article URL
- Tracks success rate per source
- Enables identification of structure changes requiring selector updates

#### **Manual Selector Updates**

When selectors fail:

1. Errors appear in logs with article URLs
2. Developer can inspect failed URLs
3. Update selector lists with new patterns
4. No code logic changes needed - just selector configuration updates

---

## 3. Combined Resilience Example

**Rappler Scraper - Complete Flow:**

1. **Celery Task Level:**

   - Task fails → Retry after 60s, 120s, 240s (exponential)

2. **Browser Navigation:**

   - `domcontentloaded` fails → Try default navigation
   - Default navigation fails → Close context, retry once more
   - HTTP 403/429 detected → Raise exception, trigger task retry

3. **Content Extraction:**

   - Try JSON-LD first (`headline`, `articleBody`)
   - If JSON-LD missing/invalid → Try CSS selector chain
   - If title selector fails → Try next selector in list
   - If all selectors fail → Log error, skip article, continue

4. **Request-Level Retries:**
   - HTTP 429 → Wait 10-20s, retry with new headers
   - HTTP 502/503 → Wait 5-12s, retry
   - Connection timeout → Exponential backoff, retry
   - Max 3 attempts before logging error

---

## 4. Key Resilience Features Summary

### **Error Handling:**

✅ Multi-layer retry (Celery + Scraper)  
✅ Exponential backoff with randomization  
✅ Specific handling for HTTP 429, 502, 503, 5xx  
✅ Connection timeout recovery  
✅ Browser context recreation on persistent failures  
✅ Circuit breaker pattern (advanced mixin)  
✅ Comprehensive error logging

### **Structure Change Resilience:**

✅ JSON-LD structured data as primary source  
✅ Multi-tier CSS selector fallback chains  
✅ Content container filtering before extraction  
✅ Multiple extraction strategies per element  
✅ Graceful degradation (skip article, don't crash)  
✅ URL validation prevents non-article scraping  
✅ Playwright multi-strategy page loading  
✅ Error logging for selector failure monitoring

This multi-layered approach ensures the system continues operating even when:

- Websites experience temporary outages
- Network connections are unstable
- Website HTML structure is updated
- CSS classes/selectors change
- Rate limiting occurs
- Server errors (5xx) happen

