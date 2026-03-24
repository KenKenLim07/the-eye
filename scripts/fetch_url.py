#!/usr/bin/env python3
"""
Fetch a URL and print status + relevant caching headers + first bytes of body.

Usage:
  python3 scripts/fetch_url.py https://ph-eye.vercel.app/api/articles?pageSize=1
"""

from __future__ import annotations

import sys
import urllib.request


SHOW_HEADERS = {
    "cache-control",
    "age",
    "date",
    "etag",
    "last-modified",
    "x-vercel-cache",
    "x-vercel-id",
    "x-powered-by",
    "content-type",
}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2

    url = argv[1]
    req = urllib.request.Request(
        url,
        headers={
            "accept": "*/*",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": "ph-eye-debug/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        print("URL:", url)
        print("Status:", resp.status)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        print("Headers:")
        for k in sorted(SHOW_HEADERS):
            if k in headers:
                print(f"  {k}: {headers[k]}")
        body = resp.read()

    preview = body[:4000]
    try:
        text = preview.decode("utf-8", errors="replace")
    except Exception:
        text = repr(preview)
    print("")
    print("Body (first 4KB):")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

