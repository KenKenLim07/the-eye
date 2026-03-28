import time
import logging
import random
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from playwright.sync_api import Browser
from bs4 import BeautifulSoup
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
import requests
from app.scrapers.support.network_debug import install_json_response_logger
from app.core.url import canonicalize_url

# SENIOR BLACK HAT: Stealth mode for Akamai bypass 🔥💀
try:
    from playwright_stealth import Stealth
    HAS_STEALTH = True
    stealth_config = Stealth()
    logger = logging.getLogger(__name__)
    logger.info("🔥 BLACK HAT MODE: playwright-stealth loaded")
except ImportError:
    HAS_STEALTH = False
    stealth_config = None

# Feature flags
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
SCRAPER_CONTENT_MAX_CHARS = _env_int("SCRAPER_CONTENT_MAX_CHARS", 8000)

# Resource blocking knobs (tune without changing code)
ABS_CBN_BLOCK_STYLESHEETS = _env_flag("ABS_CBN_BLOCK_STYLESHEETS", True)
ABS_CBN_BLOCK_IMAGES = _env_flag("ABS_CBN_BLOCK_IMAGES", True)
ABS_CBN_BLOCK_FONTS = _env_flag("ABS_CBN_BLOCK_FONTS", True)
ABS_CBN_BLOCK_MEDIA = _env_flag("ABS_CBN_BLOCK_MEDIA", True)
ABS_CBN_BLOCK_TRACKERS = _env_flag("ABS_CBN_BLOCK_TRACKERS", True)

# Performance/safety knobs
ABS_CBN_ISOLATE_CONTEXT = _env_flag("ABS_CBN_ISOLATE_CONTEXT", False)
ABS_CBN_DISCOVERY_TARGET_FACTOR = _env_int("ABS_CBN_DISCOVERY_TARGET_FACTOR", 8)  # max_articles * factor
ABS_CBN_DB_PREFLIGHT_CHUNK_SIZE = _env_int("ABS_CBN_DB_PREFLIGHT_CHUNK_SIZE", 250)
ABS_CBN_HTTP_FASTPATH = _env_flag("ABS_CBN_HTTP_FASTPATH", False)
ABS_CBN_HTTP_FASTPATH_MIN_LEN = _env_int("ABS_CBN_HTTP_FASTPATH_MIN_LEN", 700)
ABS_CBN_NETWORK_DEBUG = _env_flag("ABS_CBN_NETWORK_DEBUG", False)
ABS_CBN_NETWORK_DEBUG_MAX = _env_int("ABS_CBN_NETWORK_DEBUG_MAX", 30)
ABS_CBN_DISABLE_DELAY = _env_flag("ABS_CBN_DISABLE_DELAY", False)
ABS_CBN_HYDRATION_TIMEOUT_MS = _env_int("ABS_CBN_HYDRATION_TIMEOUT_MS", 4500)
ABS_CBN_HYDRATION_MIN_PARAS = _env_int("ABS_CBN_HYDRATION_MIN_PARAS", 3)
ABS_CBN_FAST_RENDER_WAIT_MS = _env_int("ABS_CBN_FAST_RENDER_WAIT_MS", 500)

# Discovery fast-path
ABS_CBN_RSS_DISCOVERY = _env_flag("ABS_CBN_RSS_DISCOVERY", True)
ABS_CBN_RSS_URLS = os.getenv("ABS_CBN_RSS_URLS", "https://news.abs-cbn.com/rss").strip()
ABS_CBN_RSS_MAX_AGE_H = _env_int("ABS_CBN_RSS_MAX_AGE_H", 72)

