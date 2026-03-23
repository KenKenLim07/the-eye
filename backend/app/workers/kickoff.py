from __future__ import annotations

import argparse
import os
from typing import Callable

from app.workers import tasks


def _parse_sources(raw: str | None) -> list[str]:
    if not raw:
        return []
    # Supports "a,b,c" and "a b c"
    parts = [p.strip() for p in raw.replace(" ", ",").split(",")]
    return [p for p in parts if p]


def kickoff_scrapes(sources: list[str]) -> list[dict[str, str]]:
    mapping: dict[str, Callable[[], object]] = {
        "inquirer": tasks.scrape_inquirer_task.delay,
        "gma": tasks.scrape_gma_task.delay,
        "philstar": tasks.scrape_philstar_task.delay,
        "manila_bulletin": tasks.scrape_manila_bulletin_task.delay,
        "rappler": tasks.scrape_rappler_task.delay,
        "sunstar": tasks.scrape_sunstar_task.delay,
        "manila_times": tasks.scrape_manila_times_task.delay,
        # Keep abs_cbn supported for anyone who still uses it.
        "abs_cbn": tasks.scrape_abs_cbn_task.delay,
    }

    jobs: list[dict[str, str]] = []
    for source in sources:
        key = source.strip()
        if not key:
            continue
        fn = mapping.get(key)
        if not fn:
            print(f"[kickoff] skip unknown source: {key}")
            continue
        job = fn()
        jobs.append({"source": key, "task_id": str(job)})
        print(f"[kickoff] queued {key} task_id={job}")
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

