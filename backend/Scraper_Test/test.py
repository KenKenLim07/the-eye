# test.py
import sys
import traceback
import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import random
import time

URL = "https://news.abs-cbn.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def try_httpx():
    print("Trying httpx...")
    try:
        with httpx.Client(http2=False, headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
            r = client.get(URL)
            print("Status code:", r.status_code)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                links = [a.get("href") for a in soup.select("a[href]")]
                print("Sample links (first 10):", links[:10])
                return True
            else:
                print("httpx did not return 200 — falling back. Response preview:")
                print(r.text[:400])
                return False
    except Exception as e:
        print("httpx request failed:", repr(e))
        traceback.print_exc()
        return False


def fallback_playwright():
    """
    Playwright fallback with lightweight anti-detection tweaks:
      - run headless (production mode)
      - set user_agent, locale, viewport
      - add init script to override navigator properties before page scripts run
      - set some extra http headers
      - use domcontentloaded + small wait instead of networkidle
    """
    print("\nLaunching Playwright (Chromium) with anti-detection tweaks...")
    with sync_playwright() as p:
        # Launch browser (headless for production). Headed mode requires GUI.
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])

        # Small randomization for viewport to look less bot-like
        base_w, base_h = 1280, 800
        viewport = {
            "width": base_w + random.choice([-20, 0, 20]),
            "height": base_h + random.choice([-10, 0, 10]),
        }

        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="en-US",
            viewport=viewport,
            accept_downloads=False,
        )

        # Set some extra HTTP headers (applies to all requests in this context)
        context.set_extra_http_headers({
            "Referer": HEADERS["Referer"],
            "Accept-Language": HEADERS["Accept-Language"],
        })

        # Init script: runs before any page script. Good for overriding navigator properties.
        # Keep it minimal and realistic.
        context.add_init_script(
            """
            // Minimal navigator overrides to reduce headless fingerprinting
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            // Provide a small, plausible userAgentData if available
            try {
                if (navigator.userAgentData === undefined) {
                    Object.defineProperty(navigator, 'userAgentData', {
                        get: () => ({ brands: [{brand: 'Chromium', version: '129'}, {brand: 'Google Chrome', version: '129'}], mobile: false })
                    });
                }
            } catch (e) {}
            """
        )

        page = context.new_page()

        # Optional: tiny random delay to simulate human timing before navigation
        time.sleep(random.uniform(0.1, 0.5))

        try:
            # Use domcontentloaded instead of networkidle to avoid long waits when resources are blocked
            page.goto(URL, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print("Playwright page.goto error:", repr(e))
            browser.close()
            return False

        # Wait a short time for JS-built content to appear (tunable)
        page.wait_for_timeout(2500)  # 2.5s

        # Extra small scroll to trigger lazy loading
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 4);")
            page.wait_for_timeout(500)
        except Exception:
            pass

        title = page.title()
        content = page.content()
        print("Title:", title)
        print("Content length:", len(content))

        soup = BeautifulSoup(content, "html.parser")
        headlines = [h.get_text(strip=True) for h in soup.select("h1, h2, h3") if h.get_text(strip=True)]
        print("Headlines (sample):", headlines[:10])

        # Save screenshot so you can inspect what the page produced
        try:
            page.screenshot(path="abs_cbn.png", full_page=True)
            print("Saved screenshot: abs_cbn.png")
        except Exception as e:
            print("Screenshot failed:", repr(e))

        print("\n✅ Browser session completed.")
        browser.close()
        return True


def main():
    ok = try_httpx()
    if ok:
        print("\nSuccess with httpx (no Playwright needed).")
        sys.exit(0)

    ok2 = fallback_playwright()
    if ok2:
        print("\nSuccess with Playwright.")
        sys.exit(0)
    else:
        print("\nBoth httpx and Playwright failed. Inspect the output above for errors.")
        sys.exit(2)


if __name__ == "__main__":
    main()
