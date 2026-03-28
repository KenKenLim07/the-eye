from __future__ import annotations

import logging
from typing import Any, Callable, Mapping

from app.observability.logs import finalize_run, start_run
from app.core.supabase import get_supabase
from app.pipeline.store import insert_articles
from app.workers.ml_tasks import analyze_articles_task, sync_article_sentiment_public_task

logger = logging.getLogger(__name__)


def _is_transient_storage_error(err: str | Exception | None) -> bool:
    if err is None:
        return False
    msg = str(err).lower()
    transient_markers = [
        "temporary failure in name resolution",
        "err_name_not_resolved",
        "name or service not known",
        "connect timeout",
        "read timeout",
        "connection reset",
        "connection refused",
        "service unavailable",
        "502",
        "503",
        "504",
    ]
    return any(marker in msg for marker in transient_markers)


def _handle_storage_result(
    *,
    celery_self: Any,
    task_id: str,
    source_name: str,
    run_log: Mapping[str, Any],
    articles_found: int,
    store_result: Mapping[str, Any],
    retry_base_seconds: int,
) -> bool:
    """Return True when storage is healthy; False/Retry otherwise."""
    storage_error = (store_result or {}).get("error")
    if not storage_error:
        return True

    logger.error("Task %s - %s storage failed: %s", task_id, source_name, storage_error)
    finalize_run(
        run_log["id"],
        status="error",
        articles_scraped=articles_found,
        error_message=f"storage_error: {storage_error}",
    )

    if celery_self.request.retries < celery_self.max_retries and _is_transient_storage_error(storage_error):
        logger.warning(
            "Task %s - %s transient storage error, retrying (%s/%s)",
            task_id,
            source_name,
            celery_self.request.retries + 1,
            celery_self.max_retries,
        )
        raise celery_self.retry(countdown=retry_base_seconds * (2 ** celery_self.request.retries))

    return False


def run_scrape_task(
    *,
    celery_self: Any,
    source_key: str,
    source_name: str,
    task_id: str,
    scrape_fn: Callable[[], Any],
    retry_base_seconds: int = 60,
) -> dict:
    """
    Shared scrape pipeline for Celery tasks:
    - start run log
    - scrape
    - insert_articles
    - enqueue ML analysis
    - finalize run log
    - retry on transient errors

    Keeps return payload shape consistent across sources.
    """
    run_log = start_run(source_key)
    try:
        result = scrape_fn()
        articles = getattr(result, "articles", None) or []
        errors = getattr(result, "errors", None) or []
        performance = getattr(result, "performance", None)
        metadata = getattr(result, "metadata", None)

        logger.info(
            "Task %s - %s scraped %s articles, %s errors",
            task_id,
            source_name,
            len(articles),
            len(errors),
        )
        if errors:
            logger.warning("Task %s - %s scraping errors: %s", task_id, source_name, errors)

        if articles:
            store_result = insert_articles(articles)
            logger.info("Task %s - %s storage result: %s", task_id, source_name, store_result)
            if not _handle_storage_result(
                celery_self=celery_self,
                task_id=task_id,
                source_name=source_name,
                run_log=run_log,
                articles_found=len(articles),
                store_result=store_result,
                retry_base_seconds=retry_base_seconds,
            ):
                return {
                    "ok": False,
                    "task_id": task_id,
                    "error": f"storage_failed: {store_result.get('error')}",
                    "scraping": {
                        "articles_found": len(articles),
                        "errors": errors,
                        "performance": performance,
                        "metadata": metadata,
                    },
                    "storage": store_result,
                }

            inserted_ids = [int(x) for x in (store_result.get("inserted_ids") or []) if x is not None]

            # Also backfill sentiment for duplicate URLs when the article row already exists
            # but sentiment rows are missing (common after transient ML outages).
            missing_existing_ids: list[int] = []
            existing_ids = [int(x) for x in (store_result.get("existing_ids") or []) if x is not None]
            if existing_ids:
                try:
                    sb = get_supabase()
                    analyzed = (
                        sb.table("bias_analysis")
                        .select("article_id")
                        .eq("model_type", "sentiment")
                        .in_("article_id", existing_ids)
                        .execute()
                    )
                    analyzed_set = {int(r.get("article_id")) for r in (analyzed.data or []) if r.get("article_id") is not None}
                    missing_existing_ids = [aid for aid in existing_ids if aid not in analyzed_set]
                except Exception as e:
                    logger.warning("Failed to check existing_ids sentiment coverage (will skip): %s", e)

                # Repair: if bias_analysis exists but the public cache table is missing rows,
                # sync the latest sentiment into `article_sentiment_public` (no ML compute).
                try:
                    pub = (
                        sb.table("article_sentiment_public")
                        .select("article_id")
                        .in_("article_id", existing_ids)
                        .execute()
                    )
                    pub_set = {int(r.get("article_id")) for r in (pub.data or []) if r.get("article_id") is not None}
                    missing_public = [aid for aid in existing_ids if aid not in pub_set]
                    if missing_public:
                        sync_article_sentiment_public_task.apply_async(args=[missing_public], queue="ml")
                except Exception as e:
                    logger.warning("Failed to repair article_sentiment_public for existing_ids (skip): %s", e)

            analyze_ids = inserted_ids + missing_existing_ids
            if analyze_ids:
                # Always target the ML queue; the ML worker runs with `-Q ml`.
                analyze_articles_task.apply_async(args=[analyze_ids], queue="ml")

            finalize_run(run_log["id"], status="success", articles_scraped=len(articles))
            return {
                "ok": True,
                "task_id": task_id,
                "scraping": {
                    "articles_found": len(articles),
                    "errors": errors,
                    "performance": performance,
                    "metadata": metadata,
                },
                "storage": store_result,
            }

        # No articles case
        finalize_run(run_log["id"], status="success", articles_scraped=0)
        return {
            "ok": True,
            "task_id": task_id,
            "scraping": {
                "articles_found": 0,
                "errors": errors,
                "performance": performance,
                "metadata": metadata,
            },
            "storage": {"checked": 0, "skipped": 0, "inserted": 0},
        }

    except Exception as e:
        error_msg = f"{source_name} task {task_id} failed: {str(e)}"
        logger.error(error_msg)

        # best-effort: include article count if result exists
        articles_scraped = 0
        if "result" in locals():
            try:
                articles_scraped = len(getattr(locals()["result"], "articles", None) or [])
            except Exception:
                articles_scraped = 0

        finalize_run(run_log["id"], status="error", articles_scraped=articles_scraped, error_message=str(e))

        if celery_self.request.retries < celery_self.max_retries:
            logger.info(
                "Task %s - %s retrying (%s/%s)",
                task_id,
                source_name,
                celery_self.request.retries + 1,
                celery_self.max_retries,
            )
            raise celery_self.retry(countdown=retry_base_seconds * (2 ** celery_self.request.retries))

        return {"ok": False, "task_id": task_id, "error": error_msg, "retries_exhausted": True}
