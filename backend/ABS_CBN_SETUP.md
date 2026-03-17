# ABS-CBN Scraper Setup

ABS-CBN is supported, but it is not as reliable as other sources when running in headless browser mode.

## Why It Is Different

In this repo, the ABS-CBN scraper uses Playwright and is sensitive to whether Chromium is launched in headless mode.

- Headless mode (`PLAYWRIGHT_HEADLESS=true`) may be blocked.
- Headed mode (`PLAYWRIGHT_HEADLESS=false`) works more reliably during local development.

Because of this, ABS-CBN is typically kept as a manual/on-demand scrape (not part of the default scheduled beat runs).

## Local (Development) Run

```bash
# Disable headless for ABS-CBN
export PLAYWRIGHT_HEADLESS=false

cd backend
source ../venv/bin/activate
python -c "from app.scrapers.abs_cbn import ABSCBNScraper; s = ABSCBNScraper(); print(s.scrape_latest(max_articles=3))"
```

## Server / Docker Notes

If you need to run headed Chromium on a machine without a physical display, run it with a virtual display (Xvfb) and set:

- `DISPLAY=:99`
- `PLAYWRIGHT_HEADLESS=false`

If you do not need ABS-CBN in unattended mode, the simplest approach is to leave it manual-only.
