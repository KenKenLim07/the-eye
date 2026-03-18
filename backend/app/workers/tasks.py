from celery import shared_task
from app.core.supabase import get_supabase
from datetime import datetime, timezone
from app.scrapers.inquirer import InquirerScraper
import logging
from app.observability.logs import start_run, finalize_run
from app.workers.ml_tasks import analyze_articles_task
from app.workers.scrape_pipeline import run_scrape_task

# ABS-CBN scraper (requires PLAYWRIGHT_HEADLESS=false in dev, or xvfb in prod)
from app.scrapers.abs_cbn import ABSCBNScraper
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
        scrape_fn=lambda: scraper.scrape_latest(max_articles=10),
        retry_base_seconds=60,
    )

# ABS-CBN task (requires headed mode or xvfb for Akamai bypass)
@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def scrape_abs_cbn_task(self):
    """ABS-CBN scraper - requires PLAYWRIGHT_HEADLESS=false in dev or xvfb-run in prod."""
    task_id = self.request.id
    logger.info(f"Starting ABS-CBN scraping task {task_id}")
    log = start_run("abs_cbn")
    try:
        scraper = ABSCBNScraper()
        result = scraper.scrape_latest(max_articles=10)
        logger.info(f"Task {task_id} - ABS-CBN scraped {len(result.articles)} articles, {len(result.errors)} errors")
        if result.articles:
            from app.pipeline.store import insert_articles
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - ABS-CBN storage result: {store_result}")
            # Keep ABS-CBN behavior unchanged (custom retry style).
            storage_error = (store_result or {}).get("error")
            if storage_error:
                logger.error("Task %s - ABS-CBN storage failed: %s", task_id, storage_error)
                finalize_run(log["id"], status="error", articles_scraped=len(result.articles), error_message=f"storage_error: {storage_error}")
                return {"ok": False, "task_id": task_id, "error": f"storage_failed: {storage_error}", "storage": store_result}
            inserted_ids = store_result.get("inserted_ids") or []
            if inserted_ids:
                analyze_articles_task.delay(inserted_ids)
            finalize_run(log["id"], status="success", articles_scraped=len(result.articles))
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": len(result.articles),
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata
                },
                "storage": store_result
            }
        else:
            logger.warning(f"Task {task_id} - ABS-CBN: No articles found")
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {"ok": True, "task_id": task_id, "scraping": {"articles_found": 0, "errors": result.errors}}
    except Exception as e:
        logger.error(f"Task {task_id} - ABS-CBN critical error: {e}")
        finalize_run(log["id"], status="error", error_message=str(e))
        raise self.retry(exc=e)

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
        scrape_fn=lambda: scraper.scrape_latest(max_articles=10),
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
        scrape_fn=lambda: scraper.scrape_latest(max_articles=10),
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
        scrape_fn=lambda: scraper.scrape_latest(max_articles=10),
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
        scrape_fn=lambda: scraper.scrape_latest(max_articles=50),
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
        scrape_fn=lambda: scraper.scrape_all(max_articles=10),
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
        scrape_fn=lambda: scraper.scrape_latest(max_articles=10),
        retry_base_seconds=60,
    )

