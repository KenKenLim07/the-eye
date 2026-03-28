from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


_URL_HINT_RE = re.compile(r"(graphql|api|json)", re.IGNORECASE)


def install_json_response_logger(page, *, enabled: bool, max_items: int = 30) -> Callable[[], List[Dict[str, Any]]]:
    """
    Sync-Playwright helper: collect JSON-ish responses for endpoint discovery.

    Usage:
        dump = install_json_response_logger(page, enabled=True, max_items=30)
        ... navigate ...
        rows = dump()
    """
    if not enabled:
        return lambda: []

    captured: List[Dict[str, Any]] = []

    def _on_response(resp):
        try:
            if len(captured) >= max_items:
                return
            url = resp.url or ""
            req = getattr(resp, "request", None)
            resource_type = None
            try:
                if req is not None:
                    resource_type = getattr(req, "resource_type", None)
            except Exception:
                resource_type = None
            headers = resp.headers or {}
            ctype = (headers.get("content-type") or headers.get("Content-Type") or "").lower()
            is_json = "application/json" in ctype
            hinted = bool(_URL_HINT_RE.search(url))
            is_xhr = (resource_type in {"xhr", "fetch"})
            if not (is_json or hinted or is_xhr):
                return
            captured.append(
                {
                    "url": url,
                    "status": getattr(resp, "status", None),
                    "content_type": ctype or None,
                    "resource_type": resource_type,
                    "_resp": resp,  # keep for optional sample_keys in dump()
                }
            )
        except Exception:
            return

    try:
        page.on("response", _on_response)
    except Exception as e:
        logger.debug("Failed to attach response logger: %s", e)
        return lambda: []

    def _dump() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in captured:
            row = {
                "url": item.get("url"),
                "status": item.get("status"),
                "content_type": item.get("content_type"),
                "resource_type": item.get("resource_type"),
            }
            out.append(row)

        # Enrich first few with sample keys (best-effort)
        for row, item in zip(out[:3], captured[:3]):
            try:
                resp = item.get("_resp")
                if resp is None:
                    continue
                data = resp.json()
                if isinstance(data, dict):
                    row["sample_keys"] = list(data.keys())[:25]
                elif isinstance(data, list) and data and isinstance(data[0], dict):
                    row["sample_keys"] = list(data[0].keys())[:25]
            except Exception:
                continue

        return out

    return _dump
