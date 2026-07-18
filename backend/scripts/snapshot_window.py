"""Shared date-window helpers for analytics snapshot writers.

Portfolio / demo mode uses --anchor-latest so the window ends at the newest
article still in Supabase, not "today". That keeps Trends / Correlation /
Entities populated after scraping stops.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

TZ_PH = ZoneInfo("Asia/Manila")
TZ_UTC = ZoneInfo("UTC")


def period_days(period: str) -> int:
    return 30 if period == "30d" else 7


def fetch_latest_published_at(sb) -> Optional[datetime]:
    """Return the newest articles.published_at as an aware UTC datetime, or None."""
    res = (
        sb.table("articles")
        .select("published_at")
        .order("published_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    raw = (rows[0].get("published_at") or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_UTC)
        return dt.astimezone(TZ_UTC)
    except Exception:
        return None


def window_bounds(
    period: str,
    include_today: bool = True,
    *,
    anchor_end: Optional[datetime] = None,
) -> Tuple[str, str]:
    """
    Return (start_utc_iso, end_utc_iso) for the given period.

    If anchor_end is set (typically max(published_at)), the window ends on that
    Manila calendar day instead of "now".
    """
    window_days = period_days(period)

    if anchor_end is not None:
        end_local = anchor_end.astimezone(TZ_PH)
        end_local = end_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (end_local - timedelta(days=window_days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        now_local = datetime.now(TZ_PH)
        if include_today:
            end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_local = (now_local - timedelta(days=window_days - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            end_local = (now_local - timedelta(days=1)).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            start_local = (end_local - timedelta(days=window_days - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    return start_local.astimezone(TZ_UTC).isoformat(), end_local.astimezone(TZ_UTC).isoformat()


def resolve_window(
    sb,
    period: str,
    include_today: bool = True,
    *,
    anchor_latest: bool = False,
) -> Tuple[str, str, Optional[str]]:
    """
    Resolve snapshot window. Returns (start_iso, end_iso, anchor_note).

    When anchor_latest=True and no articles exist, falls back to calendar "now".
    """
    anchor_end: Optional[datetime] = None
    note: Optional[str] = None
    if anchor_latest:
        anchor_end = fetch_latest_published_at(sb)
        if anchor_end is not None:
            note = f"anchored to latest article published_at={anchor_end.isoformat()}"
        else:
            note = "anchor-latest requested but no articles found; using calendar now"
    start_iso, end_iso = window_bounds(period, include_today=include_today, anchor_end=anchor_end)
    return start_iso, end_iso, note
