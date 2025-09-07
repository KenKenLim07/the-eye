from celery import Celery
from app.core.config import settings
from celery.schedules import schedule

celery = Celery(
    "ph_eye",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# SENIOR DEV SOLUTION: Production-grade configuration
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Manila",
    enable_utc=True,
    # Beat configuration - using default scheduler for reliability
    beat_max_loop_interval=60,  # Check every minute
    beat_sync_every=1,  # Sync every task
)

celery.autodiscover_tasks(["app.workers"])

# 🚀 PRODUCTION SCHEDULES: Intelligent intervals based on source characteristics
celery.conf.beat_schedule = {
    # HIGH-FREQUENCY SOURCES (1.0-1.25 hours)
    # Fast, reliable sources with good content volume
    "scrape_rappler": {
        "task": "app.workers.tasks.scrape_rappler_task",
        "schedule": schedule(1.0 * 60 * 60),  # 1.00 hour - Fast, reliable
    },
    "scrape_gma": {
        "task": "app.workers.tasks.scrape_gma_task", 
        "schedule": schedule(1.08 * 60 * 60),  # 1.08 hours - Consistent updates
    },
    "scrape_philstar": {
        "task": "app.workers.tasks.scrape_philstar_task",
        "schedule": schedule(1.17 * 60 * 60),  # 1.17 hours - Good balance
    },
    "scrape_inquirer": {
        "task": "app.workers.tasks.scrape_inquirer_task",
        "schedule": schedule(1.25 * 60 * 60),  # 1.25 hours - High volume, needs stealth
    },
    "scrape_abs_cbn": {
        "task": "app.workers.tasks.scrape_abs_cbn_task",
        "schedule": schedule(1.25 * 60 * 60),  # 1.25 hours - High stealth requirements (25-45s delays)
    },
    
    # MEDIUM-FREQUENCY SOURCES (1.33-1.42 hours)
    # Moderate complexity and update frequency
    "scrape_manila_bulletin": {
        "task": "app.workers.tasks.scrape_manila_bulletin_task",
        "schedule": schedule(1.33 * 60 * 60),  # 1.33 hours - Moderate complexity
    },
    "scrape_manila_times": {
        "task": "app.workers.tasks.scrape_manila_times_task",
        "schedule": schedule(1.42 * 60 * 60),  # 1.42 hours - Slower updates
    },
    
    # LOW-FREQUENCY SOURCES (1.50+ hours)
    # Regional focus, less frequent updates
    "scrape_sunstar": {
        "task": "app.workers.tasks.scrape_sunstar_task",
        "schedule": schedule(1.50 * 60 * 60),  # 1.50 hours - Regional focus
    },
}
