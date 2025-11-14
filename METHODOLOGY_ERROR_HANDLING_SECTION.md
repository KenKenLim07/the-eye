# Methodology Section: Error Handling & Resilience

## Copy this section into your methodology document:

---

### **2.7 Error Handling and Resilience Mechanisms**

The system implements multi-layered error handling and resilience mechanisms to ensure continuous operation despite network failures, connection losses, and website structure changes.

#### **2.7.1 Network Error Handling**

**Multi-Tier Retry Architecture:**

- **Celery Task-Level Retries:** All scraping tasks are configured with automatic retry (max 3 attempts) using exponential backoff: `60 * (2^attempt)` seconds (60s, 120s, 240s).
- **Scraper-Level Request Retries:** Individual HTTP requests retry with progressive delays:
  - Exponential backoff: `(2^attempt) + random_jitter`
  - Connection timeouts: Randomized 5-12 second delays with multiplier
  - Maximum 3-5 retry attempts per URL depending on scraper

**HTTP Status Code Handling:**

- **HTTP 429 (Rate Limited):** Special handling with 10-20 second randomized wait; continues retry loop without counting as failure; rotates headers/User-Agent.
- **HTTP 502/503/504 (Server Errors):** Treated as transient errors with exponential backoff and retry.
- **HTTP 5xx (Server Errors):** All trigger retry with backoff; considered transient failures.
- **Connection Loss:** Catches `httpx.RequestError` (DNS failures, connection refused); applies exponential backoff; rotates User-Agent between retries.

**Playwright Navigation Resilience:**

- Primary: `domcontentloaded` wait strategy (faster, less timeout risk)
- Fallback: Default `load` navigation with reduced timeout (15s)
- Content waiting: Short timeout (5s) for content selectors; continues even if absent (graceful degradation)
- Browser context recreation on persistent failures (max 2 attempts per article)

#### **2.7.2 Website Structure Change Resilience**

**Multi-Tier Extraction Strategy:**

1. **Tier 1: Structured Data (JSON-LD)** — Primary source

   - Extracts from `<script type="application/ld+json">` tags
   - Targets `NewsArticle`, `Article`, `BlogPosting` schema types
   - Extracts `headline`, `datePublished`, `articleBody`
   - **Advantage:** Standardized format, less affected by CSS/styling changes

2. **Tier 2: CSS Selector Fallback Chains** — Secondary source

   - Each scraper defines ordered selector lists for each element type
   - Tries selectors in sequence until one succeeds
   - Example (Title): `["h1.entry-title", "h1", ".entry-title", "title"]`
   - Example (Content): `[".entry-content .entry-body p", ".entry-content p", "article p", "p"]`
   - Example (Date): `["time.article__date", ".article__date", "time", ".date"]`

3. **Tier 3: Content Filtering & Validation**
   - Removes unwanted elements before extraction: `nav`, `footer`, `aside`, `.ad`, `.comments`
   - Filters boilerplate text ("subscribe", "newsletter", "share this")
   - Validates extracted text (non-empty, minimum length)
   - Sanitizes output (removes scripts, normalizes whitespace)

**Graceful Degradation:**

- If title extraction fails → Article skipped (logged as error)
- If content extraction fails → Article skipped (logged as error)
- If date extraction fails → Uses current timestamp as fallback
- **Result:** System continues scraping other articles instead of crashing

**URL Validation Prevents False Positives:**

- Domain validation (must match source domain)
- Path pattern matching (requires date patterns or valid sections)
- Structural validation (minimum path segments, article-like slugs)
- Blacklist patterns (excludes `/feed/`, `/tag/`, `/author/`, `/search`)

**Error Logging for Monitoring:**

- Selector failures logged at debug level
- Extraction failures logged with article URL
- Success rate tracking per source
- Enables rapid identification of structure changes requiring selector updates

#### **2.7.3 Combined Resilience Example**

When a website experiences structure changes:

1. **JSON-LD extraction attempted first** (most reliable, standardized)
2. **If JSON-LD missing/invalid** → Falls back to CSS selector chain
3. **If primary selector fails** → Tries next selector in ordered list
4. **If all selectors fail** → Logs error, skips article, continues with next article
5. **Network errors trigger retries** with exponential backoff at both task and request levels

This multi-layered approach ensures continuous operation despite:

- Temporary website outages
- Network instability
- HTML structure updates
- CSS class/selector changes
- Rate limiting
- Server errors (5xx)

---

## Integration into Your Methodology:

Add this as **subsection 2.7** in your "Data Gathering and Analysis Workflow" section, or as a separate section after your main workflow description.

The detailed technical document (`ERROR_HANDLING_AND_RESILIENCE.md`) can serve as:

- Reference documentation
- Technical appendix to your thesis
- Developer documentation for future maintenance

