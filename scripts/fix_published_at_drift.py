#!/usr/bin/env python3
"""
Fix `articles.published_at` drift caused by bad local clocks / fallback timestamps.

Problem:
- Some scrapers produce `published_at` strings without a timezone offset (e.g. `2026-03-23T21:42:51`).
- Supabase/Postgres will interpret timezone-less timestamps as UTC, even when the source time was
  actually Asia/Manila. That creates a consistent ~+8 hour skew that can push articles into the
  wrong calendar day in Trends.
- If the host clock was wrong during scraping, some fallback `published_at` values can also be
  in the *future* relative to `inserted_at`.

Approach:
- Scan recent articles (by `inserted_at`) and classify suspicious rows:
  1) Timezone skew: `published_at` is ~+8h ahead of `inserted_at` (default window 6..10h).
     Fix by shifting `published_at` back by 8 hours.
  2) True future drift: `published_at` is far ahead of `inserted_at` (default >24h).
     Fix by setting `published_at = inserted_at`.
  3) Missing/invalid `published_at`: set `published_at = inserted_at`.

Run inside Docker (recommended):
  docker compose exec worker_ml python /app/scripts/fix_published_at_drift.py --days 7 --dry-run
  docker compose exec worker_ml python /app/scripts/fix_published_at_drift.py --days 7 --apply
"""

from __future__ import annotations

import os
import sys
import time
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

# Allow running from repo root while importing backend package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

try:
    from app.core.supabase import get_supabase  # noqa: E402
except ModuleNotFoundError as e:
    missing = getattr(e, "name", None) or str(e)
    raise SystemExit(
        "\n".join(
            [
                f"Missing Python dependency: {missing}",
                "",
                "Run this script inside Docker (recommended):",
                "  docker compose exec worker_ml python /app/scripts/fix_published_at_drift.py --days 7 --dry-run",
                "",
                "Or locally in a virtualenv:",
                "  python3 -m venv .venv && source .venv/bin/activate",
                "  pip install -r backend/requirements.txt",
                "  python3 scripts/fix_published_at_drift.py --days 7 --dry-run",
                "",
            ]
        )
    ) from e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
PH_TZ = ZoneInfo("Asia/Manila")


def _extract_url_date(url: str | None) -> datetime.date | None:
    """
    Extract a YYYY/MM/DD date from URLs like:
      https://www.manilatimes.net/2026/03/23/news/...
    """
    if not url:
        return None
    try:
        m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", str(url))
        if not m:
            return None
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d).date()
    except Exception:
        return None


