#!/usr/bin/env python3
"""
Scrape Catch-Up Backfill (Ingest-Only)

Purpose:
- When your laptop/containers were OFF (school/vacation), scheduled scrapes didn't run.
- This script re-runs scrapers sequentially with a higher cap to ingest missed articles
  from the last N days, while staying "polite" (low concurrency + optional human delays).
- It only writes to `articles` via `insert_articles(...)`. It does NOT queue ML tasks.

Run (recommended inside Docker):
  ./scrape_backfill.sh 7 80
  # then (optional) queue ML for recent missing sentiment:
  ./backfill.sh 7 200
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo


PH_TZ = ZoneInfo("Asia/Manila")
INQUIRER_CATCHUP_CAP = 15

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _clamp_int(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def _as_utc_dt(value: Any) -> datetime:
    """
    Best-effort parse of published_at for window filtering.
    - Supports ISO-8601 strings and RFC 2822 (RSS-style) timestamps.
    - If tz is missing, assume Asia/Manila (matches store normalization behavior).
    """
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value or "").strip()
        if not s:
            return datetime.now(timezone.utc)
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = parsedate_to_datetime(s)
            except Exception:
                return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PH_TZ)
    return dt.astimezone(timezone.utc)


def _looks_like_block_error(msg: str) -> bool:
    m = (msg or "").lower()
    markers = [
        "429",
        "too many requests",
        "rate limit",
        "403",
        "forbidden",
        "access denied",
        "captcha",
        "akamai",
        "blocked",
        "timeout",
        "err_name_not_resolved",
        "temporary failure in name resolution",
    ]
    return any(x in m for x in markers)


def _configure_env_for_catchup(*, days: int) -> None:
    """
    Set catch-up friendly defaults for this *process*.

    Important: some scrapers read env flags at import time, so we set these BEFORE
    importing scraper modules.
    """
    # Encourage existing scrapers to use their human-delay paths when supported.
    os.environ.setdefault("USE_HUMAN_DELAY", "1")

    # Prefer RSS discovery for Inquirer when available (lowest risk for discovery).
    os.environ.setdefault("INQUIRER_RSS_DISCOVERY", "1")
    os.environ["INQUIRER_RSS_MAX_AGE_H"] = str(max(24, days * 24))
    # Reduce Playwright load for catch-up runs (still falls back when HTTP parsing is insufficient).
    os.environ.setdefault("INQUIRER_HTTP_FASTPATH", "1")

    # ABS-CBN RSS window: widen to cover the catch-up range.
    os.environ["ABS_CBN_RSS_MAX_AGE_H"] = str(max(24, days * 24))


@dataclass
class SourceRunSummary:
    source_key: str
    ok: bool
    scraped: int
    scraped_in_window: int
    skipped_old: int
    inserted: int
    skipped: int
    checked: int
    errors: list[str]
    duration_s: float


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Scrape catch-up backfill (ingest-only, sequential).")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7, max: 7)")
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=80,
        help="Max articles to attempt per source scrape run (default: 80)",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="",
        help="Optional comma-separated source keys (e.g. 'gma,inquirer,rappler'). Default: all.",
    )
    args = parser.parse_args(argv[1:])

    days = _clamp_int(args.days, 1, 7)
    max_per_source = _clamp_int(args.max_per_source, 1, 200)

    _configure_env_for_catchup(days=days)

    # Allow running from repo root while importing backend package.
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

    try:
        from app.pipeline.store import insert_articles  # noqa: E402
        from app.scrapers.abs_cbn import ABSCBNScraper  # noqa: E402
        from app.scrapers.gma import GMAScraper  # noqa: E402
        from app.scrapers.inquirer import InquirerScraper  # noqa: E402
        from app.scrapers.manila_bulletin import ManilaBulletinScraper  # noqa: E402
        from app.scrapers.manila_times import ManilaTimesScraper  # noqa: E402
        from app.scrapers.philstar import PhilStarScraper  # noqa: E402
        from app.scrapers.rappler import RapplerScraper  # noqa: E402
        from app.scrapers.sunstar import SunstarScraper  # noqa: E402
    except ModuleNotFoundError as e:
        missing = getattr(e, "name", None) or str(e)
        raise SystemExit(
            "\n".join(
                [
                    f"Missing Python dependency: {missing}",
                    "",
                    "This script is intended to run inside Docker (recommended):",
                    "  ./scrape_backfill.sh 7 80",
                    "",
                ]
            )
        ) from e

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    def _run_inquirer() -> Any:
        effective_max = min(max_per_source, INQUIRER_CATCHUP_CAP)
        prev = os.environ.get("INQUIRER_STOP_ON_BLOCK")
        os.environ["INQUIRER_STOP_ON_BLOCK"] = "1"
        try:
            return InquirerScraper().scrape_latest(max_articles=effective_max)
        finally:
            if prev is None:
                os.environ.pop("INQUIRER_STOP_ON_BLOCK", None)
            else:
                os.environ["INQUIRER_STOP_ON_BLOCK"] = prev

    all_sources: dict[str, Callable[[], Any]] = {
        "gma": lambda: GMAScraper().scrape_latest(max_articles=max_per_source),
        "abs_cbn": lambda: ABSCBNScraper().scrape_latest(max_articles=max_per_source),
        "inquirer": _run_inquirer,
        "philstar": lambda: PhilStarScraper().scrape_latest(max_articles=max_per_source),
        "manila_bulletin": lambda: ManilaBulletinScraper().scrape_latest(max_articles=max_per_source),
        "rappler": lambda: RapplerScraper().scrape_latest(max_articles=max_per_source),
        "sunstar": lambda: SunstarScraper().scrape_all(max_articles=max_per_source),
        "manila_times": lambda: ManilaTimesScraper().scrape_latest(max_articles=max_per_source),
    }

    if args.sources.strip():
        requested = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
        # allow a few aliases
        alias = {"mb": "manila_bulletin", "mt": "manila_times", "abscbn": "abs_cbn", "abs-cbn": "abs_cbn"}
        sources = [alias.get(s, s) for s in requested]
        unknown = [s for s in sources if s not in all_sources]
        if unknown:
            raise SystemExit(f"Unknown sources: {unknown}. Valid: {sorted(all_sources.keys())}")
    else:
        sources = list(all_sources.keys())

    logger.info("Scrape catch-up: days=%s cutoff_utc=%s max_per_source=%s sources=%s", days, cutoff.isoformat(), max_per_source, sources)

    summaries: list[SourceRunSummary] = []
    for idx, source_key in enumerate(sources):
        logger.info("=== %s ===", source_key)
        t0 = time.time()
        scraped_articles: list[Any] = []
        errors: list[str] = []
        try:
            result = all_sources[source_key]()
            scraped_articles = getattr(result, "articles", None) or []
            errors = getattr(result, "errors", None) or []
        except Exception as e:
            errors = [str(e)]

        # Window filter
        kept: list[Any] = []
        skipped_old = 0
        for a in scraped_articles:
            try:
                published_at = getattr(a, "published_at", None)
                dt = _as_utc_dt(published_at)
                if dt < cutoff:
                    skipped_old += 1
                    continue
            except Exception:
                # If we cannot parse published_at, keep it (best effort).
                pass
            kept.append(a)

        store = {"checked": 0, "skipped": 0, "inserted": 0}
        ok = True
        try:
            if kept:
                store = insert_articles(kept) or store
        except Exception as e:
            ok = False
            errors.append(f"store:{e}")

        duration_s = round(time.time() - t0, 2)
        checked = int(store.get("checked") or 0)
        skipped = int(store.get("skipped") or 0)
        inserted = int(store.get("inserted") or 0)

        summaries.append(
            SourceRunSummary(
                source_key=source_key,
                ok=ok and not any(_looks_like_block_error(e) for e in errors),
                scraped=len(scraped_articles),
                scraped_in_window=len(kept),
                skipped_old=skipped_old,
                inserted=inserted,
                skipped=skipped,
                checked=checked,
                errors=[str(e) for e in errors],
                duration_s=duration_s,
            )
        )

        logger.info(
            "%s: scraped=%s in_window=%s skipped_old=%s inserted=%s skipped=%s checked=%s duration_s=%s",
            source_key,
            len(scraped_articles),
            len(kept),
            skipped_old,
            inserted,
            skipped,
            checked,
            duration_s,
        )

        is_last = idx == (len(sources) - 1)
        if errors and any(_looks_like_block_error(e) for e in errors):
            # Backoff a bit before moving to the next source.
            sleep_s = 45.0
            logger.warning("%s: block-ish errors detected; backing off for %.0fs", source_key, sleep_s)
            if not is_last:
                time.sleep(sleep_s)

        # Small jitter between sources to avoid bursty patterns.
        if not is_last:
            time.sleep(1.5)

    print(json.dumps([asdict(s) for s in summaries], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
