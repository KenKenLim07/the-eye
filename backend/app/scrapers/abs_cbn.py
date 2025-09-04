import time
import logging
import random
import os
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass
from playwright.sync_api import Browser
from bs4 import BeautifulSoup
from app.pipeline.normalize import build_article, NormalizedArticle
from app.scrapers.base import launch_browser
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
    """Stealth scraper for ABS-CBN News with security hardening and RSS discovery."""

    BASE_URL = "https://news.abs-cbn.com"
    # Static article URLs as fallback (these are real current articles)
    STATIC_ARTICLE_URLS = [
        "https://news.abs-cbn.com/news/nation/2025/9/3/dpwh-ncr-no-ghost-flood-control-projects-in-metro-manila-1735",
        "https://news.abs-cbn.com/news/business/2025/9/3/airasia-launches-piso-sale-for-reopened-cebu-routes-1751",
        "https://news.abs-cbn.com/news/business/2025/9/3/sec-warns-against-investing-in-pegasus-international-1547",
        "https://news.abs-cbn.com/news/nation/2025/9/3/bfp-delayed-report-blocked-road-hamper-response-to-deadly-malabon-fire-1721",
        "https://news.abs-cbn.com/news/sports/2025/9/3/pba-commissioner-warns-players-about-social-media-posts-1750",
    ]
    
    # UA pool to randomize fingerprint
    USER_AGENTS = [
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        ),
    ]

    MIN_DELAY = 5.0
    MAX_DELAY = 12.0
    MAX_RETRIES = 3

    RSS_CANDIDATES = [
        "/rss",            # common
        "/rss.xml",        # alternative
        "/news/rss",       # section
        "/latest/rss",     # latest
    ]

    SELECTORS = {
        "title": [
            "h1.article__title",
            "h1.entry-title",
            "h1",
            ".article-title",
            "title"
        ],
        "content": [
            ".article-content p",
            ".article__content p",
            ".story-content p",
            ".post-content p",
            "article p",
            "p"
        ],
        "published_date": [
            "time[datetime]",
            ".article__date time",
            ".date",
            "time"
        ]
    }

    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q=site:news.abs-cbn.com&hl=en-PH&gl=PH&ceid=PH:en"

    def __init__(self):
        self.session_start = time.time()

    def _human_delay(self):
        delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        logger.info(f"ABS-CBN: waiting {delay:.1f}s before next request (stealth)")
        time.sleep(delay)

    def _validate_url(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if not parsed.netloc.endswith("abs-cbn.com"):
            logger.warning(f"ABS-CBN: blocked external URL {url}")
            return False
        return True

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
                    value = el.get_text().strip()
                    if value:
                        return self._sanitize_text(value)
            except Exception as e:
                logger.debug(f"ABS-CBN selector {sel} failed: {e}")
                continue
        return None

    def _get_proxy_config(self) -> Optional[Dict[str, str]]:
        """Get proxy config from environment variables."""
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if http_proxy or https_proxy:
            return {
                'http://': http_proxy or https_proxy,
                'https://': https_proxy or http_proxy,
            }
        return None

    def _random_user_agent(self) -> str:
        return random.choice(self.USER_AGENTS)

    def _http_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self._random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-PH,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': self.BASE_URL + '/',
            'Upgrade-Insecure-Requests': '1',
        }

    def _discover_links_from_static_urls(self, max_links: int = 10) -> List[str]:
        """Use static article URLs as reliable fallback."""
        logger.info(f"ABS-CBN: using {len(self.STATIC_ARTICLE_URLS)} static article URLs")
        return self.STATIC_ARTICLE_URLS[:max_links]

    def _discover_links_from_google_news_rss(self, max_links: int = 15) -> List[str]:
        """Enhanced Google News RSS parsing with better URL resolution."""
        links: List[str] = []
        try:
            proxy_config = self._get_proxy_config()
            with httpx.Client(
                follow_redirects=True, 
                timeout=15.0, 
                headers=self._http_headers(),
                proxies=proxy_config
            ) as client:
                r = client.get(self.GOOGLE_NEWS_RSS)
                if r.status_code >= 400:
                    logger.warning(f"ABS-CBN: Google News RSS returned {r.status_code}")
                    return []
                soup = BeautifulSoup(r.text, "xml")
                items = soup.select("item")
                logger.info(f"ABS-CBN: Google News RSS items={len(items)}")
                for node in items:
                    if len(links) >= max_links:
                        break
                    resolved: Optional[str] = None
                    # 1) Try to extract from content:encoded block
                    try:
                        enc = node.select_one("content\\:encoded")
                        if enc and enc.text:
                            enc_html = BeautifulSoup(enc.text, "html.parser")
                            for a in enc_html.find_all("a", href=True):
                                href = a["href"].strip()
                                if href.startswith("http") and "news.abs-cbn.com" in href:
                                    resolved = href
                                    break
                    except Exception:
                        pass
                    # 2) Try link element with url= parameter
                    if not resolved:
                        try:
                            ln = node.find("link")
                            if ln and ln.get_text():
                                gn = ln.get_text().strip()
                                if gn:
                                    p = urlparse(gn)
                                    direct = (parse_qs(p.query).get("url") or [None])[0]
                                    if direct and direct.startswith("http") and "news.abs-cbn.com" in direct:
                                        resolved = direct
                        except Exception:
                            pass
                    # 3) Try to resolve Google News URL
                    if not resolved:
                        try:
                            ln = node.find("link")
                            if ln and ln.get_text():
                                gn = ln.get_text().strip()
                                if gn:
                                    resp = client.get(gn, follow_redirects=True)
                                    if resp.status_code < 400:
                                        final_url = str(resp.url)
                                        if "news.abs-cbn.com" in final_url:
                                            resolved = final_url
                        except Exception:
                            pass
                    if resolved and self._validate_url(resolved):
                        links.append(resolved)
                logger.info(f"ABS-CBN: Google News RSS resolved {len(links)} publisher URLs")
        except Exception as e:
            logger.warning(f"ABS-CBN: Google News RSS parse error: {e}")
            return []
        # dedupe
        seen = set()
        res: List[str] = []
        for l in links:
            if l not in seen:
                seen.add(l)
                res.append(l)
        return res

    def _extract_content(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        # Remove obvious boilerplate containers
        try:
            for sel in [
                "nav", "footer", "aside", ".share", ".social", ".related", ".recommend",
                ".tags", ".breadcrumbs", ".author", ".byline", ".comments", "#comments",
                ".ad", "[class*='advert']", "[id*='advert']", "script", "style", "template", "noscript",
            ]:
                for el in soup.select(sel):
                    el.decompose()
        except Exception:
            pass
        parts: List[str] = []
        for sel in self.SELECTORS["content"]:
            try:
                for el in soup.select(sel):
                    text = el.get_text(" ", strip=True)
                    if not text:
                        continue
                    if "{{" in text and "}}" in text:
                        continue
                    up = text.upper()
                    if up.startswith("ADVERTISEMENT"):
                        continue
                    if len(text) < 25 and not (text.endswith(".") or text.endswith("!") or text.endswith("?")):
                        continue
                    parts.append(self._sanitize_text(text))
                    if len(parts) >= 40:
                        break
                if parts:
                    break
            except Exception as e:
                logger.debug(f"ABS-CBN content selector {sel} failed: {e}")
                continue
        if not parts:
            for p in soup.find_all('p'):
                t = (p.get_text(" ", strip=True) or "").strip()
                if not t:
                    continue
                if "{{" in t and "}}" in t:
                    continue
                if t.upper().startswith("ADVERTISEMENT"):
                    continue
                if len(t) < 25 and not (t.endswith(".") or t.endswith("!") or t.endswith("?")):
                    continue
                parts.append(self._sanitize_text(t))
                if len(parts) >= 40:
                    break
        if parts:
            combined = "\n\n".join(parts)
            return combined[:20000]
        logger.warning(f"ABS-CBN: no content extracted for {url}")
        return None

    def _to_amp(self, url: str) -> List[str]:
        candidates = []
        if url.endswith('/'):
            candidates.append(url + 'amp')
        else:
            candidates.append(url.rstrip('/') + '/amp')
        if '?amp' not in url:
            candidates.append(url + ('&amp' if '?' in url else '?amp'))
        candidates.append(url)
        return candidates

    def _fetch_article_http(self, url: str) -> Optional[BeautifulSoup]:
        proxy_config = self._get_proxy_config()
        with httpx.Client(
            follow_redirects=True, 
            timeout=20.0, 
            headers=self._http_headers(),
            proxies=proxy_config
        ) as client:
            for candidate in self._to_amp(url):
                try:
                    r = client.get(candidate)
                    if r.status_code < 400 and r.text:
                        return BeautifulSoup(r.text, 'html.parser')
                    logger.debug(f"ABS-CBN HTTP {r.status_code} for {candidate}")
                except Exception as e:
                    logger.debug(f"ABS-CBN HTTP error for {candidate}: {e}")
                self._human_delay()
        return None

    def _build_article_from_soup(self, soup: BeautifulSoup, url: str) -> Optional[NormalizedArticle]:
        title = self._extract_with_fallbacks(soup, self.SELECTORS["title"]) or ""
        if not title:
            return None
        content = self._extract_content(soup, url)
        published = self._extract_with_fallbacks(soup, self.SELECTORS["published_date"]) or None
        norm_cat, raw_cat = resolve_category_pair(url, soup)
        return build_article(
            source="ABS-CBN",
            title=title,
            url=url,
            content=content,
            category=norm_cat,
            published_at=published,
            raw_category=raw_cat,
        )

    def scrape_latest(self, max_articles: int = 3) -> ScrapingResult:
        start = time.time()
        articles: List[NormalizedArticle] = []
        errors: List[str] = []
        diag: Dict[str, Any] = {"static_links": 0, "gnews_rss_links": 0, "candidates": 0}
        diag_samples: Dict[str, List[str]] = {"static": [], "gnews_rss": [], "candidates": []}
        try:
            discovered: List[str] = []
            # 1) Static article URLs (reliable fallback)
            static_links = self._discover_links_from_static_urls(max_links=max_articles * 2)
            discovered.extend(static_links)
            diag["static_links"] = len(static_links)
            diag_samples["static"] = static_links[:5]
            # 2) Google News RSS (enhanced parsing)
            if len(discovered) < max_articles * 2:
                gnews_rss = self._discover_links_from_google_news_rss(max_links=max_articles * 5)
                discovered.extend(gnews_rss)
                diag["gnews_rss_links"] = len(gnews_rss)
                diag_samples["gnews_rss"] = gnews_rss[:5]
            # Dedup and validate
            seen = set()
            candidates: List[str] = []
            for u in discovered:
                if u not in seen and self._validate_url(u):
                    seen.add(u)
                    candidates.append(u)
            diag["candidates"] = len(candidates)
            diag_samples["candidates"] = candidates[:5]
            # Fetch articles
            for i, url in enumerate(candidates[:max_articles]):
                soup = self._fetch_article_http(url)
                if soup:
                    art = self._build_article_from_soup(soup, url)
                    if art:
                        articles.append(art)
                        logger.info(f"ABS-CBN: scraped {art.title}")
                    else:
                        errors.append(f"failed to extract {url}")
                else:
                    errors.append(f"failed to load {url}")
                if i < min(len(candidates), max_articles) - 1:
                    self._human_delay()
        except Exception as e:
            msg = f"ABS-CBN: critical error {e}"
            logger.error(msg)
            errors.append(str(e))
        total = time.time() - start
        performance = {
            "total_time": total,
            "articles_per_second": len(articles) / total if total > 0 else 0,
            "success_rate": len(articles) / (len(articles) + len(errors)) if (len(articles) + len(errors)) > 0 else 0
        }
        metadata = {
            "source": "ABS-CBN News",
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_articles_found": len(articles),
            "total_errors": len(errors),
            "discovery": diag,
            "samples": diag_samples
        }
        logger.info(f"ABS-CBN: completed {len(articles)} articles, {len(errors)} errors in {total:.2f}s")
        return ScrapingResult(articles=articles, errors=errors, performance=performance, metadata=metadata)


def scrape_abs_cbn_latest() -> List[NormalizedArticle]:
    scraper = ABSCBNScraper()
    result = scraper.scrape_latest(max_articles=3)
    if result.errors:
        logger.warning(f"ABS-CBN: errors {result.errors}")
    return result.articles
