#!/usr/bin/env python3
"""
ABS-CBN OneDomain API canary.

Purpose:
- Detect if the public list endpoints we rely on are still reachable
- Validate the JSON shape and required fields our scraper depends on

This script is intentionally self-contained (no app imports) so it can run:
- locally: `python backend/scripts/abs_cbn_api_canary.py`
- in Docker: `docker compose exec worker python backend/scripts/abs_cbn_api_canary.py`
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple

import requests


DEFAULT_LIST_URLS = [
    "https://od2-content-api.abs-cbn.com/prod/list/id/news?limit=60&offset=0",
    "https://od2-content-api.abs-cbn.com/prod/list/id/business?limit=60&offset=0",
    "https://od2-content-api.abs-cbn.com/prod/list/id/technology?limit=60&offset=0",
    "https://od2-content-api.abs-cbn.com/prod/list/id/sports?limit=60&offset=0",
    "https://od2-content-api.abs-cbn.com/prod/list/id/entertainment?limit=60&offset=0",
]


def _env_list_urls() -> List[str]:
    raw = os.getenv("ABS_CBN_API_LIST_URLS", "").strip()
    if not raw:
        return DEFAULT_LIST_URLS
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_slug(item: Dict[str, Any]) -> str | None:
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    slug = (
        item.get("slugline_url")
        or item.get("sluglineUrl")
        or extra.get("slugline_url")
        or extra.get("sluglineUrl")
    )
    return slug if isinstance(slug, str) and slug.strip() else None


def _check_endpoint(
    url: str,
    *,
    sample_items: int,
    min_body_chars: int,
    timeout_s: int,
) -> Tuple[bool, Dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://news.abs-cbn.com/",
    }

    out: Dict[str, Any] = {"url": url}

    try:
        r = requests.get(url, headers=headers, timeout=timeout_s)
    except Exception as e:
        out["ok"] = False
        out["error"] = f"request_failed: {e}"
        return False, out

    out["status"] = r.status_code
    out["content_type"] = r.headers.get("content-type")

    if r.status_code != 200:
        out["ok"] = False
        out["error"] = "non_200"
        return False, out

    try:
        payload = r.json()
    except Exception as e:
        out["ok"] = False
        out["error"] = f"json_parse_failed: {e}"
        out["text_prefix"] = r.text[:200]
        return False, out

    if not isinstance(payload, dict):
        out["ok"] = False
        out["error"] = "payload_not_object"
        out["payload_type"] = type(payload).__name__
        return False, out

    items = payload.get("listItem")
    if not isinstance(items, list):
        out["ok"] = False
        out["error"] = "missing_listItem"
        out["payload_keys"] = sorted(payload.keys())[:50]
        return False, out

    out["items_count"] = len(items)
    sample = [it for it in items if isinstance(it, dict)][:sample_items]
    out["sample_count"] = len(sample)
    if not sample:
        out["ok"] = False
        out["error"] = "no_object_items"
        return False, out

    has_body = 0
    has_slug = 0
    body_min_ok = 0
    first_keys = sorted(sample[0].keys())[:60]
    first_extra_keys = []
    if isinstance(sample[0].get("extra"), dict):
        first_extra_keys = sorted(sample[0]["extra"].keys())[:60]

    for it in sample:
        body_html = it.get("body_html")
        if isinstance(body_html, str) and body_html.strip():
            has_body += 1
            if len(body_html) >= min_body_chars:
                body_min_ok += 1
        if _extract_slug(it) is not None:
            has_slug += 1

    out["sample_has_body_html"] = has_body
    out["sample_body_html_min_ok"] = body_min_ok
    out["sample_has_slugline_url"] = has_slug
    out["first_item_keys"] = first_keys
    if first_extra_keys:
        out["first_extra_keys"] = first_extra_keys

    # What our scraper needs (minimum viable)
    ok = has_slug > 0 and body_min_ok > 0
    out["ok"] = ok
    if not ok:
        out["error"] = "missing_required_fields"
    return ok, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-items", type=int, default=5)
    ap.add_argument("--min-body-chars", type=int, default=int(os.getenv("ABS_CBN_API_MIN_BODY_CHARS", "600") or "600"))
    ap.add_argument("--timeout-s", type=int, default=20)
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args()

    urls = _env_list_urls()
    results: List[Dict[str, Any]] = []
    all_ok = True

    for u in urls:
        ok, info = _check_endpoint(
            u,
            sample_items=max(1, args.sample_items),
            min_body_chars=max(0, args.min_body_chars),
            timeout_s=max(1, args.timeout_s),
        )
        results.append(info)
        if not ok:
            all_ok = False

    if args.json:
        print(json.dumps({"ok": all_ok, "results": results}, indent=2, sort_keys=True))
    else:
        status = "OK" if all_ok else "FAIL"
        print(f"ABS-CBN API Canary: {status} (endpoints={len(results)})")
        for r in results:
            ok = "OK" if r.get("ok") else "FAIL"
            print(
                f"- {ok} status={r.get('status')} items={r.get('items_count')} "
                f"sample_body_min_ok={r.get('sample_body_html_min_ok')} sample_slug={r.get('sample_has_slugline_url')} "
                f"url={r.get('url')}"
            )
            if not r.get("ok"):
                print(f"  error={r.get('error')}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

