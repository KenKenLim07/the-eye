import re
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup

CANONICAL_CATEGORIES = {
    "headlines": "Headlines",
    "news": "News",
    "nation": "Nation",
    "business": "Business",
    "sports": "Sports",
    "technology": "Technology",
    "tech": "Technology",
    "world": "World",
    "entertainment": "Entertainment",
    "lifestyle": "Lifestyle",
    "opinion": "Opinion",
    "cebu": "Cebu",
    "davao": "Davao",
    "manila": "Manila",
    "bohol": "Bohol",
    "pampanga": "Pampanga",
    "baguio": "Baguio",
    "zamboanga": "Zamboanga",
    "iloilo": "Iloilo",
    "tacloban": "Tacloban",
    "general-santos": "General Santos",
}

# Canonical source display names
CANONICAL_SOURCES: Dict[str, str] = {
    "gma": "GMA",
    "manila bulletin": "Manila Bulletin",
    "sunstar": "Sunstar",
    "inquirer": "Inquirer",
    "rappler": "Rappler",
    "philstar": "Philstar",
    "manila times": "Manila Times",
    "abs-cbn": "ABS-CBN",
}

BLACKLIST_SEGMENTS = {"photo", "photos", "video", "videos", "about", "section", "tag", "author", "page"}


def normalize_source(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower()
    return CANONICAL_SOURCES.get(key) or raw.strip().title()


def normalize_category(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    key = raw.strip().lower().replace("_", "-")
    return CANONICAL_CATEGORIES.get(key) or raw.strip().title()


def extract_category_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        segments = [s for s in (parsed.path or "").split('/') if s]
        for seg in segments:
            if seg.lower() in BLACKLIST_SEGMENTS:
                continue
            canon = normalize_category(seg)
            if canon in CANONICAL_CATEGORIES.values():
                return canon
        # Heuristics for year-based paths like /2025/09/05/...
        if segments and re.match(r"^20\d{2}$", segments[0]):
            # Look backward for a known segment
            for seg in segments:
                canon = normalize_category(seg)
                if canon in CANONICAL_CATEGORIES.values():
                    return canon
    except Exception:
        return None
    return None


def extract_category_from_html(soup: Optional[BeautifulSoup]) -> Optional[str]:
    if soup is None:
        return None
    # OpenGraph / meta tags
    meta_candidates = [
        ("property", "article:section"),
        ("name", "section"),
        ("name", "category"),
    ]
    for attr, value in meta_candidates:
        tag = soup.find("meta", {attr: value})
        if tag and tag.get("content"):
            cat = normalize_category(tag.get("content"))
            if cat:
                return cat
    # Breadcrumbs
    for selector in [
        "nav.breadcrumb a", 
        ".breadcrumb a", 
        ".breadcrumbs a", 
        "ul.breadcrumb li a",
        "#breadcrumb a",
    ]:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            cat = normalize_category(el.get_text(strip=True))
            if cat:
                return cat
    # Structured data
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            import json
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                section = data.get("articleSection")
                if isinstance(section, str):
                    cat = normalize_category(section)
                    if cat:
                        return cat
        except Exception:
            continue
    return None


def resolve_category(url: Optional[str], soup: Optional[BeautifulSoup]) -> str:
    # Prefer explicit HTML signals, then URL, then fallback
    cat = extract_category_from_html(soup)
    if not cat:
        cat = extract_category_from_url(url)
    return cat or "General" 


def resolve_category_pair(url: Optional[str], soup: Optional[BeautifulSoup]) -> tuple[str, Optional[str]]:
    raw = extract_category_from_html(soup) or extract_category_from_url(url)
    normalized = normalize_category(raw) if raw else None
    return (normalized or "General", raw) 

# ============================================================================
#  SENIOR CYBER SEC & BLACK HAT VETERAN STEALTH UTILITIES 🔥💀🚀
# ============================================================================

import random
import time
import asyncio
from typing import List, Dict, Optional, Tuple
import httpx
from playwright.async_api import Browser, BrowserContext, Page

# 🎯 ADVANCED USER-AGENT ROTATION
ADVANCED_USER_AGENTS = [
    # Chrome on Windows (Most Common)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
    
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# 🌐 RESIDENTIAL PROXY POOL (Configure with your proxy provider)
PROXY_POOL = [
    # Add your residential proxy endpoints here
    # "http://username:password@proxy1.example.com:8080",
    # "http://username:password@proxy2.example.com:8080",
    # "http://username:password@proxy3.example.com:8080",
]

# 🎭 BROWSER FINGERPRINTING EVASION
VIEWPORT_POOL = [
    {"width": 1920, "height": 1080},  # Full HD
    {"width": 1366, "height": 768},   # Common laptop
    {"width": 1440, "height": 900},   # MacBook
    {"width": 1536, "height": 864},   # Windows laptop
    {"width": 1280, "height": 720},   # HD
    {"width": 1600, "height": 900},   # Widescreen
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
    """Get a random user agent from the advanced pool."""
    return random.choice(ADVANCED_USER_AGENTS)

def get_random_proxy() -> Optional[str]:
    """Get a random proxy from the pool."""
    return random.choice(PROXY_POOL) if PROXY_POOL else None

def get_random_viewport() -> Dict[str, int]:
    """Get a random viewport size."""
    return random.choice(VIEWPORT_POOL)

def get_random_timezone() -> str:
    """Get a random timezone."""
    return random.choice(TIMEZONE_POOL)

def get_random_language() -> str:
    """Get a random language preference."""
    return random.choice(LANGUAGE_POOL)

def get_advanced_stealth_headers() -> Dict[str, str]:
    """Generate advanced stealth headers with randomization."""
    return {
        "User-Agent": get_random_user_agent(),
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
        "sec-ch-ua-platform": '"Windows"' if "Windows" in get_random_user_agent() else '"macOS"',
    }

def get_human_like_delay() -> float:
    """Generate human-like delay using normal distribution."""
    # Normal distribution: mean=8.0, std=2.0
    delay = random.gauss(8.0, 2.0)
    # Clamp between 3-15 seconds
    return max(3.0, min(15.0, delay))

def get_retry_delay(attempt: int) -> float:
    """Generate exponential backoff delay for retries."""
    base_delay = 5.0
    max_delay = 60.0
    delay = base_delay * (2 ** attempt) + random.uniform(0, 5.0)
    return min(delay, max_delay)

async def create_stealth_browser_context(browser: Browser) -> BrowserContext:
    """Create a stealth browser context with advanced fingerprinting evasion."""
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
        # Advanced stealth options
        java_script_enabled=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )
    
    return context

async def setup_stealth_page(page: Page) -> None:
    """Setup a page with advanced stealth measures."""
    # Block tracking and analytics
    await page.route("**/*", lambda route: (
        route.abort() if any(
            domain in route.request.url for domain in [
                "google-analytics.com", "googletagmanager.com", "facebook.com",
                "doubleclick.net", "googlesyndication.com", "adsystem.com",
                "amazon-adsystem.com", "scorecardresearch.com", "quantserve.com",
                "outbrain.com", "taboola.com", "criteo.com"
            ]
        ) or route.request.resource_type in ["image", "media", "font", "stylesheet"]
        else route.continue_()
    ))
    
    # Inject stealth scripts
    await page.add_init_script("""
        // Remove webdriver traces
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        
        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        
        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)

async def simulate_human_behavior(page: Page) -> None:
    """Simulate human-like mouse movements and scrolling."""
    # Random mouse movements
    for _ in range(random.randint(2, 5)):
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    # Random scrolling
    for _ in range(random.randint(1, 3)):
        await page.mouse.wheel(0, random.randint(100, 500))
        await asyncio.sleep(random.uniform(0.5, 1.0))

def create_stealth_httpx_client() -> httpx.AsyncClient:
    """Create an httpx client with advanced stealth configuration."""
    return httpx.AsyncClient(
        timeout=30.0,
        headers=get_advanced_stealth_headers(),
        follow_redirects=True,
        verify=True,  # Use proper SSL
        proxies=get_random_proxy(),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )

# 🛡️ CONTENT VALIDATION UTILITIES

def validate_article_content(content: str, min_length: int = 50) -> bool:
    """Validate article content meets minimum requirements."""
    if not content:
        return False
    clean_content = content.strip()
    return len(clean_content) >= min_length

def is_video_content(url: str) -> bool:
    """Check if URL points to video content that should be skipped."""
    video_patterns = ['/videos/', '/video/', '/watch/', '/play/', '/stream/']
    return any(pattern in url.lower() for pattern in video_patterns)

def should_skip_article(url: str, content: str, min_content_length: int = 50) -> Tuple[bool, str]:
    """
    Determine if an article should be skipped and return reason.
    Returns: (should_skip, reason)
    """
    if is_video_content(url):
        return True, "video content"
    
    if not validate_article_content(content, min_content_length):
        return True, "insufficient content"
    
    return False, ""

def log_skipped_article(source: str, url: str, reason: str):
    """Log why an article was skipped."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"{source}: skipping article ({reason}) - {url}")

#  ADVANCED URL VALIDATION

def is_valid_news_url(url: str, base_domain: str) -> bool:
    """Advanced URL validation for news articles."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        
        # Check domain
        if not parsed.netloc.endswith(base_domain):
            return False
        
        # Check for blocked patterns
        blocked_patterns = [
            "lotto", "swertres", "stl", "pcso", "gambling", "betting",
            "photo", "photos", "video", "videos", "modal", "popup",
            "advertisement", "ad", "promo", "promotion", "results",
            "draw", "winning", "numbers", "play", "ticket"
        ]
        
        path_lower = (parsed.path or "").lower()
        if any(pattern in path_lower for pattern in blocked_patterns):
            return False
        
        # Check for valid article structure
        segments = [s for s in parsed.path.split('/') if s]
        return len(segments) >= 3  # At least 3 path segments
        
    except Exception:
        return False

#  STEALTH REQUEST WRAPPER
async def stealth_request(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 3,
    delay_between_requests: bool = True
) -> Optional[httpx.Response]:
    """Make a stealth HTTP request with advanced retry logic."""
    for attempt in range(max_retries):
        try:
            if delay_between_requests and attempt > 0:
                delay = get_retry_delay(attempt)
                await asyncio.sleep(delay)
            
            # Rotate headers for each request
            client.headers.update(get_advanced_stealth_headers())
            
            response = await client.get(url)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                # Rate limited - wait longer
                await asyncio.sleep(random.uniform(10.0, 20.0))
                continue
            else:
                print(f"HTTP {response.status_code} for {url}")
                
        except Exception as e:
            print(f"Request failed (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return None
    
    return None 