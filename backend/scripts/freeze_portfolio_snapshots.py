#!/usr/bin/env python3
"""
Freeze portfolio analytics snapshots from the latest articles still in Supabase.

Use this once after scraping stops so Trends / Correlation / Entities keep
showing real demo charts without workers or cron.

Requires env:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY

Examples:
  python backend/scripts/freeze_portfolio_snapshots.py
  python backend/scripts/freeze_portfolio_snapshots.py --skip-entities
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _require_env() -> None:
    if not (os.getenv("SUPABASE_URL") or "").strip():
        raise SystemExit("Missing SUPABASE_URL")
    if not (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip():
        raise SystemExit("Missing SUPABASE_SERVICE_ROLE_KEY")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Freeze portfolio analytics snapshots")
    ap.add_argument(
        "--skip-entities",
        action="store_true",
        help="Skip entity rankings (needs spaCy; trends+correlation are enough for a quick freeze)",
    )
    ap.add_argument(
        "--periods",
        default="7d,30d",
        help="Comma-separated periods (default: 7d,30d)",
    )
    args = ap.parse_args(argv[1:])
    _require_env()

    periods = [p.strip() for p in str(args.periods).split(",") if p.strip()]
    for p in periods:
        if p not in {"7d", "30d"}:
            raise SystemExit(f"Invalid period: {p}")

    import trends_snapshot as trends
    import correlation_snapshot as corr

    for period in periods:
        print(f"\n=== Freezing {period} ===")
        t_key = trends.write_snapshot(
            period=period,
            source=None,
            include_today=True,
            anchor_latest=True,
            skip_empty=True,
        )
        print(f"trends: {t_key or '(skipped empty)'}")

        c_key = corr.write_snapshot(
            period=period,
            include_today=True,
            anchor_latest=True,
            skip_empty=True,
        )
        print(f"correlation: {c_key or '(skipped empty)'}")

        if not args.skip_entities:
            import entity_rankings_snapshot as entities

            entities.run_snapshot(period, anchor_latest=True, skip_empty=True)

    print("\nDone. Set NEXT_PUBLIC_ANALYTICS_SOURCE=supabase_snapshots on Vercel.")
    print("Keep analytics_snapshots.yml schedule disabled so cron cannot wipe these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
