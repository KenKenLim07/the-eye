from fastapi import APIRouter, Body

from app.workers.celery_app import celery
from celery.result import AsyncResult

from app.workers.tasks import (
    scrape_gma_task,
    scrape_inquirer_task,
    scrape_manila_bulletin_task,
    scrape_manila_times_task,
    scrape_philstar_task,
    scrape_rappler_task,
    scrape_sunstar_task,
)


router = APIRouter()


@router.post("/scrape/run")
async def run_scrape(payload: dict = Body(default={})):
    # Handle both 'source' (singular) and 'sources' (plural) parameters
    if "source" in payload:
        sources = [payload["source"]]
    elif "sources" in payload:
        sources = payload["sources"]
    else:
        sources = ["inquirer"]  # Default fallback

    jobs = []
    for s in sources:
        if s == "inquirer":
            job = scrape_inquirer_task.delay()
            jobs.append({"source": s, "task_id": str(job)})
        elif s in ["gma", "gma_news", "gma-news"]:
            job = scrape_gma_task.delay()
            jobs.append({"source": "gma", "task_id": str(job)})
        elif s in ["philstar", "phil_star"]:
            job = scrape_philstar_task.delay()
            jobs.append({"source": "philstar", "task_id": str(job)})
        elif s in ["manila_bulletin", "manila-bulletin", "mb"]:
            job = scrape_manila_bulletin_task.delay()
            jobs.append({"source": "manila_bulletin", "task_id": str(job)})
        elif s in ["rappler", "rappler-news", "rappler-news-ph"]:
            job = scrape_rappler_task.delay()
            jobs.append({"source": "rappler", "task_id": str(job)})
        elif s in ["sunstar", "sunstar-ph", "sunstar-philippines"]:
            job = scrape_sunstar_task.delay()
            jobs.append({"source": "sunstar", "task_id": str(job)})
        elif s in ["manila_times", "manila-times", "mt"]:
            job = scrape_manila_times_task.delay()
            jobs.append({"source": "manila_times", "task_id": str(job)})
    return {"queued": True, "jobs": jobs}


@router.get("/scrape/status/{task_id}")
async def get_scrape_status(task_id: str):
    try:
        result = AsyncResult(task_id, app=celery)
        if result.ready():
            if result.successful():
                return {"status": "completed", "result": result.result}
            else:
                return {"status": "failed", "error": str(result.result)}
        else:
            return {"status": "pending"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
