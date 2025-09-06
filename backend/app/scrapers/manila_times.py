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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class ManilaTimesScraper:
    """BLACKHAT Manila Times Scraper - Ultra-Conservative Stealth Approach"""

    BASE_URL = "https://www.manilatimes.net"
    
    # Static article URLs discovered from reconnaissance
    STATIC_ARTICLE_URLS = [
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040",
        "https://www.manilatimes.net/2025/09/07/the-sunday-times/filipino-champions/be-juan-tama-advocacy-inspires-filipinos-to-choose-learning/2180194",
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040",
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040",
        "https://www.manilatimes.net/2025/09/07/news/15-drug-war-victims-cleared-to-join-dutertes-icc-case/2180040"
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

    def _fetch_with_httpx(self, url: str) -> Optional[str]:
        """Fetch URL with httpx and proper Brotli decompression."""
        try:
            timeout = random.uniform(25.0, 35.0)
            logger.info(f"{self.name}: Fetching {url} with timeout {timeout:.1f}s")
            
            with httpx.Client(
                follow_redirects=True,
                timeout=float(timeout),
                headers=self._get_stealth_headers(),
                verify=False  # KEY: Disable SSL verification
            ) as client:
                response = client.get(url)
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
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {e.response.text[:100]}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {e}")
            return None

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
                    return date_str
        
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
            
            # Build normalized article
            article = build_article(
                title=title,
                content=content,
                url=url,
                published_at=published_date,
                source="manila_times",
                category="news"
            )
            
            return article
            
        except Exception as e:
            logger.error(f"{self.name}: Error extracting article from {url}: {e}")
            return None

    def scrape_latest(self, max_articles: int = 5) -> ScrapingResult:
        """Scrape latest articles with stealth approach."""
        start_time = time.time()
        articles = []
        errors = []
        
        logger.info(f"{self.name}: Starting stealth scraping with {len(self.STATIC_ARTICLE_URLS)} static URLs")
        
        # Use static URLs for reliability
        candidate_urls = self.STATIC_ARTICLE_URLS[:max_articles]
        logger.info(f"{self.name}: Processing {len(candidate_urls)} candidate articles")
        
        for i, url in enumerate(candidate_urls, 1):
            try:
                logger.info(f"{self.name}: Scraping article {i}/{len(candidate_urls)}: {url}")
                
                # Stealth delay between requests
                if i > 1:
                    self._human_delay()
                
                # Fetch and parse
                logger.info(f"{self.name}: Scraping {url}")
                html = self._fetch_with_httpx(url)
                
                if not html:
                    error_msg = f"Failed to fetch {url}"
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
                "stealth_mode": True
            }
        )
