from celery import Celery
from app.core.config import settings
from celery.schedules import schedule

celery_app = Celery(
    "ph_eye",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.workers.tasks', 'app.workers.ml_tasks']
)

# Production-grade configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Manila",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    # Beat configuration
    beat_max_loop_interval=60,  # Check every minute
    beat_sync_every=1,  # Sync every task
)

# Production schedules with intelligent intervals
celery_app.conf.beat_schedule = {
    # HIGH-FREQUENCY SOURCES (1.0-1.25 hours)
    "scrape_rappler": {
        "task": "app.workers.tasks.scrape_rappler_task",
        "schedule": schedule(1.0 * 60 * 60),  # 1.00 hour
    },
    "scrape_gma": {
        "task": "app.workers.tasks.scrape_gma_task", 
        "schedule": schedule(1.08 * 60 * 60),  # 1.08 hours
    },
    "scrape_philstar": {
        "task": "app.workers.tasks.scrape_philstar_task",
        "schedule": schedule(1.17 * 60 * 60),  # 1.17 hours
    },
    "scrape_inquirer": {
        "task": "app.workers.tasks.scrape_inquirer_task",
        "schedule": schedule(1.25 * 60 * 60),  # 1.25 hours
    },
    
    # MEDIUM-FREQUENCY SOURCES (1.33-1.42 hours)
    "scrape_manila_bulletin": {
        "task": "app.workers.tasks.scrape_manila_bulletin_task",
        "schedule": schedule(1.33 * 60 * 60),  # 1.33 hours
    },
    "scrape_manila_times": {
        "task": "app.workers.tasks.scrape_manila_times_task",
        "schedule": schedule(1.42 * 60 * 60),  # 1.42 hours
    },
    
    # LOW-FREQUENCY SOURCES (1.50+ hours)
    "scrape_sunstar": {
        "task": "app.workers.tasks.scrape_sunstar_task",
        "schedule": schedule(1.50 * 60 * 60),  # 1.50 hours
    },
}