# ABS-CBN OneDomain content API discovery (public, fast)
ABS_CBN_API_DISCOVERY = _env_flag("ABS_CBN_API_DISCOVERY", True)
# Backwards-compatible: allow a single URL via ABS_CBN_API_LIST_URL or multiple via ABS_CBN_API_LIST_URLS (comma-separated).
ABS_CBN_API_LIST_URLS = os.getenv(
    "ABS_CBN_API_LIST_URLS",
    os.getenv(
        "ABS_CBN_API_LIST_URL",
        ",".join(
            [
                "https://od2-content-api.abs-cbn.com/prod/list/id/news?limit=60&offset=0",
                "https://od2-content-api.abs-cbn.com/prod/list/id/business?limit=60&offset=0",
                "https://od2-content-api.abs-cbn.com/prod/list/id/technology?limit=60&offset=0",
                "https://od2-content-api.abs-cbn.com/prod/list/id/sports?limit=60&offset=0",
                "https://od2-content-api.abs-cbn.com/prod/list/id/entertainment?limit=60&offset=0",
            ]
        ),
    ),
).strip()
ABS_CBN_API_CONTENT_FASTPATH = _env_flag("ABS_CBN_API_CONTENT_FASTPATH", True)
ABS_CBN_API_MIN_BODY_CHARS = _env_int("ABS_CBN_API_MIN_BODY_CHARS", 600)

try:
    from app.scrapers.utils import (
        get_advanced_stealth_headers,
        get_human_like_delay,
    )
