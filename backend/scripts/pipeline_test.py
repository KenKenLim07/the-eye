#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def _assert_ok(name: str, fn):
    print(f"[PIPELINE] {name}")
    res = fn()
    if res is None:
        raise RuntimeError(f"Pipeline check failed: {name} (null response)")
    print(f"[OK] {name}")
    return res


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="PH Eye scrape->verify pipeline test (cross-platform).")
    parser.add_argument(
        "--backend-url",
        default=os.environ.get("BACKEND_URL", "http://localhost:8000"),
        help="Backend base URL (default: env BACKEND_URL or http://localhost:8000).",
    )
    parser.add_argument("--source", default="inquirer")
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--max-minutes", type=int, default=20)
    args = parser.parse_args(argv)

    base = args.backend_url.rstrip("/")

    _assert_ok("GET /health", lambda: _request_json(f"{base}/health", timeout_sec=30))

    run = _assert_ok(
        f"POST /scrape/run (source={args.source})",
        lambda: _request_json(f"{base}/scrape/run", timeout_sec=30, method="POST", body={"source": args.source}),
    )

    jobs = (run or {}).get("jobs") if isinstance(run, dict) else None
    if not jobs or not isinstance(jobs, list):
        raise RuntimeError("Expected `jobs` array in /scrape/run response")

    task_id = jobs[0].get("task_id") if isinstance(jobs[0], dict) else None
    if not task_id:
        raise RuntimeError("Expected `jobs[0].task_id` in /scrape/run response")

    print(f"[INFO] task_id={task_id}")

    deadline = datetime.now(tz=timezone.utc) + timedelta(minutes=args.max_minutes)
    while True:
        if datetime.now(tz=timezone.utc) > deadline:
            raise RuntimeError(f"Timed out waiting for scrape task to finish ({args.max_minutes} min)")

        st = _request_json(f"{base}/scrape/status/{task_id}", timeout_sec=30)
        if isinstance(st, dict):
            status = st.get("status")
            if status == "completed":
                break
            if status == "failed":
                raise RuntimeError(f"Scrape task failed: {st.get('error')}")
        time.sleep(max(1, args.poll_seconds))

    _assert_ok(
        "GET /articles/home-optimized",
        lambda: _request_json(f"{base}/articles/home-optimized?limit_per_source=2&refresh=true", timeout_sec=60),
    )

    # These are heavier endpoints on cold cache.
    _assert_ok(
        "GET /ml/trends",
        lambda: _request_json(f"{base}/ml/trends?period=7d&include_today=true&refresh=true", timeout_sec=180),
    )
    _assert_ok(
        "GET /ml/entities/top",
        lambda: _request_json(f"{base}/ml/entities/top?period=7d&include_today=true&refresh=true", timeout_sec=180),
    )

    print("[DONE] pipeline checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        print(f"[ERROR] {e}")
        raise

