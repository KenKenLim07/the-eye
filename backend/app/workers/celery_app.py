from celery import Celery
from app.core.config import settings
from celery.schedules import schedule

celery = Celery(
    "ph_eye",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Manila",
    enable_utc=True,
)

celery.autodiscover_tasks(["app.workers"])

# Periodic schedules (in seconds). Kept conservative for stealth.
# You can tune these intervals or switch to crontab if desired.
celery.conf.beat_schedule = {
    # Run GMA (v1) roughly every 45 minutes
    "scrape_gma_v1": {
        "task": "app.workers.tasks.scrape_gma_v1_task",
        "schedule": schedule(65 * 60),
    },
    # Rappler every 60 minutes
    "scrape_rappler": {
        "task": "app.workers.tasks.scrape_rappler_task",
        "schedule": schedule(60 * 60),
    },
    # Inquirer every 75 minutes
    "scrape_inquirer": {
        "task": "app.workers.tasks.scrape_inquirer_task",
        "schedule": schedule(75 * 60),
    },
    # Philstar every 70 minutes
    "scrape_philstar": {
        "task": "app.workers.tasks.scrape_philstar_task",
        "schedule": schedule(70 * 60),
    },
    # Sunstar every 90 minutes
    "scrape_sunstar": {
        "task": "app.workers.tasks.scrape_sunstar_task",
        "schedule": schedule(90 * 60),
    },
    # Manila Bulletin every 80 minutes
    "scrape_manila_bulletin": {
        "task": "app.workers.tasks.scrape_manila_bulletin_task",
        "schedule": schedule(80 * 60),
    },
} 