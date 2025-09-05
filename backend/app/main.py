from fastapi import FastAPI, Body
from .core.config import settings
from app.workers.tasks import scrape_inquirer_task, scrape_abs_cbn_task, scrape_gma_task, scrape_philstar_task, scrape_manila_bulletin_task, scrape_rappler_task, scrape_sunstar_task
from app.workers.celery_app import celery
from celery.result import AsyncResult
from typing import Optional
from app.core.supabase import get_supabase

app = FastAPI(title="PH Eye Backend", version="0.1.0")

@app.get("/")
async def root():
    return {"ok": True, "service": "ph-eye-backend"}

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/scrape/run")
async def run_scrape(payload: dict = Body(default={})):
    sources = payload.get("sources") or ["inquirer"]
    jobs = []
    for s in sources:
        if s == "inquirer":
            job = scrape_inquirer_task.delay()
            jobs.append({"source": s, "task_id": str(job)})
        elif s in ["abs_cbn", "abs-cbn", "abscbn"]:
            job = scrape_abs_cbn_task.delay()
            jobs.append({"source": "abs_cbn", "task_id": str(job)})
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
    return {"queued": True, "jobs": jobs}

@app.get("/scrape/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status and result of a scraping task."""
    task_result = AsyncResult(task_id, app=celery)
    
    if task_result.ready():
        if task_result.successful():
            return {
                "task_id": task_id,
                "status": "completed",
                "result": task_result.result
            }
        else:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(task_result.result)
            }
    else:
        return {
            "task_id": task_id,
            "status": "pending",
            "info": task_result.info
        }

@app.get("/scrape/active")
async def get_active_tasks():
    """Get currently active scraping tasks."""

# New: logs endpoints
@app.get("/logs/recent")
async def get_recent_logs(source: Optional[str] = None, limit: int = 20):
    sb = get_supabase()
    q = sb.table("scraping_logs").select(
        "run_id,source,status,articles_scraped,started_at,completed_at,execution_time_ms"
    ).order("started_at", desc=True).limit(max(1, min(limit, 100)))
    if source:
        q = q.eq("source", source)
    res = q.execute()
    return {"data": res.data or []}

@app.get("/logs/{run_id}")
async def get_log_by_run_id(run_id: str):
    sb = get_supabase()
    res = sb.table("scraping_logs").select("*").eq("run_id", run_id).limit(1).execute()
    return {"data": (res.data or [None])[0]} 

# New: diagnostics endpoint
@app.get("/diagnostics")
async def diagnostics(dry_run: bool = False, max_articles: int = 1):
    """Comprehensive diagnostics for scrapers, Celery, and Supabase.
    - Checks Supabase connectivity and basic permissions
    - Confirms Celery broker/backends reachability
    - Verifies all scraper tasks are registered
    - Optionally triggers 1-article dry runs per scraper (non-blocking)
    """
    report: dict = {
        "env": {
            "broker": settings.celery_broker_url,
            "result_backend": settings.celery_result_backend,
            "supabase_url": settings.supabase_url[:8] + "…" if settings.supabase_url else None,
        },
        "supabase": {},
        "celery": {},
        "tasks": {},
        "dry_runs": [],
    }

    # Supabase ping
    try:
        sb = get_supabase()
        ping = sb.table("scraping_logs").select("id").limit(1).execute()
        report["supabase"] = {"ok": True, "rows": len(ping.data or [])}
    except Exception as e:
        report["supabase"] = {"ok": False, "error": str(e)}

    # Celery ping
    try:
        insp = celery.control.inspect(timeout=2)
        active = insp.active() or {}
        scheduled = insp.scheduled() or {}
        registered = insp.registered() or {}
        report["celery"] = {
            "ok": True,
            "workers": list(active.keys()) if isinstance(active, dict) else [],
            "active_counts": {k: len(v or []) for k, v in (active or {}).items()},
            "scheduled_counts": {k: len(v or []) for k, v in (scheduled or {}).items()},
        }
        # Task registration expectations
        expected = {
            "app.workers.tasks.scrape_inquirer_task": False,
            "app.workers.tasks.scrape_abs_cbn_task": False,
            "app.workers.tasks.scrape_gma_task": False,
            "app.workers.tasks.scrape_philstar_task": False,
            "app.workers.tasks.scrape_manila_bulletin_task": False,
            "app.workers.tasks.scrape_rappler_task": False,
            "app.workers.tasks.scrape_sunstar_task": False,
        }
        # Consolidate registered task names from all workers
        all_registered = set()
        for names in (registered or {}).values():
            for n in (names or []):
                all_registered.add(n)
        for name in expected.keys():
            expected[name] = name in all_registered
        report["tasks"] = expected
    except Exception as e:
        report["celery"] = {"ok": False, "error": str(e)}

    # Optional dry-run (enqueue minimal jobs)
    if dry_run:
        try:
            jobs = []
            jobs.append({"source": "inquirer", "task_id": str(scrape_inquirer_task.delay())})
            jobs.append({"source": "gma", "task_id": str(scrape_gma_task.delay())})
            jobs.append({"source": "philstar", "task_id": str(scrape_philstar_task.delay())})
            jobs.append({"source": "rappler", "task_id": str(scrape_rappler_task.delay())})
            jobs.append({"source": "sunstar", "task_id": str(scrape_sunstar_task.delay())})
            jobs.append({"source": "manila_bulletin", "task_id": str(scrape_manila_bulletin_task.delay())})
            report["dry_runs"] = jobs
        except Exception as e:
            report["dry_runs"] = {"error": str(e)}

    return report 