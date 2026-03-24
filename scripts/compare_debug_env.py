#!/usr/bin/env python3
"""
Compare /api/debug/env outputs between two deployments (e.g. local vs Vercel).

Usage:
  python3 scripts/compare_debug_env.py http://localhost:3000 https://your-app.vercel.app

This prints the key fields that commonly cause "wrong date/time" discrepancies:
- Supabase URL host (wrong project vs right project)
- Whether the runtime supports Intl timezone formatting
- Current UTC time as seen by each environment
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request


KEYS = [
    "node_env",
    "next_public_supabase_url_host",
    "next_public_backend_url_host",
    "intl_supports_asia_manila",
    "now_utc",
    "iso_7d_cutoff_utc",
    "articles_last_7d",
    "sentiment_rows_last_7d",
    "coverage_7d",
    "coverage_error",
]


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "accept": "application/json",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": "ph-eye-debug/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def normalize_base(base: str) -> str:
    base = base.strip().rstrip("/")
    if not base.startswith("http://") and not base.startswith("https://"):
        base = "https://" + base
    return base


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("Usage: python3 scripts/compare_debug_env.py <base1> <base2>")
        return 2

    base1 = normalize_base(argv[1])
    base2 = normalize_base(argv[2])
    url1 = base1 + "/api/debug/env"
    url2 = base2 + "/api/debug/env"

    try:
        j1 = fetch_json(url1)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Failed to fetch {url1}: {e}")
        return 1

    try:
        j2 = fetch_json(url2)
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Failed to fetch {url2}: {e}")
        return 1

    def pick(j: dict) -> dict:
        return {k: j.get(k) for k in KEYS}

    print("== debug/env base1 ==")
    print(url1)
    print(json.dumps(pick(j1), indent=2, sort_keys=False))
    print("")
    print("== debug/env base2 ==")
    print(url2)
    print(json.dumps(pick(j2), indent=2, sort_keys=False))
    print("")

    mismatched = [k for k in ("next_public_supabase_url_host", "intl_supports_asia_manila") if j1.get(k) != j2.get(k)]
    if mismatched:
        print("!! Key mismatch(s): " + ", ".join(mismatched))
    else:
        print("OK: Supabase host + Intl Manila support match.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

