import time
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup, Tag
import requests
import html as _html
import re
from email.utils import parsedate_to_datetime
from app.pipeline.normalize import build_article, NormalizedArticle
from app.scrapers.base import launch_browser
import random
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

# Inquirer HTTP-first fast-path (default OFF for safe rollout)
INQUIRER_HTTP_FASTPATH = _env_flag("INQUIRER_HTTP_FASTPATH", False)
INQUIRER_HTTP_DISCOVERY = _env_flag("INQUIRER_HTTP_DISCOVERY", False)
INQUIRER_HTTP_MIN_BODY_CHARS = _env_int("INQUIRER_HTTP_MIN_BODY_CHARS", 600)
INQUIRER_HTTP_TIMEOUT_CONNECT_S = _env_int("INQUIRER_HTTP_TIMEOUT_CONNECT_S", 5)
INQUIRER_HTTP_TIMEOUT_READ_S = _env_int("INQUIRER_HTTP_TIMEOUT_READ_S", 15)
INQUIRER_NETWORK_DEBUG = _env_flag("INQUIRER_NETWORK_DEBUG", False)
INQUIRER_NETWORK_DEBUG_MAX = _env_int("INQUIRER_NETWORK_DEBUG_MAX", 30)
INQUIRER_RSS_DISCOVERY = _env_flag("INQUIRER_RSS_DISCOVERY", False)
INQUIRER_RSS_URLS = os.getenv(
    "INQUIRER_RSS_URLS",
    ",".join(
        [
            "https://newsinfo.inquirer.net/feed",
            "https://globalnation.inquirer.net/feed",
            "https://business.inquirer.net/feed",
            "https://sports.inquirer.net/feed",
            "https://entertainment.inquirer.net/feed",
            "https://lifestyle.inquirer.net/feed",
            "https://technology.inquirer.net/feed",
        ]
    ),
).strip()
INQUIRER_RSS_MAX_AGE_H = _env_int("INQUIRER_RSS_MAX_AGE_H", 48)

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class InquirerScraper:
    """Production-ready scraper for Philippine Daily Inquirer with security hardening."""
    
    BASE_URL = "https://newsinfo.inquirer.net"
    USER_AGENT = "Mozilla/5.0 (compatible; PH-VibeCheck-AI-NewsBot/1.0; +https://github.com/your-repo)"
    
    # Rate limiting
    MIN_DELAY = 12.0  # seconds between requests (increased for stealth)
    MAX_RETRIES = 3
    MAX_DELAY = 25.0  # randomized upper bound for human-like delays
    
    # Enhanced selectors with more specific targeting
    SELECTORS = {
        "article_links": [
            "a"  # Catch all links, filter by URL validation
        ],
        "title": [
            "h1.entry-title",
            "h1",
            ".entry-title",
            "title"
        ],
        "content": [
            # More specific content selectors
            ".entry-content .entry-body p",  # Main article body
            ".entry-content p",              # Entry content paragraphs
            ".entry-body p",                 # Entry body paragraphs
            "article .entry-content p",      # Article content
            ".post-content p",               # Post content
            ".article-content p",            # Article content
            ".content p",                    # Generic content
            "article p",                     # Article paragraphs
            "p"                             # Fallback to all paragraphs
        ],
        "published_date": [
            "time.entry-date",
            ".entry-date",
            "time",
            ".date"
        ]
    }
    
    def __init__(self):
        self.session_start = time.time()
        self.request_count = 0
        self._http_session: Optional[requests.Session] = None

    def _get_http_session(self) -> requests.Session:
        if self._http_session is None:
            self._http_session = requests.Session()
        return self._http_session

    def _http_headers(self, url: str) -> Dict[str, str]:
        # Keep headers simple/consistent; rely on Playwright fallback for any anti-bot.
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-PH,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": self.BASE_URL,
        }

    def _discover_urls_rss(self, *, max_items: int) -> List[str]:
        """
        Best-effort RSS discovery (fast, avoids Playwright for link discovery).

        This is the Inquirer equivalent of the ABS-CBN/Rappler "structured discovery" trick:
        use publisher feeds first, then fall back to HTML/Playwright discovery.
        """
        if max_items <= 0:
            return []
        rss_urls = [u.strip() for u in (INQUIRER_RSS_URLS or "").split(",") if u.strip()]
        if not rss_urls:
            return []

        headers: Dict[str, str] = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
            "Accept-Language": "en-PH,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "https://www.google.com/",
        }
        if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
            try:
                headers.update(get_advanced_stealth_headers())
            except Exception:
                pass

        cutoff_ts: Optional[float] = None
        try:
            cutoff_ts = time.time() - max(1, int(INQUIRER_RSS_MAX_AGE_H)) * 3600
        except Exception:
            cutoff_ts = None

        out: List[str] = []
        seen: set[str] = set()
        sess = self._get_http_session()
        for feed_url in rss_urls:
            if len(out) >= max_items:
                break
            try:
                r = sess.get(feed_url, headers=headers, timeout=(INQUIRER_HTTP_TIMEOUT_CONNECT_S, INQUIRER_HTTP_TIMEOUT_READ_S))
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text or "", "xml")
                for item in soup.find_all("item"):
                    if len(out) >= max_items:
                        break
                    link_tag = item.find("link")
                    link = (link_tag.get_text() or "").strip() if link_tag else ""
                    if not link or link in seen:
                        continue

                    if cutoff_ts is not None:
                        try:
                            pub = item.find("pubDate")
                            if pub and pub.get_text():
                                dt = parsedate_to_datetime(pub.get_text().strip())
                                if dt and dt.timestamp() < cutoff_ts:
                                    continue
                        except Exception:
                            pass

                    if self._validate_url(link):
                        seen.add(link)
                        out.append(link)
            except Exception:
                continue
        return out

    def _human_delay(self):
        """Random delay to mimic human browsing behavior."""
        if USE_HUMAN_DELAY and get_human_like_delay is not None:
            delay = get_human_like_delay()
        else:
            delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"Waiting {delay:.1f}s before next request (stealth mode)")
        time.sleep(delay)
        
    def _log_performance(self, operation: str, duration: float):
        """Log performance metrics for monitoring."""
        logger.info(f"Performance - {operation}: {duration:.2f}s")
        
    def _validate_url(self, url: str) -> bool:
        """Enhanced validation to only allow actual article URLs."""
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        # Only allow *.inquirer.net and subdomains
        if not parsed.netloc.endswith('inquirer.net'):
            return False
        # Exclude non-news subdomains
        excluded_subdomains = (
            'radyo.inquirer.net',
            'pep.inquirer.net',
        )
        if parsed.netloc in excluded_subdomains:
            return False
        # Reject obvious non-article utility pages
        blocked_paths = (
            '/tag/', '/author/', '/search', '/privacy-policy', '/user-agreement', '/contact', '/newsletter',
            '/job-openings', '/article-index', '/fullfeed', '/category/', '/regions', '/regions/',
            '/page-one-single/', '/page-one-single'
        )
        if any(bp in parsed.path for bp in blocked_paths):
            return False
        # Reject URLs that are too short (likely not articles)
        if len(parsed.path) < 10:
            return False
        # Allow WP-style permalinks: https://newsinfo.inquirer.net/?p=ID
        if parsed.netloc == 'newsinfo.inquirer.net' and parsed.path == '/' and 'p=' in (parsed.query or ''):
            return True
        # For newsinfo.inquirer.net, require numeric ID in path (like /2112172/article-title)
        if parsed.netloc == 'newsinfo.inquirer.net':
            path_parts = [p for p in parsed.path.split('/') if p]
            if len(path_parts) >= 2 and path_parts[0].isdigit():
                return True
        # For other subdomains, require substantial content in path
        allowed_news_subdomains = (
            'globalnation.inquirer.net',
            'business.inquirer.net',
            'sports.inquirer.net',
            'entertainment.inquirer.net',
            'lifestyle.inquirer.net',
            'technology.inquirer.net',
        )
        if parsed.netloc in allowed_news_subdomains:
            path_parts = [p for p in parsed.path.split('/') if p]
            # Must have at least 2 path segments and not be a category page
            return len(path_parts) >= 2 and not any(part in ['category', 'regions', 'tag', 'author'] for part in path_parts)
        return False
    
    def _sanitize_text(self, text: str) -> str:
        """Security: Sanitize extracted text content."""
        if not text:
            return ""

        # Normalize HTML entities first (e.g. &#039;, &lt;p&gt;...).
        try:
            text = _html.unescape(text)
        except Exception:
            pass

        # Remove script/style payloads and unsafe URI schemes.
        text = re.sub(r"(?is)<\s*(script|style)\b.*?>.*?<\s*/\s*\1\s*>", " ", text)
        text = text.replace("javascript:", "").replace("data:", "")

        # Convert HTML fragments to plain text (instead of escaping tags).
        if "<" in text and ">" in text:
            try:
                soup = BeautifulSoup(text, "html.parser")
                text = soup.get_text(" ", strip=True)
            except Exception:
                pass

        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _scrape_article_http(self, url: str) -> Optional[NormalizedArticle]:
        """
        HTTP-first scrape (no browser).

        Priority:
        1) JSON-LD (when present)
        2) Plain HTML parsing (same selectors as Playwright path)

        Returns None when content is missing/too short so caller can fall back to Playwright.
        """
        try:
            sess = self._get_http_session()
            timeout = (INQUIRER_HTTP_TIMEOUT_CONNECT_S, INQUIRER_HTTP_TIMEOUT_READ_S)
            r = sess.get(url, headers=self._http_headers(url), timeout=timeout)
            if r.status_code >= 400:
                return None
            soup = BeautifulSoup(r.text or "", "html.parser")

            title: str = ""
            body: str = ""
            published_raw: Optional[str] = None

            jsonld = extract_json_ld_newsarticle(soup) or None
            if jsonld:
                title = self._sanitize_text((jsonld.get("headline") or "").strip())
                body = self._sanitize_text((jsonld.get("articleBody") or "").strip())
                published_raw = (jsonld.get("datePublished") or "").strip() or None

            # Many Inquirer pages don't expose JSON-LD consistently; use HTML parsing as a fallback.
            if not title:
                title = self._extract_with_fallbacks(soup, self.SELECTORS["title"]) or ""
            if not body:
                extracted = self._extract_content_with_debug(soup, url) or ""
                body = self._sanitize_text(extracted)
            if published_raw is None:
                published_raw = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])

            if not title or not body:
                return None
            if len(body) < max(0, INQUIRER_HTTP_MIN_BODY_CHARS):
                return None

            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(body) > SCRAPER_CONTENT_MAX_CHARS:
                body = body[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"

            # Category normalization stays consistent with existing logic
            norm_cat, raw_cat = resolve_category_pair(url, soup)

            return build_article(
                source="Inquirer",
                title=title,
                url=url,
                content=body,
                category=norm_cat,
                published_at=published_raw,
                raw_category=raw_cat,
            )
        except Exception:
            return None
    
    def _extract_with_fallbacks(self, soup: BeautifulSoup, selector_list: List[str], 
                               attribute: str = None) -> Optional[str]:
        """Defensive extraction with multiple fallback selectors."""
        for selector in selector_list:
            try:
                element = soup.select_one(selector)
                if element:
                    if attribute:
                        value = element.get(attribute, '')
                    else:
                        value = element.get_text()
                    
                    if value and value.strip():
                        return self._sanitize_text(value)
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        return None
    
    def _extract_content_with_debug(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Enhanced content extraction with debugging and multiple strategies."""
        content_parts = []
        
        # Strategy 1: Try specific content selectors
        for selector in self.SELECTORS["content"]:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip()
                    if text and len(text) > 50:  # Only meaningful content
                        content_parts.append(text)
                        logger.debug(f"Found content with {selector}: {text[:100]}...")
            except Exception as e:
                logger.debug(f"Content selector {selector} failed: {e}")
                continue
        
        # Strategy 2: If no content found, try broader approach
        if not content_parts:
            logger.warning(f"No content found with specific selectors for {url}")
            
            # Try to find any meaningful text content
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 30 and not text.startswith('ADVERTISEMENT'):
                    content_parts.append(text)
                    logger.debug(f"Found fallback content: {text[:100]}...")
        
        # Strategy 3: Extract from article body
        if not content_parts:
            article_body = soup.find('article') or soup.find('.entry-content') or soup.find('.post-content')
            if article_body:
                paragraphs = article_body.find_all('p')
                for p in paragraphs:
                    text = p.get_text().strip()
                    if text and len(text) > 30:
                        content_parts.append(text)
                        logger.debug(f"Found article body content: {text[:100]}...")
        
        if content_parts:
            # Combine content parts (avoid aggressive truncation; keep full text when possible)
            combined = ' '.join(content_parts)
            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(combined) > SCRAPER_CONTENT_MAX_CHARS:
                combined = combined[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
            logger.info(f"Extracted {len(content_parts)} content parts, total length: {len(combined)}")
            return combined
        else:
            logger.warning(f"Could not extract any content from {url}")
            return None
    
    def _extract_article_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract article URLs with validation."""
        urls: List[str] = []
        seen: set[str] = set()
        
        for selector in self.SELECTORS["article_links"]:
            try:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.BASE_URL, href)
                        if self._validate_url(full_url) and full_url not in seen:
                            seen.add(full_url)
                            urls.append(full_url)
            except Exception as e:
                logger.error(f"Selector '{selector}' error: {e}")
                continue
                
        return urls
    
    def _new_context(self, browser: Browser):
        """Create browser context with resource blocking for better performance."""
        if USE_ADV_HEADERS and get_advanced_stealth_headers is not None:
            headers = get_advanced_stealth_headers()
            headers.setdefault('Referer', self.BASE_URL)
            user_agent = headers.get('User-Agent', self.USER_AGENT)
        else:
            headers = {'Referer': self.BASE_URL}
            user_agent = self.USER_AGENT
        context = browser.new_context(
            user_agent=user_agent,
            locale='en-PH',
            viewport={"width": 1366, "height": 768},
            java_script_enabled=True,
        )
        
        # Block heavy resources to improve performance
        context.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
            or any(domain in route.request.url for domain in [
                "google-analytics.com", "googletagmanager.com", "facebook.com", 
                "doubleclick.net", "googlesyndication.com", "adsystem.com"
            ]) else route.continue_()
        ))
        
        return context
    
    def _scrape_article_page(self, url: str, context) -> Optional[NormalizedArticle]:
        """Scrape individual article page with enhanced content extraction."""
        page = None
        try:
            page = context.new_page()
            dump_network = install_json_response_logger(
                page,
                enabled=bool(INQUIRER_NETWORK_DEBUG),
                max_items=max(0, int(INQUIRER_NETWORK_DEBUG_MAX)),
            )
            page.set_extra_http_headers(
                get_advanced_stealth_headers() if (USE_ADV_HEADERS and get_advanced_stealth_headers is not None) else {
                'User-Agent': self.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                    'Referer': self.BASE_URL,
                }
            )
            
            # Set reasonable timeouts
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)
            
            # Retry logic for page.goto
            resp = None
            for attempt in range(2):
                try:
                    resp = page.goto(url, wait_until='domcontentloaded')
                    if resp and resp.status < 400:
                        break
                    if attempt == 0:
                        logger.warning(f"Inquirer: attempt {attempt + 1} failed for {url}, retrying...")
                        time.sleep(2)
                except Exception as e:
                    if attempt == 0:
                        logger.warning(f"Inquirer: attempt {attempt + 1} error for {url}: {e}, retrying...")
                        time.sleep(2)
                    else:
                        raise e
            
            if not resp or resp.status >= 400:
                logger.warning(f"HTTP {resp.status if resp else 'unknown'} for {url}")
                return None
            
            # Wait for content to load
            try:
                page.wait_for_selector('h1', timeout=10000)
            except:
                pass  # Continue even if h1 doesn't appear
                
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract article data with enhanced content extraction
            title = self._extract_with_fallbacks(soup, self.SELECTORS["title"])
            if not title:
                logger.warning(f"No title found for {url}")
                return None
                
            # Enhanced content extraction
            content_text = self._extract_content_with_debug(soup, url)
            published_date = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])

            if INQUIRER_NETWORK_DEBUG:
                try:
                    rows = dump_network()
                    show = min(10, len(rows))
                    if rows:
                        logger.info(
                            "Inquirer network debug (captured=%s, showing up to %s): %s",
                            len(rows),
                            show,
                            rows[:show],
                        )
                    else:
                        logger.info("Inquirer network debug: no JSON/XHR responses captured")
                except Exception:
                    pass
            
            # Log what we found for debugging
            logger.info(f"Article {url}: Title='{title}', Content length={len(content_text) if content_text else 0}")
            
            # Build normalized article
            norm_cat, raw_cat = resolve_category_pair(url, soup)
            article = build_article(
                source="Inquirer",
                title=title,
                url=url,
                content=self._sanitize_text(content_text or ""),
                category=norm_cat,
                published_at=published_date,
                raw_category=raw_cat,
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None
        finally:
            try:
                if page is not None:
                    page.close()
            except Exception:
                pass
    
    def scrape_latest(self, max_articles: int = 10) -> ScrapingResult:
        """Main scraping method with comprehensive error handling and monitoring."""
        start_time = time.time()
        articles = []
        errors = []
        discovery_existing_urls: set[str] = set()
        discovery_method = "playwright"
        timings: Dict[str, Any] = {
            "discovery_s": None,
            "preflight_s": None,
            "http_article_s": [],
            "playwright_article_s": [],
            "http_ok": 0,
            "playwright_ok": 0,
        }
        
        try:
            # -------------------------
            # Discovery (HTTP optional) + DB preflight
            # -------------------------
            logger.info("Starting Inquirer scraping session")
            logger.info(
                "Inquirer flags USE_ADV_HEADERS=%s USE_HUMAN_DELAY=%s USE_URL_FILTER=%s INQUIRER_HTTP_FASTPATH=%s INQUIRER_HTTP_DISCOVERY=%s",
                USE_ADV_HEADERS,
                USE_HUMAN_DELAY,
                USE_URL_FILTER,
                INQUIRER_HTTP_FASTPATH,
                INQUIRER_HTTP_DISCOVERY,
            )

            t_discovery0 = time.time()
            article_urls: List[str] = []

            # 0) RSS discovery (structured feed) - fastest/lowest churn when available.
            if INQUIRER_RSS_DISCOVERY:
                rss_urls = self._discover_urls_rss(max_items=max(25, max_articles * 6))
                if rss_urls:
                    article_urls = rss_urls
                    discovery_method = "rss"
                    logger.info("Inquirer discovery: method=rss raw=%s", len(article_urls))

            if INQUIRER_HTTP_DISCOVERY:
                try:
                    sess = self._get_http_session()
                    timeout = (INQUIRER_HTTP_TIMEOUT_CONNECT_S, INQUIRER_HTTP_TIMEOUT_READ_S)
                    r = sess.get(self.BASE_URL, headers=self._http_headers(self.BASE_URL), timeout=timeout)
                    if r.status_code < 400:
                        soup = BeautifulSoup(r.text or "", "html.parser")
                        article_urls = self._extract_article_links(soup)
                        if len(article_urls) >= 5:
                            discovery_method = "http"
                            logger.info("Inquirer discovery: method=http raw=%s", len(article_urls))
                        else:
                            logger.warning("Inquirer discovery: HTTP yielded too few links (raw=%s); falling back to Playwright", len(article_urls))
                            article_urls = []
                except Exception as e:
                    logger.warning("Inquirer discovery: HTTP failed (%s); falling back to Playwright", e)
                    article_urls = []

            if not article_urls:
                discovery_method = "playwright"
                with launch_browser() as browser:
                    context = self._new_context(browser)
                    page = context.new_page()
                    page.set_extra_http_headers({'User-Agent': self.USER_AGENT})
                    response = page.goto(self.BASE_URL, wait_until='domcontentloaded')
                    if not response or response.status >= 400:
                        raise Exception(f"Homepage returned {response.status if response else 'unknown'}")
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    article_urls = self._extract_article_links(soup)
                    try:
                        page.close()
                    except Exception:
                        pass
                    try:
                        context.close()
                    except Exception:
                        pass

            candidates = unique_canonical_urls(article_urls)
            t_discovery1 = time.time()
            timings["discovery_s"] = round(t_discovery1 - t_discovery0, 3)

            t_preflight0 = time.time()
            to_scrape, existing = filter_existing_article_urls(candidates)
            t_preflight1 = time.time()
            timings["preflight_s"] = round(t_preflight1 - t_preflight0, 3)

            discovery_existing_urls = existing
            logger.info(
                "Inquirer discovery: method=%s raw=%s unique=%s existing_in_db=%s new_to_scrape=%s",
                discovery_method,
                len(article_urls),
                len(candidates),
                len(existing),
                len(to_scrape),
            )

            # -------------------------
            # Article scraping (HTTP fast-path + Playwright fallback)
            # -------------------------
            context = None
            browser_cm = None
            try:
                for i, url in enumerate(to_scrape):
                    if len(articles) >= max_articles:
                        break

                    article = None

                    if INQUIRER_HTTP_FASTPATH:
                        t0 = time.time()
                        article = self._scrape_article_http(url)
                        timings["http_article_s"].append(round(time.time() - t0, 3))
                        if article is not None:
                            timings["http_ok"] += 1
                            articles.append(article)
                            logger.info("Inquirer HTTP: scraped '%s' | content_len=%s", article.title, len(article.content or ""))
                            continue

                    # Playwright fallback (lazy-init)
                    if context is None:
                        browser_cm = launch_browser()
                        browser = browser_cm.__enter__()
                        context = self._new_context(browser)

                    t0 = time.time()
                    article = self._scrape_article_page(url, context)
                    timings["playwright_article_s"].append(round(time.time() - t0, 3))

                    if article:
                        timings["playwright_ok"] += 1
                        articles.append(article)
                        logger.info("Inquirer PW: scraped '%s' | content_len=%s", article.title, len(article.content or ""))
                        # Only delay when we actually use Playwright (expensive + more bot-sensitive).
                        if len(articles) < max_articles and i < len(to_scrape) - 1:
                            self._human_delay()
                    else:
                        errors.append(f"Failed to extract article from {url}")

            finally:
                try:
                    if context is not None:
                        context.close()
                except Exception:
                    pass
                try:
                    if browser_cm is not None:
                        browser_cm.__exit__(None, None, None)
                except Exception:
                    pass
                    
        except Exception as e:
            error_msg = f"Critical scraping error: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # Performance metrics
        total_time = time.time() - start_time
        performance = {
            "total_time": total_time,
            "articles_per_second": len(articles) / total_time if total_time > 0 else 0,
            "success_rate": len(articles) / (len(articles) + len(errors)) if (len(articles) + len(errors)) > 0 else 0
        }
        
        metadata = {
            "source": "Philippine Daily Inquirer",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "method": {
                "discovery": discovery_method,
                "http_fastpath": bool(INQUIRER_HTTP_FASTPATH),
                "http_discovery": bool(INQUIRER_HTTP_DISCOVERY),
            },
            "timings": timings,
            "discovery": {
                "existing_in_db": len(discovery_existing_urls),
            },
        }
        
        logger.info(f"Scraping completed: {len(articles)} articles, {len(errors)} errors in {total_time:.2f}s")
        
        return ScrapingResult(
            articles=articles,
            errors=errors,
            performance=performance,
            metadata=metadata
        )

# Convenience function for Celery tasks
def scrape_inquirer_latest() -> List[NormalizedArticle]:
    """Entry point for Celery tasks - returns just the articles."""
    scraper = InquirerScraper()
    result = scraper.scrape_latest(max_articles=10)
    
    # Log results for monitoring
    logger.info(f"Inquirer scraping result: {result.metadata}")
    if result.errors:
        logger.warning(f"Scraping errors: {result.errors}")
    
    return result.articles 


def debug_inquirer_url(url: str) -> dict:
    """
    Developer helper: scrape a single URL and (optionally) print network debug logs.

    Usage (inside worker container):
      INQUIRER_NETWORK_DEBUG=1 python -c "from app.scrapers.inquirer import debug_inquirer_url; print(debug_inquirer_url('https://...'))"
    """
    scraper = InquirerScraper()
    try:
        with launch_browser() as browser:
            context = scraper._new_context(browser)
            art = scraper._scrape_article_page(url, context)
            try:
                context.close()
            except Exception:
                pass
            return {"ok": bool(art), "title": getattr(art, "title", None)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
