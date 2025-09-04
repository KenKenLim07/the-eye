import sys
sys.path.append('.')
from app.scrapers.manila_bulletin import ManilaBulletinScraper
import logging
logging.basicConfig(level=logging.INFO)

# Create a patched version of the scraper
class FixedManilaBulletinScraper(ManilaBulletinScraper):
    def _discover_links_from_homepage(self, max_links: int = 20) -> List[str]:
        """Discover links directly from Manila Bulletin homepage."""
        try:
            data = self._fetch_url(self.BASE_URL)
            if not data:
                return []
            
            html = data.decode('utf-8', errors='ignore')
            links = self._discover_links_from_html(html)
            return links[:max_links]
        except Exception as e:
            logger.error(f"Homepage discovery failed: {e}")
            return []

    def scrape_latest(self, max_articles: int = 3):
        """Updated scrape_latest with homepage discovery first."""
        start = time.time()
        articles: List[NormalizedArticle] = []
        errors: List[str] = []
        discovered: List[str] = []
        
        # 1) First try homepage discovery (fastest and most reliable)
        homepage_links = []
        try:
            logger.info("Trying homepage discovery")
            homepage_links = self._discover_links_from_homepage(max_links=max_articles * 10)
            discovered.extend(homepage_links)
            logger.info(f"Homepage found {len(homepage_links)} links")
        except Exception as e:
            errors.append(f"homepage:{e}")
            logger.error(f"Homepage discovery failed: {e}")

        # 2) Then try section HTML discovery if still low
        html_links_found = 0
        if len(discovered) < max_articles * 2:
            try:
                with launch_browser() as browser:
                    for path in self.START_PATHS[:2]:  # only first 2 sections
                        try:
                            self._human_delay()
                            context = browser.new_context(
                                user_agent=self.USER_AGENT,
                                extra_http_headers={"Referer": self.BASE_URL}
                            )
                            page = context.new_page()
                            page.set_default_navigation_timeout(20_000)
                            page.set_default_timeout(20_000)
                            url = urljoin(self.BASE_URL, path)
                            try:
                                page.goto(url, wait_until="networkidle")
                            except Exception:
                                page.goto(url, wait_until="domcontentloaded")
                            new_links = self._discover_links_from_html(page.content())[:5]  # cap per section
                            html_links_found += len(new_links)
                            discovered.extend(new_links)
                            context.close()
                        except Exception as e:
                            errors.append(f"discover@{path}:{e}")
                            try:
                                context.close()
                            except Exception:
                                pass
            except Exception as e:
                errors.append(f"sections:{e}")

        # 3) Finally sitemaps if not cooled down
        sitemap_links = []
        if len(discovered) < max_articles * 2:
            try:
                sitemap_links = self._discover_links_from_sitemaps(max_links=max_articles * 10)
                discovered.extend(sitemap_links)
            except Exception as e:
                errors.append(f"sitemaps:{e}")

        # Dedup and validate
        candidates: List[str] = []
        seen = set()
        for u in discovered:
            if u not in seen and self._validate_url(u):
                seen.add(u)
                candidates.append(u)

        logger.info(
            f"MB discovery: homepage={len(homepage_links)}, html={html_links_found}, sitemaps={len(sitemap_links)}, candidates={len(candidates)}"
        )

        # Scrape articles
        try:
            with launch_browser() as browser:
                for url in candidates:
                    if len(articles) >= max_articles:
                        break
                    art = self._scrape_article(url, browser)
                    if art:
                        articles.append(art)
        except Exception as e:
            errors.append(str(e))
        
        duration = time.time() - start
        perf = {"duration_s": round(duration, 2), "count": len(articles)}
        meta = {"domain": "mb.com.ph", "candidates": len(discovered)}
        return ScrapingResult(articles=articles, errors=errors, performance=perf, metadata=meta)

# Test the fixed scraper
scraper = FixedManilaBulletinScraper()
print('Testing fixed Manila Bulletin scraper...')
result = scraper.scrape_latest(max_articles=3)
print(f'Result: {len(result.articles)} articles, {len(result.errors)} errors')
for article in result.articles:
    print(f'  - {article.title}')
