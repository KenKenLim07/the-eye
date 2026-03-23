from __future__ import annotations

import argparse
import os
import time

from app.workers.celery_app import celery


def _parse_sources(raw: str | None) -> list[str]:
    if not raw:
        return []
    # Supports "a,b,c" and "a b c"
    parts = [p.strip() for p in raw.replace(" ", ",").split(",")]
    return [p for p in parts if p]


def kickoff_scrapes(sources: list[str]) -> list[dict[str, str]]:
    # Use `celery.send_task(...)` (instead of `task.delay()`) so this script always
    # publishes to the same broker/backend configured in `app.workers.celery_app`,
    # even when run outside a Celery worker process.
    mapping: dict[str, str] = {
        "inquirer": "app.workers.tasks.scrape_inquirer_task",
        "gma": "app.workers.tasks.scrape_gma_task",
        "philstar": "app.workers.tasks.scrape_philstar_task",
        "manila_bulletin": "app.workers.tasks.scrape_manila_bulletin_task",
        "rappler": "app.workers.tasks.scrape_rappler_task",
        "sunstar": "app.workers.tasks.scrape_sunstar_task",
        "manila_times": "app.workers.tasks.scrape_manila_times_task",
    }

    jobs: list[dict[str, str]] = []
    for source in sources:
        key = source.strip()
        if not key:
            continue
        task_name = mapping.get(key)
        if not task_name:
            print(f"[kickoff] skip unknown source: {key}")
            continue
        # Retry publishing in case Redis is still coming up.
        last_err: Exception | None = None
        for attempt in range(1, 11):
            try:
                async_result = celery.send_task(task_name)
                task_id = str(async_result.id)
                jobs.append({"source": key, "task_id": task_id})
                print(f"[kickoff] queued {key} task_id={task_id}")
                last_err = None
                break
            except Exception as e:
                last_err = e
                sleep_s = min(5, attempt)
                print(f"[kickoff] publish failed (source={key}, attempt={attempt}/10): {e} (sleep {sleep_s}s)")
                time.sleep(sleep_s)

        if last_err is not None:
            raise RuntimeError(f"Failed to publish task for source={key}: {last_err}") from last_err
    return jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue one-time scrape jobs on startup.")
    parser.add_argument(
        "--sources",
        default="",
        help="Comma-separated sources (overrides SCRAPE_ON_STARTUP_SOURCES).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if SCRAPE_ON_STARTUP is not true.",
    )
    args = parser.parse_args()

    enabled = os.getenv("SCRAPE_ON_STARTUP", "false").strip().lower() == "true"
    if not enabled and not args.force:
        print("[kickoff] SCRAPE_ON_STARTUP is not true; skipping")
        return 0

    sources = _parse_sources(args.sources) or _parse_sources(os.getenv("SCRAPE_ON_STARTUP_SOURCES", ""))
    if not sources:
        print("[kickoff] no sources provided; nothing to do")
        return 0

    kickoff_scrapes(sources)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
