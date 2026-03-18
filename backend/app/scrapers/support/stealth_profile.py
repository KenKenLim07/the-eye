from __future__ import annotations

import random
from typing import Dict, Optional


# Advanced User-Agent rotation
ADVANCED_USER_AGENTS = [
    # Chrome on Windows (most common)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# Residential proxy pool (optional: populate with your proxy provider)
PROXY_POOL: list[str] = []


VIEWPORT_POOL = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
    {"width": 1600, "height": 900},
]

TIMEZONE_POOL = [
    "Asia/Manila",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Tokyo",
    "America/New_York",
    "Europe/London",
]

LANGUAGE_POOL = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-PH,en;q=0.9",
    "en-US,en;q=0.8",
    "en-GB,en;q=0.8",
]


def get_random_user_agent() -> str:
    return random.choice(ADVANCED_USER_AGENTS)


def get_random_proxy() -> Optional[str]:
    return random.choice(PROXY_POOL) if PROXY_POOL else None


def get_random_viewport() -> Dict[str, int]:
    return random.choice(VIEWPORT_POOL)


def get_random_timezone() -> str:
    return random.choice(TIMEZONE_POOL)


def get_random_language() -> str:
    return random.choice(LANGUAGE_POOL)


def get_advanced_stealth_headers() -> Dict[str, str]:
    ua = get_random_user_agent()
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": get_random_language(),
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"' if "Windows" in ua else '"macOS"',
    }


def get_human_like_delay() -> float:
    # Normal distribution: mean=8.0, std=2.0, clamped to 3-15 seconds.
    delay = random.gauss(8.0, 2.0)
    return max(3.0, min(15.0, delay))


def get_retry_delay(attempt: int) -> float:
    base_delay = 5.0
    max_delay = 60.0
    delay = base_delay * (2**attempt) + random.uniform(0, 5.0)
    return min(delay, max_delay)

