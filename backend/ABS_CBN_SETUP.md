# ABS-CBN Scraper Setup

## Overview

ABS-CBN uses **Akamai Bot Manager** which is one of the most sophisticated anti-bot systems. The scraper works but requires special configuration.

## Why Special Setup is Needed

ABS-CBN's Akamai protection blocks:

- ❌ Simple HTTP requests (httpx, requests)
- ❌ Headless browsers (Playwright with `headless=True`)
- ✅ **Headed browsers** (Playwright with `headless=False`) - WORKS!

The key difference: **headed browsers** have more realistic fingerprints that pass Akamai's checks.

## Development Setup (Local)

### Option 1: Run with Visible Browser (Easiest)

```bash
# Set environment variable to disable headless mode
export PLAYWRIGHT_HEADLESS=false

# Run the scraper
cd backend
source ../venv/bin/activate
python -c "from app.scrapers.abs_cbn import ABSCBNScraper; s = ABSCBNScraper(); print(s.scrape_latest(max_articles=3))"
```

This will open a visible browser window (Chrome) - you'll see it scraping in real-time.

### Option 2: Test Script

```bash
cd backend/Scraper_Test
python3 test.py
```

This uses the original test script with `headless=False`.

## Production Setup (Docker/Headless Server)

For production, you need **Xvfb** (X Virtual Frame Buffer) to run headed mode without a physical display:

### Docker Configuration

Update `docker-compose.yml`:

```yaml
services:
  worker:
    environment:
      - PLAYWRIGHT_HEADLESS=false
      - DISPLAY=:99
    command: >
      sh -c "
        Xvfb :99 -screen 0 1280x1024x24 &
        celery -A app.celery worker --loglevel=info
      "
```

Update `Dockerfile`:

```dockerfile
# Install Xvfb for headed Playwright in headless environment
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    fluxbox \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium
```

### Manual Server Setup

```bash
# Install Xvfb
sudo apt-get install -y xvfb

# Start virtual display
Xvfb :99 -screen 0 1280x1024x24 &
export DISPLAY=:99

# Set Playwright to headed mode
export PLAYWRIGHT_HEADLESS=false

# Run Celery worker
celery -A app.celery worker --loglevel=info
```

## Verification

### Test Access

```bash
cd backend
source ../venv/bin/activate
python -c "
from app.scrapers.abs_cbn import ABSCBNScraper
scraper = ABSCBNScraper()
result = scraper.scrape_latest(max_articles=1)
print(f'Articles: {len(result.articles)}')
print(f'Errors: {result.errors}')
print(f'Metadata: {result.metadata}')
"
```

### Expected Output (Success)

```
ABS-CBN: Testing access...
ABS-CBN: Trying https://news.abs-cbn.com/
ABS-CBN: ✓ Access successful! Title: Leading Entertainment and News Network | ABS-CBN
ABS-CBN: found 45 URLs
ABS-CBN: scraped Typhoon Tino makes landfall...
Articles: 1
Errors: []
```

### Expected Output (Blocked - headless mode)

```
ABS-CBN: blocked 403
Articles: 0
Errors: ['All landing pages blocked']
```

## Alternative Solutions (If Headed Mode Doesn't Work)

1. **Residential Proxies** ($50-200/month)

   - Add to `PROXY_POOL` in `backend/app/scrapers/utils.py`
   - Services: BrightData, Smartproxy, Oxylabs

2. **Undetected ChromeDriver**

   - Use `undetected-chromedriver` package
   - More complex setup but better stealth

3. **Skip ABS-CBN**
   - Focus on 7 working sources
   - Re-enable when proxy budget allows

## Current Status

- ✅ Scraper implemented
- ✅ Works in headed mode (tested)
- ⚠️ Requires Xvfb for production
- ⚠️ May still get blocked occasionally (Akamai updates)

## Troubleshooting

### "Access Denied" Error

- Check `PLAYWRIGHT_HEADLESS=false` is set
- Verify Xvfb is running (`ps aux | grep Xvfb`)
- Check DISPLAY variable (`echo $DISPLAY`)

### Chromium Not Found

```bash
python -m playwright install chromium
python -m playwright install-deps chromium
```

### Still Getting Blocked

- Add delays between requests (already implemented)
- Consider adding residential proxies
- Verify User-Agent matches real Chrome version

## Notes

- ABS-CBN's Akamai protection is **enterprise-grade**
- It fingerprints: WebDriver flags, browser automation, headless mode, TLS, HTTP/2
- Our scraper bypasses most checks but **headed mode is critical**
- Budget 2-3x longer scraping time vs other sources








