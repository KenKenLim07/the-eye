import time
import logging
import random
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from playwright.sync_api import Browser
from bs4 import BeautifulSoup
import requests
import html as _html
from app.pipeline.normalize import build_article, NormalizedArticle
from app.scrapers.base import launch_browser
from datetime import datetime
import re
from app.scrapers.utils import resolve_category_pair
from app.scrapers.support.db_dedupe import (
    filter_existing_article_urls,
    unique_canonical_urls,
)
from app.scrapers.support.structured_data import extract_json_ld_newsarticle
from app.scrapers.support.network_debug import install_json_response_logger
# Feature flags (env-driven) for gradual rollout
import os

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default

USE_ADV_HEADERS = _env_flag("USE_ADV_HEADERS", False)
USE_HUMAN_DELAY = _env_flag("USE_HUMAN_DELAY", False)
USE_URL_FILTER = _env_flag("USE_URL_FILTER", False)
SCRAPER_CONTENT_MAX_CHARS = _env_int("SCRAPER_CONTENT_MAX_CHARS", 8000)

# Default ON: safe HTTP-first with Playwright fallback.
GMA_HTTP_FASTPATH = _env_flag("GMA_HTTP_FASTPATH", True)
GMA_HTTP_DISCOVERY = _env_flag("GMA_HTTP_DISCOVERY", True)
GMA_NETWORK_DEBUG = _env_flag("GMA_NETWORK_DEBUG", False)
GMA_NETWORK_DEBUG_MAX = _env_int("GMA_NETWORK_DEBUG_MAX", 30)
GMA_HTTP_MIN_BODY_CHARS = _env_int("GMA_HTTP_MIN_BODY_CHARS", 600)
GMA_HTTP_MAX_EXCERPT_CHARS = _env_int("GMA_HTTP_MAX_EXCERPT_CHARS", 5000)
GMA_STORY_API_FASTPATH = _env_flag("GMA_STORY_API_FASTPATH", True)
GMA_STORY_API_CODES = os.getenv("GMA_STORY_API_CODES", "227,394").strip()
GMA_HTTP_TIMEOUT_CONNECT_S = _env_int("GMA_HTTP_TIMEOUT_CONNECT_S", 5)
GMA_HTTP_TIMEOUT_READ_S = _env_int("GMA_HTTP_TIMEOUT_READ_S", 15)

# Optional advanced utils
try:
    from app.scrapers.utils import (
        get_advanced_stealth_headers,
        get_human_like_delay,
        is_valid_news_url,
    )
