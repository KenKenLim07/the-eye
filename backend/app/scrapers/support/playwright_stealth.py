from __future__ import annotations

import asyncio
import logging
import random

from playwright.async_api import Browser, BrowserContext, Page

from app.scrapers.support.stealth_profile import (
    get_advanced_stealth_headers,
    get_random_language,
    get_random_proxy,
    get_random_timezone,
    get_random_user_agent,
    get_random_viewport,
)

logger = logging.getLogger(__name__)


async def create_stealth_browser_context(browser: Browser) -> BrowserContext:
    viewport = get_random_viewport()
    timezone = get_random_timezone()

    context = await browser.new_context(
        user_agent=get_random_user_agent(),
        viewport=viewport,
        timezone_id=timezone,
        locale="en-US",
        permissions=["geolocation"],
        extra_http_headers=get_advanced_stealth_headers(),
        proxy=get_random_proxy(),
        java_script_enabled=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )
    return context


async def setup_stealth_page(page: Page) -> None:
    await page.route(
        "**/*",
        lambda route: (
            route.abort()
            if any(
                domain in route.request.url
                for domain in [
                    "google-analytics.com",
                    "googletagmanager.com",
                    "facebook.com",
                    "doubleclick.net",
                    "googlesyndication.com",
                    "adsystem.com",
                    "amazon-adsystem.com",
                    "scorecardresearch.com",
                    "quantserve.com",
                    "outbrain.com",
                    "taboola.com",
                    "criteo.com",
                ]
            )
            or route.request.resource_type in ["image", "media", "font", "stylesheet"]
            else route.continue_()
        ),
    )

    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
          parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
        );
        """
    )


async def simulate_human_behavior(page: Page) -> None:
    for _ in range(random.randint(2, 5)):
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))

    # small scrolls
    for _ in range(random.randint(1, 3)):
        await page.mouse.wheel(0, random.randint(200, 600))
        await asyncio.sleep(random.uniform(0.2, 0.6))

    try:
        await page.set_extra_http_headers({"Accept-Language": get_random_language()})
    except Exception as e:
        logger.debug("Failed to set extra headers: %s", e)

