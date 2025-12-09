#!/usr/bin/env python3
"""
SENIOR CYBER SEC & BLACK HAT VETERAN - ABS-CBN PRODUCTION SCRAPER 🔥💀🚀
==========================================================================
Production-grade scraper for ABS-CBN with advanced Akamai bypass.
"""
import sys
import time
import random
import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright, Browser
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ABSCBNScraper:
    """Advanced stealth scraper for ABS-CBN News with Akamai bypass."""
    
    BASE_URL = "https://news.abs-cbn.com"
    START_PATHS = [
        "/",
        "/news",
        "/breaking-news",
    ]
    
    # Rotating User-Agents (production pool)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]
    
    VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
    ]
    
    TIMEZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Hong_Kong"]
    
    def _get_random_ua(self) -> str:
        return random.choice(self.USER_AGENTS)
    
    def _get_random_viewport(self) -> dict:
        return random.choice(self.VIEWPORTS)
    
    def _get_random_timezone(self) -> str:
        return random.choice(self.TIMEZONES)
    
    def _human_delay(self):
        """Human-like delay using normal distribution."""
        delay = random.gauss(8.0, 2.0)
        delay = max(3.0, min(15.0, delay))
        logger.info(f"ABS-CBN: stealth delay {delay:.1f}s")
        time.sleep(delay)
    
    def _new_context(self, browser: Browser):
        """Create stealth browser context with advanced evasion."""
        user_agent = self._get_random_ua()
        viewport = self._get_random_viewport()
        timezone = self._get_random_timezone()
        
        context = browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            timezone_id=timezone,
            locale="en-PH",
            permissions=[],
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=False,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,en-PH;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "Referer": "https://www.google.com/",
            }
        )
        
        # CRITICAL: Inject stealth scripts BEFORE any page loads
        context.add_init_script("""
            // Remove webdriver traces (critical for Akamai)
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            
            // Mock plugins (empty plugins array is suspicious)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'en-PH'],
            });
            
            // Mock chrome object (Playwright lacks this)
            if (!window.chrome) {
                window.chrome = {
                    runtime: {}
                };
            }
            
            // Mock permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Hide automation
            delete navigator.__proto__.webdriver;
        """)
        
        return context
    
    def _harden_page(self, page):
        """Block tracking and heavy resources to speed up and avoid fingerprinting."""
        try:
            # Block analytics, ads, images, fonts, css to reduce fingerprinting surface
            page.route("**/*", lambda route: (
                route.abort() if any([
                    # Analytics & tracking
                    "google-analytics.com" in route.request.url,
                    "googletagmanager.com" in route.request.url,
                    "facebook.com" in route.request.url,
                    "doubleclick.net" in route.request.url,
                    "googlesyndication.com" in route.request.url,
                    "scorecardresearch.com" in route.request.url,
                    "quantserve.com" in route.request.url,
                    # Heavy resources
                    route.request.resource_type in ["image", "media", "font", "stylesheet"],
                    # External domains (keep only abs-cbn)
                    (urlparse(route.request.url).netloc and 
                     "abs-cbn.com" not in urlparse(route.request.url).netloc and
                     route.request.resource_type not in ["document", "script"])
                ]) else route.continue_()
            ))
        except Exception as e:
            logger.warning(f"Route setup failed: {e}")
    
    def _goto_with_retry(self, page, url: str, retries: int = 2) -> bool:
        """Navigate with retry and multiple wait strategies."""
        for attempt in range(retries):
            try:
                if attempt > 0:
                    logger.info(f"ABS-CBN: retry {attempt+1}/{retries} for {url}")
                    time.sleep(random.uniform(3.0, 6.0))
                
                # Try domcontentloaded first (faster)
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if resp and resp.status == 200:
                    return True
                elif resp and resp.status in (403, 429):
                    logger.warning(f"ABS-CBN: blocked {resp.status}")
                    return False
                
            except Exception as e:
                logger.warning(f"ABS-CBN: navigation error attempt {attempt+1}: {e}")
                if attempt < retries - 1:
                    continue
                # Last attempt: try without wait_until
                try:
                    page.goto(url, timeout=45000)
                    page.wait_for_load_state("domcontentloaded", timeout=20000)
                    return True
                except Exception as e2:
                    logger.error(f"ABS-CBN: final navigation failed: {e2}")
                    return False
        
        return False
    
    def _extract_article_links(self, soup: BeautifulSoup) -> List[str]:
        """Extract article links with validation."""
        urls = []
        seen = set()
        
        # Multiple selectors for article links
        selectors = [
            "article a[href]",
            ".list-group a[href]",
            ".article-item a[href]",
            "h3 a[href]",
            "h2 a[href]",
            "a[href*='/news/']",
            "a[href*='/breaking-news/']",
        ]
        
        for sel in selectors:
            try:
                for a in soup.select(sel):
                    href = a.get('href')
                    if not href:
                        continue
                    
                    # Resolve relative URLs
                    full = urljoin(self.BASE_URL, href)
                    
                    if full in seen:
                        continue
                    
                    # Validate URL
                    if self._validate_url(full):
                        urls.append(full)
                        seen.add(full)
            except Exception as e:
                logger.debug(f"Selector {sel} failed: {e}")
                continue
        
        return urls
    
    def _validate_url(self, url: str) -> bool:
        """Advanced URL validation for ABS-CBN articles."""
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            
            # Must be ABS-CBN domain
            if not parsed.netloc.endswith("abs-cbn.com"):
                return False
            
            path = (parsed.path or "").lower()
            
            # Block non-article paths
            blocked_patterns = [
                "photo", "photos", "video", "videos", "gallery", "galleries",
                "tag", "tags", "author", "search", "page",
                ".jpg", ".png", ".pdf", ".mp4",
            ]
            
            if any(pattern in path for pattern in blocked_patterns):
                return False
            
            # Must have article-like structure (at least 2 segments)
            segments = [s for s in parsed.path.split('/') if s]
            if len(segments) < 2:
                return False
            
            # Check for date pattern or news section
            if not (
                "/news/" in path or
                "/breaking-news/" in path or
                "/20" in path  # year pattern
            ):
                return False
            
            return True
            
        except Exception:
            return False
    
    def test_access(self) -> dict:
        """Test if we can access ABS-CBN and extract content."""
        logger.info("ABS-CBN: Testing access...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ])
            
            context = self._new_context(browser)
            page = context.new_page()
            self._harden_page(page)
            
            page.set_default_timeout(45000)
            page.set_default_navigation_timeout(45000)
            
            # Small delay before first request
            time.sleep(random.uniform(1.0, 3.0))
            
            result = {"success": False, "status": None, "title": None, "links_found": 0, "content_preview": None}
            
            for path in self.START_PATHS:
                url = urljoin(self.BASE_URL, path)
                logger.info(f"ABS-CBN: Trying {url}")
                
                ok = self._goto_with_retry(page, url)
                if not ok:
                    logger.warning(f"ABS-CBN: Failed to load {path}")
                    self._human_delay()
                    continue
                
                # Wait for content to appear
                try:
                    page.wait_for_selector("article, .article, h1, h2", timeout=8000)
                except:
                    pass
                
                # Check if blocked
                title = page.title()
                content = page.content()
                
                if "access denied" in title.lower() or "access denied" in content[:1000].lower():
                    logger.error(f"ABS-CBN: Still blocked - {title}")
                    result["title"] = title
                    result["content_preview"] = content[:500]
                    break
                
                # Success - extract info
                logger.info(f"ABS-CBN: ✓ Access successful! Title: {title}")
                soup = BeautifulSoup(content, "html.parser")
                links = self._extract_article_links(soup)
                
                result.update({
                    "success": True,
                    "status": 200,
                    "title": title,
                    "links_found": len(links),
                    "sample_links": links[:10],
                    "content_preview": content[:500]
                })
                
                # Save screenshot for verification
                try:
                    page.screenshot(path="abs_cbn_success.png", full_page=False)
                    logger.info("Screenshot saved: abs_cbn_success.png")
                except:
                    pass
                
                context.close()
                browser.close()
                return result
            
            context.close()
            browser.close()
            return result


def main():
    scraper = ABSCBNScraper()
    result = scraper.test_access()
    
    print("\n" + "="*60)
    print("ABS-CBN SCRAPER TEST RESULTS")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"Title: {result.get('title', 'N/A')}")
    print(f"Links Found: {result.get('links_found', 0)}")
    
    if result['success']:
        print("\n✅ ABS-CBN scraper is WORKING!")
        print("\nSample article links:")
        for link in result.get('sample_links', [])[:5]:
            print(f"  - {link}")
    else:
        print("\n❌ ABS-CBN scraper is BLOCKED")
        print("\nContent preview:")
        print(result.get('content_preview', 'N/A'))
    
    print("="*60)
    
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()









