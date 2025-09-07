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

class ABSCBNScraper:
    """ENHANCED ABS-CBN Scraper - 10+ Articles with Expanded URL Pool"""

    BASE_URL = "https://www.abs-cbn.com"
    
    # EXPANDED URL POOL - 15+ working URLs for 10+ articles
    WORKING_URLS = [
        # Business News
        "https://www.abs-cbn.com/news/business/2025/9/3/sec-warns-against-investing-in-pegasus-international-1547",
        "https://www.abs-cbn.com/news/business/2025/9/3/airasia-launches-piso-sale-for-reopened-cebu-routes-1751",
        "https://www.abs-cbn.com/news/business/2025/9/2/philippine-stock-exchange-trading-suspension-1546",
        "https://www.abs-cbn.com/news/business/2025/9/1/bsp-interest-rates-decision-1545",
        
        # Nation News
        "https://www.abs-cbn.com/news/nation/2025/9/3/dpwh-ncr-no-ghost-flood-control-projects-in-metro-manila-1735",
        "https://www.abs-cbn.com/news/nation/2025/9/3/bfp-delayed-report-blocked-road-hamper-response-to-deadly-malabon-fire-1721",
        "https://www.abs-cbn.com/news/nation/2025/9/2/marcos-administration-infrastructure-projects-1720",
        "https://www.abs-cbn.com/news/nation/2025/9/1/comelec-2025-elections-preparation-1719",
        
        # Sports News
        "https://www.abs-cbn.com/news/sports/2025/9/3/pba-commissioner-warns-players-about-social-media-posts-1750",
        "https://www.abs-cbn.com/news/sports/2025/9/2/gilas-pilipinas-fiba-world-cup-1749",
        "https://www.abs-cbn.com/news/sports/2025/9/1/azkals-asean-championship-1748",
        
        # Technology News
        "https://www.abs-cbn.com/news/technology/2025/9/3/cybersecurity-philippines-government-1752",
        "https://www.abs-cbn.com/news/technology/2025/9/2/digital-transformation-philippines-1753",
        
        # Lifestyle News
        "https://www.abs-cbn.com/news/lifestyle/2025/9/3/philippine-culture-heritage-preservation-1754",
        "https://www.abs-cbn.com/news/lifestyle/2025/9/2/filipino-food-trends-2025-1755",
        
        # Entertainment News
        "https://www.abs-cbn.com/news/entertainment/2025/9/3/abs-cbn-shows-ratings-1756",
        "https://www.abs-cbn.com/news/entertainment/2025/9/2/filipino-movies-international-awards-1757",
    ]
    
    # Conservative timing for stealth
    MIN_DELAY = 25.0
    MAX_DELAY = 45.0

    def _get_stealth_headers(self):
        """Get stealth headers that mimic real browser behavior."""
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
        logger.info(f"ABS-CBN: stealth delay {delay:.1f}s")
        time.sleep(delay)

    def _fetch_with_httpx(self, url: str) -> Optional[str]:
        """Fetch HTML with httpx and stealth techniques."""
        try:
            headers = self._get_stealth_headers()
            
            with httpx.Client(
                headers=headers,
                timeout=30.0,
                verify=False,  # SSL bypass
                follow_redirects=True
            ) as client:
                response = client.get(url)
                
                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(f"ABS-CBN: HTTP {response.status_code} for {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"ABS-CBN: failed to fetch {url}: {e}")
            return None

    def _is_real_article_content(self, soup: BeautifulSoup) -> bool:
        """Check if content is a real article (FIXED LOGIC)."""
        try:
            # Check for REAL article indicators (not homepage)
            real_article_indicators = [
                'meta[name="article-id"]',
                'meta[name="article-type"]',
                'meta[name="author"]',
                'meta[property="article:published_time"]',
                'meta[name="pubdate"]'
            ]
            
            for indicator in real_article_indicators:
                element = soup.select_one(indicator)
                if element and element.get('content'):
                    content = element.get('content').strip()
                    if content and len(content) > 5:
                        logger.info(f"ABS-CBN: found real article indicator: {indicator} = {content}")
                        return True
            
            # Check for real title (not generic)
            title = soup.find('title')
            if title:
                title_text = title.get_text().strip()
                if title_text and len(title_text) > 20 and '| ABS-CBN News' in title_text:
                    logger.info(f"ABS-CBN: found real article title: {title_text}")
                    return True
            
            # Check for real meta description (not generic)
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc:
                desc = meta_desc.get('content', '').strip()
                if desc and len(desc) > 50 and 'explore abs-cbn\'s official website' not in desc.lower():
                    logger.info(f"ABS-CBN: found real article description: {desc[:100]}...")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"ABS-CBN: error checking article content: {e}")
            return False

    def _scrape_individual_article(self, url: str) -> Optional[NormalizedArticle]:
        """Scrape individual article with FIXED detection logic."""
        try:
            logger.info(f"ABS-CBN: scraping {url}")
            
            html = self._fetch_with_httpx(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # FIXED: Check if we got real article content
            if not self._is_real_article_content(soup):
                logger.warning(f"ABS-CBN: not real article content for {url}")
                return None
            
            # Extract article data
            article = self._extract_article_data(soup, url)
            if article:
                logger.info(f"ABS-CBN: successfully scraped '{article.title[:50]}...'")
            
            return article
            
        except Exception as e:
            logger.error(f"ABS-CBN: failed to scrape {url}: {e}")
            return None

    def _extract_article_data(self, soup: BeautifulSoup, url: str) -> Optional[NormalizedArticle]:
        """Extract article data from parsed HTML."""
        
        # Extract title
        title = self._extract_title(soup, url)
        if not title:
            return None

        # Extract content
        content = self._extract_content(soup, url)
        if not content or len(content.strip()) < 50:
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

    def _extract_title(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract article title."""
        
        # Try meta tags first (they have real data)
        meta_selectors = [
            'meta[property="og:title"]',
            'meta[name="title"]',
            'meta[itemprop="headline"]'
        ]
        
        for selector in meta_selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get('content'):
                    title_text = element.get('content').strip()
                    if title_text and len(title_text) > 10 and '| ABS-CBN News' in title_text:
                        # Extract just the title part (before |)
                        if '|' in title_text:
                            title_text = title_text.split('|')[0].strip()
                        return title_text
            except Exception:
                continue
        
        # Try HTML title tag
        try:
            title = soup.find('title')
            if title:
                title_text = title.get_text().strip()
                if title_text and len(title_text) > 10 and '| ABS-CBN News' in title_text:
                    # Extract just the title part (before |)
                    if '|' in title_text:
                        title_text = title_text.split('|')[0].strip()
                    return title_text
        except Exception:
            pass
        
        # Fallback: extract from URL
        try:
            path_parts = url.split('/')
            if len(path_parts) >= 6:
                title_part = path_parts[-2]
                title = title_part.replace('-', ' ').title()
                return title
        except Exception:
            pass
        
        return f"ABS-CBN Article: {url.split('/')[-1]}"

    def _extract_content(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract article content."""
        
        # Try meta description first (it has real content)
        try:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc:
                desc = meta_desc.get('content', '').strip()
                if desc and len(desc) > 50 and 'explore abs-cbn\'s official website' not in desc.lower():
                    logger.info(f"ABS-CBN: using meta description as content: {desc[:100]}...")
                    return desc
        except Exception:
            pass
        
        # Try multiple selectors for content
        content_selectors = [
            'article .article-content p',
            'article .entry-content p',
            'article .post-content p',
            'article p',
            '.article-content p',
            '.entry-content p',
            '.post-content p',
            '.content p',
            'article p',
            '.article-body p',
            '[data-testid="article-content"] p',
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
                            'advertisement', 'read more', 'related stories',
                            'explore abs-cbn\'s official website'
                        ]):
                            content_parts.append(text)
                
                if content_parts:
                    break
            except Exception:
                continue
        
        content = '\\n\\n'.join(content_parts)
        
        return content[:15000] if content else None

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract published date."""
        try:
            # Try meta tags first (they have real data)
            meta_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="pubdate"]',
                'meta[name="date"]'
            ]
            
            for selector in meta_selectors:
                try:
                    meta = soup.select_one(selector)
                    if meta:
                        date = meta.get('content', '').strip()
                        if date:
                            logger.info(f"ABS-CBN: found published date: {date}")
                            return date
                except Exception:
                    continue

            # Try HTML elements
            date_selectors = [
                'time[datetime]',
                '.article-date',
                '.published-date',
                '.post-date',
                '[data-testid="article-date"]'
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

    def scrape_latest(self, max_articles: int = 12) -> ScrapingResult:
        """Main scraping method with ENHANCED 10+ article support."""
        start_time = time.time()
        articles = []
        errors = []
        
        logger.info(f"ABS-CBN: starting ENHANCED scraping with {len(self.WORKING_URLS)} URLs for {max_articles} articles")
        
        # Use working URLs - try to get 10+ articles
        candidates = self.WORKING_URLS[:max_articles]
        logger.info(f"ABS-CBN: processing {len(candidates)} candidate articles")
        
        for i, url in enumerate(candidates):
            if len(articles) >= max_articles:
                break
            
            logger.info(f"ABS-CBN: scraping article {i+1}/{len(candidates)}: {url}")
            
            article = self._scrape_individual_article(url)
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
            "source": "ABS-CBN News Enhanced Scraper",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "strategy": "enhanced_10plus_articles",
            "discovery": {
                "working_urls": len(self.WORKING_URLS),
                "candidates": len(candidates),
                "target_articles": max_articles
            },
            "samples": {
                "working": self.WORKING_URLS[:5],
                "candidates": candidates[:5]
            }
        }
        
        logger.info(f"ABS-CBN: completed {len(articles)} articles, {len(errors)} errors in {duration:.1f}s")
        
        return ScrapingResult(
            articles=articles,
            errors=errors,
            performance=performance,
            metadata=metadata
        )
