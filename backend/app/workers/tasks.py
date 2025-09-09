from celery import shared_task
from app.core.supabase import get_supabase
from datetime import datetime, timezone
from app.scrapers.inquirer import scrape_inquirer_latest, InquirerScraper
from app.pipeline.store import insert_articles
import logging
from app.observability.logs import start_run, finalize_run

# Guarded import for ABS-CBN (may be removed)
try:
    from app.scrapers.abs_cbn import ABSCBNScraper
except Exception:
    ABSCBNScraper = None
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
        existing = sb.table("articles").select("id").eq("url", url).limit(1).execute()
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
    task_id = self.request.id
    logger.info(f"Starting Inquirer scraping task {task_id}")
    log = start_run("inquirer")
    
    try:
        # Run the scraper
        scraper = InquirerScraper()
        import random
        result = scraper.scrape_latest(max_articles=12)
        
        # Log scraping results
        logger.info(f"Task {task_id} - Scraping completed: {len(result.articles)} articles, {len(result.errors)} errors")
        logger.info(f"Task {task_id} - Performance: {result.performance}")
        
        if result.errors:
            logger.warning(f"Task {task_id} - Scraping errors: {result.errors}")
        
        # Store articles in database
        if result.articles:
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - Storage result: {store_result}")
            finalize_run(log["id"], status="success", articles_scraped=len(result.articles))
            
            # Return comprehensive result
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
            logger.warning(f"Task {task_id} - No articles found to store")
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0}
            }
            
    except Exception as e:
        error_msg = f"Task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        finalize_run(log["id"], status="error", articles_scraped=(len(result.articles) if "result" in locals() else 0), error_message=str(e))
        
        # Retry logic for transient failures
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        else:
            logger.error(f"Task {task_id} - Max retries exceeded, marking as failed")
            return {
                "ok": False,
                "task_id": task_id,
                "error": error_msg,
                "retries_exhausted": True
            }

# ABS-CBN task is disabled (site defense too strong / scraper removed)
@shared_task(bind=True, max_retries=0)
def scrape_abs_cbn_task(self):
    task_id = self.request.id
    logger.info(f"ABS-CBN task {task_id} requested but DISABLED")
    log = start_run("abs_cbn")
    finalize_run(log["id"], status="success", articles_scraped=0)
    return {"ok": True, "task_id": task_id, "disabled": True, "reason": "ABS-CBN scraper removed/disabled"}

# New GMA task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_gma_task(self):
    task_id = self.request.id
    logger.info(f"Starting GMA scraping task {task_id}")
    log = start_run("gma")
    try:
        scraper = GMAScraper()
        import random
        result = scraper.scrape_latest(max_articles=12)
        logger.info(f"Task {task_id} - GMA scraped {len(result.articles)} articles, {len(result.errors)} errors")
        if result.articles:
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - GMA storage result: {store_result}")
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
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0}
            }
    except Exception as e:
        error_msg = f"GMA task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        finalize_run(log["id"], status="error", articles_scraped=(len(result.articles) if "result" in locals() else 0), error_message=str(e))
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {"ok": False, "task_id": task_id, "error": error_msg, "retries_exhausted": True} 

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_philstar_task(self):
    task_id = self.request.id
    logger.info(f"Starting Philstar scraping task {task_id}")
    log = start_run("philstar")
    try:
        scraper = PhilStarScraper()
        import random
        result = scraper.scrape_latest(max_articles=12)
        logger.info(f"Task {task_id} - Philstar scraped {len(result.articles)} articles, {len(result.errors)} errors")
        if result.articles:
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - Philstar storage result: {store_result}")
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
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0}
            }
    except Exception as e:
        error_msg = f"Philstar task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        finalize_run(log["id"], status="error", articles_scraped=(len(result.articles) if "result" in locals() else 0), error_message=str(e))
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {"ok": False, "task_id": task_id, "error": error_msg, "retries_exhausted": True} 
        
        # New Manila Bulletin task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_manila_bulletin_task(self):
    task_id = self.request.id
    logger.info(f"Starting Manila Bulletin scraping task {task_id}")
    log = start_run("manila_bulletin")
    try:
        scraper = ManilaBulletinScraper()
        import random
        result = scraper.scrape_latest(max_articles=random.randint(2, 4))  # More conservative range
        logger.info(f"Task {task_id} - Manila Bulletin scraped {len(result.articles)} articles, {len(result.errors)} errors")
        if result.articles:
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - Manila Bulletin storage result: {store_result}")
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
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0}
            }
    except Exception as e:
        error_msg = f"Manila Bulletin task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        finalize_run(log["id"], status="error", articles_scraped=(len(result.articles) if "result" in locals() else 0), error_message=str(e))
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {"ok": False, "task_id": task_id, "error": error_msg, "retries_exhausted": True} 
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_rappler_task(self):
    """Advanced Rappler scraping task with senior dev and black hat techniques."""
    task_id = self.request.id
    logger.info(f"Starting Rappler scraping task {task_id}")
    
    log = start_run("rappler")
    
    try:
        import random
        scraper = RapplerScraper()
        result = scraper.scrape_latest(max_articles=random.randint(3, 5))
        
        logger.info(f"Task {task_id} - Rappler scraped {len(result.articles)} articles, {len(result.errors)} errors")
        
        if result.articles:
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - Rappler storage result: {store_result}")
            
            finalize_run(log["id"], status="success", articles_scraped=len(result.articles))
            
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": len(result.articles),
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata,
                },
                "storage": store_result,
            }
        else:
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata,
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0},
            }
    
    except Exception as e:
        error_msg = f"Rappler task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        
        finalize_run(
            log["id"],
            status="error",
            articles_scraped=(len(result.articles) if "result" in locals() else 0),
            error_message=str(e),
        )
        
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {
                "ok": False, 
                "task_id": task_id, 
                "error": error_msg, 
                "retries_exhausted": True
            }

