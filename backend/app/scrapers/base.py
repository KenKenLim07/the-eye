from contextlib import contextmanager
from typing import Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEFAULT_TIMEOUT_MS = 20000

@contextmanager
def launch_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()

def fetch_html(url: str, wait_selector: Optional[str] = None, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    with launch_browser() as browser:
        page = browser.new_page()
        page.set_default_timeout(timeout_ms)
        page.goto(url)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except Exception:
                pass
        return page.content()

def to_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml") 