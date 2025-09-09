import time
import logging
import random
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
# from playwright.sync_api import Browser, Page
from bs4 import BeautifulSoup
from app.pipeline.normalize import build_article, NormalizedArticle
# from app.scrapers.base import launch_browser
from datetime import datetime
import re
import urllib.request
import json
import httpx
from fake_useragent import UserAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class ManilaBulletinV2Scraper:
    """
    🕵️ ADVANCED STEALTH SCRAPER FOR MANILA BULLETIN
    ================================================
    
    Features:
    - 🥷 Maximum stealth with rotating user agents
    - 🎯 Multi-strategy content discovery
    - 🛡️ Anti-detection measures
    - ⚡ High-performance async operations
    - 🔄 Intelligent retry mechanisms
    - 📊 Comprehensive error handling
    """
    
    BASE_URL = "https://mb.com.ph"
    START_PATHS = [
        "/",
        "/latest",
        "/news",
        "/nation", 
        "/business",
        "/sports",
        "/entertainment",
        "/technology",
        "/lifestyle",
        "/opinion"
    ]
    
    # 🥷 STEALTH CONFIGURATION
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
    ]
    
    # ⏱️ DELAY CONFIGURATION (More aggressive than Sunstar)
    MIN_DELAY = 8.0  # Faster than Sunstar's 3.0
    MAX_DELAY = 18.0  # Faster than Sunstar's 8.0
    REQUEST_DELAY = 0.3  # Small delay between requests
    
    # 🎯 DISCOVERY LIMITS
    MAX_HOMEPAGE_ARTICLES = 20
    MAX_SECTION_ARTICLES = 15
    MAX_GOOGLE_NEWS_ARTICLES = 10
    
    # 🚫 DISALLOWED PATTERNS
    DISALLOW_PATTERNS = [
        r"/ajax/",
        r"/api/",
        r"/print/",
        r"/login",
        r"/register",
        r"/search\?",
        r"/tag/",
        r"/author/",
        r"/category/",
        r"/archive/",
        r"/rss",
        r"/sitemap",
        r"/404",
        r"/error",
        r"\.pdf$",
        r"\.jpg$",
        r"\.png$",
        r"\.gif$",
        r"\.css$",
        r"\.js$"
    ]
    
    def __init__(self):
        self.articles_scraped = 0
        self.session = None
        self.ua = UserAgent()
        
    def _get_random_delay(self) -> float:
        """Generate random delay for stealth"""
        return random.uniform(self.MIN_DELAY, self.MAX_DELAY)
    
    def _get_random_user_agent(self) -> str:
        """Get random user agent for stealth"""
        return random.choice(self.USER_AGENTS)
    
    def _is_disallowed_url(self, url: str) -> bool:
        """Check if URL should be avoided"""
        for pattern in self.DISALLOW_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def _is_article_url(self, url: str) -> bool:
        """Check if URL looks like an article"""
        if not url or self._is_disallowed_url(url):
            return False
        
        # Must be from mb.com.ph
        if "mb.com.ph" not in url:
            return False
            
        # Must have date pattern (YYYY/MM/DD)
        if not re.search(r'/\d{4}/\d{2}/\d{2}/', url):
            return False
            
        # Must not be too short (likely not an article)
        if len(url.split('/')[-1]) < 10:
            return False
            
        return True
    
    async def _fetch_with_stealth(self, url: str, timeout: int = 15) -> Optional[bytes]:
        """Fetch URL with maximum stealth measures"""
        if not self.session:
            self.session = httpx.AsyncClient(
                timeout=timeout,
                headers={
                    'User-Agent': self._get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0'
                },
                follow_redirects=True
            )
        
        try:
            # Random delay before request
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            response = await self.session.get(url)
            response.raise_for_status()
            
            # Random delay after request
            await asyncio.sleep(self.REQUEST_DELAY)
            
            return response.content
            
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None
    
    def _extract_article_links_from_html(self, html: str, max_links: int = 50) -> List[str]:
        """Extract article links from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Multiple selectors for article links
        selectors = [
            'a[href*="/2025/"]',  # Date-based links
            'a[href*="/2024/"]',
            'a[href*="/news/"]',
            'a[href*="/nation/"]',
            'a[href*="/business/"]',
            'a[href*="/sports/"]',
            'a[href*="/entertainment/"]',
            'a[href*="/technology/"]',
            'a[href*="/lifestyle/"]',
            'a[href*="/opinion/"]',
            '.article-link',
            '.news-link',
            '.story-link',
            'h1 a',
            'h2 a',
            'h3 a',
            '.title a',
            '.headline a'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(self.BASE_URL, href)
                    if self._is_article_url(full_url):
                        links.append(full_url)
                        
                        if len(links) >= max_links:
                            break
            
            if len(links) >= max_links:
                break
        
        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        return unique_links[:max_links]
    
    async def _discover_articles_from_homepage(self, max_articles: int = 20) -> List[str]:
        """Discover articles from homepage"""
        logger.info("🔍 Discovering articles from homepage...")
        
        html = await self._fetch_with_stealth(self.BASE_URL)
        if not html:
            logger.warning("Failed to fetch homepage")
            return []
        
        links = self._extract_article_links_from_html(html.decode('utf-8', errors='ignore'), max_articles)
        logger.info(f"Found {len(links)} article links from homepage")
        
        return links
    
    async def _discover_articles_from_sections(self, max_articles: int = 15) -> List[str]:
        """Discover articles from section pages"""
        logger.info("🔍 Discovering articles from sections...")
        
        all_links = []
        
        for section in self.START_PATHS[1:]:  # Skip homepage
            if len(all_links) >= max_articles:
                break
                
            url = urljoin(self.BASE_URL, section)
            html = await self._fetch_with_stealth(url)
            
            if html:
                links = self._extract_article_links_from_html(
                    html.decode('utf-8', errors='ignore'), 
                    max_articles - len(all_links)
                )
                all_links.extend(links)
                logger.info(f"Found {len(links)} links from {section}")
                
                # Delay between sections
                await asyncio.sleep(self._get_random_delay())
        
        # Remove duplicates
        seen = set()
        unique_links = []
        for link in all_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        logger.info(f"Total unique section links: {len(unique_links)}")
        return unique_links[:max_articles]
    
    async def _discover_articles_from_google_news(self, max_articles: int = 10) -> List[str]:
        """Discover articles using Google News RSS"""
        logger.info("🔍 Discovering articles from Google News...")
        
        google_news_url = "https://news.google.com/rss/search?q=site:mb.com.ph&hl=en-PH&gl=PH&ceid=PH:en"
        
        try:
            html = await self._fetch_with_stealth(google_news_url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            links = []
            
            # Extract links from Google News RSS
            for item in soup.find_all('item')[:max_articles]:
                link_elem = item.find('link')
                if link_elem and link_elem.text:
                    # Google News links need to be cleaned
                    url = link_elem.text
                    if 'mb.com.ph' in url:
                        links.append(url)
            
            logger.info(f"Found {len(links)} links from Google News")
            return links[:max_articles]
            
        except Exception as e:
            logger.warning(f"Google News discovery failed: {e}")
            return []
    
    async def _scrape_article(self, url: str) -> Optional[NormalizedArticle]:
        """Scrape individual article with stealth"""
        try:
            html = await self._fetch_with_stealth(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = None
            title_selectors = [
                'h1.article-title',
                'h1.entry-title',
                'h1.post-title',
                'h1.headline',
                'h1',
                '.article-title',
                '.entry-title',
                '.post-title',
                '.headline'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem and title_elem.get_text(strip=True):
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title or len(title) < 10:
                return None
            
            # Extract content
            content = ""
            content_selectors = [
                '.article-content',
                '.entry-content',
                '.post-content',
                '.article-body',
                '.story-content',
                '.content',
                'article',
                '.article'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # Remove script and style elements
                    for script in content_elem(["script", "style", "nav", "header", "footer", "aside"]):
                        script.decompose()
                    
                    content = content_elem.get_text(separator=' ', strip=True)
                    if len(content) > 100:  # Ensure substantial content
                        break
            
            if not content or len(content) < 100:
                return None
            
            # Extract category
            category = "News"
            category_selectors = [
                '.category',
                '.section',
                '.breadcrumb a',
                '.article-category',
                '.post-category'
            ]
            
            for selector in category_selectors:
                cat_elem = soup.select_one(selector)
                if cat_elem and cat_elem.get_text(strip=True):
                    category = cat_elem.get_text(strip=True)
                    break
            
            # Extract published date
            published = None
            date_selectors = [
                'time[datetime]',
                '.published',
                '.date',
                '.article-date',
                '.post-date'
            ]
            
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    datetime_attr = date_elem.get('datetime')
                    if datetime_attr:
                        published = datetime_attr
                        break
                    elif date_elem.get_text(strip=True):
                        published = date_elem.get_text(strip=True)
                        break
            
            # Build normalized article
            article = build_article(
                title=title,
                content=content,
                url=url,
                published=published,
                category=category,
                source="Manila Bulletin"
            )
            
            if article:
                self.articles_scraped += 1
                logger.info(f"✅ Scraped article {self.articles_scraped}: {title[:60]}...")
            
            return article
            
        except Exception as e:
            logger.warning(f"Failed to scrape article {url}: {e}")
            return None
    
    async def scrape_all(self, max_articles: int = 25) -> ScrapingResult:
        """
        🎯 MAIN SCRAPING METHOD
        ======================
        
        Multi-strategy approach:
        1. Homepage discovery (primary)
        2. Section pages (secondary) 
        3. Google News RSS (fallback)
        4. Direct article scraping
        """
        start_time = time.time()
        articles = []
        errors = []
        discovered_urls = []
        
        logger.info(f"🚀 Starting Manila Bulletin V2 scraping (max: {max_articles} articles)")
        
        try:
            # 🎯 Strategy 1: Homepage Discovery
            try:
                homepage_links = await self._discover_articles_from_homepage(
                    min(max_articles, self.MAX_HOMEPAGE_ARTICLES)
                )
                discovered_urls.extend(homepage_links)
                logger.info(f"Homepage discovery: {len(homepage_links)} links")
            except Exception as e:
                errors.append(f"homepage_discovery: {e}")
            
            # 🎯 Strategy 2: Section Pages
            if len(discovered_urls) < max_articles:
                try:
                    section_links = await self._discover_articles_from_sections(
                        min(max_articles - len(discovered_urls), self.MAX_SECTION_ARTICLES)
                    )
                    discovered_urls.extend(section_links)
                    logger.info(f"Section discovery: {len(section_links)} links")
                except Exception as e:
                    errors.append(f"section_discovery: {e}")
            
            # 🎯 Strategy 3: Google News RSS (Fallback)
            if len(discovered_urls) < max_articles:
                try:
                    google_links = await self._discover_articles_from_google_news(
                        min(max_articles - len(discovered_urls), self.MAX_GOOGLE_NEWS_ARTICLES)
                    )
                    discovered_urls.extend(google_links)
                    logger.info(f"Google News discovery: {len(google_links)} links")
                except Exception as e:
                    errors.append(f"google_news_discovery: {e}")
            
            # Remove duplicates while preserving order
            seen = set()
            unique_urls = []
            for url in discovered_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            logger.info(f"📊 Total unique URLs discovered: {len(unique_urls)}")
            
            # 🎯 Strategy 4: Scrape Articles
            for i, url in enumerate(unique_urls[:max_articles]):
                if len(articles) >= max_articles:
                    break
                
                try:
                    article = await self._scrape_article(url)
                    if article:
                        articles.append(article)
                    
                    # Stealth delay between articles
                    if i < len(unique_urls) - 1:  # Don't delay after last article
                        await asyncio.sleep(self.REQUEST_DELAY)
                        
                except Exception as e:
                    errors.append(f"article_scraping_{url}: {e}")
                    continue
            
        except Exception as e:
            errors.append(f"main_scraping: {e}")
        
        finally:
            if self.session:
                await self.session.aclose()
        
        duration = time.time() - start_time
        
        result = ScrapingResult(
            articles=articles,
            errors=errors,
            performance={
                'duration_s': round(duration, 2),
                'articles_scraped': len(articles),
                'urls_discovered': len(unique_urls),
                'success_rate': round(len(articles) / max(len(unique_urls), 1) * 100, 1)
            },
            metadata={
                'domain': 'mb.com.ph',
                'scraper_version': '2.0',
                'strategies_used': ['homepage', 'sections', 'google_news'],
                'stealth_enabled': True
            }
        )
        
        logger.info(f"✅ Scraping complete: {len(articles)} articles in {duration:.2f}s")
        return result

# 🎯 CONVENIENCE FUNCTIONS
async def scrape_manila_bulletin_latest(max_articles: int = 25) -> ScrapingResult:
    """Scrape latest Manila Bulletin articles"""
    scraper = ManilaBulletinV2Scraper()
    return await scraper.scrape_all(max_articles)

def scrape_manila_bulletin_latest_sync(max_articles: int = 25) -> ScrapingResult:
    """Synchronous wrapper for Manila Bulletin scraping"""
    return asyncio.run(scrape_manila_bulletin_latest(max_articles))
