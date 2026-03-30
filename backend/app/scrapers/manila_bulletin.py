import time
import logging
import random
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse, urlparse as parse_url, parse_qs
from dataclasses import dataclass
from contextlib import ExitStack
from playwright.sync_api import Browser
from bs4 import BeautifulSoup
from app.pipeline.normalize import build_article, NormalizedArticle
from app.scrapers.base import launch_browser
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
import urllib.request
import json
import html as html_lib
# Feature flags (env-driven) for gradual rollout
import os
from app.core.url import canonicalize_url
from app.scrapers.support.db_dedupe import (
    filter_existing_article_urls,
    unique_canonical_urls,
)
from app.scrapers.support.structured_data import extract_json_ld_newsarticle
from app.scrapers.support.network_debug import install_json_response_logger


def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in {"1", "true", "yes", "on"}

USE_ADV_HEADERS = _env_flag("USE_ADV_HEADERS", False)
USE_HUMAN_DELAY = _env_flag("USE_HUMAN_DELAY", False)
USE_URL_FILTER = _env_flag("USE_URL_FILTER", False)

# HTTP fast-path (structured data) to reduce Playwright cost
MB_HTTP_FASTPATH = _env_flag("MB_HTTP_FASTPATH", False)
try:
    MB_HTTP_MIN_BODY_CHARS = int(os.getenv("MB_HTTP_MIN_BODY_CHARS", "600"))
except Exception:
    MB_HTTP_MIN_BODY_CHARS = 600
try:
    MB_HTTP_TIMEOUT_S = int(os.getenv("MB_HTTP_TIMEOUT_S", "20"))
except Exception:
    MB_HTTP_TIMEOUT_S = 20

MB_NETWORK_DEBUG = _env_flag("MB_NETWORK_DEBUG", False)
try:
    MB_NETWORK_DEBUG_MAX = int(os.getenv("MB_NETWORK_DEBUG_MAX", "30"))
except Exception:
    MB_NETWORK_DEBUG_MAX = 30

try:
    MB_CONTENT_MIN_CHARS = int(os.getenv("MB_CONTENT_MIN_CHARS", "250"))
except Exception:
    MB_CONTENT_MIN_CHARS = 250
MB_CONTENT_MIN_CHARS = max(1, MB_CONTENT_MIN_CHARS)

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

# Module-level cooldown for sitemap attempts (seconds)
SITEMAP_COOLDOWN_SECONDS = 24 * 3600
_last_sitemap_404_at: Optional[float] = None


@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]


