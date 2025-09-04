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
from datetime import datetime
import re
import urllib.request
import json
import httpx
import xml.etree.ElementTree as ET

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
                        content = soup.get_text(strip=True)
                    elif description_elem and description_elem.text:
                        content = description_elem.text.strip()
                    
                    # Parse publication date
                    published_at = None
                    if pub_date_elem and pub_date_elem.text:
                        try:
                            # Parse RFC 2822 date format
                            from email.utils import parsedate_to_datetime
                            published_at = parsedate_to_datetime(pub_date_elem.text).isoformat()
                        except:
                            published_at = datetime.now().isoformat()

                    # Extract category from categories
                    category = None
                    categories = item.findall('category')
                    if categories:
                        # Use the first category that's not too generic
                        for cat in categories:
                            if cat.text and cat.text not in ['Balita', 'News']:
                                category = cat.text
                                break
                        if not category and categories[0].text:
                            category = categories[0].text
                    
                    # If no category from RSS, extract from URL
                    if not category:
                        category = self._extract_category_from_url(url)
                    
                    # Build article
                    article = build_article(
                        source="Sunstar",
                        title=title,
                        url=url,
                        content=content,
                        category=category,
                        published_at=published_at
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
                    content = content_elem.get_text(strip=True)
                    break
            
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
                        article = build_article(
                            source="Sunstar",
                            title=title,
                            url=article_url,
                            content=None,
                            category=self._extract_category_from_url(article_url),
                            published_at=None
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
            '.jpg', '.png', '.gif', '.pdf'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                return False
                
        return True

    def scrape_all(self, max_articles: int = 3) -> ScrapingResult:
        """Main scraping method - combines RSS and section scraping."""
        logger.info("🚀 Starting comprehensive Sunstar scraping...")
        
        all_articles = []
        
        # Primary method: RSS feed
        rss_articles = self.scrape_rss_feed(max_articles)
        all_articles.extend(rss_articles)
        
        # If RSS doesn't give enough articles, supplement with section scraping
        if len(all_articles) < max_articles:
            logger.info("📰 Supplementing with section scraping...")
            for section in self.SECTIONS[:2]:  # Limit to first 2 sections for stealth
                section_articles = self.scrape_section(section)
                all_articles.extend(section_articles)
                
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
            "scraped_at": datetime.now().isoformat(),
            "total_articles_found": len(all_articles),
            "unique_articles": len(final_articles),
            "rss_articles": len(rss_articles),
            "sections_scraped": min(2, len(self.SECTIONS))
        }

        logger.info(f"✅ Sunstar scraping completed: {len(final_articles)} unique articles")
        logger.info(f"📊 Performance: {performance['articles_per_second']:.2f} articles/sec")
        
        return ScrapingResult(
            articles=final_articles,
            errors=self.errors,
            performance=performance,
            metadata=metadata
        )


def scrape_sunstar_latest(max_articles: int = 3) -> ScrapingResult:
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
