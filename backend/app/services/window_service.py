from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def window_bounds(period: str, include_today: bool = True):
    tz_ph = ZoneInfo("Asia/Manila")
    now_local = datetime.now(tz_ph)
    if period == "30d":
        window_days = 30
    else:
        window_days = 7
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
    start_utc = start_local.astimezone(ZoneInfo("UTC"))
    end_utc = end_local.astimezone(ZoneInfo("UTC"))
    return start_utc.isoformat(), end_utc.isoformat()