class ManilaBulletinScraper:
    """Stealth scraper for Manila Bulletin with conservative crawling and sanitization."""

    BASE_URL = "https://mb.com.ph"
    # Updated category structure (observed live)
    START_PATHS = [
        "/category/philippines",
        "/category/world",
        "/category/business",
        "/category/opinion",
        "/category/lifestyle",
        "/category/entertainment",
        "/category/sports",
    ]
    FEED_PATHS: List[str] = [
        "/feed",
        "/latest/feed",
    ]
    SITEMAP_PATHS = [
        "/sitemap_index.xml",
        "/sitemap.xml",
        "/news-sitemap.xml",
        "/sitemap-news.xml",
        "/post-sitemap.xml",
        "/sitemap_posts.xml",
    ]
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=site:mb.com.ph&hl=en-PH&gl=PH&ceid=PH:en"

    # Descriptive UA with contact pointer
    USER_AGENT = (
        "ph-vibecheck-ai-bot/1.0 (+https://example.com/contact) "
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )

    MIN_DELAY = 8.0
    MAX_DELAY = 28.0
    # Safety cap for candidates per run
    MAX_CANDIDATES = 30

    # Robots.txt disallow-derived patterns (must NOT fetch)
    DISALLOW_PATTERNS = [
        r"/ajax(/|$)",
        r"/print",
        r"/getRelatedArticles",
        r"/getMostReadArticles",
        r"/article_count/",
        r"/get-menu-header",
        r"/article\.php",
        r"/login-mgt",
        r"/[^/]+\.php($|\?)",
        r"/widget/",
        r"[?&]page=",
        r"/test-ads",
        r"/api/",
        r"/redirect-email",
        r"[?&]s=",
        r"/search-results\?s=",
    ]

    SELECTORS = {
        "article_links": [
            # Generic article titles
            "article h1 a",
            "article h2 a",
            "h1 a",
            "h2 a",
            # Listing layouts
            ".post-title a",
            ".post-item a",
            ".card a",
            ".archive-list a",
            ".entry-title a",
            # Date-based direct URLs
            "a[href*='/2025/']",
            "a[href*='/2024/']",
            # Category-based URLs
            "a[href*='/category/philippines/']",
            "a[href*='/category/world/']",
            "a[href*='/category/business/']",
            "a[href*='/category/opinion/']",
            "a[href*='/category/lifestyle/']",
            "a[href*='/category/entertainment/']",
            "a[href*='/category/sports/']",
        ],
        "title": [
            "h1.entry-title",
            "h1.post-title",
            "h1.article-title",
            "h1",
            "title",
        ],
        "content": [
            ".entry-content p",
            ".post-content p",
            ".article-content p",
            "article p",
            "p",
        ],
        "published_date": [
            "time[datetime]",
            ".entry-meta time",
            ".post-meta time",
            ".date",
            "time",
        ],
    }

    def _human_delay(self):
        delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"Manila Bulletin: waiting {delay:.1f}s (stealth)")
        time.sleep(delay)

    def _is_disallowed(self, path_and_query: str) -> bool:
        for pattern in self.DISALLOW_PATTERNS:
            if re.search(pattern, path_and_query):
                return True
        return False

    def _validate_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not parsed.netloc.endswith("mb.com.ph"):
            return False
        # Check path+query against disallow rules
        path_q = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        if self._is_disallowed(path_q):
            return False
        if url.lower().startswith(("javascript:", "data:")):
            return False
        return True

    def _extract_with_fallbacks(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el:
                    text = el.get_text().strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        s = html_lib.unescape(str(text))
        # Strip obvious scheme injections
        s = s.replace("javascript:", "").replace("data:", "")
        # If this looks like HTML (common in JSON-LD bodies), convert to plain text.
        if "<" in s and ">" in s:
            try:
                soup = BeautifulSoup(s, "html.parser")
                for el in soup.select("script, style, noscript"):
                    el.decompose()
                # Prefer semantic blocks to preserve paragraph breaks.
                parts: List[str] = []
                for el in soup.select("p, li"):
                    t = el.get_text(" ", strip=True)
                    t = re.sub(r"\s+", " ", t).strip()
                    if t:
                        parts.append(t)
                if parts:
                    s = "\n\n".join(parts)
                else:
                    s = soup.get_text(" ", strip=True)
            except Exception:
                s = re.sub(r"<[^>]+>", " ", s)
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse whitespace but keep paragraph breaks.
        s = re.sub(r"[ \t]+", " ", s)
        s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        s = s.strip()
        return s

    def _post_process_content(self, content: str) -> str:
        """
        Manila Bulletin pages sometimes include non-article UI text (e.g. "Related Tags")
        or duplicate lead sections (e.g. "At A Glance"). Normalize to clean plain text.
        """
        s = (content or "").strip()
        if not s:
            return ""

        # Remove leading UI labels.
        s = re.sub(r"^\s*At A Glance\s+", "", s, flags=re.IGNORECASE)

        paras = [p.strip() for p in re.split(r"\n{2,}", s) if p.strip()]

        # Strip a leading "Related Tags" block (header + tag list).
        if paras and paras[0].lower() == "related tags":
            paras = paras[1:]
            if paras and len(paras[0]) <= 120 and not re.search(r"[.!?]", paras[0]):
                paras = paras[1:]

        # Drop any remaining "Related Tags" paragraphs.
        paras = [p for p in paras if p.strip().lower() != "related tags"]

        # De-duplicate exact/repeated paragraphs (common when a lead summary repeats).
        seen: set[str] = set()
        deduped: List[str] = []
        for p in paras:
            key = re.sub(r"[^a-z0-9]+", "", p.lower())
            if not key:
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)

        return "\n\n".join(deduped).strip()

    def _find_article_container(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        container_selectors = [
            "article",
            "main[role='main'] article",
            ".single-post",
            ".single-article",
            ".post-single",
            ".post",
            ".entry-content",
            ".post-content",
            ".article-content",
            ".story-content",
            "#content article",
        ]
        candidates: List[BeautifulSoup] = []
        for sel in container_selectors:
            try:
                for el in soup.select(sel):
                    candidates.append(el)
            except Exception:
                continue
        if not candidates:
            return None
        # Score by total text length of <p> inside
        def score(el: BeautifulSoup) -> int:
            try:
                text = "\n".join(p.get_text(" ", strip=True) for p in el.select("p"))
                return len(text)
            except Exception:
                return 0
        best = max(candidates, key=score)
        return best if score(best) > 0 else None

    def _extract_content(self, soup: BeautifulSoup) -> str:
        # Boilerplate class/section blacklist
        blacklist_selectors = [
            "nav", "footer", "aside", ".newsletter", ".subscribe", ".subscription", ".share",
            ".social", ".related", ".recommend", ".tags", ".breadcrumbs", ".author", ".byline",
            ".comments", "#comments", ".ad", "[class*='advert']", "[id*='advert']",
        ]
        boilerplate_phrases = [
            "sign up by email", "all rights reserved", "©", "copyright", "read next", "related stories",
            "follow us", "advertisement", "subscribe", "share this", "newsletter",
            "published", "updated", "read more",
            "press escape to quit searching",
        ]
        # Regex-based skip rules for header widgets (temperature, time, date)
        header_skip_patterns = [
            re.compile(r"^\s*(?:[A-Z][a-z]+\s*)?\d{1,2}°[CF]\b"),                # Manila 27°C
            re.compile(r"^\s*\d{1,2}:\d{2}\s*(?:AM|PM)\b", re.IGNORECASE),       # 10:37 PM
            re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b\s+\d{1,2},\s+\d{4}", re.IGNORECASE),  # September 3, 2025
        ]
        # Remove blacklisted sections from a copy soup for cleaner scoring
        try:
            for sel in blacklist_selectors:
                for el in soup.select(sel):
                    el.decompose()
        except Exception:
            pass
        # Exclude script/style/template/noscript content from consideration
        try:
            for el in soup.find_all(["script", "style", "template", "noscript"]):
                el.decompose()
        except Exception:
            pass
        # Prefer a scoped article container
        container = self._find_article_container(soup) or soup
        parts: List[str] = []
        try:
            paragraphs = container.select("p, li")
        except Exception:
            paragraphs = []
        def should_skip_text(txt: str) -> bool:
            low = txt.lower()
            if any(phrase in low for phrase in boilerplate_phrases):
                return True
            if "{{" in txt and "}}" in txt:
                return True
            for pat in header_skip_patterns:
                if pat.search(txt):
                    return True
            return False
        for p in paragraphs:
            try:
                parent_name = (p.parent.name or "").lower() if p.parent else ""
                if parent_name in {"script", "style", "template", "noscript"}:
                    continue
                txt = (p.get_text(" ", strip=True) or "").strip()
            except Exception:
                txt = ""
            if not txt:
                continue
            if should_skip_text(txt):
                continue
            # Less strict threshold to avoid dropping valid short lead lines
            if len(txt) < 25 and not (txt.endswith(".") or txt.endswith("!") or txt.endswith("?")):
                continue
            parts.append(self._sanitize_text(txt))
            if len(parts) >= 40:
                break
        content = "\n\n".join(parts)
        # Relaxed second pass if too short
        if len(content) < 250:
            parts = []
            for p in paragraphs:
                try:
                    parent_name = (p.parent.name or "").lower() if p.parent else ""
                    if parent_name in {"script", "style", "template", "noscript"}:
                        continue
                    txt = (p.get_text(" ", strip=True) or "").strip()
                except Exception:
                    txt = ""
                if not txt:
                    continue
                if should_skip_text(txt):
                    continue
                parts.append(self._sanitize_text(txt))
                if len(parts) >= 40:
                    break
            content = "\n\n".join(parts)
        # Fallback to original broad selectors if still empty
        if not content:
            parts = []
            for sel in self.SELECTORS["content"]:
                try:
                    for p in soup.select(sel):
                        parent_name = (p.parent.name or "").lower() if p.parent else ""
                        if parent_name in {"script", "style", "template", "noscript"}:
                            continue
                        txt = (p.get_text(" ", strip=True) or "").strip()
                        if not txt:
                            continue
                        if should_skip_text(txt):
                            continue
                        parts.append(self._sanitize_text(txt))
                        if len(parts) >= 40:
                            break
                    if parts:
                        break
                except Exception:
                    continue
            content = "\n\n".join(parts)
        # Meta description fallback
        if len(content) < 120:
            try:
                meta = soup.select_one("meta[property='og:description']") or soup.select_one("meta[name='description']")
                if meta:
                    desc = (meta.get("content") or "").strip()
                    if desc and ("{{" not in desc and "}}" not in desc) and not any(p.search(desc) for p in header_skip_patterns):
                        content = desc if not content else content + "\n\n" + desc
            except Exception:
                pass
        # Final text fallback: take top-level text from container
        if len(content) < 120:
            try:
                text = container.get_text(" ", strip=True)
                if text and ("{{" not in text and "}}" not in text):
                    # Remove obvious header tokens
                    lines = [ln for ln in text.splitlines() if ln.strip() and not should_skip_text(ln.strip())]
                    content = ("\n\n".join(lines))[:1500]
            except Exception:
                pass
        content = self._post_process_content(content)
        # Cap to avoid oversized rows
        return (content or "")[:20000]

    def _parse_published(self, raw: Optional[str]) -> Optional[str]:
        """
        Parse Manila Bulletin published date into a timezone-aware UTC ISO string.

        Manila Bulletin often provides timestamps without an explicit offset; those should be
        treated as Asia/Manila (UTC+8) before converting to UTC.
        """
        if not raw:
            return None
        try:
            s = str(raw).strip()
            # Remove common PH tz abbreviations without offsets
            s = re.sub(r"\b(PHT|PST)\b", "", s, flags=re.IGNORECASE).strip()

            # 1) ISO-ish strings (may include Z / offset)
            if re.search(r"\d{4}-\d{2}-\d{2}", s):
                try:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=ZoneInfo("Asia/Manila"))
                    return dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    # Fall through to display formats
                    pass

            # 2) Display formats (date-only or date+time)
            for fmt in (
                "%B %d, %Y %I:%M %p",
                "%b %d, %Y %I:%M %p",
                "%B %d, %Y",
                "%b %d, %Y",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt_naive = datetime.strptime(s, fmt)
                    dt = dt_naive.replace(tzinfo=ZoneInfo("Asia/Manila"))
                    return dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    continue

            # 3) Fallback: always return an aware UTC time (avoid naive utcnow()).
            return datetime.now(timezone.utc).isoformat()
        except Exception:
            return None

    def _fetch_url(self, url: str, timeout: int = 15) -> Optional[bytes]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "*/*", "Referer": self.BASE_URL})
            # Try normally first
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except Exception:
                # Retry with relaxed SSL if TLS handshake issues occur
                try:
                    import ssl
                    ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:  # type: ignore
                        return resp.read()
                except Exception as e2:
                    raise e2
        except Exception as e:
            logger.warning(f"fetch failed {url}: {e}")
            return None

    def _fetch_url_with_status(self, url: str, timeout: int = 15) -> Tuple[Optional[bytes], Optional[int]]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT, "Accept": "*/*", "Referer": self.BASE_URL})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read(), getattr(resp, 'status', 200)
            except Exception:
                # Retry with relaxed SSL
                try:
                    import ssl
                    ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:  # type: ignore
                        return resp.read(), getattr(resp, 'status', 200)
                except urllib.error.HTTPError as he:  # type: ignore
                    return None, he.code
                except Exception:
                    return None, None
        except urllib.error.HTTPError as he:  # type: ignore
            return None, he.code
        except Exception:
            return None, None

    def _discover_links_from_rss(self, max_links: int = 50) -> List[str]:
        links: List[str] = []
        for path in self.FEED_PATHS:
            url = urljoin(self.BASE_URL, path)
            data = self._fetch_url(url)
            if not data:
                continue
            try:
                soup = BeautifulSoup(data, "xml")
                for item in soup.find_all("item"):
                    link_el = item.find("link")
                    href = (link_el.get_text() if link_el else "") or ""
                    href = href.strip()
                    if href and self._validate_url(href):
                        links.append(href)
                        if len(links) >= max_links:
                            break
                if len(links) >= max_links:
                    break
            except Exception:
                continue
        # unique preserve order
        seen = set()
        uniq: List[str] = []
        for u in links:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq

    def _discover_links_from_google_news(self, max_links: int = 50) -> List[str]:
        data = self._fetch_url(self.GOOGLE_NEWS_RSS)
        if not data:
            return []
        soup = BeautifulSoup(data, "xml")
        links: List[str] = []
        for item in soup:
            href = (item.get_text() or "").strip()
            if not href:
                continue
            try:
                p = parse_url(href)
                qs = parse_qs(p.query)
                direct = (qs.get("url") or [None])[0]
                candidate = direct or href
            except Exception:
                candidate = href
            if self._validate_url(candidate):
                links.append(candidate)
            if len(links) >= max_links:
                break
        # unique
        seen = set()
        unique: List[str] = []
        for u in links:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def _discover_links_from_sitemaps(self, max_links: int = 100) -> List[str]:
        global _last_sitemap_404_at
        # Cooldown check
        if _last_sitemap_404_at and (time.time() - _last_sitemap_404_at) < SITEMAP_COOLDOWN_SECONDS:
            logger.debug("Skipping sitemap discovery due to cooldown")
            return []

        discovered: List[str] = []
        saw_404 = False
        for path in self.SITEMAP_PATHS:
            url = urljoin(self.BASE_URL, path)
            data, status = self._fetch_url_with_status(url)
            if status == 404:
                saw_404 = True
                logger.debug(f"sitemap 404: {url}")
                continue
            if not data:
                logger.debug(f"sitemap fetch failed: {url}")
                continue
            try:
                soup = BeautifulSoup(data, "xml")
                for loc in soup:
                    child = (loc.get_text() or "").strip()
                    cdata, cstatus = self._fetch_url_with_status(child)
                    if cstatus == 404:
                        logger.debug(f"sitemap child 404: {child}")
                        continue
                    if not cdata:
                        logger.debug(f"sitemap child fetch failed: {child}")
                        continue
                    child_soup = BeautifulSoup(cdata, "xml")
                    for url_el in child_soup:
                        href = (url_el.get_text() or "").strip()
                        if self._validate_url(href):
                            discovered.append(href)
                            if len(discovered) >= max_links:
                                break
                    if len(discovered) >= max_links:
                        break
                if not discovered:
                    for url_el in soup:
                        href = (url_el.get_text() or "").strip()
                        if self._validate_url(href):
                            discovered.append(href)
                            if len(discovered) >= max_links:
                                break
            except Exception as e:
                logger.debug(f"sitemap parse failed {url}: {e}")
        if saw_404 and not discovered:
            _last_sitemap_404_at = time.time()
        # unique
        seen = set()
        unique: List[str] = []
        for u in discovered:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def _discover_links_from_html(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        links: List[str] = []
        # Primary: CSS selectors
        for sel in self.SELECTORS["article_links"]:
            try:
                for a in soup.select(sel):
                    href = a.get("href")
                    if not href:
                        continue
                    full = urljoin(self.BASE_URL, href)
                    if self._validate_url(full):
                        links.append(full)
            except Exception:
                continue
        # Secondary: broad anchor scan with heuristics
        if len(links) < 10:
            for a in soup.find_all('a'):
                href = a.get("href")
                if not href:
                    continue
                full = urljoin(self.BASE_URL, href)
                if not self._validate_url(full):
                    continue
                path = urlparse(full).path or ""
                # Prefer date-based article URLs or deep slugs under categories
                if re.search(r"/20\d{2}/", path):
                    links.append(full)
                elif re.search(r"^/category/(philippines|world|business|opinion|lifestyle|entertainment|sports)/", path):
                    # take deep links that look like article slugs (hyphenated, > 20 chars)
                    last = (path.rstrip('/').split('/')[-1] or '')
                    if '-' in last and len(last) > 20:
                        links.append(full)
        # Dedup preserve order
        seen = set()
        unique = []
        for u in links:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def _discover_links_from_sections_http(self, max_links_per_section: int = 10) -> List[str]:
        """Fetch section pages with urllib and extract links without Playwright (more resilient, faster)."""
        discovered: List[str] = []
        for path in self.START_PATHS:
            try:
                url = urljoin(self.BASE_URL, path)
                data = self._fetch_url(url)
                if not data:
                    continue
                html = data.decode('utf-8', errors='ignore')
                links = self._discover_links_from_html(html)[:max_links_per_section]
                discovered.extend(links)
            except Exception:
                continue
        # unique
        seen = set()
        uniq: List[str] = []
        for u in discovered:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq

    def _extract_json_ld(self, soup: BeautifulSoup) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        try:
            for script in soup.select('script[type="application/ld+json"]'):
                try:
                    payload = json.loads(script.get_text(strip=True))
                    if isinstance(payload, dict):
                        if payload.get("@type") in ["NewsArticle", "Article", "BlogPosting"]:
                            data["headline"] = payload.get("headline")
                            data["datePublished"] = payload.get("datePublished")
                            data["articleBody"] = payload.get("articleBody")
                            break
                except Exception:
                    continue
        except Exception:
            pass
        return data

    def _scrape_article_http_fastpath(self, url: str) -> Optional[NormalizedArticle]:
        """
        Best-effort HTTP-first article extraction (no Playwright).
        Uses JSON-LD when present, falls back to HTML parsing only when necessary.
        """
        if not MB_HTTP_FASTPATH:
            return None
        data = self._fetch_url(url, timeout=MB_HTTP_TIMEOUT_S)
        if not data:
            return None
        html = data.decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        jsonld = extract_json_ld_newsarticle(soup) or self._extract_json_ld(soup)
        title = (
            (jsonld.get("headline") if isinstance(jsonld, dict) else None)
            or self._extract_with_fallbacks(soup, self.SELECTORS["title"])
            or ""
        )
        title = self._sanitize_text(title)
        if not title:
            return None

        content_raw = (jsonld.get("articleBody") if isinstance(jsonld, dict) else None) or ""
        content = self._post_process_content(self._sanitize_text(content_raw))
        if len(content) < MB_HTTP_MIN_BODY_CHARS:
            # Fallback to DOM extraction from static HTML
            content = self._post_process_content(self._sanitize_text(self._extract_content(soup)))

        if len(content) < MB_HTTP_MIN_BODY_CHARS:
            return None

        raw_published = (jsonld.get("datePublished") if isinstance(jsonld, dict) else None) or self._extract_with_fallbacks(
            soup, self.SELECTORS["published_date"]
        )
        published_iso = self._parse_published(raw_published)

        return build_article(
            source="Manila Bulletin",
            category="General",
            title=title,
            url=canonicalize_url(url) or url,
            content=content,
            published_at=published_iso,
        )

    def _scrape_article(self, url: str, browser: Browser) -> Optional[NormalizedArticle]:
        # Backward-compat entrypoint; prefer using _scrape_article_with_context.
        try:
            with launch_browser() as browser:
                context = self._new_context(browser)
                try:
                    return self._scrape_article_with_context(url, context)
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Manila Bulletin scrape failed for {url}: {e}")
            return None

    def _new_context(self, browser: Browser):
        context = browser.new_context(
            user_agent=self.USER_AGENT,
            extra_http_headers={"Referer": self.BASE_URL},
            ignore_https_errors=True,
        )
        # Block heavy/static resources and third-party requests to reduce timeouts
        try:
            blocked_ext = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".css", ".woff", ".woff2", ".ttf", ".otf")

            def _handler(route):
                try:
                    u = (route.request.url or "").lower()
                    if u.endswith(blocked_ext):
                        return route.abort()
                    # Keep first-party only (avoids ad/analytics timeouts)
                    if not (route.request.url or "").startswith(self.BASE_URL):
                        return route.abort()
                except Exception:
                    pass
                return route.continue_()

            context.route("**/*", _handler)
        except Exception:
            pass
        return context

    def _scrape_article_with_context(self, url: str, context) -> Optional[NormalizedArticle]:
        page = None
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                page = context.new_page()
                page.set_default_navigation_timeout(30_000)
                page.set_default_timeout(30_000)
                dump_json = install_json_response_logger(
                    page,
                    enabled=MB_NETWORK_DEBUG,
                    max_items=max(1, MB_NETWORK_DEBUG_MAX),
                )
                if attempt == 0:
                    self._human_delay()
                try:
                    # Prefer domcontentloaded for speed; load can hang on ads/analytics
                    page.goto(url, wait_until="domcontentloaded")
                except Exception as e:
                    last_error = e
                    page.goto(url)
                    page.wait_for_load_state("domcontentloaded", timeout=15_000)
                # Attempt to wait for some content to appear but don't block too long
                try:
                    page.wait_for_selector("article, .entry-content, .post-content", timeout=5_000)
                except Exception:
                    pass
                soup = BeautifulSoup(page.content(), "html.parser")
                jsonld = self._extract_json_ld(soup)
                if MB_NETWORK_DEBUG:
                    try:
                        rows = dump_json()
                        if rows:
                            logger.info(
                                "MB network debug (captured=%s, showing up to 10): %s",
                                len(rows),
                                rows[: min(10, len(rows))],
                            )
                        else:
                            logger.info("MB network debug: no JSON/XHR responses captured")
                    except Exception:
                        pass

                title = jsonld.get("headline") or self._extract_with_fallbacks(soup, self.SELECTORS["title"]) or ""
                if not title:
                    continue
                content = self._post_process_content(
                    self._sanitize_text(jsonld.get("articleBody") or self._extract_content(soup))
                )
                if len(content) < MB_CONTENT_MIN_CHARS:
                    logger.warning(
                        "MB: extracted too-short content (len=%s, min=%s) for %s",
                        len(content),
                        MB_CONTENT_MIN_CHARS,
                        url,
                    )
                    continue
                raw_published = jsonld.get("datePublished") or self._extract_with_fallbacks(soup, self.SELECTORS["published_date"]) or None
                published_iso = self._parse_published(raw_published)
                article = build_article(
                    source="Manila Bulletin",
                    category="General",
                    title=title,
                    url=url,
                    content=content,
                    published_at=published_iso,
                )
                return article
            except Exception as e:
                last_error = e
                continue
            finally:
                try:
                    if page is not None:
                        page.close()
                except Exception:
                    pass
                page = None

        if last_error:
            logger.error(f"Manila Bulletin scrape failed for {url}: {last_error}")
        return None


    def _discover_links_from_homepage(self, max_links: int = 20) -> List[str]:
        """Discover links directly from Manila Bulletin homepage."""
        try:
            data = self._fetch_url(self.BASE_URL)
            if not data:
                return []
            
            html = data.decode('utf-8', errors='ignore')
            links = self._discover_links_from_html(html)
            return links[:max_links]
        except Exception as e:
            logger.error(f'Homepage discovery failed: {e}')
            return []

    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        start = time.time()
        articles: List[NormalizedArticle] = []
        errors: List[str] = []
        discovered: List[str] = []
        discovery_existing_urls: set[str] = set()
        
        # 1) First try homepage discovery (fastest and most reliable)
        homepage_links = []
        try:
            logger.info('Trying homepage discovery')
            homepage_links = self._discover_links_from_homepage(max_links=max_articles * 10)
            discovered.extend(homepage_links)
            logger.info(f'Homepage found {len(homepage_links)} links')
        except Exception as e:
            errors.append(f'homepage:{e}')
            logger.error(f'Homepage discovery failed: {e}')

        # 2) Prefer HTTP section discovery (fast, avoids Playwright timeouts)
        html_links_found = 0
        if len(discovered) < max_articles * 4:
            try:
                http_links = self._discover_links_from_sections_http(max_links_per_section=8)
                html_links_found += len(http_links)
                discovered.extend(http_links)
            except Exception as e:
                errors.append(f'sections_http:{e}')

        # 2b) If still low, fallback to Playwright-based section discovery (more expensive)
        if len(discovered) < max_articles * 2:
            try:
                with launch_browser() as browser:
                    for path in self.START_PATHS[:3]:
                        try:
                            self._human_delay()
                            context = browser.new_context(
                                user_agent=self.USER_AGENT,
                                extra_http_headers={'Referer': self.BASE_URL},
                                ignore_https_errors=True,
                            )
                            page = context.new_page()
                            page.set_default_navigation_timeout(30_000)
                            page.set_default_timeout(30_000)
                            url = urljoin(self.BASE_URL, path)
                            try:
                                page.goto(url, wait_until='domcontentloaded')
                            except Exception:
                                page.goto(url)
                                page.wait_for_load_state('domcontentloaded', timeout=15_000)
                            try:
                                page.wait_for_selector('article, a[href*="/202"], a[href*="/news/"]', timeout=5_000)
                            except Exception:
                                pass
                            new_links = self._discover_links_from_html(page.content())[:6]
                            html_links_found += len(new_links)
                            discovered.extend(new_links)
                            context.close()
                        except Exception as e:
                            errors.append(f'discover@{path}:{e}')
                            try:
                                context.close()
                            except Exception:
                                pass
            except Exception as e:
                errors.append(f'sections_pw:{e}')

        # 3) Try RSS feeds
        rss_links = []
        if len(discovered) < max_articles * 2:
            try:
                rss_links = self._discover_links_from_rss(max_links=max_articles * 5)
                discovered.extend(rss_links)
            except Exception as e:
                errors.append(f'rss:{e}')

        # 4) Google News fallback
        gnews_links = []
        if len(discovered) < max_articles * 2:
            try:
                gnews_links = self._discover_links_from_google_news(max_links=max_articles * 5)
                discovered.extend(gnews_links)
            except Exception as e:
                errors.append(f'gnews:{e}')

        # 5) Finally sitemaps if not cooled down
        sitemap_links = []
        if len(discovered) < max_articles * 2:
            try:
                sitemap_links = self._discover_links_from_sitemaps(max_links=max_articles * 10)
                discovered.extend(sitemap_links)
            except Exception as e:
                errors.append(f'sitemaps:{e}')

        # Dedup and validate
        candidates: List[str] = []
        seen = set()
        for u in discovered:
            cu = canonicalize_url(u)
            if cu and cu not in seen and self._validate_url(cu):
                seen.add(cu)
                candidates.append(cu)

        # Safety cap to avoid over-scraping
        if len(candidates) > self.MAX_CANDIDATES:
            candidates = candidates[:self.MAX_CANDIDATES]

        candidates = unique_canonical_urls(candidates)
        to_scrape, existing = filter_existing_article_urls(candidates)
        discovery_existing_urls = existing
        logger.info(
            "MB discovery: raw=%s unique=%s existing_in_db=%s new_to_scrape=%s cap=%s",
            len(discovered),
            len(candidates),
            len(existing),
            len(to_scrape),
            self.MAX_CANDIDATES,
        )

        # Compact JSON-style summary for easier searching/alerting
        discovery_summary = {
            "source": "ManilaBulletin",
            "homepage": len(homepage_links),
            "sections_html": html_links_found,
            "rss": len(rss_links),
            "gnews": len(gnews_links),
            "sitemaps": len(sitemap_links),
            "candidates": len(candidates),
            "cap": self.MAX_CANDIDATES,
        }
        logger.info(f"MB discovery summary: {discovery_summary}")
        if discovery_summary["candidates"] == 0:
            logger.warning("MB discovery yielded 0 candidates; check selectors/structure or upstream availability")

        # Scrape articles
        http_ok = 0
        playwright_used = 0
        playwright_ok = 0
        try:
            with ExitStack() as stack:
                browser = None
                context = None
                for url in to_scrape:
                    if len(articles) >= max_articles:
                        break

                    art = None
                    if MB_HTTP_FASTPATH:
                        art = self._scrape_article_http_fastpath(url)
                        if art:
                            http_ok += 1

                    if art is None:
                        if browser is None:
                            browser = stack.enter_context(launch_browser())
                            context = self._new_context(browser)
                            def _safe_close_ctx():
                                try:
                                    if context:
                                        context.close()
                                except Exception:
                                    pass

                            stack.callback(_safe_close_ctx)
                        playwright_used += 1
                        art = self._scrape_article_with_context(url, context)
                        if art:
                            playwright_ok += 1

                    if art:
                        articles.append(art)
        except Exception as e:
            errors.append(str(e))
        
        duration = time.time() - start
        perf = {
            "duration_s": round(duration, 2),
            "count": len(articles),
            "http_ok": http_ok,
            "playwright_used": playwright_used,
            "playwright_ok": playwright_ok,
        }
        meta = {
            'domain': 'mb.com.ph',
            'discovered_total': len(discovered),
            'candidates_used': len(to_scrape),
            'max_candidates': self.MAX_CANDIDATES,
            'existing_in_db': len(discovery_existing_urls),
            "mb_http_fastpath": bool(MB_HTTP_FASTPATH),
        }
        if len(articles) == 0:
            logger.warning("MB scrape produced 0 articles; verify selectors and content extraction")
        return ScrapingResult(articles=articles, errors=errors, performance=perf, metadata=meta) 


def debug_mb_url(url: str) -> dict:
    """
    Developer helper: scrape a single URL and (optionally) print network debug logs.

    Usage (inside worker container):
      MB_NETWORK_DEBUG=1 python -c "from app.scrapers.manila_bulletin import debug_mb_url; print(debug_mb_url('https://mb.com.ph/...'))"
    """
    scraper = ManilaBulletinScraper()
    try:
        with launch_browser() as browser:
            context = scraper._new_context(browser)
            art = scraper._scrape_article_with_context(url, context)
            try:
                context.close()
            except Exception:
                pass
            return {
                "ok": bool(art),
                "title": getattr(art, "title", None),
                "content_len": len(getattr(art, "content", None) or ""),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}