except Exception:
    get_advanced_stealth_headers = None
    get_human_like_delay = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class ABSCBNScraper:
    """Advanced stealth scraper for ABS-CBN with Akamai bypass (requires headed mode in dev, xvfb in prod)."""
    
    BASE_URL = "https://news.abs-cbn.com"
    START_PATHS = [
        "/",
        "/news",
        "/breaking-news",
    ]
    
    # Chrome 129 (matching real browsers)
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    )
    
    MIN_DELAY = 8.0
    MAX_DELAY = 15.0
    
    SELECTORS = {
        "article_links": [
            "article a[href]",
            ".list-group a[href]",
            ".article-item a[href]",
            "h3 a[href]",
            "h2 a[href]",
            "a[href*='/news/']",
        ],
        "title": [
            "h1.article-title",
            "h1",
            ".page-title",
            ".entry-title",
            "title"
        ],
        "content": [
            ".article-content p",
            ".entry-content p",
            ".post-content p",
            "article p",
            "p",
        ],
        "published_date": [
            "time[datetime]",
            ".article-date time",
            ".date",
            "time",
        ]
    }
    
    def _human_delay(self):
        if ABS_CBN_DISABLE_DELAY:
            return
        if USE_HUMAN_DELAY and get_human_like_delay is not None:
            delay = get_human_like_delay()
        else:
            delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"ABS-CBN: stealth delay {delay:.1f}s")
        time.sleep(delay)
    
    def _validate_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not parsed.netloc.endswith("abs-cbn.com"):
            return False
        
        path = (parsed.path or "").lower()

        # Block obvious non-article patterns (segment-based; avoid false-positives like:
        # - "mostly" matching "stl"
        # - "in-search-of" matching "search")
        segments = [s for s in parsed.path.split('/') if s]
        if len(segments) < 2:
            return False
        segs = [s.lower() for s in segments]

        blocked_segments = {
            "photo", "photos", "video", "videos", "gallery",
            "tag", "tags", "author", "search", "page",
            # Lotto/Gambling
            "lotto", "swertres", "stl", "pcso", "gambling", "betting",
            "draw", "winning", "numbers", "results", "lottery",
        }
        if any(seg in blocked_segments for seg in segs):
            return False

        blocked_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".mp4")
        if any(seg.endswith(blocked_ext) for seg in segs):
            return False

        segments = [s for s in parsed.path.split('/') if s]

        # ABS-CBN section pages (e.g. /news/nation) look like articles at a glance.
        # Require a dated path segment (YYYY/M/D) + a slug segment after the date.
        year_idx = None
        for i, seg in enumerate(segments):
            if re.fullmatch(r"20\d{2}", seg):
                year_idx = i
                break
        if year_idx is None:
            return False
        if year_idx + 3 >= len(segments):
            return False
        if not segments[year_idx + 1].isdigit() or not segments[year_idx + 2].isdigit():
            return False
        
        return True
    
    def _is_probable_article(self, url: str) -> bool:
        return self._validate_url(url)
    
    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        text = text.replace('<script>', '').replace('</script>', '')
        text = text.replace('javascript:', '').replace('data:', '')
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        return text.strip()
    
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
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        parts = []
        seen = set()
        
        for sel in self.SELECTORS["content"]:
            try:
                for el in soup.select(sel):
                    text = el.get_text().strip()
                    if not text or text in seen:
                        continue
                    seen.add(text)
                    if len(text) <= 30:
                        continue
                    if text.upper().startswith("ADVERTISEMENT"):
                        continue
                    parts.append(text)
                    
                if parts:
                    break
            except Exception:
                continue
        
        if not parts:
            for p in soup.find_all('p'):
                t = p.get_text().strip()
                if not t or t in seen or len(t) <= 30:
                    continue
                if t.upper().startswith("ADVERTISEMENT"):
                    continue
                seen.add(t)
                parts.append(t)
        
        if parts:
            combined = ' '.join(parts)
            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(combined) > SCRAPER_CONTENT_MAX_CHARS:
                combined = combined[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
            return combined
        
        return None
    
    def _parse_published(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            return dt.isoformat()
        except:
            pass
        return None
    
    def _new_context(self, browser: Browser):
        """Create context with anti-Akamai stealth (CRITICAL: use headless=False in dev)."""
        return browser.new_context(
            user_agent=self.USER_AGENT,
            locale='en-US',
            viewport={"width": 1280 + random.choice([-20, 0, 20]), "height": 800 + random.choice([-10, 0, 10])},
            accept_downloads=False,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
    
    def _harden_page(self, page):
        """Block tracking and heavy resources."""
        try:
            blocked_types = set()
            if ABS_CBN_BLOCK_IMAGES:
                blocked_types.add("image")
            if ABS_CBN_BLOCK_MEDIA:
                blocked_types.add("media")
            if ABS_CBN_BLOCK_FONTS:
                blocked_types.add("font")
            if ABS_CBN_BLOCK_STYLESHEETS:
                blocked_types.add("stylesheet")

            tracker_domains = [
                "google-analytics.com",
                "googletagmanager.com",
                "doubleclick.net",
                "googlesyndication.com",
                "adsystem.com",
                "scorecardresearch.com",
                "quantserve.com",
                "facebook.com",
                "connect.facebook.net",
                "twitter.com",
                "t.co",
                "taboola.com",
                "outbrain.com",
            ]

            def _handler(route):
                try:
                    u = (route.request.url or "").lower()
                    rtype = route.request.resource_type
                    if ABS_CBN_BLOCK_TRACKERS and any(d in u for d in tracker_domains):
                        return route.abort()
                    if rtype in blocked_types:
                        return route.abort()
                except Exception:
                    pass
                return route.continue_()

            page.route("**/*", _handler)
        except:
            pass
    
    def _add_stealth_scripts(self, context):
        """Inject stealth scripts before page loads (CRITICAL for Akamai bypass)."""
        context.add_init_script("""
            // Minimal navigator overrides
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            
            // Mock userAgentData
            try {
                if (navigator.userAgentData === undefined) {
                    Object.defineProperty(navigator, 'userAgentData', {
                        get: () => ({ 
                            brands: [{brand: 'Chromium', version: '129'}, {brand: 'Google Chrome', version: '129'}], 
                            mobile: false 
                        })
                    });
                }
            } catch (e) {}
            
            // Hide automation
            delete navigator.__proto__.webdriver;
        """)
    
    def _goto_with_retry(self, page, url: str, retries: int = 2) -> bool:
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(3.0, 6.0))

                t0 = time.time()
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                logger.info("ABS-CBN: navigated in %.2fs (attempt %s/%s)", time.time() - t0, attempt + 1, retries)
                
                # Check if blocked
                title = page.title()
                if "access denied" in title.lower():
                    logger.error(f"ABS-CBN: Blocked (403) - {title}")
                    return False
                
                return True
            except Exception as e:
                logger.warning(f"ABS-CBN: navigation error attempt {attempt+1}: {e}")
                if attempt == retries - 1:
                    return False
        return False
    
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
                    if self._validate_url(full):
                        urls.append(full)
                        seen.add(full)
            except:
                continue
        
        return urls

    def _extract_api_item_url(self, item: dict) -> Optional[str]:
        try:
            extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
            slug = (
                item.get("slugline_url")
                or item.get("sluglineUrl")
                or extra.get("slugline_url")
                or extra.get("sluglineUrl")
            )
            if not isinstance(slug, str) or not slug.strip():
                return None
            slug = slug.strip()
            if not slug.startswith("/"):
                slug = "/" + slug
            return urljoin(self.BASE_URL, slug)
        except Exception:
            return None

    def _category_from_slug_url(self, url: str) -> tuple[str, Optional[str]]:
        try:
            parsed = urlparse(url)
            segs = [s for s in (parsed.path or "").split("/") if s]
            # Patterns:
            #   /news/<section>/YYYY/M/D/<slug>
            #   /sports/<section>/YYYY/M/D/<slug>
            #   /entertainment/<section>/YYYY/M/D/<slug>
            raw = None
            if segs:
                if segs[0].lower() == "news" and len(segs) > 1:
                    raw = segs[1]
                else:
                    raw = segs[0]
            # Reuse shared normalizer
            norm, _raw = resolve_category_pair(url, BeautifulSoup("", "html.parser"))
            # resolve_category_pair tends to pick "News" from the first segment; override when we have better raw.
            if raw:
                from app.scrapers.utils import normalize_category  # local import to avoid cycles
                normalized = normalize_category(raw) or raw.title()
                return normalized, raw
            return norm, _raw
        except Exception:
            return "General", None

    def _article_from_api_item(self, item: dict, *, url: str) -> Optional[NormalizedArticle]:
        try:
            title = item.get("headline") or item.get("slugline") or ""
            if isinstance(title, dict):
                # Some payloads may store headline in a structured object; keep best-effort.
                title = title.get("main") or title.get("default") or ""
            if not isinstance(title, str) or not title.strip():
                return None

            body_html = item.get("body_html")
            if not isinstance(body_html, str) or not body_html.strip():
                return None

            # Convert HTML to clean paragraph text
            soup = BeautifulSoup(body_html, "html.parser")
            parts: List[str] = []
            for p in soup.find_all("p"):
                t = p.get_text(" ", strip=True)
                if t and len(t) > 30 and not t.upper().startswith("ADVERTISEMENT"):
                    parts.append(t)
            content = " ".join(parts).strip()
            if len(content) < max(0, int(ABS_CBN_API_MIN_BODY_CHARS)):
                return None
            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(content) > SCRAPER_CONTENT_MAX_CHARS:
                content = content[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"

            published_raw = item.get("firstpublished") or item.get("versioncreated") or item.get("_created") or None
            published_iso = self._parse_published(published_raw if isinstance(published_raw, str) else None)

            norm_cat, raw_cat = self._category_from_slug_url(url)

            return build_article(
                source="ABS-CBN",
                title=self._sanitize_text(title),
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_iso,
                raw_category=raw_cat,
            )
        except Exception:
            return None

    def _discover_urls_rss(self, *, max_items: int) -> List[str]:
        """
        Best-effort RSS discovery (faster + avoids Playwright for link discovery).
        Falls back to Playwright discovery when RSS is blocked/unavailable.
        """
        if max_items <= 0:
            return []
        rss_urls = [u.strip() for u in (ABS_CBN_RSS_URLS or "").split(",") if u.strip()]
        if not rss_urls:
            return []

        headers: Dict[str, str] = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
        }
        if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
            try:
                headers.update(get_advanced_stealth_headers())
            except Exception:
                pass

        out: List[str] = []
        seen: set[str] = set()
        cutoff = None
        try:
            cutoff = time.time() - max(1, int(ABS_CBN_RSS_MAX_AGE_H)) * 3600
        except Exception:
            cutoff = None

        for feed_url in rss_urls:
            try:
                r = requests.get(feed_url, headers=headers, timeout=20)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text or "", "xml")
                for item in soup.find_all("item"):
                    link = None
                    try:
                        link_tag = item.find("link")
                        if link_tag:
                            link = (link_tag.get_text() or "").strip()
                    except Exception:
                        link = None
                    if not link or link in seen:
                        continue

                    # Optional freshness filter based on pubDate when present
                    if cutoff is not None:
                        try:
                            pub = item.find("pubDate")
                            if pub and pub.get_text():
                                dt = datetime.strptime(pub.get_text().strip(), "%a, %d %b %Y %H:%M:%S %z")
                                if dt.timestamp() < cutoff:
                                    continue
                        except Exception:
                            pass

                    if self._validate_url(link):
                        out.append(link)
                        seen.add(link)
                    if len(out) >= max_items:
                        break
            except Exception:
                continue
            if len(out) >= max_items:
                break
        return out

    def _discover_urls_api(self, *, max_items: int) -> List[str]:
        """
        Use ABS-CBN's OneDomain content API list endpoints to discover fresh article links.

        This avoids Playwright for discovery and is much faster on slow connections.
        """
        if max_items <= 0:
            return []
        api_urls = [u.strip() for u in (ABS_CBN_API_LIST_URLS or "").split(",") if u.strip()]
        if not api_urls:
            return []

        headers: Dict[str, str] = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": self.BASE_URL + "/",
        }
        out: List[str] = []
        seen: set[str] = set()
        for list_url in api_urls:
            if len(out) >= max_items:
                break
            try:
                r = requests.get(list_url, headers=headers, timeout=20)
                if r.status_code != 200:
                    continue
                payload = r.json()
            except Exception:
                continue

            items = payload.get("listItem") if isinstance(payload, dict) else None
            if not isinstance(items, list):
                continue

            for it in items:
                if len(out) >= max_items:
                    break
                if not isinstance(it, dict):
                    continue
                extra = it.get("extra") if isinstance(it.get("extra"), dict) else {}
                slug = (
                    it.get("slugline_url")
                    or it.get("sluglineUrl")
                    or extra.get("slugline_url")
                    or extra.get("sluglineUrl")
                    or None
                )
                if not isinstance(slug, str) or not slug.strip():
                    continue
                slug = slug.strip()
                # `slugline_url` comes as `news/...` without leading slash.
                if not slug.startswith("/"):
                    slug = "/" + slug
                full = urljoin(self.BASE_URL, slug)
                if full in seen:
                    continue
                if self._validate_url(full):
                    out.append(full)
                    seen.add(full)

        return out

    def _scrape_article_http(self, url: str) -> Optional[NormalizedArticle]:
        """
        Fast path: attempt to extract the full article from HTML + JSON-LD without Playwright.

        ABS-CBN can be Akamai-sensitive; keep this best-effort and fall back to Playwright when blocked/short.
        """
        try:
            headers: Dict[str, str] = {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
                try:
                    headers.update(get_advanced_stealth_headers())
                except Exception:
                    pass

            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text or "", "html.parser")
            jsonld = extract_json_ld_newsarticle(soup)
            if not jsonld:
                return None

            title = jsonld.get("headline")
            body = jsonld.get("articleBody")
            date_published = jsonld.get("datePublished")
            if not isinstance(title, str) or not title.strip():
                return None
            if not isinstance(body, str) or len(body.strip()) < ABS_CBN_HTTP_FASTPATH_MIN_LEN:
                return None

            # Keep behavior consistent with Playwright path.
            title = self._sanitize_text(title)
            if re.search(r"\b(lotto|swertres|stl|4d|3d|6/\d{2}|pcso|lottery)\b", title, re.IGNORECASE):
                return None

            content = body.strip()
            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(content) > SCRAPER_CONTENT_MAX_CHARS:
                content = content[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"

            published_iso = self._parse_published(date_published if isinstance(date_published, str) else None)
            norm_cat, raw_cat = resolve_category_pair(url, soup)

            return build_article(
                source="ABS-CBN",
                title=title,
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_iso,
                raw_category=raw_cat,
            )
        except Exception:
            return None
    
    def _scrape_article(self, url: str, browser: Browser, *, context=None) -> Optional[NormalizedArticle]:
        try:
            if ABS_CBN_HTTP_FASTPATH:
                fast = self._scrape_article_http(url)
                if fast is not None:
                    logger.info("ABS-CBN fast-path (HTTP+JSON-LD): scraped %s", fast.title)
                    return fast

            t0 = time.time()
            local_context = None
            if context is None or ABS_CBN_ISOLATE_CONTEXT:
                local_context = self._new_context(browser)
                self._add_stealth_scripts(local_context)
                context_to_use = local_context
            else:
                context_to_use = context

            page = context_to_use.new_page()
            logger.info("ABS-CBN: loading %s", url)
            dump_json = install_json_response_logger(
                page,
                enabled=ABS_CBN_NETWORK_DEBUG,
                max_items=max(1, ABS_CBN_NETWORK_DEBUG_MAX),
            )
            
            # BLACK HAT: Apply stealth patches to evade Akamai fingerprinting 🔥
            if HAS_STEALTH and stealth_config:
                stealth_config.apply_stealth_sync(page)
                logger.info("🔥 Stealth patches applied to page")
            
            self._harden_page(page)
            page.set_default_timeout(45000)
            
            # Small delay before navigation
            time.sleep(random.uniform(0.1, 0.5))
            
            ok = self._goto_with_retry(page, url)
            if not ok:
                try:
                    page.close()
                except Exception:
                    pass
                if local_context is not None:
                    local_context.close()
                return None
            t_nav = time.time()

            # Fast render wait: keep small so we don't pay the max timeout on every article.
            try:
                page.wait_for_selector("h1", timeout=6000)
            except Exception:
                pass
            try:
                page.wait_for_timeout(max(0, int(ABS_CBN_FAST_RENDER_WAIT_MS)))
            except Exception:
                pass

            # Parse once immediately; only wait for hydration if content looks excerpt-only/short.
            html_doc = page.content()
            soup = BeautifulSoup(html_doc, "html.parser")
            title = self._extract_with_fallbacks(soup, self.SELECTORS["title"])
            content = self._extract_content(soup)
            looks_excerpt = bool(content and re.search(r"(\.\.\.|…)\s*$", content))
            needs_hydration = (not content) or looks_excerpt or (content is not None and len(content) < 900)

            t_ready = time.time()
            if needs_hydration:
                try:
                    page.wait_for_load_state("networkidle", timeout=max(500, int(ABS_CBN_HYDRATION_TIMEOUT_MS)))
                except Exception:
                    pass
                try:
                    page.wait_for_function(
                        f"""() => {{
                          const sels = ['.article-content p', '.entry-content p', 'article p'];
                          const minN = {max(1, int(ABS_CBN_HYDRATION_MIN_PARAS))};
                          return sels.some((s) => document.querySelectorAll(s).length >= minN);
                        }}""",
                        timeout=max(500, int(ABS_CBN_HYDRATION_TIMEOUT_MS)),
                    )
                except Exception:
                    pass
                html_doc = page.content()
                soup = BeautifulSoup(html_doc, "html.parser")
                # Re-read title/content after hydration.
                title = title or self._extract_with_fallbacks(soup, self.SELECTORS["title"])
                content2 = self._extract_content(soup)
                if content2 and (not content or len(content2) > len(content) + 200):
                    content = content2
                t_ready = time.time()

            logger.info("ABS-CBN: content-ready wait took %.2fs", t_ready - t_nav)

            if ABS_CBN_NETWORK_DEBUG:
                try:
                    rows = dump_json()
                    if rows:
                        logger.info(
                            "ABS-CBN network debug (captured=%s, showing up to 10): %s",
                            len(rows),
                            rows[: min(10, len(rows))],
                        )
                    else:
                        logger.info("ABS-CBN network debug: no JSON/XHR responses captured")
                except Exception:
                    pass

            if ABS_CBN_NETWORK_DEBUG:
                try:
                    # Sometimes the “real” content endpoint is embedded in scripts but not obvious
                    # from response logs (or appears after our cap). Surface any ABS-CBN JSON/API URLs.
                    api_urls = re.findall(r"https://[a-z0-9.-]*abs-cbn\.com/[^\s\"'>]+", html_doc, flags=re.IGNORECASE)
                    hinted = []
                    static_ext = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".css", ".woff", ".woff2", ".ttf", ".otf", ".mp4")
                    for u in api_urls:
                        lu_raw = u.lower()
                        lu = lu_raw.rstrip("\\'\"),;")
                        if lu.endswith(static_ext):
                            continue
                        if "od2-image-api.abs-cbn.com" in lu:
                            continue
                        if "od2-workbench-api.abs-cbn.com" in lu:
                            continue
                        if any(h in lu for h in ("api", "json", "graphql", "od2-content-api")):
                            hinted.append(u)
                    hinted = list(dict.fromkeys(hinted))  # de-dupe preserve order
                    if hinted:
                        logger.info(
                            "ABS-CBN network debug (html hinted urls=%s, showing up to 10): %s",
                            len(hinted),
                            hinted[: min(10, len(hinted))],
                        )
                except Exception:
                    pass

            # At this point soup/title/content are already computed (and hydration may have reloaded them).
            if not title or "access denied" in title.lower():
                try:
                    page.close()
                except Exception:
                    pass
                if local_context is not None:
                    local_context.close()
                return None
            t_parse = time.time()
            logger.info(
                "ABS-CBN: timings nav=%.2fs ready=%.2fs parse=%.2fs total=%.2fs",
                (t_nav - t0),
                (t_ready - t_nav),
                (t_parse - t_ready),
                (t_parse - t0),
            )

            # Filter lotto titles (like GMA does)
            if re.search(r"\b(lotto|swertres|stl|4d|3d|6/\d{2}|pcso|lottery)\b", title, re.IGNORECASE):
                logger.info(f"ABS-CBN: Skipping lotto article - {title}")
                try:
                    page.close()
                except Exception:
                    pass
                if local_context is not None:
                    local_context.close()
                return None

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
                content2 = self._extract_content(soup2)
                if content2 and len(content2) > len(content) + 200:
                    content = content2
                    soup = soup2
            raw_published = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])
            published_iso = self._parse_published(raw_published)
            norm_cat, raw_cat = resolve_category_pair(url, soup)
            
            article = build_article(
                source="ABS-CBN",
                title=title,
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_iso,
                raw_category=raw_cat,
            )
            
            try:
                page.close()
            except Exception:
                pass
            if local_context is not None:
                local_context.close()
            return article
        except Exception as e:
            logger.error(f"ABS-CBN: failed {url}: {e}")
            return None
    
    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        start = time.time()
        articles = []
        errors = []

        # Check if we're in headed mode (required for ABS-CBN)
        headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
        if headless_mode:
            logger.warning("ABS-CBN: Running in headless mode - may be blocked by Akamai. Set PLAYWRIGHT_HEADLESS=false for dev.")

        # -------------------------
        # Discovery + DB preflight (no browser)
        # -------------------------
        target_candidates = max(25, int(max_articles) * max(2, ABS_CBN_DISCOVERY_TARGET_FACTOR))
        t_discovery0 = time.time()
        discovery_urls: List[str] = []
        api_items_by_canon: Dict[str, dict] = {}

        if ABS_CBN_API_DISCOVERY or ABS_CBN_API_CONTENT_FASTPATH:
            try:
                headers: Dict[str, str] = {
                    "User-Agent": self.USER_AGENT,
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                    "Referer": self.BASE_URL + "/",
                }
                list_urls = [u.strip() for u in (ABS_CBN_API_LIST_URLS or "").split(",") if u.strip()]
                for list_url in list_urls:
                    if len(discovery_urls) >= target_candidates:
                        break
                    try:
                        r = requests.get(list_url, headers=headers, timeout=20)
                        if r.status_code != 200:
                            continue
                        payload = r.json()
                        items = payload.get("listItem") if isinstance(payload, dict) else None
                        if not isinstance(items, list):
                            continue
                        for it in items:
                            if len(discovery_urls) >= target_candidates:
                                break
                            if not isinstance(it, dict):
                                continue
                            full = self._extract_api_item_url(it)
                            if not full:
                                continue
                            if not self._validate_url(full):
                                continue
                            discovery_urls.append(full)
                            api_items_by_canon.setdefault(canonicalize_url(full), it)
                    except Exception:
                        continue
                if discovery_urls:
                    logger.info("ABS-CBN API discovery: raw=%s", len(discovery_urls))
            except Exception:
                pass

        if ABS_CBN_RSS_DISCOVERY and len(discovery_urls) < target_candidates:
            rss = self._discover_urls_rss(max_items=target_candidates - len(discovery_urls))
            if rss:
                discovery_urls.extend(rss)
                logger.info("ABS-CBN RSS discovery: raw=%s", len(rss))

        candidates = unique_canonical_urls(discovery_urls)
        t_discovery1 = time.time()
        logger.info("ABS-CBN discovery (no-browser): raw=%s unique=%s", len(discovery_urls), len(candidates))

        t_preflight0 = time.time()
        to_scrape, existing = filter_existing_article_urls(
            candidates,
            chunk_size=ABS_CBN_DB_PREFLIGHT_CHUNK_SIZE,
        )
        t_preflight1 = time.time()
        logger.info(
            "ABS-CBN preflight (no-browser): candidates=%s existing_in_db=%s new_to_scrape=%s",
            len(candidates),
            len(existing),
            len(to_scrape),
        )
        logger.info(
            "ABS-CBN perf (no-browser): discovery=%.2fs preflight=%.2fs",
            t_discovery1 - t_discovery0,
            t_preflight1 - t_preflight0,
        )

        # API content fast-path: build articles directly from API payload when possible (no Playwright).
        if ABS_CBN_API_CONTENT_FASTPATH and api_items_by_canon and to_scrape:
            api_built: List[NormalizedArticle] = []
            remaining: List[str] = []
            for u in to_scrape:
                if len(api_built) >= max_articles:
                    break
                it = api_items_by_canon.get(canonicalize_url(u))
                if it is None:
                    remaining.append(u)
                    continue
                art = self._article_from_api_item(it, url=u)
                if art is not None:
                    api_built.append(art)
                else:
                    remaining.append(u)

            if api_built:
                articles.extend(api_built)
                logger.info(
                    "ABS-CBN API content fast-path: built=%s remaining_urls=%s",
                    len(api_built),
                    len(remaining),
                )

                # If we already satisfied max_articles, return without launching Chromium.
                if len(articles) >= max_articles:
                    total = time.time() - start
                    performance = {
                        "total_time": total,
                        "articles_per_second": len(articles) / total if total > 0 else 0,
                        "success_rate": 1.0,
                    }
                    metadata = {
                        "source": "ABS-CBN",
                        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "total_articles_found": len(articles),
                        "total_errors": 0,
                        "headless_mode": headless_mode,
                    }
                    logger.info("ABS-CBN: completed %s articles via API (no browser)", len(articles))
                    return ScrapingResult(articles=articles, errors=[], performance=performance, metadata=metadata)

            # Continue with browser only for leftover URLs
            to_scrape = remaining

        # If nothing new, return early without launching Chromium (big RAM/time win).
        if not to_scrape:
            total = time.time() - start
            performance = {
                "total_time": total,
                "articles_per_second": 0.0,
                "success_rate": 1.0,
            }
            metadata = {
                "source": "ABS-CBN",
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_articles_found": len(articles),
                "total_errors": 0,
                "headless_mode": headless_mode,
            }
            if articles:
                logger.info("ABS-CBN: completed %s articles via API fast-path (no browser)", len(articles))
                performance["articles_per_second"] = len(articles) / total if total > 0 else 0
                return ScrapingResult(articles=articles, errors=[], performance=performance, metadata=metadata)
            logger.info("ABS-CBN: no new URLs to scrape (preflight filtered all candidates)")
            return ScrapingResult(articles=[], errors=[], performance=performance, metadata=metadata)

        try:
            # Use custom browser launch for headed mode in dev
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=headless_mode,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
                )
                
                context = self._new_context(browser)
                self._add_stealth_scripts(context)

                for i, url in enumerate(to_scrape):
                    if len(articles) >= max_articles:
                        break

                    art = self._scrape_article(url, browser, context=context)
                    if art:
                        articles.append(art)
                        logger.info(f"ABS-CBN: scraped {art.title}")
                    else:
                        errors.append(f"failed to extract {url}")
                    
                    if i < len(to_scrape) - 1 and len(articles) < max_articles:
                        self._human_delay()
                
                context.close()
                browser.close()
                
        except Exception as e:
            errors.append(str(e))
            logger.error(f"ABS-CBN: critical error {e}")
        
        total = time.time() - start
        performance = {
            "total_time": total,
            "articles_per_second": len(articles) / total if total > 0 else 0,
            "success_rate": len(articles) / (len(articles) + len(errors)) if (len(articles) + len(errors)) > 0 else 0
        }
        metadata = {
            "source": "ABS-CBN",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "headless_mode": headless_mode,
        }
        
        logger.info(f"ABS-CBN: completed {len(articles)} articles, {len(errors)} errors in {total:.2f}s")
        return ScrapingResult(articles=articles, errors=errors, performance=performance, metadata=metadata)


def scrape_abs_cbn_latest() -> List[NormalizedArticle]:
    scraper = ABSCBNScraper()
    result = scraper.scrape_latest(max_articles=3)
    if result.errors:
        logger.warning(f"ABS-CBN: errors {result.errors}")
    return result.articles
