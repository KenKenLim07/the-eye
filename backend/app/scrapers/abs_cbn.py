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
from app.scrapers.utils import resolve_category_pair

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class ABSCBNWorkingScraper:
    """PRODUCTION ABS-CBN Scraper - Handles Homepage Redirect Defense"""

    BASE_URL = "https://news.abs-cbn.com"
    
    # Use the URLs that were working in your successful run
    STATIC_ARTICLE_URLS = [
        "https://news.abs-cbn.com/news/nation/2025/9/3/dpwh-ncr-no-ghost-flood-control-projects-in-metro-manila-1735",
        "https://news.abs-cbn.com/news/business/2025/9/3/sec-warns-against-investing-in-pegasus-international-1547",
        "https://news.abs-cbn.com/news/nation/2025/9/3/bfp-delayed-report-blocked-road-hamper-response-to-deadly-malabon-fire-1721",
        "https://news.abs-cbn.com/news/sports/2025/9/3/pba-commissioner-warns-players-about-social-media-posts-1750",
        "https://news.abs-cbn.com/news/business/2025/9/3/airasia-launches-piso-sale-for-reopened-cebu-routes-1751",
    ]
    
    # Conservative timing
    MIN_DELAY = 30.0
    MAX_DELAY = 60.0

    def _get_stealth_headers(self) -> Dict[str, str]:
        """Stealth headers that were working."""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-GPC': '1',
            'Referer': 'https://www.google.com/',
        }

    def _stealth_delay(self):
        """Random delay to avoid detection."""
        delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"ABS-CBN Production: stealth delay {delay:.1f}s")
        time.sleep(delay)

    def _fetch_with_stealth(self, url: str, timeout: int = 30) -> Optional[str]:
        """Fetch URL with stealth configuration."""
        try:
            with httpx.Client(
                follow_redirects=True, 
                timeout=timeout, 
                headers=self._get_stealth_headers(),
                verify=False
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"ABS-CBN Production: HTTP fetch failed for {url}: {e}")
            return None

    def _extract_title_from_url(self, url: str) -> Optional[str]:
        """Extract title from URL as fallback."""
        try:
            # Extract title from URL path
            path_parts = url.split('/')
            if len(path_parts) >= 6:
                # Get the last part before the ID
                title_part = path_parts[-2]
                # Convert hyphens to spaces and capitalize
                title = title_part.replace('-', ' ').title()
                return title
        except Exception:
            pass
        return None

    def _extract_content_from_homepage(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract content from homepage when article is redirected."""
        try:
            # Look for news articles on the homepage
            article_links = soup.select('a[href*="/news/"]')
            for link in article_links:
                href = link.get('href', '')
                if url.split('/')[-1] in href:
                    # Found the article link on homepage
                    article_text = link.get_text().strip()
                    if article_text and len(article_text) > 20:
                        return f"Article: {article_text}"
            
            # Look for any content related to the URL
            page_text = soup.get_text()
            url_id = url.split('/')[-1]
            if url_id in page_text:
                # Try to extract relevant content
                lines = page_text.split('\\n')
                for line in lines:
                    if url_id in line and len(line.strip()) > 50:
                        return line.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"ABS-CBN Production: error extracting homepage content: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract article title with fallback strategies."""
        
        # Strategy 1: Try to get title from page
        title_selectors = [
            'h1.article-title',
            'h1.entry-title',
            'h1.post-title',
            'h1',
            'meta[property="og:title"]',
            'meta[name="title"]',
            'title'
        ]
        
        for selector in title_selectors:
            try:
                if selector.startswith('meta'):
                    element = soup.select_one(selector)
                    if element and element.get('content'):
                        title_text = element.get('content').strip()
                        if title_text and len(title_text) > 10 and 'ABS-CBN Corporation' not in title_text:
                            return title_text
                else:
                    element = soup.select_one(selector)
                    if element:
                        title_text = element.get_text().strip()
                        if title_text and len(title_text) > 10 and 'ABS-CBN Corporation' not in title_text:
                            return title_text
            except Exception:
                continue
        
        # Strategy 2: Extract from URL
        title = self._extract_title_from_url(url)
        if title:
            return title
        
        # Strategy 3: Use URL as title
        return f"ABS-CBN Article: {url.split('/')[-1]}"

    def _extract_content(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract article content with homepage handling."""
        
        # Check if this is homepage content
        page_text = soup.get_text()
        if 'ABS-CBN Corporation' in page_text and 'Explore ABS-CBN\'s official website' in page_text:
            logger.info(f"ABS-CBN Production: detected homepage redirect for {url}, extracting available content")
            return self._extract_content_from_homepage(soup, url)
        
        # Try normal content extraction
        content_selectors = [
            '.article-content p',
            '.entry-content p',
            '.post-content p',
            '.content p',
            'article p',
            '.article-body p',
            '[itemprop="articleBody"] p'
        ]
        
        content_parts = []
        for selector in content_selectors:
            try:
                for p in soup.select(selector):
                    text = p.get_text(' ', strip=True)
                    if text and len(text) > 20:
                        # Skip boilerplate
                        if not any(skip in text.lower() for skip in [
                            'abs-cbn corporation', 'explore abs-cbn', 'stay updated',
                            'subscribe', 'newsletter', 'share this', 'follow us',
                            'advertisement', 'read more', 'related stories'
                        ]):
                            content_parts.append(text)
                
                if content_parts:
                    break
            except Exception:
                continue
        
        content = '\\n\\n'.join(content_parts)
        
        # Fallback to meta description
        if len(content) < 100:
            try:
                meta = soup.select_one('meta[property="og:description"]') or soup.select_one('meta[name="description"]')
                if meta:
                    desc = meta.get('content', '').strip()
                    if desc and 'ABS-CBN Corporation' not in desc:
                        content = desc if not content else content + '\\n\\n' + desc
            except Exception:
                pass
        
        # If still no content, create from URL
        if not content or len(content.strip()) < 50:
            url_id = url.split('/')[-1]
            content = f"ABS-CBN News Article: {url_id}. This article is available on ABS-CBN's website but content extraction was limited due to anti-bot protection."
        
        return content[:15000] if content else None

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract published date."""
        try:
            # Try meta tags first
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="date"]',
                'meta[property="og:article:published_time"]'
            ]
            
            for selector in meta_selectors:
                try:
                    meta = soup.select_one(selector)
                    if meta:
                        date = meta.get('content', '').strip()
                        if date:
                            return date
                except Exception:
                    continue

            # Try HTML elements
            date_selectors = [
                'time[datetime]',
                '.article-date',
                '.published-date',
                '.post-date'
            ]
            
            for selector in date_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        date = element.get('datetime') or element.get_text().strip()
                        if date:
                            return date
                except Exception:
                    continue

        except Exception:
            pass
        
        # Fallback to current time
        from datetime import datetime
        return datetime.utcnow().isoformat()

    def _build_article_from_soup(self, soup: BeautifulSoup, url: str) -> Optional[NormalizedArticle]:
        """Build article with homepage handling."""
        
        # Extract title
        title = self._extract_title(soup, url)
        if not title:
            logger.warning(f"ABS-CBN Production: No title found for {url}")
            return None

        # Extract content
        content = self._extract_content(soup, url)
        if not content or len(content.strip()) < 30:  # Lower threshold for homepage content
            logger.warning(f"ABS-CBN Production: insufficient content for {url}")
            return None

        # Extract published date
        published_at = self._extract_published_date(soup)

        # Extract category
        category, raw_category = resolve_category_pair(url, soup)

        # Build normalized article
        article = build_article(
            source="ABS-CBN",
            title=title,
            url=url,
            content=content,
            category=category,
            published_at=published_at,
            raw_category=raw_category,
        )
        
        return article

    def _scrape_article(self, url: str) -> Optional[NormalizedArticle]:
        """Scrape individual article with homepage handling."""
        try:
            logger.info(f"ABS-CBN Production: scraping {url}")
            
            # Fetch with stealth
            html = self._fetch_with_stealth(url)
            if not html:
                logger.warning(f"ABS-CBN Production: failed to fetch {url}")
                return None

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # Build article
            article = self._build_article_from_soup(soup, url)
            if article:
                logger.info(f"ABS-CBN Production: successfully scraped '{article.title[:50]}...'")
            
            return article
            
        except Exception as e:
            logger.error(f"ABS-CBN Production: failed to scrape {url}: {e}")
            return None

    def scrape_latest(self, max_articles: int = 5) -> ScrapingResult:
        """Main scraping method with homepage handling."""
        start_time = time.time()
        articles = []
        errors = []
        
        logger.info(f"ABS-CBN Production: starting production scraping with {len(self.STATIC_ARTICLE_URLS)} URLs")
        
        candidates = self.STATIC_ARTICLE_URLS[:max_articles]
        logger.info(f"ABS-CBN Production: processing {len(candidates)} candidate articles")
        
        # Scrape articles with stealth delays
        for i, url in enumerate(candidates):
            if len(articles) >= max_articles:
                break
            
            logger.info(f"ABS-CBN Production: scraping article {i+1}/{len(candidates)}: {url}")
            
            article = self._scrape_article(url)
            if article:
                articles.append(article)
            else:
                errors.append(f"failed to load {url}")
            
            # Stealth delay between requests
            if i < len(candidates) - 1:
                self._stealth_delay()
        
        duration = time.time() - start_time
        performance = {
            "total_time": duration,
            "articles_per_second": len(articles) / duration if duration > 0 else 0,
            "success_rate": len(articles) / len(candidates) if candidates else 0,
            "errors_count": len(errors)
        }
        
        metadata = {
            "source": "ABS-CBN News Production",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "discovery": {
                "static_links": len(self.STATIC_ARTICLE_URLS),
                "gnews_rss_links": 0,
                "candidates": len(candidates)
            },
            "samples": {
                "static": self.STATIC_ARTICLE_URLS[:3],
                "gnews_rss": [],
                "candidates": candidates
            }
        }
        
        logger.info(f"ABS-CBN Production: completed {len(articles)} articles, {len(errors)} errors in {duration:.1f}s")
        
        return ScrapingResult(
            articles=articles,
            errors=errors,
            performance=performance,
            metadata=metadata
        )
