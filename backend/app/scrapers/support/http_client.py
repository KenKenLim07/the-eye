from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional

import httpx

from app.scrapers.support.stealth_profile import get_advanced_stealth_headers, get_retry_delay

logger = logging.getLogger(__name__)


async def stealth_request(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    delay_between_requests: bool = True,
) -> Optional[httpx.Response]:
    """Make a request with retry/backoff and rotating headers."""
    for attempt in range(max_retries):
        try:
            if delay_between_requests and attempt > 0:
                await asyncio.sleep(get_retry_delay(attempt))

            client.headers.update(get_advanced_stealth_headers())
            response = await client.get(url)

            if response.status_code == 200:
                return response
            if response.status_code == 429:
                await asyncio.sleep(random.uniform(10.0, 20.0))
                continue

            logger.info("HTTP %s for %s", response.status_code, url)
        except Exception as e:
            logger.warning("Request failed (attempt %s/%s) url=%s err=%s", attempt + 1, max_retries, url, e)
            if attempt == max_retries - 1:
                return None

    return None

