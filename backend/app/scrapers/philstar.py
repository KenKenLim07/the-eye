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

    MIN_DELAY = 5.0
    MAX_DELAY = 12.0

    SELECTORS = {
        "article_links": [
            "article h2 a",
            ".article__title a",
            ".listing__item a",
            ".headline__title a",
            "h2 a",
            "a[href*='/headlines']",
        ],
        "title": [
            "h1.article__title",
            "h1.headline__title",
            "h1",
            ".article-title",
            "title"
        ],
        "content": [
            ".article__content p",
            ".article-content p",
            ".story-content p",
            ".content p",
            "article p",
            "p"
        ],
        "published_date": [
            ".article__date",
            ".article__meta",
            "time[datetime]",
            "time",
            ".date"
        ]
    }

    def _human_delay(self):
        delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"PhilStar: waiting {delay:.1f}s (stealth)")
        time.sleep(delay)

    def _validate_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not parsed.netloc.endswith("philstar.com"):
            return False
        return True

    def _is_probable_article(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            path = parsed.path or ""
            # Typical: /headlines/2025/09/03/XXXX/slug
            segments = [s for s in path.split('/') if s]
            blacklist = {"photos", "photo", "videos", "video", "about", "section"}
            if any(seg in blacklist for seg in segments):
                return False
            # Must include a section and a slug
            return len(segments) >= 2
        except Exception:
            return False

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
        parts: List[str] = []
        for sel in self.SELECTORS["content"]:
            try:
                for el in soup.select(sel):
                    txt = el.get_text().strip()
                    if txt and len(txt) > 50 and not txt.upper().startswith("ADVERTISEMENT"):
                        parts.append(txt)
            except Exception:
                continue
        if not parts:
            for p in soup.find_all('p'):
                t = p.get_text().strip()
                if t and len(t) > 30 and not t.upper().startswith("ADVERTISEMENT"):
                    parts.append(t)
        if parts:
            combined = ' '.join(parts)
            if len(combined) > 1000:
                combined = combined[:1000] + "..."
            elif len(combined) > 500:
                combined = combined[:500] + "..."
            return combined
        return None

    def _parse_published(self, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        txt = raw.strip()
        # Common formats: "September 3, 2025 | 5:13pm" or "September 3, 2025 - 5:13pm"
        txt = re.sub(r"\s*[|\-]\s*", " ", txt)
        candidates = [
            (txt, "%B %d, %Y %I:%M%p"),
            (txt, "%B %d, %Y"),
        ]
        for val, fmt in candidates:
            try:
                norm = re.sub(r"\s+", " ", val)
                dt = datetime.strptime(norm, fmt)
                return dt.isoformat()
            except Exception:
                continue
        return None

    def _new_context(self, browser: Browser):
        context = browser.new_context(
            user_agent=self.USER_AGENT,
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

    def _set_headers(self, page):
        page.set_extra_http_headers({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-PH,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': self.BASE_URL + '/',
            'Upgrade-Insecure-Requests': '1',
        })

    def _discover_links(self, soup: BeautifulSoup) -> List[str]:
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
                    if self._validate_url(full) and self._is_probable_article(full):
                        urls.append(full)
                        seen.add(full)
            except Exception:
                continue
        return urls

    def _scrape_article(self, url: str, browser: Browser) -> Optional[NormalizedArticle]:
        try:
            context = self._new_context(browser)
            page = context.new_page()
            self._set_headers(page)
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
                        logger.warning(f"PhilStar: attempt {attempt + 1} failed for {url}, retrying...")
                        time.sleep(2)
                except Exception as e:
                    if attempt == 0:
                        logger.warning(f"PhilStar: attempt {attempt + 1} error for {url}: {e}, retrying...")
                        time.sleep(2)
                    else:
                        raise e
            
            if not resp or resp.status >= 400:
                context.close()
                return None
                
            try:
                page.wait_for_selector('h1', timeout=8000)
            except:
                pass
            soup = BeautifulSoup(page.content(), 'html.parser')
            title = self._extract_with_fallbacks(soup, self.SELECTORS["title"]) or ""
            if not title:
                context.close()
                return None
            content = self._extract_content(soup)
            raw_published = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"]) or None
            published_iso = self._parse_published(raw_published)
            norm_cat, raw_cat = resolve_category_pair(url, soup)
            article = build_article(
                source="Philstar",
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
            logger.error(f"PhilStar: failed {url}: {e}")
            return None

    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        start = time.time()
        articles: List[NormalizedArticle] = []
        errors: List[str] = []
        try:
            with launch_browser() as browser:
                context = self._new_context(browser)
                page = context.new_page()
                self._set_headers(page)
                page.set_default_timeout(30000)
                page.set_default_navigation_timeout(30000)

                resp = None
                for path in self.START_PATHS:
                    try:
                        resp = page.goto(urljoin(self.BASE_URL, path), wait_until='domcontentloaded')
                        if resp and resp.status < 400:
                            break
                        logger.warning(f"PhilStar: landing {path} returned {resp.status if resp else 'unknown'}")
                    except Exception as e:
                        logger.warning(f"PhilStar: error loading {path}: {e}")
                    self._human_delay()

                if not resp or resp.status >= 400:
                    raise RuntimeError(f"PhilStar: landing returned {resp.status if resp else 'unknown'}")

                soup = BeautifulSoup(page.content(), 'html.parser')
                urls = self._discover_links(soup)
                logger.info(f"PhilStar: found {len(urls)} URLs")

                for i, url in enumerate(urls[:max_articles]):
                    art = self._scrape_article(url, browser)
                    if art:
                        articles.append(art)
                        logger.info(f"PhilStar: scraped {art.title}")
                    else:
                        errors.append(f"failed to extract {url}")
                    if i < len(urls[:max_articles]) - 1:
                        self._human_delay()

                context.close()
        except Exception as e:
            errors.append(str(e))
            logger.error(f"PhilStar: critical error {e}")

        total = time.time() - start
        performance = {
            "total_time": total,
            "articles_per_second": len(articles) / total if total > 0 else 0,
            "success_rate": len(articles) / (len(articles) + len(errors)) if (len(articles) + len(errors)) > 0 else 0
        }
        metadata = {
            "source": "Philippine Star",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors)
        }
        logger.info(f"PhilStar: completed {len(articles)} articles, {len(errors)} errors in {total:.2f}s")
        return ScrapingResult(articles=articles, errors=errors, performance=performance, metadata=metadata)


def scrape_philstar_latest() -> List[NormalizedArticle]:
    scraper = PhilStarScraper()
    result = scraper.scrape_latest(max_articles=3)
    if result.errors:
        logger.warning(f"PhilStar: errors {result.errors}")
    return result.articles 
