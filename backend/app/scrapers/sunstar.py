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
from datetime import datetime, timezone
import re
import urllib.request
import json
import httpx
import xml.etree.ElementTree as ET
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
SUNSTAR_FETCH_FULL_ON_SHORT = _env_flag("SUNSTAR_FETCH_FULL_ON_SHORT", True)
SCRAPER_CONTENT_MAX_CHARS = _env_int("SCRAPER_CONTENT_MAX_CHARS", 8000)

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


class SunstarScraper:
    """Advanced stealth scraper for Sunstar with senior dev + black hat techniques."""

    BASE_URL = "https://www.sunstar.com.ph"
    RSS_URL = "https://www.sunstar.com.ph/api/v1/collections/home.rss"
    SECTIONS = [
        "/cebu/",
        "/davao/", 
        "/manila/",
        "/bohol/",
        "/pampanga/",
        "/baguio/",
        "/zamboanga/",
        "/iloilo/",
        "/tacloban/",
        "/general-santos/",
    ]

    def _extract_sunstar_category(self, url: str, rss_category: Optional[str]) -> Tuple[str, Optional[str]]:
        """Extract normalized and raw category for SunStar using URL + RSS hints.
        Priority: URL path → RSS category → fallback 'General'."""
        normalized = "General"
        raw = None

        try:
            parsed = urlparse(url)
            parts = [p for p in parsed.path.split('/') if p]
            # Patterns:
            # /{city}/local-news/... ; /{city}/business/... ; /{city}/sports/...
            # /article/{id}/{city}/{section}/{slug}
            city_or_prefix = parts[0].lower() if len(parts) >= 1 else None
            section = None

            if city_or_prefix == "article" and len(parts) >= 4:
                # /article/1976093/davao/local-news/slug
                section = parts[3].lower()
            elif len(parts) >= 2:
                # /cebu/local-news/slug  or /manila/business/slug
                section = parts[1].lower()

            # Map section keywords to canonical categories
            section_map = {
                "local-news": "Nation",
                "nation": "Nation",
                "business": "Business",
                "sports": "Sports",
                "opinion": "Opinion",
                "world": "World",
                "lifestyle": "Lifestyle",
                "entertainment": "Entertainment",
                "traffic": "Metro",
            }

            if section in section_map:
                normalized = section_map[section]
                raw = section.replace('-', ' ').title()
            else:
                # Fallback to city/region as raw when section unknown
                if city_or_prefix and city_or_prefix not in {"article"}:
                    raw = city_or_prefix.replace('-', ' ').title()
                    # Treat city buckets as Nation/Local
                    normalized = "Nation"
        except Exception:
            pass

        # Use RSS category as a hint if URL did not provide anything specific
        if (raw is None or normalized == "General") and rss_category:
            hint = rss_category.strip()
            raw = raw or hint
            key = hint.lower()
            if "business" in key:
                normalized = "Business"
            elif "sport" in key:
                normalized = "Sports"
            elif "opinion" in key or "editorial" in key:
                normalized = "Opinion"
            elif "world" in key:
                normalized = "World"
            elif "lifestyle" in key:
                normalized = "Lifestyle"
            elif "entertainment" in key or "showbiz" in key:
                normalized = "Entertainment"
            elif "nation" in key or "local" in key or "metro" in key:
                normalized = "Nation"

        return normalized, raw

    # User-Agent rotation for stealth
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    def __init__(self):
        self.session = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": random.choice(self.USER_AGENTS)},
            follow_redirects=True
        )
        self.articles_scraped = 0
        self.errors = []
        self.start_time = time.time()

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()

    def _get_random_delay(self) -> float:
        """Generate random delay to avoid rate limiting."""
        return random.uniform(5.0, 12.0)  # Increased for better stealth

    def _make_request(self, url: str, retries: int = 3) -> Optional[httpx.Response]:
        """Make HTTP request with retry logic and stealth headers."""
        for attempt in range(retries):
            try:
                # Random delay between requests
                if attempt > 0:
                    delay = self._get_random_delay() * (attempt + 1)
                    logger.info(f"Retrying request to {url} after {delay:.2f}s delay")
                    time.sleep(delay)
                else:
                    time.sleep(self._get_random_delay())

                # Rotate User-Agent
                headers = {
                    "User-Agent": random.choice(self.USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Cache-Control": "max-age=0",
                }

                response = self.session.get(url, headers=headers)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    logger.warning(f"Rate limited on {url}, waiting longer...")
                    time.sleep(random.uniform(5.0, 10.0))
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt == retries - 1:
                    self.errors.append(f"Failed to fetch {url}: {str(e)}")
                    
        return None

    def scrape_rss_feed(self, max_articles: int = 3) -> List[NormalizedArticle]:
        """Scrape articles from Sunstar RSS feed - primary method."""
        logger.info("🎯 Starting Sunstar RSS feed scraping...")
        articles = []
        
        try:
            response = self._make_request(self.RSS_URL)
            if not response:
                logger.error("Failed to fetch RSS feed")
                return articles

            # Parse XML
            root = ET.fromstring(response.text)
            
            # Handle namespaces
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'dc': 'http://purl.org/dc/elements/1.1/',
                'content': 'http://purl.org/rss/1.0/modules/content/',
                'media': 'http://search.yahoo.com/mrss/'
            }

            # Find all items
            items = root.findall('.//item')
            logger.info(f"Found {len(items)} items in RSS feed")

            # Limit processing to max_articles for stealth
            items_to_process = items[:max_articles]
            logger.info(f"Processing {len(items_to_process)} items (stealth limit)")

            for item in items_to_process:
                try:
                    # Extract basic info
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    description_elem = item.find('description')
                    pub_date_elem = item.find('pubDate')
                    
                    # Try to get content from content:encoded
                    content_elem = item.find('{http://purl.org/rss/1.0/modules/content/}encoded')
                    
                    # Check if we have valid title and link with text content
                    if title_elem is None or link_elem is None or not title_elem.text or not link_elem.text:
                        continue

                    title = title_elem.text.strip()
                    url = link_elem.text.strip()
                    
                    # Get content from content:encoded or description
                    content = ""
                    if content_elem is not None and content_elem.text:
                        # Clean HTML content
                        soup = BeautifulSoup(content_elem.text, 'html.parser')
                        content = soup.get_text(" ", strip=True)
                    elif description_elem and description_elem.text:
                        content = description_elem.text.strip()

                    # If RSS only provides an excerpt, fetch the full article body as a best-effort.
                    # Keep this conservative (only when clearly too short), since it adds requests.
                    if SUNSTAR_FETCH_FULL_ON_SHORT and content and (len(content) < 280 or re.search(r"(\.\.\.|…)\s*$", content)):
                        full = self.scrape_article_content(url)
                        if full and len(full) > len(content) + 200:
                            content = full

                    if SCRAPER_CONTENT_MAX_CHARS > 0 and len(content) > SCRAPER_CONTENT_MAX_CHARS:
                        content = content[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
                    
                    # Parse publication date
                    published_at = None
                    if pub_date_elem and pub_date_elem.text:
                        try:
                            # Parse RFC 2822 date format
                            from email.utils import parsedate_to_datetime
                            published_at = parsedate_to_datetime(pub_date_elem.text).isoformat()
                        except:
                            published_at = datetime.now(timezone.utc).isoformat()

                    # Prefer URL-derived category; fall back to RSS-provided category
                    rss_category = None
                    categories = item.findall('category')
                    if categories:
                        for cat in categories:
                            if cat.text and cat.text not in ['Balita', 'News']:
                                rss_category = cat.text
                                break
                        if not rss_category and categories[0].text:
                            rss_category = categories[0].text

                    norm_cat, raw_cat = self._extract_sunstar_category(url, rss_category)
                    
                    # Build article
                    article = build_article(
                        source="Sunstar",
                        title=title,
                        url=url,
                        content=content,
                        category=norm_cat,
                        published_at=published_at,
                        raw_category=raw_cat,
                    )
                    
                    articles.append(article)
                    self.articles_scraped += 1
                    
                    # Stealth delay between articles
                    if len(articles) < max_articles:
                        delay = random.uniform(1.0, 3.0)
                        logger.info(f"Sunstar: waiting {delay:.1f}s (stealth)")
                        time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"Error processing RSS item: {e}")
                    self.errors.append(f"RSS item processing error: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"RSS feed parsing error: {e}")
            self.errors.append(f"RSS feed error: {str(e)}")

        logger.info(f"✅ RSS scraping completed: {len(articles)} articles")
        return articles

    def _extract_category_from_url(self, url: str) -> Optional[str]:
        """Extract category from URL path."""
        if not url:
            return None
            
        # Extract from URL path
        url_lower = url.lower()
        if '/cebu/' in url_lower:
            return "Cebu"
        elif '/davao/' in url_lower:
            return "Davao"
        elif '/manila/' in url_lower:
            return "Manila"
        elif '/bohol/' in url_lower:
            return "Bohol"
        elif '/pampanga/' in url_lower:
            return "Pampanga"
        elif '/baguio/' in url_lower:
            return "Baguio"
        elif '/zamboanga/' in url_lower:
            return "Zamboanga"
        elif '/iloilo/' in url_lower:
            return "Iloilo"
        elif '/tacloban/' in url_lower:
            return "Tacloban"
        elif '/general-santos/' in url_lower:
            return "General Santos"
        elif '/sports/' in url_lower:
            return "Sports"
        elif '/business/' in url_lower:
            return "Business"
        elif '/entertainment/' in url_lower:
            return "Entertainment"
        elif '/lifestyle/' in url_lower:
            return "Lifestyle"
        elif '/opinion/' in url_lower:
            return "Opinion"
        else:
            return "General"

    def scrape_article_content(self, url: str) -> Optional[str]:
        """Scrape full article content from individual article page."""
        try:
            response = self._make_request(url)
            if not response:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Multiple selectors for article content
            content_selectors = [
                'div.article-content',
                'div.entry-content',
                'div.post-content',
                'div.content',
                'article .content',
                '.article-body',
                '.post-body'
            ]
            
            content = None
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Remove script and style elements
                    for script in content_elem(["script", "style"]):
                        script.decompose()
                    # Prefer paragraph text to avoid nav/related leakage.
                    paragraphs = [p.get_text(" ", strip=True) for p in content_elem.find_all("p")]
                    paragraphs = [p for p in paragraphs if p and len(p) > 25 and not p.lower().startswith("advertisement")]
                    content = "\n\n".join(paragraphs) if paragraphs else content_elem.get_text(" ", strip=True)
                    break

            if content:
                # Preserve paragraph breaks while normalizing intra-line spacing.
                content = re.sub(r"[ \t]+", " ", content)
                content = re.sub(r"\n{3,}", "\n\n", content).strip()
                if SCRAPER_CONTENT_MAX_CHARS > 0 and len(content) > SCRAPER_CONTENT_MAX_CHARS:
                    content = content[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
            return content
            
        except Exception as e:
            logger.error(f"Error scraping article content from {url}: {e}")
            return None

    def scrape_section(self, section: str) -> List[NormalizedArticle]:
        """Scrape articles from a specific section."""
        logger.info(f"🎯 Scraping Sunstar section: {section}")
        articles = []
        
        section_url = urljoin(self.BASE_URL, section)
        
        try:
            response = self._make_request(section_url)
            if not response:
                return articles

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find article links
            article_links = soup.find_all('a', href=True)
            
            for link in article_links[:20]:  # Limit to first 20 articles
                href = link.get('href')
                if not href:
                    continue
                    
                # Make absolute URL
                article_url = urljoin(section_url, href)
                
                # Check if it's an article URL
                if self._is_article_url(article_url):
                    title = link.get_text(strip=True)
                    if title and len(title) > 10:  # Filter out short titles
                        norm_cat, raw_cat = self._extract_sunstar_category(article_url, None)
                        article = build_article(
                            source="Sunstar",
                            title=title,
                            url=article_url,
                            content=None,
                            category=norm_cat,
                            published_at=None,
                            raw_category=raw_cat,
                        )
                        articles.append(article)

        except Exception as e:
            logger.error(f"Error scraping section {section}: {e}")
            self.errors.append(f"Section scraping error: {str(e)}")

        return articles

    def _is_article_url(self, url: str) -> bool:
        """Check if URL is likely an article."""
        if not url or self.BASE_URL not in url:
            return False
            
        # Skip non-article URLs
        skip_patterns = [
            '/category/',
            '/tag/',
            '/author/',
            '/page/',
            '/search/',
            '/contact/',
            '/about/',
            '/advertisement/',
            '/opinion/',
            '/editorial/',
            '.jpg', '.png', '.gif', '.pdf'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                return False
                
        return True

    def scrape_all(self, max_articles: int = 10) -> ScrapingResult:
        """Main scraping method - combines RSS and section scraping."""
        logger.info("🚀 Starting comprehensive Sunstar scraping...")
        logger.info(f"Sunstar flags USE_ADV_HEADERS={USE_ADV_HEADERS}, USE_HUMAN_DELAY={USE_HUMAN_DELAY}, USE_URL_FILTER={USE_URL_FILTER}")
        
        all_articles = []
        
        # Primary method: RSS feed
        rss_articles = self.scrape_rss_feed(max_articles)
        all_articles.extend(rss_articles)
        
        # If RSS doesn't give enough articles, supplement with section scraping
        sections_used = 0
        if len(all_articles) < max_articles:
            logger.info("📰 Supplementing with section scraping...")
            try:
                max_sections = int(os.getenv("SUNSTAR_MAX_SECTIONS", "4"))
            except Exception:
                max_sections = 4
            for section in self.SECTIONS[:max_sections]:
                section_articles = self.scrape_section(section)
                all_articles.extend(section_articles)
                sections_used += 1
                
                if len(all_articles) >= max_articles:
                    break
                    
                # Delay between sections
                delay = self._get_random_delay()
                logger.info(f"Sunstar: waiting {delay:.1f}s between sections (stealth)")
                time.sleep(delay)

        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article.url and article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)

        # Limit to max_articles
        final_articles = unique_articles[:max_articles]
        
        # Calculate performance metrics
        end_time = time.time()
        performance = {
            "total_time": end_time - self.start_time,
            "articles_per_second": len(final_articles) / (end_time - self.start_time),
            "success_rate": len(final_articles) / max(len(all_articles), 1),
            "errors_count": len(self.errors)
        }
        
        metadata = {
            "source": "Sunstar",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_articles_found": len(all_articles),
            "unique_articles": len(final_articles),
            "rss_articles": len(rss_articles),
            "sections_scraped": sections_used
        }

        logger.info(f"✅ Sunstar scraping completed: {len(final_articles)} unique articles")
        logger.info(f"📊 Performance: {performance['articles_per_second']:.2f} articles/sec")
        
        return ScrapingResult(
            articles=final_articles,
            errors=self.errors,
            performance=performance,
            metadata=metadata
        )


def scrape_sunstar_latest(max_articles: int = 10) -> ScrapingResult:
    """Convenience function for scraping latest Sunstar articles."""
    scraper = SunstarScraper()
    return scraper.scrape_all(max_articles)


if __name__ == "__main__":
    # Test the scraper
    result = scrape_sunstar_latest(20)
    print(f"Scraped {len(result.articles)} articles")
    print(f"Performance: {result.performance}")
    if result.errors:
        print(f"Errors: {result.errors}")
    
    # Print first few articles
    for i, article in enumerate(result.articles[:5]):
        print(f"\n{i+1}. {article.title}")
        print(f"   URL: {article.url}")
        print(f"   Category: {article.category}")
        print(f"   Published: {article.published_at}")
