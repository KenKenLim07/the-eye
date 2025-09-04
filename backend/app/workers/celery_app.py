from celery import Celery
from app.core.config import settings

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