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

class PhilStarScraper:
    """Stealth scraper for PhilStar."""

    BASE_URL = "https://www.philstar.com"
    START_PATHS = [
        "/headlines",   # main
        "/nation",
        "/business",
        "/sports",
        "/entertainment",
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
            "article h2 a",
            ".article__title a",
            ".listing__item a",
            "h2 a",
            "h3 a",
            "a[href*='/headlines/']",
            "a[href*='/nation/']",
            "a[href*='/business/']",
            "a[href*='/sports/']",
            "a[href*='/entertainment/']",
        ],
        "title": [
            "h1.article__title",
            "h1",
            ".article__title",
            "title"
        ],
        "content": [
            ".article__content p",
            ".article-content p",
            ".post-content p",
            ".content p",
            "article p",
            "p"
        ],
        "published_date": [
            "time.article__date",
            ".article__date",
            "time",
            ".date"
        ]
    }

    def _human_delay(self):
        """Random delay to mimic human browsing behavior."""
        if USE_HUMAN_DELAY and get_human_like_delay is not None:
            delay = get_human_like_delay()
        else:
            delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"Waiting {delay:.1f}s (stealth)")
        time.sleep(delay)

    def _validate_url(self, url: str) -> bool:
        """Validate if URL is a legitimate PhilStar article."""
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not ("philstar.com" in parsed.netloc):
            return False
        
        if USE_URL_FILTER and is_valid_news_url is not None:
            if not is_valid_news_url(url, "philstar.com"):
                return False
            return True
        
        return True

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

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract article content with filtering."""
        parts = []
        for sel in self.SELECTORS["content"]:
            try:
                for p in soup.select(sel):
                    text = p.get_text(" ", strip=True)
                    if text and len(text) > 20:
                        # Skip boilerplate
                        if not any(skip in text.lower() for skip in [
                            "philstar", "subscribe", "newsletter", "share this",
                            "follow us", "advertisement", "read more",
                            "related stories", "comments", "copyright"
                        ]):
                            parts.append(text)
                    
                    if len(parts) >= 15:
                        break
                        
                if parts:
                    break
            except Exception:
                continue

        content = "\n\n".join(parts)
        return (content or "")[:15000]

    def _new_context(self, browser: Browser):
        """Create browser context with resource blocking."""
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
        
        # Block heavy resources
        context.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
            or any(domain in route.request.url for domain in [
                "google-analytics.com", "googletagmanager.com", "facebook.com", 
                "doubleclick.net", "googlesyndication.com", "adsystem.com"
            ]) else route.continue_()
        ))
        
        return context

    def _scrape_article(self, url: str, browser: Browser) -> Optional[NormalizedArticle]:
        """Scrape individual article."""
        try:
            context = self._new_context(browser)
            page = context.new_page()
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
            
            page.set_default_timeout(30000)
            page.goto(url, wait_until='domcontentloaded')
            
            # Wait for content
            try:
                page.wait_for_selector('h1', timeout=10000)
            except:
                pass
                
            soup = BeautifulSoup(page.content(), 'html.parser')
            context.close()
            
            # Extract article data
            title = self._extract_with_fallbacks(soup, self.SELECTORS["title"])
            if not title:
                logger.warning(f"No title found for {url}")
                return None
                
            content = self._extract_content(soup)
            published_date = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])
            
            # Build normalized article
            norm_cat, raw_cat = resolve_category_pair(url, soup)
            article = build_article(
                source="PhilStar",
                title=title,
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_date,
                raw_category=raw_cat,
            )
            
            return article
            
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None

    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        """Main scraping method."""
        start_time = time.time()
        articles = []
        errors = []
        
        logger.info("Starting PhilStar scraping session")
        logger.info(f"PhilStar flags USE_ADV_HEADERS={USE_ADV_HEADERS}, USE_HUMAN_DELAY={USE_HUMAN_DELAY}, USE_URL_FILTER={USE_URL_FILTER}")
        
        try:
            with launch_browser() as browser:
                # Scrape homepage for article links
                context = self._new_context(browser)
                page = context.new_page()
                page.set_extra_http_headers({'User-Agent': self.USER_AGENT})
                
                try:
                    response = page.goto(self.BASE_URL, wait_until='domcontentloaded')
                    if not response or response.status >= 400:
                        raise Exception(f"Homepage returned {response.status if response else 'unknown'}")
                        
                    # Extract article links
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    article_urls = []
                    
                    for sel in self.SELECTORS["article_links"]:
                        try:
                            for a in soup.select(sel):
                                href = a.get('href')
                                if href and self._validate_url(href):
                                    full_url = urljoin(self.BASE_URL, href)
                                    article_urls.append(full_url)
                        except Exception:
                            continue
                    
                    # Remove duplicates
                    article_urls = list(dict.fromkeys(article_urls))
                    
                    logger.info(f"Found {len(article_urls)} article URLs")
                    
                    # Scrape each article
                    for i, url in enumerate(article_urls[:max_articles]):
                        try:
                            logger.info(f"Scraping article {i+1}/{len(article_urls[:max_articles])}: {url}")
                            
                            article = self._scrape_article(url, browser)
                            if article:
                                articles.append(article)
                                logger.info(f"Successfully scraped: {article.title}")
                            else:
                                errors.append(f"Failed to extract article from {url}")
                            
                            # Stealthy rate limiting between article requests
                            if i < len(article_urls[:max_articles]) - 1:
                                self._human_delay()
                                
                        except Exception as e:
                            error_msg = f"Error scraping {url}: {str(e)}"
                            errors.append(error_msg)
                            logger.error(error_msg)
                            continue
                            
                    context.close()
                    
                except Exception as e:
                    error_msg = f"Failed to scrape homepage: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    
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
            "source": "Philippine Star",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors)
        }
        
        logger.info(f"Scraping completed: {len(articles)} articles, {len(errors)} errors in {total_time:.2f}s")
        
        return ScrapingResult(
            articles=articles,
            errors=errors,
            performance=performance,
            metadata=metadata
        )

# Convenience function for Celery tasks
def scrape_philstar_latest() -> List[NormalizedArticle]:
    """Entry point for Celery tasks - returns just the articles."""
    scraper = PhilStarScraper()
    result = scraper.scrape_latest(max_articles=3)
    
    # Log results for monitoring
    logger.info(f"PhilStar scraping result: {result.metadata}")
    if result.errors:
        logger.warning(f"Scraping errors: {result.errors}")
    
    return result.articles
