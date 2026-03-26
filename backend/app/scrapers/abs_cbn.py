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

# SENIOR BLACK HAT: Stealth mode for Akamai bypass 🔥💀
try:
    from playwright_stealth import Stealth
    HAS_STEALTH = True
    stealth_config = Stealth()
    logger = logging.getLogger(__name__)
    logger.info("🔥 BLACK HAT MODE: playwright-stealth loaded")
except ImportError:
    HAS_STEALTH = False
    stealth_config = None

# Feature flags
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
SCRAPER_CONTENT_MAX_CHARS = _env_int("SCRAPER_CONTENT_MAX_CHARS", 8000)

try:
    from app.scrapers.utils import (
        get_advanced_stealth_headers,
        get_human_like_delay,
    )
except Exception:
    get_advanced_stealth_headers = None
    get_human_like_delay = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    articles: List[NormalizedArticle]
    errors: List[str]
    performance: Dict[str, float]
    metadata: Dict[str, Any]

class ABSCBNScraper:
    """Advanced stealth scraper for ABS-CBN with Akamai bypass (requires headed mode in dev, xvfb in prod)."""
    
    BASE_URL = "https://news.abs-cbn.com"
    START_PATHS = [
        "/",
        "/news",
        "/breaking-news",
    ]
    
    # Chrome 129 (matching real browsers)
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    )
    
    MIN_DELAY = 8.0
    MAX_DELAY = 15.0
    
    SELECTORS = {
        "article_links": [
            "article a[href]",
            ".list-group a[href]",
            ".article-item a[href]",
            "h3 a[href]",
            "h2 a[href]",
            "a[href*='/news/']",
        ],
        "title": [
            "h1.article-title",
            "h1",
            ".page-title",
            ".entry-title",
            "title"
        ],
        "content": [
            ".article-content p",
            ".entry-content p",
            ".post-content p",
            "article p",
            "p",
        ],
        "published_date": [
            "time[datetime]",
            ".article-date time",
            ".date",
            "time",
        ]
    }
    
    def _human_delay(self):
        if USE_HUMAN_DELAY and get_human_like_delay is not None:
            delay = get_human_like_delay()
        else:
            delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"ABS-CBN: stealth delay {delay:.1f}s")
        time.sleep(delay)
    
    def _validate_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not parsed.netloc.endswith("abs-cbn.com"):
            return False
        
        path = (parsed.path or "").lower()
        
        # Block non-article patterns INCLUDING LOTTO/GAMBLING
        blocked_patterns = [
            "photo", "photos", "video", "videos", "gallery",
            "tag", "tags", "author", "search", "page",
            ".jpg", ".png", ".pdf", ".mp4",
            # Lotto/Gambling filters (like PhilStar stock market filter)
            "lotto", "swertres", "stl", "pcso", "gambling", "betting",
            "draw", "winning", "numbers", "results", "lottery",
        ]
        
        if any(pattern in path for pattern in blocked_patterns):
            return False
        
        segments = [s for s in parsed.path.split('/') if s]
        if len(segments) < 2:
            return False
        
        if not ("/news/" in path or "/breaking-news/" in path or "/20" in path):
            return False
        
        return True
    
    def _is_probable_article(self, url: str) -> bool:
        return self._validate_url(url)
    
    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        text = text.replace('<script>', '').replace('</script>', '')
        text = text.replace('javascript:', '').replace('data:', '')
        text = text.replace('<', '&lt;').replace('>', '&gt;')
        return text.strip()
    
    def _extract_with_fallbacks(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el:
                    val = el.get_text().strip()
                    if val:
                        return self._sanitize_text(val)
            except Exception:
                continue
        return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        parts = []
        seen = set()
        
        for sel in self.SELECTORS["content"]:
            try:
                for el in soup.select(sel):
                    text = el.get_text().strip()
                    if not text or text in seen:
                        continue
                    seen.add(text)
                    if len(text) <= 30:
                        continue
                    if text.upper().startswith("ADVERTISEMENT"):
                        continue
                    parts.append(text)
                    
                if parts:
                    break
            except Exception:
                continue
        
        if not parts:
            for p in soup.find_all('p'):
                t = p.get_text().strip()
                if not t or t in seen or len(t) <= 30:
                    continue
                if t.upper().startswith("ADVERTISEMENT"):
                    continue
                seen.add(t)
                parts.append(t)
        
        if parts:
            combined = ' '.join(parts)
            if SCRAPER_CONTENT_MAX_CHARS > 0 and len(combined) > SCRAPER_CONTENT_MAX_CHARS:
                combined = combined[:SCRAPER_CONTENT_MAX_CHARS].rstrip() + "…"
            return combined
        
        return None
    
    def _parse_published(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            return dt.isoformat()
        except:
            pass
        return None
    
    def _new_context(self, browser: Browser):
        """Create context with anti-Akamai stealth (CRITICAL: use headless=False in dev)."""
        return browser.new_context(
            user_agent=self.USER_AGENT,
            locale='en-US',
            viewport={"width": 1280 + random.choice([-20, 0, 20]), "height": 800 + random.choice([-10, 0, 10])},
            accept_downloads=False,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
    
    def _harden_page(self, page):
        """Block tracking and heavy resources."""
        try:
            page.route("**/*", lambda route: (
                route.abort() if any([
                    "google-analytics.com" in route.request.url,
                    "googletagmanager.com" in route.request.url,
                    "facebook.com" in route.request.url,
                    "doubleclick.net" in route.request.url,
                    route.request.resource_type in ["image", "media", "font"],
                ]) else route.continue_()
            ))
        except:
            pass
    
    def _add_stealth_scripts(self, context):
        """Inject stealth scripts before page loads (CRITICAL for Akamai bypass)."""
        context.add_init_script("""
            // Minimal navigator overrides
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            
            // Mock userAgentData
            try {
                if (navigator.userAgentData === undefined) {
                    Object.defineProperty(navigator, 'userAgentData', {
                        get: () => ({ 
                            brands: [{brand: 'Chromium', version: '129'}, {brand: 'Google Chrome', version: '129'}], 
                            mobile: false 
                        })
                    });
                }
            } catch (e) {}
            
            // Hide automation
            delete navigator.__proto__.webdriver;
        """)
    
    def _goto_with_retry(self, page, url: str, retries: int = 2) -> bool:
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(3.0, 6.0))
                
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                
                # Check if blocked
                title = page.title()
                if "access denied" in title.lower():
                    logger.error(f"ABS-CBN: Blocked (403) - {title}")
                    return False
                
                return True
            except Exception as e:
                logger.warning(f"ABS-CBN: navigation error attempt {attempt+1}: {e}")
                if attempt == retries - 1:
                    return False
        return False
    
    def _extract_article_links(self, soup: BeautifulSoup) -> List[str]:
        urls = []
        seen = set()
        
        for sel in self.SELECTORS["article_links"]:
            try:
                for a in soup.select(sel):
                    href = a.get('href')
                    if not href:
                        continue
                    full = urljoin(self.BASE_URL, href)
                    if full in seen:
                        continue
                    if self._validate_url(full):
                        urls.append(full)
                        seen.add(full)
            except:
                continue
        
        return urls
    
    def _scrape_article(self, url: str, browser: Browser) -> Optional[NormalizedArticle]:
        try:
            context = self._new_context(browser)
            self._add_stealth_scripts(context)
            page = context.new_page()
            
            # BLACK HAT: Apply stealth patches to evade Akamai fingerprinting 🔥
            if HAS_STEALTH and stealth_config:
                stealth_config.apply_stealth_sync(page)
                logger.info("🔥 Stealth patches applied to page")
            
            self._harden_page(page)
            page.set_default_timeout(45000)
            
            # Small delay before navigation
            time.sleep(random.uniform(0.1, 0.5))
            
            ok = self._goto_with_retry(page, url)
            if not ok:
                context.close()
                return None
            
            # Wait for content
            try:
                page.wait_for_timeout(2500)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 4);")
                page.wait_for_timeout(500)
            except:
                pass

            # ABS-CBN pages can hydrate article bodies after the initial HTML.
            # Waiting briefly for network idle + multiple paragraphs reduces excerpt-only captures.
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            try:
                page.wait_for_function(
                    """() => {
                      const sels = ['.article-content p', '.entry-content p', 'article p'];
                      return sels.some((s) => document.querySelectorAll(s).length >= 4);
                    }""",
                    timeout=8000,
                )
            except Exception:
                pass
            
            soup = BeautifulSoup(page.content(), 'html.parser')
            title = self._extract_with_fallbacks(soup, self.SELECTORS["title"])
            if not title or "access denied" in title.lower():
                context.close()
                return None
            
            # Filter lotto titles (like GMA does)
            if re.search(r"\b(lotto|swertres|stl|4d|3d|6/\d{2}|pcso|lottery)\b", title, re.IGNORECASE):
                logger.info(f"ABS-CBN: Skipping lotto article - {title}")
                context.close()
                return None
            
            content = self._extract_content(soup)
            # Retry once if it still looks like an excerpt (common: ends with ... / …).
            if content and re.search(r"(\.\.\.|…)\s*$", content) and len(content) < max(800, SCRAPER_CONTENT_MAX_CHARS - 50):
                try:
                    page.wait_for_timeout(1500)
                except Exception:
                    pass
                try:
                    page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    pass
                soup2 = BeautifulSoup(page.content(), "html.parser")
                content2 = self._extract_content(soup2)
                if content2 and len(content2) > len(content) + 200:
                    content = content2
                    soup = soup2
            raw_published = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"])
            published_iso = self._parse_published(raw_published)
            norm_cat, raw_cat = resolve_category_pair(url, soup)
            
            article = build_article(
                source="ABS-CBN",
                title=title,
                url=url,
                content=content,
                category=norm_cat,
                published_at=published_iso,
                raw_category=raw_cat,
            )
            
            context.close()
            return article
        except Exception as e:
            logger.error(f"ABS-CBN: failed {url}: {e}")
            return None
    
    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        start = time.time()
        articles = []
        errors = []
        
        # Check if we're in headed mode (required for ABS-CBN)
        headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
        if headless_mode:
            logger.warning("ABS-CBN: Running in headless mode - may be blocked by Akamai. Set PLAYWRIGHT_HEADLESS=false for dev.")
        
        try:
            # Use custom browser launch for headed mode in dev
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=headless_mode,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
                )
                
                context = self._new_context(browser)
                self._add_stealth_scripts(context)
                page = context.new_page()
                
                # BLACK HAT: Apply stealth patches to main page 🔥
                if HAS_STEALTH and stealth_config:
                    stealth_config.apply_stealth_sync(page)
                    logger.info("🔥 Stealth patches applied to main discovery page")
                
                self._harden_page(page)
                page.set_default_timeout(60000)
                
                # Try landing pages
                loaded = False
                for path in self.START_PATHS:
                    url = urljoin(self.BASE_URL, path)
                    logger.info(f"ABS-CBN: Trying {url}")
                    ok = self._goto_with_retry(page, url)
                    if ok:
                        loaded = True
                        break
                    self._human_delay()
                
                if not loaded:
                    raise RuntimeError("ABS-CBN: All landing pages blocked")
                
                # Wait for JS content
                try:
                    page.wait_for_timeout(2500)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 4);")
                    page.wait_for_timeout(500)
                except:
                    pass
                
                soup = BeautifulSoup(page.content(), 'html.parser')
                urls = self._extract_article_links(soup)
                logger.info(f"ABS-CBN: found {len(urls)} URLs")
                
                for i, url in enumerate(urls[:max_articles]):
                    art = self._scrape_article(url, browser)
                    if art:
                        articles.append(art)
                        logger.info(f"ABS-CBN: scraped {art.title}")
                    else:
                        errors.append(f"failed to extract {url}")
                    
                    if i < len(urls[:max_articles]) - 1:
                        self._human_delay()
                
                context.close()
                browser.close()
                
        except Exception as e:
            errors.append(str(e))
            logger.error(f"ABS-CBN: critical error {e}")
        
        total = time.time() - start
        performance = {
            "total_time": total,
            "articles_per_second": len(articles) / total if total > 0 else 0,
            "success_rate": len(articles) / (len(articles) + len(errors)) if (len(articles) + len(errors)) > 0 else 0
        }
        metadata = {
            "source": "ABS-CBN",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "headless_mode": headless_mode,
        }
        
        logger.info(f"ABS-CBN: completed {len(articles)} articles, {len(errors)} errors in {total:.2f}s")
        return ScrapingResult(articles=articles, errors=errors, performance=performance, metadata=metadata)


def scrape_abs_cbn_latest() -> List[NormalizedArticle]:
    scraper = ABSCBNScraper()
    result = scraper.scrape_latest(max_articles=3)
    if result.errors:
        logger.warning(f"ABS-CBN: errors {result.errors}")
    return result.articles
