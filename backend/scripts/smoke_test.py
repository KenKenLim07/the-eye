#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _sleep_ms(ms: int) -> None:
    time.sleep(ms / 1000)


def _request_json(url: str, timeout_sec: int, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout_sec) as res:
        raw = res.read().decode("utf-8")
        if not raw:
            return None
        return json.loads(raw)


def _with_retry(name: str, retries: int, retry_delay_ms: int, fn):
    attempt = 0
    while True:
        try:
            attempt += 1
            return fn()
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
            if attempt >= retries:
                raise
            print(f"[RETRY] {name} (attempt {attempt} failed; retrying in {retry_delay_ms}ms): {e}")
            _sleep_ms(retry_delay_ms)


def _assert_ok(name: str, retries: int, retry_delay_ms: int, fn) -> None:
    print(f"[SMOKE] {name}")
    res = _with_retry(name, retries, retry_delay_ms, fn)
    if res is None:
        raise RuntimeError(f"Smoke check failed: {name} (null response)")
    print(f"[OK] {name}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="PH VibeCheck AI backend smoke test (cross-platform).")
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("BACKEND_URL", "http://localhost:8000"),
        help="Backend base URL (default: env BACKEND_URL or http://localhost:8000).",
    )
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--retry-delay-ms", type=int, default=750)
    args = parser.parse_args(argv)

    base = args.backend_url.rstrip("/")
    retries = args.retries
    retry_delay_ms = args.retry_delay_ms

    _assert_ok("GET /health", retries, retry_delay_ms, lambda: _request_json(f"{base}/health", timeout_sec=30))
    _assert_ok(
        "GET /articles/home-optimized",
        retries,
        retry_delay_ms,
        lambda: _request_json(f"{base}/articles/home-optimized?limit_per_source=2&refresh=true", timeout_sec=60),
    )
    _assert_ok(
        "GET /ml/trends",
        retries,
        retry_delay_ms,
        lambda: _request_json(f"{base}/ml/trends?period=7d&include_today=true&refresh=true", timeout_sec=180),
    )
    _assert_ok(
        "GET /ml/correlation",
        retries,
        retry_delay_ms,
        lambda: _request_json(f"{base}/ml/correlation?period=7d&include_today=true&refresh=true", timeout_sec=180),
    )
    _assert_ok(
        "GET /ml/entities/top",
        retries,
        retry_delay_ms,
        lambda: _request_json(f"{base}/ml/entities/top?period=7d&include_today=true&refresh=true", timeout_sec=180),
    )

    print("[DONE] smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