def _parse_iso_utc(dt: str | None) -> datetime | None:
    """
    Parse a Supabase timestamp into an aware UTC datetime.

    - If the value includes an offset / Z, honor it.
    - If it has no timezone, assume UTC (this matches how `timestamptz` inputs are
      interpreted by Postgres when the offset is missing).
    """
    if dt is None:
        return None
    try:
        if isinstance(dt, datetime):
            parsed = dt
        else:
            s = str(dt).strip()
            if not s:
                return None

            # Normalize common PostgREST / Supabase timestamp shapes into something `fromisoformat` accepts.
            # - allow trailing Z
            # - truncate fractional seconds to microseconds (<= 6 digits)
            # - normalize offsets like +0800 -> +08:00
            s = s.replace("Z", "+00:00")

            m = re.match(
                r"^(?P<ymd>\d{4}-\d{2}-\d{2})"
                r"(?:[T\s](?P<hms>\d{2}:\d{2}:\d{2}))?"
                r"(?P<frac>\.\d+)?"
                r"(?P<tz>(?:[+-]\d{2}:?\d{2})|(?:[+-]\d{2})|(?:\+00:00))?$",
                s,
            )
            if m:
                ymd = m.group("ymd")
                hms = m.group("hms") or "00:00:00"
                frac = m.group("frac") or ""
                tz = m.group("tz") or ""

                if frac:
                    digits = frac[1:]
                    if len(digits) > 6:
                        frac = "." + digits[:6]

                if tz and re.fullmatch(r"[+-]\d{4}", tz):
                    tz = tz[:3] + ":" + tz[3:]
                elif tz and re.fullmatch(r"[+-]\d{2}$", tz):
                    tz = tz + ":00"

                s = f"{ymd}T{hms}{frac}{tz}"

            parsed = datetime.fromisoformat(s)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _chunked(items: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


@dataclass(frozen=True)
class DriftRow:
    id: int
    source: str
    url: str | None
    published_at: str | None
    inserted_at: str | None
    reason: str
    drift_hours: float | None
    fix_action: str | None


def _fetch_recent_articles(since_iso: str, page_size: int = 1000) -> list[dict]:
    sb = get_supabase()
    out: list[dict] = []
    offset = 0
    while True:
        res = (
            sb.table("articles")
            .select("id,source,url,published_at,inserted_at")
            .gte("inserted_at", since_iso)
            .order("inserted_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break
        out.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return out


def find_published_at_drift(*, days: int, threshold_hours: float) -> list[DriftRow]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = _fetch_recent_articles(since)
    if not rows:
        return []

    drift: list[DriftRow] = []
    for r in rows:
        rid = r.get("id")
        if rid is None:
            continue
        try:
            article_id = int(rid)
        except Exception:
            continue

        published_at = r.get("published_at")
        inserted_at = r.get("inserted_at")
        pub_dt = _parse_iso_utc(published_at)
        ins_dt = _parse_iso_utc(inserted_at)

        if ins_dt is None:
            continue  # can't safely fix

        if pub_dt is None:
            drift.append(
                DriftRow(
                    id=article_id,
                    source=str(r.get("source") or ""),
                    url=r.get("url"),
                    published_at=published_at,
                    inserted_at=inserted_at,
                    reason="published_at_missing_or_invalid",
                    drift_hours=None,
                    fix_action="set_to_inserted_at",
                )
            )
            continue

        delta_h = (pub_dt - ins_dt).total_seconds() / 3600.0

        # URL date heuristic:
        # Some PH sources embed the publish date in the URL path. If the stored published_at,
        # when viewed in Asia/Manila, is off by a day but shifting by -8h matches the URL date,
        # it's a strong signal that a PH-local timestamp was stored as UTC.
        try:
            source = str(r.get("source") or "")
            if source in {"Manila Times", "Inquirer", "GMA", "Philstar", "Sunstar", "Manila Bulletin", "Rappler"}:
                url_date = _extract_url_date(r.get("url"))
                if url_date is not None:
                    pub_mnl_date = pub_dt.astimezone(PH_TZ).date()
                    shifted_mnl_date = (pub_dt - timedelta(hours=8)).astimezone(PH_TZ).date()
                    if pub_mnl_date != url_date and shifted_mnl_date == url_date:
                        drift.append(
                            DriftRow(
                                id=article_id,
                                source=source,
                                url=r.get("url"),
                                published_at=published_at,
                                inserted_at=inserted_at,
                                reason="url_date_mismatch_suggests_missing_tz",
                                drift_hours=delta_h,
                                fix_action="shift_minus_8h",
                            )
                        )
                        continue
        except Exception:
            pass

        # Most PH sources publish in Asia/Manila. A very common failure mode is inserting a local
        # timestamp without an offset, which Postgres treats as UTC, resulting in ~+8h skew.
        if 6.0 <= delta_h <= 10.0:
            drift.append(
                DriftRow(
                    id=article_id,
                    source=str(r.get("source") or ""),
                    url=r.get("url"),
                    published_at=published_at,
                    inserted_at=inserted_at,
                    reason="likely_manila_timestamp_missing_tz",
                    drift_hours=delta_h,
                    fix_action="shift_minus_8h",
                )
            )
            continue

        # True drift: published_at is significantly *after* insertion (clock issues / bad parse).
        if delta_h > max(24.0, threshold_hours):
            drift.append(
                DriftRow(
                    id=article_id,
                    source=str(r.get("source") or ""),
                    url=r.get("url"),
                    published_at=published_at,
                    inserted_at=inserted_at,
                    reason=f"published_at_after_inserted_at_by_{max(24.0, threshold_hours)}h+",
                    drift_hours=delta_h,
                    fix_action="set_to_inserted_at",
                )
            )

    return drift


def apply_fix(rows: list[DriftRow]) -> int:
    if not rows:
        return 0

    sb = get_supabase()
    fixed = 0
    for idx, r in enumerate(rows, start=1):
        ins_dt = _parse_iso_utc(r.inserted_at)
        pub_dt = _parse_iso_utc(r.published_at)
        if ins_dt is None:
            continue

        if r.fix_action == "shift_minus_8h" and pub_dt is not None:
            new_pub = (pub_dt - timedelta(hours=8)).astimezone(timezone.utc).isoformat()
        else:
            new_pub = ins_dt.astimezone(timezone.utc).isoformat()

        try:
            # Use UPDATE to avoid NOT NULL constraints being checked on a partial upsert/insert.
            sb.table("articles").update({"published_at": new_pub}).eq("id", r.id).execute()
            fixed += 1
            if idx % 50 == 0:
                logger.info("Progress: fixed %s/%s ...", fixed, len(rows))
            # Be gentle to PostgREST to avoid rate-limits.
            time.sleep(0.03)
        except Exception as e:
            logger.warning("Failed to update article_id=%s: %s", r.id, e)
    return fixed


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fix future-dated articles.published_at using inserted_at")
    parser.add_argument("--days", type=int, default=7, help="Look back by inserted_at (default: 7)")
    parser.add_argument("--threshold-hours", type=float, default=2.0, help="Flag if published_at is this many hours after inserted_at (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Print the rows that would be fixed")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (sets published_at = inserted_at)")
    args = parser.parse_args(argv[1:])

    if not args.dry_run and not args.apply:
        args.dry_run = True

    logger.info("Scanning last %s days for published_at drift...", args.days)
    rows = find_published_at_drift(days=args.days, threshold_hours=args.threshold_hours)
    logger.info("Found %s suspicious rows.", len(rows))

    if args.dry_run:
        action_counts: dict[str, int] = {}
        for r in rows:
            k = r.fix_action or "unknown"
            action_counts[k] = action_counts.get(k, 0) + 1
        if action_counts:
            logger.info("Planned fixes: %s", action_counts)

        for i, r in enumerate(rows[:20], start=1):
            drift = f"{r.drift_hours:.2f}h" if isinstance(r.drift_hours, float) else "n/a"
            logger.info(
                "%02d) id=%s source=%s drift=%s action=%s reason=%s published_at=%s inserted_at=%s url=%s",
                i,
                r.id,
                r.source,
                drift,
                r.fix_action,
                r.reason,
                r.published_at,
                r.inserted_at,
                r.url,
            )
        if len(rows) > 20:
            logger.info("... and %s more", len(rows) - 20)

    if args.apply:
        fixed = apply_fix(rows)
        logger.info("Fixed %s rows.", fixed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
