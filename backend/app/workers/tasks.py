from celery import shared_task
from app.core.supabase import get_supabase
from datetime import datetime, timezone
from app.scrapers.inquirer import InquirerScraper
import logging
from app.observability.logs import start_run, finalize_run
from app.workers.ml_tasks import analyze_articles_task
from app.workers.scrape_pipeline import run_scrape_task

# New import for GMA
from app.scrapers.gma import GMAScraper
# New import for Philstar
from app.scrapers.philstar import PhilStarScraper

# New import for Manila Bulletin
from app.scrapers.manila_bulletin import ManilaBulletinScraper

# New import for Rappler
# New import for Manila Times
from app.scrapers.manila_times import ManilaTimesScraper
from app.scrapers.rappler import RapplerScraper
from app.scrapers.sunstar import SunstarScraper

# New import for ABS-CBN (Akamai-sensitive; needs headed mode via Xvfb in Docker)
from app.scrapers.abs_cbn import ABSCBNScraper

logger = logging.getLogger(__name__)

@shared_task
def scrape_sample(source: str = "Inquirer"):
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()

    title = f"Sample scrape at {now}"
    url = f"https://example.com/sample-{int(datetime.now().timestamp())}"
    content = "This is a sample article created by the Celery worker."

    # Insert a sample row; ignore duplicate URLs
    try:
        existing = sb.table("articles").eq("url", url).limit(1).execute()
        if existing.data:
            return {"ok": True, "skipped": True, "url": url}
        res = sb.table("articles").insert({
            "source": source,
            "category": "Technology",
            "title": title,
            "url": url,
            "content": content,
            "published_at": now,
        }).execute()
        return {"ok": True, "inserted": len(res.data or [])}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_inquirer_task(self):
    """Enhanced Inquirer scraping task with retry logic and comprehensive monitoring."""
    task_id = str(self.request.id)
    logger.info("Starting Inquirer scraping task %s", task_id)
    scraper = InquirerScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="inquirer",
        source_name="Inquirer",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=15),
        retry_base_seconds=60,
    )

# New GMA task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_gma_task(self):
    task_id = str(self.request.id)
    logger.info("Starting GMA scraping task %s", task_id)
    scraper = GMAScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="gma",
        source_name="GMA",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=15),
        retry_base_seconds=60,
    )

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_philstar_task(self):
    task_id = str(self.request.id)
    logger.info("Starting Philstar scraping task %s", task_id)
    scraper = PhilStarScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="philstar",
        source_name="Philstar",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=15),
        retry_base_seconds=60,
    )
        
        # New Manila Bulletin task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_manila_bulletin_task(self):
    task_id = str(self.request.id)
    logger.info("Starting Manila Bulletin scraping task %s", task_id)
    scraper = ManilaBulletinScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="manila_bulletin",
        source_name="Manila Bulletin",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=20),
        retry_base_seconds=60,
    )
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_rappler_task(self):
    task_id = str(self.request.id)
    logger.info("Starting Rappler scraping task %s", task_id)
    scraper = RapplerScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="rappler",
        source_name="Rappler",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=20),
        retry_base_seconds=60,
    )

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_sunstar_task(self):
    """Celery task for scraping Sunstar articles."""
    task_id = str(self.request.id)
    logger.info("Starting Sunstar scraping task %s", task_id)
    scraper = SunstarScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="sunstar",
        source_name="Sunstar",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_all(max_articles=15),
        retry_base_seconds=60,
    )

# Manila Times task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_manila_times_task(self):
    task_id = str(self.request.id)
    logger.info("Starting Manila Times scraping task %s", task_id)
    scraper = ManilaTimesScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="manila_times",
        source_name="Manila Times",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=15),
        retry_base_seconds=60,
    )


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def scrape_abs_cbn_task(self):
    """
    ABS-CBN is often blocked in headless mode (Akamai).
    Run the Celery worker under Xvfb and set PLAYWRIGHT_HEADLESS=false for best results.
    """
    task_id = str(self.request.id)
    logger.info("Starting ABS-CBN scraping task %s", task_id)
    scraper = ABSCBNScraper()
    return run_scrape_task(
        celery_self=self,
        source_key="abs_cbn",
        source_name="ABS-CBN",
        task_id=task_id,
        scrape_fn=lambda: scraper.scrape_latest(max_articles=10),
        retry_base_seconds=120,
    )