except Exception:
    get_advanced_stealth_headers = None
    get_human_like_delay = None
    is_valid_news_url = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class GMAScraper:
    """Stealth scraper for GMA News Online (v1)."""

    BASE_URL = "https://www.gmanetwork.com"
    START_PATHS = [
        "/news/",
        "/news/topstories/",
        "/news/money/",
        "/news/sports/",
        "/news/lifestyle/",
        "/news/scitech/",
    ]

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    MIN_DELAY = 12.0
    MAX_DELAY = 25.0

    SELECTORS = {
        "article_links": [
            "article h3 a",
            ".story-title a",
            ".latest__list a",
            "h3 a",
            "a[href*='/news/']",
        ],
        "title": [
            "h1.article__title",
            "h1.entry-title",
            "h1",
            ".story__title",
            ".article-title",
            "title"
        ],
        "content": [
            ".article__content p",
            ".story__content p",
            ".article-content p",
            ".post-content p",
            ".article-body p",
            ".story-content p",
            ".content__article p",
            "article p",
            "p",
        ],
        "published_date": [
            "time[datetime]",
            ".article__date time",
            ".date",
            "time",
            ".article__meta",
        ]
    }

    def _human_delay(self):
        if USE_HUMAN_DELAY and get_human_like_delay is not None:
            delay = get_human_like_delay()
        else:
            delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"GMA v1: waiting {delay:.1f}s before next request (stealth)")
        time.sleep(delay)

    def _validate_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and parsed.netloc
        except Exception:
            return False

    def _is_probable_article(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            path = parsed.path or ""
            if not path.startswith("/news/"):
                return False
            # Explicitly skip archive/listing pages that look like articles by URL shape
            # (e.g. /news/archives/sports-basketball).
            if "/news/archives" in path.rstrip("/"):
                return False
            if USE_URL_FILTER and is_valid_news_url is not None:
                # Use advanced validator with domain guard
                if not is_valid_news_url(url, "gmanetwork.com"):
                    return False
                # Passed advanced checks
                return True
            # Legacy checks (fallback)
            segments = [seg for seg in path.split('/') if seg]
            blacklist = {"photo", "photos", "video", "videos", "balitambayan", "cbb", "lotto", "opinion", "editorial", "archives"}
            if any(seg in blacklist for seg in segments):
                return False
            return len(segments) >= 3
        except Exception:
            return False

    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        # Normalize HTML entities (e.g. &#039;, &lt;p&gt;...) first.
        try:
            text = _html.unescape(text)
        except Exception:
            pass

        # Remove obvious script/style payloads and unsafe URI schemes.
        text = re.sub(r"(?is)<\s*(script|style)\b.*?>.*?<\s*/\s*\1\s*>", " ", text)
        text = text.replace("javascript:", "").replace("data:", "")

        # Some fast-path payloads include HTML fragments (often in JSON-LD articleBody).
        # Convert to plain text instead of escaping, so we don't leak tags into the UI.
        if "<" in text and ">" in text:
            try:
                soup = BeautifulSoup(text, "html.parser")
                text = soup.get_text(" ", strip=True)
            except Exception:
                pass

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _extract_with_fallbacks(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el:
                    val = el.get_text().strip()
                    if val:
                        return self._sanitize_text(val)
            except Exception:
                continue
        return None

    def _extract_content(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        parts: List[str] = []
        # Blacklist boilerplate/ads/lotto instructions commonly embedded in GMA pages
        blacklist = re.compile(r"(how\s+to\s+play|pcso|\b4\s*-?\s*digit\b|lotto|lucky\s*pick|permutations?\s+of\s+the\s+number|advertisement)", re.IGNORECASE)
        seen: set[str] = set()

        def _collect_for_selector(selector: str) -> List[str]:
            out: List[str] = []
            for el in soup.select(selector):
                text = el.get_text().strip()
                if not text:
                    continue
                if text in seen:
                    continue
                if len(text) <= 50:
                    continue
                if text.upper().startswith("ADVERTISEMENT"):
                    continue
                if blacklist.search(text):
                    continue
                seen.add(text)
                out.append(text)
            return out

        # Prefer the first selector that yields a credible body (avoid mixing in unrelated <p> text).
        for sel in self.SELECTORS["content"]:
            try:
                candidate = _collect_for_selector(sel)
                if not parts and candidate:
                    parts = candidate
                if len(candidate) >= 3 or sum(len(x) for x in candidate) >= 900:
                    parts = candidate
                    break
            except Exception:
                continue
        if not parts:
            for p in soup.find_all('p'):
                t = p.get_text().strip()
                if not t:
                    continue
                if t in seen:
                    continue
                seen.add(t)
                if len(t) <= 30:
                    continue
                if t.upper().startswith("ADVERTISEMENT"):
                    continue
                if blacklist.search(t):
                    continue
                parts.append(t)
        if parts:
            combined = ' '.join(parts)
            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(combined) > SCRAPER_CONTENT_MAX_CHARS:
                combined = combined[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
            logger.info(f"GMA v1: content parts={len(parts)}, length={len(combined)}")
            return combined
        logger.warning(f"GMA v1: no content extracted for {url}")
        return None

    def _parse_published(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        txt = raw.strip()
        # JSON-LD is usually ISO; accept it first.
        try:
            dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
            return dt.isoformat()
        except Exception:
            pass
        txt = re.sub(r"^(Published|Updated)\s*", "", txt, flags=re.IGNORECASE)
        txt = re.sub(r"[•|]", " ", txt).strip()
        candidates = [
            (txt, "%B %d, %Y %I:%M%p"),
            (txt.replace(" at ", " "), "%B %d, %Y %I:%M%p"),
            (txt, "%B %d, %Y"),
        ]
        for val, fmt in candidates:
            try:
                norm = re.sub(r"\s+", " ", val)
                dt = datetime.strptime(norm, fmt)
                return dt.isoformat()
            except Exception:
                continue
        return None

    def _http_headers(self) -> dict:
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-PH,en;q=0.9",
            "Referer": urljoin(self.BASE_URL, "/news/"),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def _http_timeout(self) -> tuple[int, int]:
        return (max(1, int(GMA_HTTP_TIMEOUT_CONNECT_S)), max(2, int(GMA_HTTP_TIMEOUT_READ_S)))

    def _get_http_session(self) -> requests.Session:
        # Keep-alive helps a bit on slow connections (reused TLS/session).
        s = getattr(self, "_http_session", None)
        if s is None:
            s = requests.Session()
            setattr(self, "_http_session", s)
        return s

    def _discover_urls_http(self, max_articles: int) -> tuple[list[str], dict]:
        """
        Discovery fast-path: fetch section pages over HTTP and extract candidate links.
        Falls back to Playwright discovery if this yields nothing (or errors).
        """
        urls: list[str] = []
        seen: set[str] = set()
        try:
            try:
                max_paths = int(os.getenv("GMA_MAX_START_PATHS", str(len(self.START_PATHS))))
            except Exception:
                max_paths = len(self.START_PATHS)
            paths_scanned = 0
            headers = self._http_headers()
            sess = self._get_http_session()
            timeout = self._http_timeout()

            for path in self.START_PATHS[:max_paths]:
                section_url = urljoin(self.BASE_URL, path)
                try:
                    r = sess.get(section_url, headers=headers, timeout=timeout)
                    if r.status_code >= 400:
                        continue
                    soup = BeautifulSoup(r.text or "", "html.parser")
                    seeded = self._extract_article_links(soup)
                    new_count = 0
                    for u in seeded:
                        if u in seen:
                            continue
                        seen.add(u)
                        urls.append(u)
                        new_count += 1
                    paths_scanned += 1
                    logger.info("GMA HTTP discovery: seeded %s new URLs from %s", new_count, path)
                    if len(urls) >= max_articles * 4:
                        break
                except Exception:
                    continue
                # keep HTTP discovery lightweight; avoid long stealth sleeps
                time.sleep(random.uniform(0.15, 0.45))

            return urls, {
                "method": "http",
                "paths_configured": min(max_paths, len(self.START_PATHS)),
                "paths_scanned": paths_scanned,
                "urls_discovered": len(urls),
            }
        except Exception as e:
            return [], {"method": "http", "error": str(e)}

    def _scrape_article_http(self, url: str) -> Optional[NormalizedArticle]:
        """
        Fast-path: fetch HTML over HTTP and use JSON-LD (no browser rendering).
        Falls back to Playwright path if JSON-LD is missing/too short.
        """
        try:
            # Hard guardrail: never scrape archive/listing URLs as articles.
            if not self._is_probable_article(url):
                return None
            headers = self._http_headers()
            sess = self._get_http_session()
            timeout = self._http_timeout()

            # Fastest attempt: if URL contains a numeric story id, try the compact story API directly.
            story_id = self._extract_story_id_from_url(url)
            if story_id and GMA_STORY_API_FASTPATH:
                direct = self._try_fetch_story_api_from_id(story_id, headers=headers, timeout=timeout)
                if direct:
                    title = direct.get("title") or ""
                    body = direct.get("body") or ""
                    published_raw = direct.get("published_raw") or None
                    if title and body and len(body) >= max(0, GMA_HTTP_MIN_BODY_CHARS):
                        try:
                            api_url = direct.get("api_url")
                            if api_url:
                                logger.info("GMA fast-path (story_api): %s", api_url)
                        except Exception:
                            pass
                        if SCRAPER_CONTENT_MAX_CHARS > 0 and len(body) > SCRAPER_CONTENT_MAX_CHARS:
                            body = body[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
                        # Infer category from URL structure (no extra request).
                        soup_min = BeautifulSoup("", "html.parser")
                        norm_cat, raw_cat = self._extract_gma_category(url, soup_min)
                        return build_article(
                            source="GMA",
                            title=self._sanitize_text(title),
                            url=url,
                            content=self._sanitize_text(body),
                            category=norm_cat,
                            published_at=self._parse_published(published_raw),
                            raw_category=raw_cat,
                        )

            resp = sess.get(url, headers=headers, timeout=timeout)
            if resp.status_code >= 400:
                return None
            html = resp.text or ""
            if not html:
                return None
            soup = BeautifulSoup(html, "html.parser")
            jsonld = extract_json_ld_newsarticle(soup) or None

            title = ""
            body = ""
            published_raw = None
            if jsonld:
                title = _html.unescape(str(jsonld.get("headline") or "")).strip()
                body = _html.unescape(str(jsonld.get("articleBody") or "")).strip()
                published_raw = jsonld.get("datePublished") or None

            # If JSON-LD looks like an excerpt (common: ends with .../… while still short),
            # prefer the Playwright extractor which often yields the full body.
            jsonld_usable = bool(title and body and len(body) >= max(0, GMA_HTTP_MIN_BODY_CHARS))
            if jsonld_usable and re.search(r"(\.\.\.|…)\s*$", body) and (
                (SCRAPER_CONTENT_MAX_CHARS <= 0 or len(body) < SCRAPER_CONTENT_MAX_CHARS)
                and len(body) <= max(0, GMA_HTTP_MAX_EXCERPT_CHARS)
            ):
                jsonld_usable = False

            if not jsonld_usable and GMA_STORY_API_FASTPATH:
                story = self._try_fetch_story_api(html, headers=headers)
                if story:
                    title = story.get("title") or title
                    body = story.get("body") or body
                    published_raw = story.get("published_raw") or published_raw

            if not title or not body:
                return None
            if len(body) < max(0, GMA_HTTP_MIN_BODY_CHARS):
                return None

            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(body) > SCRAPER_CONTENT_MAX_CHARS:
                body = body[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"

            published_iso = self._parse_published(published_raw)
            norm_cat, raw_cat = self._extract_gma_category(url, soup)
            return build_article(
                source="GMA",
                title=self._sanitize_text(title),
                url=url,
                content=self._sanitize_text(body),
                category=norm_cat,
                published_at=published_iso,
                raw_category=raw_cat,
            )
        except Exception:
            return None

    def _extract_story_id_from_url(self, url: str) -> Optional[str]:
        try:
            m = re.search(r"/news/(?:[^/]+/){1,3}(\d{5,})/", url or "")
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def _try_fetch_story_api_from_id(self, story_id: str, *, headers: dict, timeout: tuple[int, int]) -> Optional[dict]:
        """
        Try fetching story blobs by id using known GMA "site codes" (small list, fast).
        Example observed: https://data.gmanetwork.com/227/gno/story/981722.gz
        """
        try:
            raw_codes = [c.strip() for c in (GMA_STORY_API_CODES or "").split(",") if c.strip()]
            codes = [c for c in raw_codes if c.isdigit()]
            if not codes:
                return None
            sess = self._get_http_session()
            for code in codes:
                api_url = f"https://data.gmanetwork.com/{code}/gno/story/{story_id}.gz"
                try:
                    r = sess.get(api_url, headers=headers, timeout=timeout)
                    if r.status_code != 200:
                        continue
                    try:
                        data = r.json()
                    except Exception:
                        continue
                    extracted = self._extract_story_from_api_json(data)
                    if extracted and extracted.get("body"):
                        extracted["api_url"] = api_url
                        return extracted
                except Exception:
                    continue
        except Exception:
            return None
        return None

    def _try_fetch_story_api(self, html: str, *, headers: dict) -> Optional[dict]:
        """
        GMA pages often request a story JSON payload from data.gmanetwork.com.
        If we can find that URL in the HTML, fetch it directly and extract the body text.
        """
        try:
            if not html:
                return None
            # Example observed: https://data.gmanetwork.com/227/gno/story/981722.gz
            m = re.search(r"https://data\.gmanetwork\.com/\d+/gno/story/\d+\.gz", html)
            if not m:
                return None
            api_url = m.group(0)
            r = requests.get(api_url, headers=headers, timeout=(8, 25))
            if r.status_code >= 400:
                return None
            try:
                data = r.json()
            except Exception:
                return None
            extracted = self._extract_story_from_api_json(data)
            if not extracted:
                return None
            extracted["api_url"] = api_url
            return extracted
        except Exception:
            return None

    def _extract_story_from_api_json(self, data: Any) -> Optional[dict]:
        """
        Best-effort extraction from GMA story JSON blobs.
        Returns {"title": str|None, "body": str|None, "published_raw": str|None}
        """
        if data is None:
            return None

        def _maybe_text(v: Any) -> str:
            if not isinstance(v, str):
                return ""
            return _html.unescape(v).strip()

        # Gather candidate strings by key name
        candidates: list[tuple[str, str]] = []

        def _walk(obj: Any, key_hint: str = ""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    kh = f"{key_hint}.{k}" if key_hint else str(k)
                    _walk(v, kh)
                return
            if isinstance(obj, list):
                for it in obj:
                    _walk(it, key_hint)
                return
            if isinstance(obj, str):
                txt = _maybe_text(obj)
                if txt:
                    candidates.append((key_hint, txt))

        _walk(data)

        # Prefer body-ish keys with long content
        body_key_re = re.compile(r"(articlebody|article_body|storybody|story_body|article|story|content|body|html)", re.IGNORECASE)
        title_key_re = re.compile(r"(headline|title)", re.IGNORECASE)
        published_key_re = re.compile(r"(datepublished|published|created|timestamp|date)", re.IGNORECASE)

        title = ""
        published_raw: Optional[str] = None

        for k, v in candidates:
            if not title and title_key_re.search(k) and 10 <= len(v) <= 250:
                title = v
                break

        # Extract body: prioritize HTML with <p>, else long plain text.
        body = ""
        scored: list[tuple[int, str]] = []
        for k, v in candidates:
            if not body_key_re.search(k):
                continue
            score = 0
            if "<p" in v.lower() or "</p>" in v.lower():
                score += 50
            score += min(len(v) // 200, 50)
            scored.append((score, v))
        if scored:
            scored.sort(key=lambda t: t[0], reverse=True)
            body = scored[0][1]

        # If body is HTML, strip to paragraphs.
        if body and ("<" in body and ">" in body):
            try:
                soup = BeautifulSoup(body, "html.parser")
                parts: list[str] = []
                for p in soup.find_all("p"):
                    t = p.get_text(" ", strip=True)
                    if t and len(t) > 30:
                        parts.append(t)
                if parts:
                    body = " ".join(parts)
            except Exception:
                pass

        # Published: pick the first plausible date-ish string.
        for k, v in candidates:
            if published_key_re.search(k) and 8 <= len(v) <= 40:
                published_raw = v
                break

        if not body:
            return None
        return {"title": title or None, "body": body or None, "published_raw": published_raw}

    def _new_context(self, browser: Browser):
        return browser.new_context(
            user_agent=(get_advanced_stealth_headers()["User-Agent"] if (USE_ADV_HEADERS and get_advanced_stealth_headers is not None) else self.USER_AGENT),
            locale='en-PH',
            viewport={"width": 1366, "height": 768},
            java_script_enabled=True,
        )

    def _harden_page(self, page):
        # Block heavy/static resources and 3rd-party domains
        try:
            allowed_host = urlparse(self.BASE_URL).netloc
            allowed_apex = ".".join((allowed_host or "").split(".")[-2:])
            blocked_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".css", ".woff", ".woff2", ".ttf", ".otf")
            page.route("**/*", lambda route: (
                route.abort()
                if (route.request.url.lower().endswith(blocked_extensions))
                or (
                    urlparse(route.request.url).netloc
                    and allowed_apex
                    and not urlparse(route.request.url).netloc.endswith(allowed_apex)
                )
                else route.continue_()
            ))
        except Exception:
            pass

    def _harden_context(self, context):
        # Same logic as _harden_page, but applied once per context (more efficient).
        try:
            allowed_host = urlparse(self.BASE_URL).netloc
            allowed_apex = ".".join((allowed_host or "").split(".")[-2:])
            blocked_extensions = (
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
                ".css", ".woff", ".woff2", ".ttf", ".otf",
            )

            def _handler(route):
                try:
                    u = (route.request.url or "").lower()
                    if u.endswith(blocked_extensions):
                        return route.abort()
                    host = urlparse(route.request.url).netloc
                    # Allow first-party + subdomains (e.g., api.gmanetwork.com). Block true 3rd-party.
                    if host and allowed_apex and not host.endswith(allowed_apex):
                        return route.abort()
                except Exception:
                    pass
                return route.continue_()

            context.route("**/*", _handler)
        except Exception:
            pass

    def _set_headers(self, page):
        if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
            headers = get_advanced_stealth_headers()
            # Ensure referer points to news
            headers.setdefault('Referer', urljoin(self.BASE_URL, '/news/'))
            page.set_extra_http_headers(headers)
        else:
            page.set_extra_http_headers({
                'User-Agent': self.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-PH,en;q=0.9',
                'Connection': 'keep-alive',
                'Referer': urljoin(self.BASE_URL, '/news/'),
                'Upgrade-Insecure-Requests': '1',
            })

    def _extract_article_links(self, soup: BeautifulSoup) -> List[str]:
        urls = []
        seen = set()
        for sel in self.SELECTORS["article_links"]:
            try:
                for a in soup.select(sel):
                    href = a.get('href')
                    if not href:
                        continue
                    full = urljoin(self.BASE_URL, href)
                    if full in seen:
                        continue
                    if self._validate_url(full) and self._is_probable_article(full):
                        urls.append(full)
                        seen.add(full)
            except Exception:
                continue
        return urls

    def _goto_with_retry(self, page, url: str, wait_until: str = 'domcontentloaded') -> bool:
        try:
            page.goto(url, wait_until=wait_until)
            return True
        except Exception:
            try:
                page.goto(url)
                page.wait_for_load_state("domcontentloaded", timeout=15_000)
                return True
            except Exception:
                return False

    def _extract_gma_category(self, url: str, soup: BeautifulSoup) -> Tuple[str, Optional[str]]:
        """Extract category specifically for GMA's structure."""
        raw_category = None
        
        # 1. Try to extract from URL structure first (most reliable for GMA)
        if url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split('/') if p]
                
                if path_parts and len(path_parts) >= 2:
                    # GMA URLs: /news/topstories/nation/... or /news/business/... or /news/sports/...
                    if path_parts[0] == 'news' and len(path_parts) > 1:
                        main_category = path_parts[1].lower()
                        category_map = {
                            'topstories': 'News',
                            'business': 'Business',
                            'sports': 'Sports',
                            'entertainment': 'Entertainment',
                            'world': 'World',
                            'lifestyle': 'Lifestyle',
                            'opinion': 'Opinion',
                            'nation': 'Nation',
                            'politics': 'Politics',
                            'metro': 'Metro',
                            'cebu': 'Cebu',
                            'davao': 'Davao',
                            'bohol': 'Bohol',
                            'pampanga': 'Pampanga',
                            'baguio': 'Baguio',
                            'zamboanga': 'Zamboanga',
                            'iloilo': 'Iloilo',
                            'tacloban': 'Tacloban',
                            'general-santos': 'General Santos',
                            'lotto': 'Lotto',  # GMA has lotto results
                            'weather': 'Weather',
                            'technology': 'Technology',
                            'health': 'Health',
                            'education': 'Education'
                        }
                        
                        if main_category in category_map:
                            raw_category = category_map[main_category]
                        
                        # For topstories, check the sub-category
                        if main_category == 'topstories' and len(path_parts) > 2:
                            sub_category = path_parts[2].lower()
                            if sub_category in category_map:
                                raw_category = category_map[sub_category]
            except Exception:
                pass
        
        # 2. Extract from meta tags (GMA uses standard meta tags)
        if not raw_category:
            try:
                # Check for article:section meta tag
                meta_section = soup.find('meta', property='article:section')
                if meta_section and meta_section.get('content'):
                    raw_category = meta_section.get('content').strip()
                
                # Check for og:type and other meta tags
                if not raw_category:
                    meta_type = soup.find('meta', property='og:type')
                    if meta_type and meta_type.get('content') == 'article':
                        # Try to extract from breadcrumbs or other indicators
                        pass
            except Exception:
                pass
        
        # 3. Extract from breadcrumbs (if available)
        if not raw_category:
            try:
                for selector in ['nav.breadcrumb a', '.breadcrumb a', '.breadcrumbs a', 'ol.breadcrumb li a', '.breadcrumb-list a']:
                    breadcrumb = soup.select_one(selector)
                    if breadcrumb:
                        text = breadcrumb.get_text(strip=True)
                        if text and text.lower() not in ['home', 'gma', 'gmanetwork', 'news']:
                            raw_category = text
                            break
            except Exception:
                pass
        
        # 4. Extract from page title (fallback)
        if not raw_category:
            try:
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text()
                    # Look for category indicators in title
                    if '| GMA News Online' in title_text:
                        # Extract category from title structure
                        parts = title_text.split('|')
                        if len(parts) > 1:
                            category_part = parts[1].strip()
                            if category_part and category_part != 'GMA News Online':
                                raw_category = category_part
            except Exception:
                pass
        
        # Normalize the category
        if raw_category:
            # Clean up the category name
            raw_category = raw_category.strip().title()
            # Map common variations
            if raw_category.lower() in ['topstories', 'top stories', 'headlines']:
                normalized = 'News'
            elif raw_category.lower() in ['business', 'biz', 'economy']:
                normalized = 'Business'
            elif raw_category.lower() in ['sports', 'sport']:
                normalized = 'Sports'
            elif raw_category.lower() in ['nation', 'national', 'politics']:
                normalized = 'Nation'
            elif raw_category.lower() in ['world', 'international']:
                normalized = 'World'
            elif raw_category.lower() in ['entertainment', 'showbiz']:
                normalized = 'Entertainment'
            elif raw_category.lower() in ['lifestyle', 'life']:
                normalized = 'Lifestyle'
            elif raw_category.lower() in ['opinion', 'editorial']:
                normalized = 'Opinion'
            elif raw_category.lower() in ['lotto', 'lottery']:
                normalized = 'Lotto'
            elif raw_category.lower() in ['weather', 'climate']:
                normalized = 'Weather'
            elif raw_category.lower() in ['technology', 'tech']:
                normalized = 'Technology'
            elif raw_category.lower() in ['health', 'medical']:
                normalized = 'Health'
            elif raw_category.lower() in ['education', 'school']:
                normalized = 'Education'
            else:
                normalized = raw_category
        else:
            normalized = 'General'
            raw_category = None
        
        return normalized, raw_category


    def _scrape_article(self, url: str, context) -> Optional[NormalizedArticle]:
        page = None
        try:
            # Hard guardrail: never scrape archive/listing URLs as articles.
            if not self._is_probable_article(url):
                return None
            page = context.new_page()
            self._set_headers(page)
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)
            dump_json = install_json_response_logger(
                page,
                enabled=GMA_NETWORK_DEBUG,
                max_items=max(1, GMA_NETWORK_DEBUG_MAX),
            )
            ok = self._goto_with_retry(page, url, wait_until='domcontentloaded')
            if not ok:
                return None
            try:
                page.wait_for_selector('h1', timeout=8000)
            except:
                pass
            # GMA pages sometimes hydrate/replace article bodies after DOMContentLoaded.
            # Waiting briefly for network to settle and for multiple paragraphs to appear
            # reduces "excerpt-only" captures (which often end with .../…).
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            try:
                page.wait_for_function(
                    """() => {
                      const sels = [
                        '.article__content p',
                        '.story__content p',
                        '.article-content p',
                        '.article-body p',
                        '.content__article p',
                      ];
                      return sels.some((s) => document.querySelectorAll(s).length >= 4);
                    }""",
                    timeout=8000,
                )
            except Exception:
                pass
            soup = BeautifulSoup(page.content(), 'html.parser')
            if GMA_NETWORK_DEBUG:
                try:
                    rows = dump_json()
                    if rows:
                        logger.info("GMA network debug (captured=%s, showing up to 10): %s", len(rows), rows[: min(10, len(rows))])
                    else:
                        logger.info("GMA network debug: no JSON/XHR responses captured")
                except Exception:
                    pass
            title = self._extract_with_fallbacks(soup, self.SELECTORS["title"]) or ""
            if not title:
                return None
            # Skip lotto-related posts by title keywords
            if re.search(r"\b(lotto|swertres|stl|4d|3d|6/\d{2}|pcso)\b", title, re.IGNORECASE):
                return None
            content = self._extract_content(soup, url)
            # Retry once if it still looks like an excerpt (common: ends with ... / …).
            if content and re.search(r"(\.\.\.|…)\s*$", content) and len(content) < max(800, SCRAPER_CONTENT_MAX_CHARS - 50):
                try:
                    page.wait_for_timeout(1500)
                except Exception:
                    pass
                try:
                    page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
                soup2 = BeautifulSoup(page.content(), "html.parser")
                content2 = self._extract_content(soup2, url)
                if content2 and len(content2) > len(content) + 200:
                    content = content2
                    soup = soup2

            raw_published = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"]) or None
            published_iso = self._parse_published(raw_published)
            norm_cat, raw_cat = self._extract_gma_category(url, soup)
            article = build_article(
                source="GMA",
                title=title,
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_iso,
                raw_category=raw_cat,
            )
            return article
        except Exception as e:
            logger.error(f"GMA v1: failed {url}: {e}")
            return None
        finally:
            try:
                if page is not None:
                    page.close()
            except Exception:
                pass

    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        start = time.time()
        articles: List[NormalizedArticle] = []
        errors: List[str] = []
        discovery_existing_urls: set[str] = set()
        discovery_meta: dict[str, Any] = {}
        logger.info(f"GMA v1: flags USE_ADV_HEADERS={USE_ADV_HEADERS}, USE_HUMAN_DELAY={USE_HUMAN_DELAY}, USE_URL_FILTER={USE_URL_FILTER}")
        try:
            urls: List[str] = []
            if GMA_HTTP_FASTPATH and GMA_HTTP_DISCOVERY:
                t0 = time.time()
                urls, discovery_meta = self._discover_urls_http(max_articles=max_articles)
                discovery_meta["discovery_s"] = round(time.time() - t0, 2)

            # If HTTP discovery found nothing (or disabled), use Playwright discovery.
            if not urls:
                with launch_browser() as browser:
                    context = self._new_context(browser)
                    self._harden_context(context)
                    page = context.new_page()
                    self._set_headers(page)
                    page.set_default_timeout(30000)
                    page.set_default_navigation_timeout(30000)

                    resp = None
                    seen_urls: set[str] = set()
                    try:
                        max_paths = int(os.getenv("GMA_MAX_START_PATHS", str(len(self.START_PATHS))))
                    except Exception:
                        max_paths = len(self.START_PATHS)
                    paths_scanned = 0
                    for path in self.START_PATHS[:max_paths]:
                        try:
                            ok = self._goto_with_retry(page, urljoin(self.BASE_URL, path), wait_until='domcontentloaded')
                            if ok:
                                resp = type('obj', (), {'status': 200})()
                                paths_scanned += 1
                                soup = BeautifulSoup(page.content(), 'html.parser')
                                seeded_urls = self._extract_article_links(soup)
                                new_count = 0
                                for u in seeded_urls:
                                    if u not in seen_urls:
                                        seen_urls.add(u)
                                        urls.append(u)
                                        new_count += 1
                                logger.info(f"GMA v1: seeded {new_count} new URLs from {path}")
                                if len(urls) >= max_articles * 4:
                                    break
                            else:
                                logger.warning(f"GMA v1: error loading {path}")
                        except Exception as e:
                            logger.warning(f"GMA v1: error loading {path}: {e}")
                        self._human_delay()

                    if not resp:
                        # Fallback to HTTP discovery so GMA still works when Playwright landing pages time out.
                        t_fb0 = time.time()
                        fb_urls, fb_meta = self._discover_urls_http(max_articles=max_articles)
                        if not fb_urls:
                            raise RuntimeError("GMA v1: landing failed")
                        urls = fb_urls
                        discovery_meta = {
                            **fb_meta,
                            "method": "http_fallback",
                            "discovery_s": round(time.time() - t_fb0, 2),
                        }
                    else:
                        discovery_meta = {
                            "method": "playwright",
                            "paths_configured": min(max_paths, len(self.START_PATHS)),
                            "paths_scanned": paths_scanned,
                            "urls_discovered": len(urls),
                        }

                    # Continue below with scraping; keep the context open for fallbacks.
                    candidates = unique_canonical_urls(urls)
                    # Belt-and-suspenders filter: even if discovery selectors pick up non-articles,
                    # we never want to scrape or store them.
                    before = len(candidates)
                    candidates = [u for u in candidates if self._is_probable_article(u)]
                    filtered = before - len(candidates)
                    if filtered:
                        logger.info("GMA discovery: filtered_out=%s non-article URLs after canonicalization", filtered)
                    to_scrape, existing = filter_existing_article_urls(candidates)
                    discovery_existing_urls = existing
                    logger.info(
                        "GMA discovery: raw=%s unique=%s existing_in_db=%s new_to_scrape=%s",
                        len(urls),
                        len(candidates),
                        len(existing),
                        len(to_scrape),
                    )

                    for i, url in enumerate(to_scrape):
                        if len(articles) >= max_articles:
                            break
                        art = None
                        if GMA_HTTP_FASTPATH:
                            art = self._scrape_article_http(url)
                            if art:
                                logger.info("GMA fast-path (HTTP): scraped %s", art.title)
                        if not art:
                            art = self._scrape_article(url, context)
                        if art:
                            articles.append(art)
                            try:
                                content = getattr(art, "content", "") or ""
                                ends_ellipsis = bool(re.search(r"(\.\.\.|…)\s*$", content))
                                logger.info(
                                    "GMA v1: scraped %s | content_len=%s | ends_with_ellipsis=%s",
                                    art.title,
                                    len(content),
                                    ends_ellipsis,
                                )
                            except Exception:
                                logger.info(f"GMA v1: scraped {art.title}")
                        else:
                            errors.append(f"failed to extract {url}")
                        if len(articles) < max_articles and i < len(to_scrape) - 1:
                            self._human_delay()

                    context.close()
                    urls = urls  # keep for metadata

            # HTTP discovery path: scrape without launching Playwright unless needed.
            if urls and discovery_meta.get("method") == "http":
                t_pf0 = time.time()
                candidates = unique_canonical_urls(urls)
                before = len(candidates)
                candidates = [u for u in candidates if self._is_probable_article(u)]
                filtered = before - len(candidates)
                if filtered:
                    logger.info("GMA discovery: filtered_out=%s non-article URLs after canonicalization", filtered)
                to_scrape, existing = filter_existing_article_urls(candidates)
                discovery_existing_urls = existing
                discovery_meta["preflight_s"] = round(time.time() - t_pf0, 2)
                logger.info(
                    "GMA discovery: raw=%s unique=%s existing_in_db=%s new_to_scrape=%s",
                    len(urls),
                    len(candidates),
                    len(existing),
                    len(to_scrape),
                )

                needs_pw: list[str] = []
                for url in to_scrape:
                    if len(articles) >= max_articles:
                        break
                    t_art0 = time.time()
                    art = None
                    if GMA_HTTP_FASTPATH:
                        art = self._scrape_article_http(url)
                        if art:
                            logger.info("GMA fast-path (HTTP): scraped %s", art.title)
                    try:
                        discovery_meta.setdefault("article_http_s", []).append(round(time.time() - t_art0, 2))
                    except Exception:
                        pass
                    if art:
                        articles.append(art)
                        try:
                            content = getattr(art, "content", "") or ""
                            ends_ellipsis = bool(re.search(r"(\.\.\.|…)\s*$", content))
                            logger.info(
                                "GMA v1: scraped %s | content_len=%s | ends_with_ellipsis=%s",
                                art.title,
                                len(content),
                                ends_ellipsis,
                            )
                        except Exception:
                            logger.info(f"GMA v1: scraped {art.title}")
                        continue
                    needs_pw.append(url)

                if needs_pw and len(articles) < max_articles:
                    with launch_browser() as browser:
                        context = self._new_context(browser)
                        self._harden_context(context)
                        for url in needs_pw:
                            if len(articles) >= max_articles:
                                break
                            art = self._scrape_article(url, context)
                            if art:
                                articles.append(art)
                        try:
                            context.close()
                        except Exception:
                            pass
        except Exception as e:
            errors.append(str(e))
            logger.error(f"GMA v1: critical error {e}")

        total = time.time() - start
        performance = {
            "total_time": total,
            "articles_per_second": len(articles) / total if total > 0 else 0,
            "success_rate": len(articles) / (len(articles) + len(errors)) if (len(articles) + len(errors)) > 0 else 0
        }
        metadata = {
            "source": "GMA News Online",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "discovery": {
                **(discovery_meta if "discovery_meta" in locals() else {}),
                "existing_in_db": len(discovery_existing_urls),
            }
        }
        logger.info(f"GMA v1: completed {len(articles)} articles, {len(errors)} errors in {total:.2f}s")
        return ScrapingResult(articles=articles, errors=errors, performance=performance, metadata=metadata)


def scrape_gma_latest() -> List[NormalizedArticle]:
    scraper = GMAScraper()
    result = scraper.scrape_latest(max_articles=3)
    if result.errors:
        logger.warning(f"GMA v1: errors {result.errors}")
    return result.articles


def debug_gma_url(url: str) -> dict:
    """
    Developer helper: scrape a single URL and (optionally) print network debug logs.

    Usage (inside worker container):
      GMA_NETWORK_DEBUG=1 python -c "from app.scrapers.gma import debug_gma_url; print(debug_gma_url('https://...'))"
    """
    scraper = GMAScraper()
    try:
        with launch_browser() as browser:
            context = scraper._new_context(browser)
            scraper._harden_context(context)
            art = scraper._scrape_article(url, context)
            try:
                context.close()
            except Exception:
                pass
            return {"ok": bool(art), "title": getattr(art, "title", None)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
