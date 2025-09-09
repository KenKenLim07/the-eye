import time
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup, Tag
from app.pipeline.normalize import build_article, NormalizedArticle
from app.scrapers.base import launch_browser
import random
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
    USER_AGENT = "Mozilla/5.0 (compatible; PH-Eye-NewsBot/1.0; +https://github.com/your-repo)"
    
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
        """Security: minimal validation – only allow inquirer.net domains with whitelisted sections."""
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
            '/job-openings', '/article-index', '/fullfeed'
        )
        if any(bp in parsed.path for bp in blocked_paths):
            return False
        # Whitelist: allow only key sections/domains
        allowed_section_prefixes = (
            '/news/',
            '/headlines/',
            '/nation/',
            '/business/',
            '/sports/',
            '/entertainment/',
            '/lifestyle/',
            '/opinion/',
            '/technology/',
            '/globalnation/',
        )
        allowed_news_subdomains = (
            'newsinfo.inquirer.net',
            'globalnation.inquirer.net',
            'business.inquirer.net',
            'sports.inquirer.net',
            'entertainment.inquirer.net',
            'lifestyle.inquirer.net',
            'opinion.inquirer.net',
            'technology.inquirer.net',
        )
        # Allow WP-style permalinks: https://newsinfo.inquirer.net/?p=ID
        if parsed.netloc == 'newsinfo.inquirer.net' and parsed.path == '/' and 'p=' in (parsed.query or ''):
            return True
        # If on an allowed subdomain, accept if path is non-empty
        if parsed.netloc in allowed_news_subdomains:
            return parsed.path not in ('', '/')
        # Otherwise, require allowed section prefixes in the path
        if any(parsed.path.startswith(prefix) for prefix in allowed_section_prefixes):
            return True
        return False
    
    def _sanitize_text(self, text: str) -> str:
        """Security: Sanitize extracted text content."""
        if not text:
            return ""
            
        # Remove potentially dangerous content
        text = text.replace('<script>', '').replace('</script>', '')
        text = text.replace('javascript:', '').replace('data:', '')
        
        # Basic XSS prevention
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        
        return text.strip()
    
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
            # Combine content parts and limit length dynamically
            combined = ' '.join(content_parts)
            if len(combined) > 1000:
                combined = combined[:1000] + "..."
            elif len(combined) > 500:
                combined = combined[:500] + "..."
            logger.info(f"Extracted {len(content_parts)} content parts, total length: {len(combined)}")
            return combined
        else:
            logger.warning(f"Could not extract any content from {url}")
            return None
    
    def _extract_article_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract article URLs with validation."""
        urls = set()
        
        for selector in self.SELECTORS["article_links"]:
            try:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.BASE_URL, href)
                        if self._validate_url(full_url):
                            urls.add(full_url)
            except Exception as e:
                logger.error(f"Selector '{selector}' error: {e}")
                continue
                
        return list(urls)
    
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
    
    def _scrape_article_page(self, url: str, browser: Browser) -> Optional[NormalizedArticle]:
        """Scrape individual article page with enhanced content extraction."""
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
                context.close()
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
                context.close()
                return None
                
            # Enhanced content extraction
            content_text = self._extract_content_with_debug(soup, url)
            published_date = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])
            
            # Log what we found for debugging
            logger.info(f"Article {url}: Title='{title}', Content length={len(content_text) if content_text else 0}")
            
            # Build normalized article
            norm_cat, raw_cat = resolve_category_pair(url, soup)
            article = build_article(
                source="Inquirer",
                title=title,
                url=url,
                content=content_text,
                category=norm_cat,
                published_at=published_date,
                raw_category=raw_cat,
            )
            
            context.close()
            return article
            
        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return None
    
    def scrape_latest(self, max_articles: int = 10) -> ScrapingResult:
        """Main scraping method with comprehensive error handling and monitoring."""
        start_time = time.time()
        articles = []
        errors = []
        
        try:
            with launch_browser() as browser:
                # Scrape homepage for article links
                logger.info("Starting Inquirer scraping session")
                logger.info(f"Inquirer flags USE_ADV_HEADERS={USE_ADV_HEADERS}, USE_HUMAN_DELAY={USE_HUMAN_DELAY}, USE_URL_FILTER={USE_URL_FILTER}")
                
                # Get homepage
                context = self._new_context(browser)
                page = context.new_page()
                page.set_extra_http_headers({'User-Agent': self.USER_AGENT})
                
                try:
                    response = page.goto(self.BASE_URL, wait_until='domcontentloaded')
                    if not response or response.status >= 400:
                        raise Exception(f"Homepage returned {response.status if response else 'unknown'}")
                        
                    # Extract article links
                    soup = BeautifulSoup(page.content(), 'html.parser')
                    article_urls = self._extract_article_links(soup)
                    
                    # Debug: log some URLs found
                    if article_urls:
                        logger.info(f"Found {len(article_urls)} article URLs")
                        logger.info(f"Sample URLs: {article_urls[:3]}")
                    else:
                        logger.warning("No article URLs found - checking selectors")
                        # Debug: check what links exist
                        all_links = soup.find_all('a', href=True)
                        logger.info(f"Total links found: {len(all_links)}")
                        if all_links:
                            sample_links = [link.get('href') for link in all_links[:5]]
                            logger.info(f"Sample links: {sample_links}")
                    
                    # Scrape each article
                    for i, url in enumerate(article_urls[:max_articles]):
                        try:
                            logger.info(f"Scraping article {i+1}/{len(article_urls[:max_articles])}: {url}")
                            
                            article = self._scrape_article_page(url, browser)
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
            "source": "Philippine Daily Inquirer",
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
def scrape_inquirer_latest() -> List[NormalizedArticle]:
    """Entry point for Celery tasks - returns just the articles."""
    scraper = InquirerScraper()
    result = scraper.scrape_latest(max_articles=10)
    
    # Log results for monitoring
    logger.info(f"Inquirer scraping result: {result.metadata}")
    if result.errors:
        logger.warning(f"Scraping errors: {result.errors}")
    
    return result.articles 
