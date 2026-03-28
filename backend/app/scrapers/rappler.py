import time
import logging
import random
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass
from playwright.sync_api import Browser
from bs4 import BeautifulSoup
from app.pipeline.normalize import build_article, NormalizedArticle
from app.scrapers.base import launch_browser
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import re
import urllib.request
import json
import httpx
from app.scrapers.utils import resolve_category_pair
from email.utils import parsedate_to_datetime
from app.core.supabase import get_supabase
from app.core.url import canonicalize_url

# Feature flags (env-driven) for gradual rollout
import os

def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in {"1", "true", "yes", "on"}

USE_ADV_HEADERS = _env_flag("USE_ADV_HEADERS", False)
USE_HUMAN_DELAY = _env_flag("USE_HUMAN_DELAY", False)
USE_URL_FILTER = _env_flag("USE_URL_FILTER", False)

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


class RapplerScraper:
    """Advanced stealth scraper for Rappler with senior dev + black hat techniques."""

    BASE_URL = "https://www.rappler.com"
    FEED_URL = "https://www.rappler.com/feed/"
    SECTIONS = [
        "/",
        "/latest/",
        "/newsbreak/", 
        "/nation/",
        "/business/",
        "/sports/",
        "/technology/",
        "/world/",
        "/entertainment/",
        "/philippines/",
        "/multimedia/",
        "/investigative/",
        "/data/",
        "/civic-engagement/",
        "/public-interest/",
    ]
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=site:rappler.com&hl=en-PH&gl=PH&ceid=PH:en"

    # User-Agent rotation for stealth
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    ]

    # Respectful crawling delays
    MIN_DELAY = 10.0
    MAX_DELAY = 20.0

    # Content selectors for Rappler
    SELECTORS = {
        "article_links": [
            "h2 a[href*='/news/']",
            "h3 a[href*='/newsbreak/']", 
            "h2 a[href*='/nation/']",
            "h2 a[href*='/business/']",
            "h2 a[href*='/sports/']",
            "h2 a[href*='/technology/']",
            "h2 a[href*='/world/']",
            "h2 a[href*='/entertainment/']",
            ".post-card__title a",
            ".archive-article h3 a",
            ".trending-header a",
            # removed overly-broad year-based selector that captured media assets
            # "a[href*='/20']",
            "article h2 a",
            "article h3 a",
            ".archive-article__latest-post h3 a",
            
            # TARGET: Latest News container
            ".latest-news a[href*='/']",
            ".latest a[href*='/']",
            "section[aria-label*='Latest'] a[href*='/']",
            "section[aria-label*='Latest News'] a[href*='/']",
            "section:has(h2:contains('Latest News')) a[href]",
            "section:has(h2:contains('Latest news')) a[href]",
            "section:has(h2:contains('Latest')) a[href]",
            "h2:contains('Latest News') ~ * a[href*='/']",
            
            # TARGET: Thematic blocks (Philippine tropical cyclones, UAAP, House, flood control)
            "section:has(h2:contains('Philippine tropical cyclones')) a[href*='/']",
            "section:has(h2:contains('UAAP')) a[href*='/']",
            "section:has(h2:contains('House of Representatives')) a[href*='/']",
            "section:has(h2:contains('flood control')) a[href*='/']",
            
            # TARGETED SELECTORS FOR LATEST ARTICLES - SURGICAL APPROACH
            # Catch specific article patterns found on latest page
            "a[href*='/sports/volleyball/']",
            "a[href*='/sports/uaap/']",
            "a[href*='/sports/']",
            "a[href*='/philippines/']",
            "a[href*='/nation/']",
            "a[href*='/business/']",
            "a[href*='/world/']",
            "a[href*='/entertainment/']",
            "a[href*='/technology/']",
            "a[href*='/newsbreak/']",
            "a[href*='/news/']",
            
            # Catch headlines in article containers (not pagination)
            ".post-card a[href*='/sports/']",
            ".post-card a[href*='/philippines/']",
            ".post-card a[href*='/nation/']",
            ".archive-article a[href*='/sports/']",
            ".archive-article a[href*='/philippines/']",
            ".archive-article a[href*='/nation/']",
            "article a[href*='/sports/']",
            "article a[href*='/philippines/']",
            "article a[href*='/nation/']",
            
            # Catch links in specific containers (avoid pagination)
            "h2 a[href*='/sports/']",
            "h2 a[href*='/philippines/']",
            "h2 a[href*='/nation/']",
            "h3 a[href*='/sports/']",
            "h3 a[href*='/philippines/']",
            "h3 a[href*='/nation/']",
        ],
        "title": [
            "h1.post-single__title",
            "h1.entry-title", 
            "h1.article-title",
            "h1",
            "title",
        ],
        "content": [
            ".entry-content p",
            ".post-single__content p",
            ".single-article p",
            ".article-content p",
            "article p",
        ],
        "published_date": [
            "time[datetime]",
            ".post-single__date",
            ".entry-meta time",
            "time",
            ".date",
        ],
    }

    # Known section/landing endpoints we want to exclude (not individual articles)
    DISALLOWED_SECTION_PATHS = {
        "/newsbreak/fact-check",
        "/newsbreak/inside-track",
        "/newsbreak/podcasts-videos",
        "/newsbreak/data-documents",
        "/philippines/rappler-talk",
        "/philippines/special-coverage",
        "/philippines/overseas-filipinos",
        "/philippines/metro-manila",
        "/sports/gilas-pilipinas",
        "/business/personal-finance",
        "/business/stocks-banking",
        "/business/consumer-issues",
        "/world/asia-pacific",
        "/world/global-affairs",
        "/world/latin-america",
        "/world/middle-east",
        "/world/us-canada",
        "/world/south-central-asia",
        "/technology/internet-culture",
        "/technology/social-media",
    }

    def _get_random_ua(self) -> str:
        return random.choice(self.USER_AGENTS)

    def _human_delay(self):
        if USE_HUMAN_DELAY and get_human_like_delay is not None:
            delay = get_human_like_delay()
        else:
            delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"Rappler: stealth delay {delay:.1f}s")
        time.sleep(delay)

    def _validate_url(self, url: str) -> bool:
        """Validate if URL is a legitimate Rappler article."""
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not ("rappler.com" in parsed.netloc):
            return False

        # Rappler-specific blocklist: keep dataset "news-only"
        try:
            path_lower = (parsed.path or "").lower()
            # People/human-interest/food/features tend to pollute "news" signals
            if path_lower.startswith("/people/"):
                return False
        except Exception:
            pass

        # Optional advanced validator: treat as an additional gate, not an override.
        if USE_URL_FILTER and is_valid_news_url is not None:
            try:
                if not is_valid_news_url(url, "rappler.com"):
                    return False
            except Exception:
                # If advanced filter errors, fall back to legacy checks
                pass
        
        # Legacy checks (fallback)
        # Filter out non-article URLs
        blacklist_patterns = [
            r"/feed/",
            r"/search",
            r"/tag/",
            r"/author/",
            r"/newsletter",
            r"/subscribe", 
            r"/login",
            r"/register",
            r"/wp-",
            r"/wp-content/",
            r"/tachyon/",
            r"/latest-from",  # listing hubs
            r"/topics/",
            r"/section/",
            r"/categories?/",
            r"/page/\d+/?$",
            r"/latest/$",
            r"\.(css|js|png|jpg|jpeg|gif|svg|webp|avif|mp4|pdf)(\?|$)",
        ]
        
        for pattern in blacklist_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        if re.search(r"/opinion(/|$)|/editorial(/|$)", parsed.path or "", re.IGNORECASE):
            return False

        # Block exact-known section landing endpoints
        try:
            norm_path = (parsed.path or "/").rstrip("/")
            if norm_path in self.DISALLOWED_SECTION_PATHS:
                return False
        except Exception:
            pass
        
        # Must have date pattern or be in valid sections
        path = parsed.path
        if not (
            re.search(r"/20\d{2}/", path) or  # year pattern
            any(section in path for section in ["/news/", "/newsbreak/", "/nation/", "/business/", "/sports/", "/technology/", "/world/", "/entertainment/", "/philippines/"])
        ):
            return False
        
        # Stricter shape: avoid section roots; prefer article-like slug
        try:
            segments = [s for s in (parsed.path or "").split('/') if s]
            if len(segments) < 2:
                return False
            last = segments[-1]
            # Article-ish if has hyphenated slug or date segments exist
            looks_like_slug = ('-' in last and len(last) > 8) or re.search(r"/20\d{2}/", path)
            if not looks_like_slug:
                return False
        except Exception:
            return False

        return True

    def _canon(self, url: str) -> str:
        return canonicalize_url(url, force_https=True)

    def _unique_valid_canon_links(self, links: List[str]) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for link in links or []:
            c = self._canon(link)
            if not c or c in seen:
                continue
            if not self._validate_url(c):
                continue
            seen.add(c)
            out.append(c)
        return out

    def _filter_existing_urls(self, urls: List[str]) -> tuple[List[str], set[str]]:
        """
        Return (urls_not_in_db, existing_urls_in_db) for the canonicalized URLs.

        Best-effort: on any storage/DNS failure, return the original list and an empty existing-set.
        """
        cleaned = [self._canon(u) for u in (urls or []) if u]
        # Preserve order while de-duping
        seen: set[str] = set()
        ordered: List[str] = []
        for u in cleaned:
            if u and u not in seen:
                seen.add(u)
                ordered.append(u)
        if not ordered:
            return [], set()
        try:
            sb = get_supabase()
            res = sb.table("articles").select("url").in_("url", ordered).execute()
            existing = {str(r.get("url")) for r in (res.data or []) if r.get("url")}
            remaining = [u for u in ordered if u not in existing]
            return remaining, existing
        except Exception as e:
            logger.warning("Rappler DB preflight failed (will scrape without it): %s", e)
            return ordered, set()

    def _extract_with_fallbacks(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        """Extract text using fallback selectors."""
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
        """Sanitize and clean text content."""
        if not text:
            return ""
        # Remove script/style content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract article content with advanced filtering."""
        # Remove unwanted elements
        unwanted_selectors = [
            "nav", "footer", "aside", ".share", ".social", ".related", 
            ".newsletter", ".subscribe", ".ad", ".advertisement",
            ".comments", "#comments", ".author-info", ".tags",
            ".breadcrumbs", ".rappler-speechify", "[class*='ad-']"
        ]
        
        for sel in unwanted_selectors:
            for el in soup.select(sel):
                el.decompose()

        # Extract from content containers
        parts = []
        for sel in self.SELECTORS["content"]:
            try:
                for p in soup.select(sel):
                    text = p.get_text(" ", strip=True)
                    if text and len(text) > 20:  # Min length filter
                        # Skip boilerplate text
                        if not any(skip in text.lower() for skip in [
                            "rappler", "subscribe", "newsletter", "share this",
                            "follow us", "advertisement", "read more",
                            "related stories", "comments", "copyright"
                        ]):
                            parts.append(self._sanitize_text(text))
                    
                    if len(parts) >= 20:  # Limit paragraphs
                        break
                        
                if parts:
                    break
            except Exception:
                continue

        content = "\n\n".join(parts)
        
        # Fallback to meta description if content too short
        if len(content) < 100:
            try:
                meta = soup.select_one("meta[property='og:description']") or soup.select_one("meta[name='description']")
                if meta:
                    desc = meta.get("content", "").strip()
                    if desc:
                        content = desc if not content else content + "\n\n" + desc
            except Exception:
                pass

        return (content or "")[:15000]  # Cap length

    def _parse_published_date(self, raw_date: Optional[str]) -> Optional[str]:
        """Parse and normalize published date."""
        if not raw_date:
            return None
            
        try:
            s = str(raw_date).strip()

            # 0) RFC822 / RSS style dates: "Tue, 23 Mar 2026 12:10:00 +0800"
            try:
                if "," in s and re.search(r"\s[+-]\d{4}\b", s):
                    dt_rfc = parsedate_to_datetime(s)
                    if dt_rfc is not None:
                        if dt_rfc.tzinfo is None:
                            dt_rfc = dt_rfc.replace(tzinfo=timezone.utc)
                        return dt_rfc.astimezone(timezone.utc).isoformat()
            except Exception:
                pass

            # 1) ISO-ish strings (prefer this; Rappler JSON-LD often includes +08:00)
            if re.search(r"\d{4}-\d{2}-\d{2}", s):
                try:
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        # Rappler's displayed times are PH local; assume Asia/Manila when offset is missing.
                        dt = dt.replace(tzinfo=ZoneInfo("Asia/Manila"))
                    return dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    # If it's an unparseable ISO-like string, fall through to other patterns.
                    pass

            # 2) Display format: "Mar 23, 2026 8:10 PM PHT" (or full month name)
            cleaned = re.sub(r"\b(PHT|PST)\b", "", s, flags=re.IGNORECASE).strip()
            for fmt in ("%b %d, %Y %I:%M %p", "%B %d, %Y %I:%M %p", "%b %d, %Y", "%B %d, %Y"):
                try:
                    dt_naive = datetime.strptime(cleaned, fmt)
                    dt = dt_naive.replace(tzinfo=ZoneInfo("Asia/Manila"))
                    return dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    continue

            # 3) Final fallback: use an aware UTC timestamp (avoid naive utcnow()).
            return datetime.now(timezone.utc).isoformat()
        except Exception:
            return None

    def _extract_published_date_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the most trustworthy published date string from the rendered HTML.

        Prefer explicit machine-readable attributes (e.g. time[datetime], meta tags),
        then fall back to visible text.
        """
        try:
            time_el = soup.select_one("time[datetime]")
            if time_el:
                # Some Rappler pages expose a PH-local *display* string that is more trustworthy than the
                # datetime attribute (which can occasionally be ambiguous). If we see a human string, use it.
                text = time_el.get_text(" ", strip=True)
                if text and (re.search(r"\b(PHT|PST)\b", text, flags=re.IGNORECASE) or re.search(r"\d{1,2}:\d{2}", text)):
                    return text

                dt_attr = (time_el.get("datetime") or "").strip()
                if dt_attr:
                    return dt_attr
                if text:
                    return text
        except Exception:
            pass

        # Common meta tags used by news sites
        meta_selectors = [
            "meta[property='article:published_time']",
            "meta[property='og:published_time']",
            "meta[name='pubdate']",
            "meta[name='publish-date']",
            "meta[name='publish_date']",
        ]
        for sel in meta_selectors:
            try:
                el = soup.select_one(sel)
                if not el:
                    continue
                content = (el.get("content") or "").strip()
                if content:
                    return content
            except Exception:
                continue

        # Visible-text fallback using existing selector list
        try:
            return self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])
        except Exception:
            return None

    def _choose_raw_published_date(self, html_raw: Optional[str], ld_raw: Optional[str]) -> Optional[str]:
        """
        Choose between HTML-derived and JSON-LD-derived raw dates.

        Rappler pages sometimes expose a PH-local display time (e.g. "… PM PHT") alongside
        structured data. When the structured value is ambiguous, prefer the HTML signal.
        """
        if html_raw:
            h = str(html_raw)
            # If HTML explicitly signals PH time, always trust it.
            if re.search(r"\b(PHT|PST)\b", h, flags=re.IGNORECASE) or "+08" in h or "GMT+8" in h.upper():
                return html_raw
            # If HTML contains a time-of-day and JSON-LD is missing, use HTML.
            if (re.search(r"\d{1,2}:\d{2}", h) or re.search(r"\b(AM|PM)\b", h, flags=re.IGNORECASE)) and not ld_raw:
                return html_raw
            # If JSON-LD looks like a date-only value, prefer HTML.
            if ld_raw and not re.search(r"\d{1,2}:\d{2}", str(ld_raw)):
                return html_raw
            # Otherwise keep JSON-LD if it exists; fall back to HTML.
            return ld_raw or html_raw
        return ld_raw

    def _extract_json_ld(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract structured data from JSON-LD."""
        data = {}
        try:
            for script in soup.select('script[type="application/ld+json"]'):
                try:
                    payload = json.loads(script.get_text(strip=True))

                    # Payloads can be dict, list, or dict with @graph.
                    candidates = []
                    if isinstance(payload, dict):
                        if isinstance(payload.get("@graph"), list):
                            candidates.extend([x for x in payload.get("@graph") if isinstance(x, dict)])
                        else:
                            candidates.append(payload)
                    elif isinstance(payload, list):
                        candidates.extend([x for x in payload if isinstance(x, dict)])

                    for obj in candidates:
                        t = obj.get("@type")
                        types = [t] if isinstance(t, str) else (t if isinstance(t, list) else [])
                        if any(x in {"NewsArticle", "Article", "BlogPosting"} for x in types):
                            data["headline"] = obj.get("headline")
                            data["datePublished"] = obj.get("datePublished")
                            data["articleBody"] = obj.get("articleBody")
                            raise StopIteration
                except Exception:
                    continue
        except Exception:
            pass
        except StopIteration:
            pass
        return data

    def _extract_rappler_category(self, url: str, soup: BeautifulSoup) -> Tuple[str, Optional[str]]:
        """Extract category specifically for Rappler's structure."""
        raw_category = None
        
        # 1. Try to extract from URL structure first (most reliable)
        if url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split('/') if p]
                
                if path_parts:
                    # Rappler URLs: /technology/article-name or /newsbreak/politics/article-name
                    first_segment = path_parts[0].lower()
                    category_map = {
                        'technology': 'Technology',
                        'tech': 'Technology', 
                        'business': 'Business',
                        'sports': 'Sports',
                        'world': 'World',
                        'entertainment': 'Entertainment',
                        'nation': 'Nation',
                        'newsbreak': 'News',
                        'latest': 'News',
                        'politics': 'Politics',
                        'lifestyle': 'Lifestyle',
                        'opinion': 'Opinion'
                    }
                    
                    if first_segment in category_map:
                        raw_category = category_map[first_segment]
                    
                    # For newsbreak URLs, check second segment
                    if first_segment == 'newsbreak' and len(path_parts) > 1:
                        second_segment = path_parts[1].lower()
                        if second_segment in category_map:
                            raw_category = category_map[second_segment]
            except Exception:
                pass
        
        # 2. Extract from JavaScript dataLayer (very reliable for Rappler)
        if not raw_category:
            try:
                # Look for window.dataLayer.push with primary_category
                for script in soup.find_all('script'):
                    if script.string and 'primary_category' in script.string:
                        script_text = script.string
                        import re
                        match = re.search(r'"primary_category":"([^"]+)"', script_text)
                        if match:
                            raw_category = match.group(1)
                            break
            except Exception:
                pass
        
        # 3. Extract from JSON-LD structured data
        if not raw_category:
            try:
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        import json
                        data = json.loads(script.string or '')
                        if isinstance(data, dict) and '@graph' in data:
                            for item in data['@graph']:
                                if item.get('@type') == 'NewsArticle':
                                    section = item.get('articleSection')
                                    if section:
                                        raw_category = section
                                        break
                        elif isinstance(data, dict) and data.get('@type') == 'NewsArticle':
                            section = data.get('articleSection')
                            if section:
                                raw_category = section
                    except:
                        continue
            except Exception:
                pass
        
        # 4. Fallback to breadcrumbs
        if not raw_category:
            try:
                for selector in ['nav.breadcrumb a', '.breadcrumb a', '.breadcrumbs a']:
                    breadcrumb = soup.select_one(selector)
                    if breadcrumb:
                        text = breadcrumb.get_text(strip=True)
                        if text and text.lower() not in ['home', 'latest news', 'rappler']:
                            raw_category = text
                            break
            except Exception:
                pass
        
        # Normalize the category
        if raw_category:
            # Clean up the category name
            raw_category = raw_category.strip().title()
            # Map common variations
            if raw_category.lower() in ['tech', 'technology']:
                normalized = 'Technology'
            elif raw_category.lower() in ['biz', 'business']:
                normalized = 'Business'
            elif raw_category.lower() in ['sports', 'sport']:
                normalized = 'Sports'
            elif raw_category.lower() in ['world', 'international']:
                normalized = 'World'
            elif raw_category.lower() in ['entertainment', 'showbiz']:
                normalized = 'Entertainment'
            elif raw_category.lower() in ['nation', 'national', 'politics']:
                normalized = 'Nation'
            elif raw_category.lower() in ['news', 'newsbreak', 'latest']:
                normalized = 'News'
            else:
                normalized = raw_category
        else:
            normalized = 'General'
            raw_category = None
        
        return normalized, raw_category


    def _fetch_with_httpx(self, url: str, timeout: int = 15) -> Optional[str]:
        """Fetch URL with httpx and stealth headers."""
        try:
            if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
                headers = get_advanced_stealth_headers()
                # Ensure referer points to Rappler
                headers.setdefault('Referer', self.BASE_URL)
            else:
                headers = {
                    "User-Agent": self._get_random_ua(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Referer": self.BASE_URL,
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                }
            
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"HTTP fetch failed for {url}: {e}")
            return None

    def _discover_from_rss(self, max_links: int = 30) -> List[str]:
        """Discover article links from RSS feed."""
        try:
            logger.info("Discovering from RSS feed")
            xml_content = self._fetch_with_httpx(self.FEED_URL)
            if not xml_content:
                return []
            
            soup = BeautifulSoup(xml_content, "xml")
            links = []

            # Optional freshness gate to reduce churn on frequent runs.
            try:
                freshness_hours = int(os.getenv("RAPPLER_RSS_FRESHNESS_HOURS", "48"))
            except Exception:
                freshness_hours = 48
            cutoff = None
            if freshness_hours and freshness_hours > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours)
            
            for item in soup.find_all("item"):
                if cutoff is not None:
                    try:
                        pub = item.select_one("pubDate")
                        if pub and pub.get_text(strip=True):
                            dt = parsedate_to_datetime(pub.get_text(strip=True))
                            if dt is not None:
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                if dt.astimezone(timezone.utc) < cutoff:
                                    continue
                    except Exception:
                        # If we can't parse pubDate, keep the item (safer).
                        pass
                link_el = item.select_one("link")
                if link_el:
                    url = link_el.get_text().strip()
                    if self._validate_url(url):
                        links.append(url)
                        
                if len(links) >= max_links:
                    break
            
            logger.info(f"RSS discovered {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"RSS discovery failed: {e}")
            return []

    def _discover_from_google_news(self, max_links: int = 20) -> List[str]:
        """Discover from Google News RSS."""
        try:
            logger.info("Discovering from Google News")
            xml_content = self._fetch_with_httpx(self.GOOGLE_NEWS_RSS)
            if not xml_content:
                return []
            
            soup = BeautifulSoup(xml_content, "xml")
            links = []
            
            for item in soup.find_all("item"):
                link_el = item.select_one("link")
                if link_el:
                    gn_url = link_el.get_text().strip()
                    # Extract actual URL from Google News redirect
                    try:
                        parsed = urlparse(gn_url)
                        qs = parse_qs(parsed.query)
                        actual_url = (qs.get("url") or [None])[0]
                        if actual_url and self._validate_url(actual_url):
                            links.append(actual_url)
                    except Exception:
                        continue
                        
                if len(links) >= max_links:
                    break
            
            logger.info(f"Google News discovered {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Google News discovery failed: {e}")
            return []

    def _discover_from_homepage(self, max_links: int = 20) -> List[str]:
        """Discover from homepage blocks (Latest News, thematic sections) using Playwright locators."""
        links = []
        try:
            with launch_browser() as browser:
                if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
                    headers = get_advanced_stealth_headers()
                    headers.setdefault('Referer', self.BASE_URL)
                    user_agent = headers.get('User-Agent', self._get_random_ua())
                else:
                    user_agent = self._get_random_ua()
                    headers = {"Referer": self.BASE_URL}
                
                context = browser.new_context(
                    user_agent=user_agent,
                    extra_http_headers=headers
                )
                page = context.new_page()
                
                # Block heavy resources
                page.route("**/*", lambda route: (
                    route.abort() if any(
                        route.request.url.lower().endswith(ext) 
                        for ext in [".png", ".jpg", ".jpeg", ".gif", ".css", ".woff", ".woff2", ".svg"]
                    ) else route.continue_()
                ))
                
                page.goto(self.BASE_URL + "/", wait_until="domcontentloaded", timeout=20000)
                try:
                    page.wait_for_selector("section", timeout=10000)
                except Exception:
                    pass
                
                # Robust locators for blocks by visible text
                block_locators = [
                    "section:has-text('Top stories')",
                    "section:has-text('Latest news')",
                    "section:has-text('Latest News')",
                    "section:has-text('Budget Watch')",
                    "section:has-text('Philippine tropical cyclones')",
                    "section:has-text('UAAP Basketball')",
                    "section:has-text('House of Representatives')",
                    "section:has-text('protests in the Philippines')",
                ]
                
                seen = set()
                for locator in block_locators:
                    try:
                        els = page.locator(locator)
                        count = els.count()
                        for i in range(count):
                            # anchor tags inside the block
                            for a in els.nth(i).locator("a").all():
                                href = a.get_attribute("href")
                                if not href:
                                    continue
                                full_url = urljoin(self.BASE_URL, href)
                                if full_url in seen:
                                    continue
                                if self._validate_url(full_url):
                                    seen.add(full_url)
                                    links.append(full_url)
                                    if len(links) >= max_links:
                                        break
                            if len(links) >= max_links:
                                break
                        if len(links) >= max_links:
                            break
                    except Exception:
                        continue
                
                context.close()
            logger.info(f"Homepage discovered {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Homepage discovery failed: {e}")
            return []

    def _discover_from_latest(self, max_links: int = 30) -> List[str]:
        """Discover strictly from /latest/ page, with dynamic scroll & 'Load more' handling."""
        links = []
        try:
            try:
                latest_timeout_ms = int(os.getenv("RAPPLER_LATEST_TIMEOUT_MS", "25000"))
            except Exception:
                latest_timeout_ms = 25000
            with launch_browser() as browser:
                # Setup advanced or fallback headers
                if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
                    headers = get_advanced_stealth_headers()
                    headers.setdefault('Referer', self.BASE_URL)
                    user_agent = headers.get('User-Agent', self._get_random_ua())
                else:
                    user_agent = self._get_random_ua()
                    headers = {"Referer": self.BASE_URL}

                context = browser.new_context(
                    user_agent=user_agent,
                    extra_http_headers=headers
                )
                page = context.new_page()

                # Block heavy resources for speed
                page.route("**/*", lambda route: (
                    route.abort() if any(
                        route.request.url.lower().endswith(ext)
                        for ext in [".png", ".jpg", ".jpeg", ".gif", ".woff", ".woff2", ".svg"]
                    ) else route.continue_()
                ))

                url = urljoin(self.BASE_URL, "/latest/")
                logger.info(f"[+] Navigating to {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=latest_timeout_ms)

                # Wait for article elements to appear
                try:
                    page.wait_for_selector(
                        ".archive-article, article, .post-card",
                        timeout=min(20000, max(5000, latest_timeout_ms)),
                    )
                except Exception:
                    logger.warning("[!] Initial selector not found — continuing anyway")

                prev_height = 0
                scroll_round = 0
                no_change_rounds = 0
                load_more_clicks = 0
                # Cap how deep we go to avoid endless scrolling
                try:
                    max_pages = int(os.getenv("RAPPLER_LATEST_MAX_PAGES", "2"))
                except Exception:
                    max_pages = 2
                max_scroll_rounds = 12

                # Dynamic scrolling to load more content
                while (
                    len(links) < max_links and
                    no_change_rounds < 3 and
                    scroll_round < max_scroll_rounds and
                    load_more_clicks < max_pages
                ):
                    scroll_round += 1
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception:
                        pass
                    time.sleep(2)

                    # Try to click "Load more" if available (several selector variants)
                    try:
                        clicked = False
                        for btn_selector in [
                            "button:has-text('Load more')",
                            "button:has-text('LOAD MORE')",
                            "button.load-more",
                            ".load-more button",
                        ]:
                            btn = page.locator(btn_selector)
                            if btn.count() > 0 and btn.first.is_visible():
                                try:
                                    btn.first.click()
                                    clicked = True
                                    logger.info("[+] Clicked 'Load more' button")
                                    time.sleep(2)
                                    load_more_clicks += 1
                                    break
                                except Exception:
                                    continue
                        if not clicked:
                            # Some implementations use anchor links
                            a_more = page.locator("a:has-text('Load more')")
                            if a_more.count() > 0 and a_more.first.is_visible():
                                try:
                                    a_more.first.click()
                                    logger.info("[+] Clicked 'Load more' link")
                                    time.sleep(2)
                                    load_more_clicks += 1
                                except Exception:
                                    pass
                        if load_more_clicks >= max_pages:
                            logger.info(f"[+] Reached configured max pages ({max_pages}); stopping further clicks")
                    except Exception:
                        pass

                    # Detect scroll end by page height
                    try:
                        curr_height = page.evaluate("document.body.scrollHeight")
                    except Exception:
                        curr_height = prev_height
                    if curr_height == prev_height:
                        no_change_rounds += 1
                    else:
                        no_change_rounds = 0
                    prev_height = curr_height

                    logger.info(f"[+] Scroll round {scroll_round}, page height={curr_height}")

                logger.info(f"[+] Finished scrolling after {scroll_round} rounds (load_more_clicks={load_more_clicks})")

                # Prefer extracting anchors inside the Latest section directly via Playwright first
                raw_links: List[str] = []
                try:
                    latest_section_locator_candidates = [
                        "section:has(h2:has-text('Latest News'))",
                        "section:has(h2:has-text('Latest news'))",
                        "section[aria-label*='Latest']",
                    ]
                    seen_href = set()
                    for sec_sel in latest_section_locator_candidates:
                        try:
                            sec = page.locator(sec_sel)
                            count = sec.count()
                            for i in range(count):
                                anchors = sec.nth(i).locator("a")
                                a_count = anchors.count()
                                for j in range(min(a_count, 200)):
                                    href = anchors.nth(j).get_attribute("href")
                                    if not href:
                                        continue
                                    full_url = urljoin(self.BASE_URL, href)
                                    if full_url in seen_href:
                                        continue
                                    seen_href.add(full_url)
                                    raw_links.append(full_url)
                        except Exception:
                            continue
                except Exception:
                    pass

                # Fallback to BeautifulSoup parsing
                try:
                    soup = BeautifulSoup(page.content(), "html.parser")
                    if not raw_links:
                        raw_links = self._extract_links_from_html(soup)
                    else:
                        # Merge with soup extraction for completeness
                        merged = self._extract_links_from_html(soup)
                        raw_links.extend([u for u in merged if u not in raw_links])
                except Exception:
                    soup = None

                seen = set()
                for l in raw_links:
                    if len(links) >= max_links:
                        break
                    if "brandrap" in l.lower():
                        continue
                    if l not in seen and self._validate_url(l):
                        seen.add(l)
                        links.append(l)

                context.close()
            logger.info(f"Latest discovered {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Latest discovery failed: {e}")
            return []

    def _discover_from_sections(self, max_links: int = 20) -> List[str]:
        """Discover from section pages using Playwright."""
        links = []
        try:
            logger.info("Discovering from section pages")
            try:
                max_sections = int(os.getenv("RAPPLER_MAX_SECTION_PAGES", "6"))
            except Exception:
                max_sections = 6
            try:
                section_timeout = int(os.getenv("RAPPLER_SECTION_TIMEOUT_MS", "15000"))
            except Exception:
                section_timeout = 15000
            with launch_browser() as browser:
                for section in self.SECTIONS[:max_sections]:
                    try:
                        if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
                            headers = get_advanced_stealth_headers()
                            headers.setdefault('Referer', self.BASE_URL)
                            user_agent = headers.get('User-Agent', self._get_random_ua())
                        else:
                            user_agent = self._get_random_ua()
                            headers = {"Referer": self.BASE_URL}
                        
                        context = browser.new_context(
                            user_agent=user_agent,
                            extra_http_headers=headers
                        )
                        page = context.new_page()
                        
                        # Block heavy resources for speed
                        page.route("**/*", lambda route: (
                            route.abort() if any(
                                route.request.url.lower().endswith(ext) 
                                for ext in [".png", ".jpg", ".jpeg", ".gif", ".css", ".woff", ".woff2"]
                            ) else route.continue_()
                        ))
                        
                        url = urljoin(self.BASE_URL, section)
                        page.goto(url, wait_until="domcontentloaded", timeout=section_timeout)
                        
                        # Wait for content to load
                        try:
                            page.wait_for_selector(".archive-article, .post-card", timeout=section_timeout)
                        except Exception:
                            pass
                        
                        soup = BeautifulSoup(page.content(), "html.parser")
                        section_links = self._extract_links_from_html(soup)
                        links.extend(section_links[:10])  # Limit per section
                        
                        context.close()
                        self._human_delay()
                        
                        if len(links) >= max_links:
                            break
                            
                    except Exception as e:
                        logger.warning(f"Section discovery failed for {section}: {e}")
                        try:
                            context.close()
                        except Exception:
                            pass
                        continue
            
            logger.info(f"Sections discovered {len(links)} links")
            return links
        except Exception as e:
            logger.error(f"Section discovery failed: {e}")
            return []

    def _extract_links_from_html(self, soup: BeautifulSoup) -> List[str]:
        """Extract article links from HTML."""
        links = []
        
        for sel in self.SELECTORS["article_links"]:
            try:
                for a in soup.select(sel):
                    href = a.get("href")
                    if href:
                        full_url = urljoin(self.BASE_URL, href)
                        if self._validate_url(full_url):
                            # Exclude listing hub patterns like /latest-from-/ /latest-from
                            if re.search(r"/latest-from|/latest-from-", full_url, re.IGNORECASE):
                                continue
                            links.append(full_url)
            except Exception:
                continue
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links

    def _scrape_article(self, url: str, browser: Browser) -> Optional[NormalizedArticle]:
        """Scrape individual article with stealth techniques."""
        try:
            if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
                headers = get_advanced_stealth_headers()
                headers.setdefault('Referer', self.BASE_URL)
                user_agent = headers.get('User-Agent', self._get_random_ua())
            else:
                user_agent = self._get_random_ua()
                headers = {"Referer": self.BASE_URL}
            
            context = browser.new_context(
                user_agent=user_agent,
                locale="en-PH",
                timezone_id="Asia/Manila",
                extra_http_headers=headers
            )
            page = context.new_page()
            
            # Block heavy resources
            page.route("**/*", lambda route: (
                route.abort() if any(
                    route.request.url.lower().endswith(ext) 
                    for ext in [".png", ".jpg", ".jpeg", ".gif", ".css", ".woff", ".woff2", ".svg"]
                ) or not route.request.url.startswith("https://www.rappler.com")
                else route.continue_()
            ))
            
            page.set_default_timeout(25000)
            
            # Random delay before navigation
            self._human_delay()
            
            resp = page.goto(url, wait_until="domcontentloaded")
            try:
                status = resp.status if resp else None
                if status in (403, 429):
                    raise Exception(f"rappler_cooldown: upstream status {status}")
                if status in (500, 502, 503):
                    logger.info(f"Transient upstream error {status}; backing off briefly")
                    time.sleep(random.randint(5, 12))
            except Exception:
                raise
            
            # Wait for content
            try:
                page.wait_for_selector("h1, .post-single__title", timeout=10000)
            except Exception:
                pass
            
            soup = BeautifulSoup(page.content(), "html.parser")
            context.close()
            
            # Extract structured data
            json_ld = self._extract_json_ld(soup)
            
            # Extract article data
            title = (
                json_ld.get("headline") or 
                self._extract_with_fallbacks(soup, self.SELECTORS["title"]) or 
                ""
            )
            
            if not title:
                logger.warning(f"No title found for {url}")
                return None
            
            content = (
                json_ld.get("articleBody") or 
                self._extract_content(soup)
            )
            
            # Content gate: skip media/placeholder pages
            minimal_content = (content or "").strip()
            og_type = None
            try:
                og = soup.select_one("meta[property='og:type']")
                if og:
                    og_type = (og.get("content") or "").strip().lower()
            except Exception:
                pass
            # Relax content gate: allow if content is moderately sized even if og:type is not strictly 'article'
            if (len(minimal_content) < 80) and (og_type and og_type != "article"):
                logger.info(f"Skipping non-article page by content gate: {url} (og:type={og_type}, len={len(minimal_content)})")
                return None
            
            raw_date = (
                self._choose_raw_published_date(
                    self._extract_published_date_from_html(soup),
                    json_ld.get("datePublished"),
                )
            )
            published_at = self._parse_published_date(raw_date)
            
            # Build normalized article
            norm_cat, raw_cat = self._extract_rappler_category(url, soup)
            article = build_article(
                source="Rappler",
                title=title,
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_at,
                raw_category=raw_cat,
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None

    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        """Main scraping method with multiple discovery strategies."""
        start_time = time.time()
        articles = []
        errors = []
        
        logger.info(f"Rappler: flags USE_ADV_HEADERS={USE_ADV_HEADERS}, USE_HUMAN_DELAY={USE_HUMAN_DELAY}, USE_URL_FILTER={USE_URL_FILTER}")
        
        # Discovery (Hybrid: RSS primary, /latest fallback)
        rss_links_raw: List[str] = []
        latest_links_raw: List[str] = []
        existing_urls: set[str] = set()
        candidates: List[str] = []

        try:
            rss_links_raw = self._discover_from_rss(max_articles * 8)
        except Exception as e:
            errors.append(f"RSS: {e}")

        rss_links = self._unique_valid_canon_links(rss_links_raw)
        rss_to_scrape, rss_existing = self._filter_existing_urls(rss_links)
        existing_urls |= rss_existing
        candidates.extend(rss_to_scrape)

        # Only pay the Playwright cost for /latest if RSS doesn't yield enough *new* URLs.
        if len(candidates) < max_articles:
            try:
                latest_links_raw = self._discover_from_latest(max_articles * 8)
            except Exception as e:
                errors.append(f"Latest: {e}")

            latest_links = self._unique_valid_canon_links(latest_links_raw)
            # Remove anything already considered from RSS
            rss_set = set(rss_links)
            latest_only = [u for u in latest_links if u not in rss_set]
            latest_to_scrape, latest_existing = self._filter_existing_urls(latest_only)
            existing_urls |= latest_existing
            # Preserve order: RSS first, then /latest
            seen_cand = set(candidates)
            for u in latest_to_scrape:
                if u not in seen_cand:
                    seen_cand.add(u)
                    candidates.append(u)

        # Give some buffer for scrape failures
        candidates = candidates[: max_articles * 6]

        logger.info(
            "Rappler candidates: rss_raw=%s rss_unique=%s rss_existing=%s rss_new=%s latest_raw=%s total_new_to_scrape=%s",
            len(rss_links_raw),
            len(rss_links),
            len(rss_existing),
            len(rss_to_scrape),
            len(latest_links_raw),
            len(candidates),
        )
        for preview in candidates[:8]:
            logger.info("Candidate: %s", preview)
        
        # Scrape articles
        try:
            with launch_browser() as browser:
                for url in candidates:
                    if len(articles) >= max_articles:
                        break
                    
                    article = self._scrape_article(url, browser)
                    if article:
                        # Ensure URL matches store canonicalization shape
                        try:
                            article.url = self._canon(article.url)
                        except Exception:
                            pass
                        articles.append(article)
                        logger.info(f"Successfully scraped: {article.title[:50]}...")
        except Exception as e:
            errors.append(f"Scraping: {e}")
        
        duration = time.time() - start_time
        performance = {
            "duration_s": round(duration, 2),
            "articles_scraped": len(articles),
            "candidates_found": len(candidates)
        }
        
        metadata = {
            "domain": "rappler.com",
            "discovery_sources": ["rss", "latest"],
            "rss_links_raw": len(rss_links_raw),
            "rss_links_unique": len(rss_links),
            "db_existing_urls": len(existing_urls),
            "candidates_new_to_scrape": len(candidates),
            "latest_links_raw": len(latest_links_raw),
        }
        
        return ScrapingResult(
            articles=articles,
            errors=errors,
            performance=performance,
            metadata=metadata
        )
