import time
import logging
import random
import json
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass
from bs4 import BeautifulSoup
from app.pipeline.normalize import build_article, NormalizedArticle
import httpx
import brotli
from app.scrapers.utils import resolve_category_pair
from datetime import datetime, timezone
import re
# Feature flags (env-driven) for gradual rollout
import os


def _env_flag(name: str, default: bool = False) -> bool:
    val = os.getenv(name, str(default)).strip().lower()
    return val in {"1", "true", "yes", "on"}

USE_ADV_HEADERS = _env_flag("USE_ADV_HEADERS", False)
USE_HUMAN_DELAY = _env_flag("USE_HUMAN_DELAY", False)
USE_URL_FILTER = _env_flag("USE_URL_FILTER", False)

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

class ManilaTimesScraper:
    """BLACKHAT Manila Times Scraper - Ultra-Conservative Stealth Approach with 502 handling"""

    BASE_URL = "https://www.manilatimes.net"
    
    # Static article URLs discovered from reconnaissance
    STATIC_ARTICLE_URLS = [
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040",
        "https://www.manilatimes.net/2025/09/07/the-sunday-times/filipino-champions/be-juan-tama-advocacy-inspires-filipinos-to-choose-learning/2180194",
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040",
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040",
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040"
    ]
    
    # Discovery entry points for latest news
    DISCOVERY_PATHS = [
        "/business/",
        "/sports/",
        "/opinion/",
        "/world/",
        "/lifestyle/",
        "/entertainment/",
        "/politics/",
        "/news/latest/",
        "/news/"
    ]
    
    # Rotating User-Agents for stealth
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]
    
    # Ultra-conservative delays
    MIN_DELAY = 30.0
    MAX_DELAY = 60.0

    def __init__(self):
        self.name = "manila_times"
        logger.info(f"{self.name}: Initialized with stealth approach")

    def _get_random_ua(self) -> str:
        """Get random User-Agent for stealth."""
        return random.choice(self.USER_AGENTS)

    def _human_delay(self):
        """Ultra-conservative human-like delay."""
        delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"{self.name}: Stealth delay {delay:.1f}s")
        time.sleep(delay)

    def _get_stealth_headers(self) -> Dict[str, str]:
        """Get stealth headers to avoid detection."""
        return {
            "User-Agent": self._get_random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/",  # KEY: Google referrer
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

    def _normalize_published_date(self, date_str: str) -> Optional[str]:
        """Normalize published date to ISO format."""
        if not date_str:
            return None
        
        try:
            # Try common date formats
            formats = [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z", 
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%B %d, %Y",
                "%b %d, %Y",
                "%d %B %Y",
                "%d %b %Y"
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.isoformat()
                except ValueError:
                    continue
            
            # If all formats fail, return current time
            logger.warning(f"{self.name}: Could not parse date '{date_str}', using current time")
            return datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            logger.warning(f"{self.name}: Date normalization error: {e}")
            return datetime.now(timezone.utc).isoformat()

    def _fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch URL with retry logic for 502 errors."""
        for attempt in range(max_retries):
            try:
                timeout = random.uniform(25.0, 35.0)
                logger.info(f"{self.name}: Fetching {url} (attempt {attempt + 1}/{max_retries}) with timeout {timeout:.1f}s")
                
                with httpx.Client(
                    follow_redirects=True,
                    timeout=float(timeout),
                    headers=self._get_stealth_headers(),
                    verify=False  # KEY: Disable SSL verification
                ) as client:
                    response = client.get(url)
                    
                    # Handle 502 specifically
                    if response.status_code == 502:
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) + random.uniform(1, 3)  # Exponential backoff
                            logger.warning(f"{self.name}: 502 error for {url}, retrying in {wait_time:.1f}s")
                            time.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"{self.name}: 502 error for {url} after {max_retries} attempts")
                            return None
                    
                    response.raise_for_status()
                    
                    # Handle Brotli decompression manually
                    if response.headers.get("content-encoding") == "br":
                        try:
                            decompressed_content = brotli.decompress(response.content)
                            return decompressed_content.decode("utf-8")
                        except Exception as e:
                            logger.warning(f"Brotli decompression failed for {url}: {e}")
                            return response.text
                    
                    return response.text
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 502 and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(f"{self.name}: 502 error for {url}, retrying in {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"{self.name}: HTTP error fetching {url}: {e.response.status_code} - {e.response.text[:100]}")
                    return None
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(f"{self.name}: Request error for {url}, retrying in {wait_time:.1f}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"{self.name}: Request error fetching {url}: {e}")
                    return None
            except Exception as e:
                logger.error(f"{self.name}: Unexpected error fetching {url}: {e}")
                return None
        
        return None

    def _validate_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            if not parsed.netloc.endswith("manilatimes.net"):
                return False
            return True
        except Exception:
            return False

    def _is_probable_article(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            path = parsed.path or ""
            if not path.startswith("/2025/") and "/news/" not in path:
                return False
            bad_segments = {"video", "videos", "photo", "photos", "gallery", "opinion", "regions"}
            segments = [seg for seg in path.split('/') if seg]
            if any(seg in bad_segments for seg in segments):
                return False
            # Likely article if ends with numeric id or has long slug
            return path.rstrip('/').split('/')[-1].isdigit() or len(path) > 40
        except Exception:
            return False

    def _discover_latest_urls(self, limit: int = 10) -> List[str]:
        urls: List[str] = []
        seen = set()
        try:
            for path in self.DISCOVERY_PATHS:
                html = self._fetch_with_retry(urljoin(self.BASE_URL, path))
                if not html:
                    continue
                soup = BeautifulSoup(html, 'html.parser')
                # Broad selectors covering Manila Times listing blocks
                link_selectors = [
                    "h3 a",
                    ".td-module-thumb a",
                    ".tdb_module_loop a",
                    "a.td-image-wrap",
                    "a[href*='/2025/']",
                    "a[href*='/news/']",
                ]
                for sel in link_selectors:
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
                        if len(urls) >= limit:
                            break
                    if len(urls) >= limit:
                        break
                if len(urls) >= limit:
                    break
        except Exception as e:
            logger.warning(f"{self.name}: discovery failed: {e}")
        return urls

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title."""
        # Try multiple selectors for Manila Times
        title_selectors = [
            "h1",
            "h2", 
            "h3",
            ".article-title",
            ".tdb-title-text",
            "title",
            "h1.article-title.tdb-title-text",
            "h1.article-title.font-700",
            "h1.article-title.roboto-slab-3",
            "h1.article-title",
            "h1.tdb-title-text",
            "h1.roboto-slab-3",
            'h1.article-title-h1',
            'h1.article-title-h2', 
            'h1.article-title-h3',
            'h1',
            '.article-title',
            'title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 10:  # Basic validation
                    return title
        
        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article content."""
        content_selectors = [
            "div.tdb-block-inner p",
            "div.tdb-block-inner",
            "div.tdb-block",
            ".article-content",
            ".entry-content",
            ".post-content",
            "article p",
            ".content p",
            "main p",
            "p"
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Get all paragraphs
                paragraphs = content_elem.find_all("p") if content_elem.name != "p" else [content_elem]
                if paragraphs:
                    content = " ".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                    if content and len(content) > 100:  # Basic validation
                        return content
        
        return None

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract published date."""
        date_selectors = [
            "time[datetime]",
            ".published-date",
            ".article-date",
            ".post-date",
            "meta[property='article:published_time']",
            "meta[name='publish_date']"
        ]
        
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                if date_elem.name == "meta":
                    date_str = date_elem.get("content", "").strip()
                else:
                    date_str = date_elem.get("datetime", "").strip() or date_elem.get_text(strip=True)
                
                if date_str:
                    return self._normalize_published_date(date_str)
        
        return None

    def _sanitize_text(self, text: str) -> str:
        """Sanitize extracted text."""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = " ".join(text.split())
        
        # Remove common unwanted patterns
        unwanted_patterns = [
            "Advertisement",
            "Subscribe to our newsletter",
            "Follow us on",
            "Share this article",
            "Read more:",
            "Continue reading",
            "Advertisement"
        ]
        
        for pattern in unwanted_patterns:
            text = text.replace(pattern, "")
        
        return text.strip()

    def _extract_manila_times_category(self, url: str, soup: BeautifulSoup) -> (str, Optional[str]):
        """Infer canonical and raw category for Manila Times.
        Priority: URL path → meta tags/breadcrumbs → fallback 'News'."""
        normalized = "News"
        raw = None
        try:
            parsed = urlparse(url)
            parts = [p for p in parsed.path.split('/') if p]
            # URL patterns often include a section after the date or at the top-level
            # e.g., /2025/09/07/news/.../{id} or /opinion/columns/.../{id}
            candidates = []
            for p in parts:
                lp = p.lower()
                # collect plausible category tokens (including sub-sections)
                if any(k in lp for k in [
                    "news", "business", "sports", "opinion", "editorial", "world",
                    "regions", "lifestyle", "entertainment", "campus", "politics",
                    "top-business", "foreign-business", "top-sports", "columns",
                    "the-sunday-times", "top-news"
                ]):
                    candidates.append(lp)
            # prefer more specific sub-section if present, else the first
            section = None
            if candidates:
                # prioritize explicit main sections
                priority = [
                    "business", "sports", "opinion", "world", "politics",
                    "lifestyle", "entertainment", "news", "regions", "campus"
                ]
                for pri in priority:
                    for c in candidates:
                        if c == pri or c.startswith(f"{pri}/"):
                            section = pri
                            break
                    if section:
                        break
                if not section:
                    section = candidates[0]
            mapping = {
                "news": "News",
                "top-news": "News",
                "business": "Business",
                "top-business": "Business",
                "foreign-business": "Business",
                "sports": "Sports",
                "top-sports": "Sports",
                "opinion": "Opinion",
                "columns": "Opinion",
                "editorial": "Opinion",
                "world": "World",
                "regions": "Nation",
                "politics": "Politics",
                "lifestyle": "Lifestyle",
                "entertainment": "Entertainment",
                "campus": "Campus",
                "the-sunday-times": "News",
            }
            if section in mapping:
                normalized = mapping[section]
                raw = section.replace("-", " ").title()
        except Exception:
            pass
        # Meta fallbacks
        try:
            if not raw:
                # Common meta keys used by MT
                meta = (soup.find("meta", {"property": "article:section"})
                        or soup.find("meta", {"itemprop": "articleSection"})
                        or soup.find("meta", {"property": "mrf:sections"})
                        or soup.find("meta", attrs={"name": "section"}))
                if meta and (meta.get("content") or meta.get("value")):
                    raw_val = (meta.get("content") or meta.get("value") or "").strip()
                    if raw_val:
                        raw = raw_val
                        key = raw_val.lower().replace(" ", "-")
                        normalized = mapping.get(key, raw_val.title())
        except Exception:
            pass
        # Breadcrumb fallback
        try:
            if not raw:
                for sel in [".breadcrumb a", "nav.breadcrumb a", "ol.breadcrumb li a", ".breadcrumbs a"]:
                    a = soup.select_one(sel)
                    if a:
                        text = a.get_text(strip=True)
                        if text and text.lower() not in {"home", "the manila times", "manila times"}:
                            raw = text
                            normalized = mapping.get(text.lower(), text.title())
                            break
        except Exception:
            pass
        return normalized, raw

    def _extract_with_fallbacks(self, soup: BeautifulSoup, url: str) -> Optional[NormalizedArticle]:
        """Extract article with multiple fallback strategies."""
        try:
            # Extract basic fields
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            published_date = self._extract_published_date(soup)
            
            # Sanitize content
            if content:
                content = self._sanitize_text(content)
            
            # Validate required fields
            if not title or not content:
                logger.warning(f"{self.name}: Missing required fields for {url}")
                return None
            
            # Category extraction
            norm_cat, raw_cat = self._extract_manila_times_category(url, soup)
            logger.info(f"{self.name}: resolved category norm={norm_cat}, raw={raw_cat} for {url}")
            
            # Build normalized article
            article = build_article(
                title=title,
                content=content,
                url=url,
                published_at=published_date,
                source="Manila Times",
                category=norm_cat,
                raw_category=raw_cat,
            )
            
            return article
            
        except Exception as e:
            logger.error(f"{self.name}: Error extracting article from {url}: {e}")
            return None

    def scrape_latest(self, max_articles: int = 10) -> ScrapingResult:
        """Scrape latest articles with stealth approach and 502 handling."""
        start_time = time.time()
        articles = []
        errors = []
        
        # Try discovery first
        discovered = self._discover_latest_urls(limit=max_articles * 3)
        candidate_urls = discovered[:max_articles] if discovered else self.STATIC_ARTICLE_URLS[:max_articles]
        logger.info(f"{self.name}: Using {len(candidate_urls)} candidate articles (discovered={len(discovered)})")
        
        for i, url in enumerate(candidate_urls, 1):
            try:
                logger.info(f"{self.name}: Scraping article {i}/{len(candidate_urls)}: {url}")
                
                # Stealth delay between requests
                if i > 1:
                    self._human_delay()
                
                # Fetch and parse
                logger.info(f"{self.name}: Scraping {url}")
                html = self._fetch_with_retry(url)
                
                if not html:
                    error_msg = f"Failed to fetch {url} (likely 502 or network error)"
                    logger.warning(f"{self.name}: {error_msg}")
                    errors.append(error_msg)
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                article = self._extract_with_fallbacks(soup, url)
                
                if article:
                    articles.append(article)
                    logger.info(f"{self.name}: Successfully scraped: {article.title[:50]}...")
                else:
                    error_msg = f"Failed to extract article from {url}"
                    logger.warning(f"{self.name}: {error_msg}")
                    errors.append(error_msg)
                
            except Exception as e:
                error_msg = f"Error processing {url}: {str(e)}"
                logger.error(f"{self.name}: {error_msg}")
                errors.append(error_msg)
        
        # Calculate performance metrics
        total_time = time.time() - start_time
        success_rate = len(articles) / len(candidate_urls) if candidate_urls else 0
        
        logger.info(f"{self.name}: Completed {len(articles)} articles, {len(errors)} errors in {total_time:.1f}s")
        
        return ScrapingResult(
            articles=articles,
            errors=errors,
            performance={
                "total_time": total_time,
                "success_rate": success_rate,
                "articles_per_second": len(articles) / total_time if total_time > 0 else 0
            },
            metadata={
                "scraper": self.name,
                "urls_processed": len(candidate_urls),
                "stealth_mode": True,
                "502_handling": True
            }
        )