# New import for Sunstar
from app.scrapers.sunstar import SunstarScraper

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_sunstar_task(self):
    """Celery task for scraping Sunstar articles."""
    task_id = str(self.request.id)
    logger.info(f"Starting Sunstar scraping task {task_id}")
    
    log = start_run("sunstar")
    
    try:
        scraper = SunstarScraper()
        import random
        result = scraper.scrape_all(max_articles=random.randint(3, 5))  # Conservative range like other scrapers
        
        if result.articles:
            # Store articles in database
            storage_result = insert_articles(result.articles)
            finalize_run(log["id"], status="success", articles_scraped=len(result.articles))
            
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": len(result.articles),
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata,
                },
                "storage": storage_result,
            }
        else:
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata,
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0},
            }
    except Exception as e:
        error_msg = f"Sunstar task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        finalize_run(log["id"], status="error", articles_scraped=(len(result.articles) if "result" in locals() else 0), error_message=str(e))
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {
                "ok": False, 
                "task_id": task_id, 
                "error": error_msg, 
                "retries_exhausted": True
            }

# Manila Times task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_manila_times_task(self):
    """Manila Times scraping task with stealth approach."""
    task_id = self.request.id
    logger.info(f"Starting Manila Times scraping task {task_id}")
    log = start_run("manila_times")
    
    try:
        scraper = ManilaTimesScraper()
        import random
        result = scraper.scrape_latest(max_articles=12)
        
        logger.info(f"Task {task_id} - Manila Times scraped {len(result.articles)} articles, {len(result.errors)} errors")
        
        if result.articles:
            store_result = insert_articles(result.articles)
            logger.info(f"Task {task_id} - Manila Times storage result: {store_result}")
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
            finalize_run(log["id"], status="success", articles_scraped=0)
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": 0,
                    "errors": result.errors,
                    "performance": result.performance,
                    "metadata": result.metadata
                },
                "storage": {"checked": 0, "skipped": 0, "inserted": 0}
            }
            
    except Exception as e:
        error_msg = f"Manila Times task {task_id} failed: {str(e)}"
        logger.error(error_msg)
        finalize_run(log["id"], status="error", articles_scraped=(len(result.articles) if "result" in locals() else 0), error_message=str(e))
        
        if self.request.retries < self.max_retries:
            logger.info(f"Task {task_id} - Retrying ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        else:
            return {
                "ok": False,
                "task_id": task_id,
                "error": error_msg,
                "retries_exhausted": True
            }
