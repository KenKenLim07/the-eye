#!/usr/bin/env python3
"""
Test script for ABS-CBN scraping to check if we can get data before scheduling.
"""

import sys
import os
sys.path.append('backend')

import httpx
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Test URLs from the current scraper
TEST_URLS = [
    "https://news.abs-cbn.com/news/nation/2025/9/3/dpwh-ncr-no-ghost-flood-control-projects-in-metro-manila-1735",
    "https://news.abs-cbn.com/news/business/2025/9/3/airasia-launches-piso-sale-for-reopened-cebu-routes-1751",
    "https://news.abs-cbn.com/news/business/2025/9/3/sec-warns-against-investing-in-pegasus-international-1547",
    "https://news.abs-cbn.com/news/nation/2025/9/3/bfp-delayed-report-blocked-road-hamper-response-to-deadly-malabon-fire-1721",
    "https://news.abs-cbn.com/news/sports/2025/9/3/pba-commissioner-warns-players-about-social-media-posts-1750",
]

# Enhanced user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.71 Mobile/15E148 Safari/604.1",
]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-PH,en;q=0.9,fil;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://news.abs-cbn.com/',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'max-age=0',
    }

def test_url(url):
    """Test a single URL to see if we can fetch and parse it."""
    print(f"\n🔍 Testing: {url}")
    
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=20.0,
            headers=get_headers()
        ) as client:
            
            response = client.get(url)
            print(f"   Status: {response.status_code}")
            
            if response.status_code >= 400:
                print(f"   ❌ HTTP Error: {response.status_code}")
                return False
                
            if not response.text:
                print(f"   ❌ Empty response")
                return False
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Test title extraction
            title_selectors = [
                "h1.article__title",
                "h1.entry-title", 
                "h1.article-title",
                "h1",
                ".article-title",
                "title"
            ]
            
            title = None
            for selector in title_selectors:
                try:
                    el = soup.select_one(selector)
                    if el:
                        title = el.get_text().strip()
                        if title:
                            break
                except:
                    continue
                    
            if title:
                print(f"   ✅ Title: {title[:80]}...")
            else:
                print(f"   ❌ No title found")
                
            # Test content extraction
            content_selectors = [
                ".article-content p",
                ".article__content p",
                ".story-content p",
                ".post-content p",
                "article p",
                ".content p",
                "p"
            ]
            
            content_parts = []
            for selector in content_selectors:
                try:
                    for el in soup.select(selector):
                        text = el.get_text(" ", strip=True)
                        if text and len(text) > 25:
                            content_parts.append(text)
                            if len(content_parts) >= 5:
                                break
                    if content_parts:
                        break
                except:
                    continue
                    
            if content_parts:
                total_content = len(" ".join(content_parts))
                print(f"   ✅ Content: {len(content_parts)} paragraphs, {total_content} chars")
            else:
                print(f"   ❌ No content found")
                
            # Check for blocking indicators
            blocking_indicators = [
                "access denied",
                "blocked",
                "forbidden",
                "cloudflare",
                "captcha",
                "robot",
                "bot"
            ]
            
            page_text = response.text.lower()
            for indicator in blocking_indicators:
                if indicator in page_text:
                    print(f"   ⚠️  Possible blocking detected: {indicator}")
                    
            return title and content_parts
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_homepage():
    """Test if we can access the homepage."""
    print(f"\n🏠 Testing homepage: https://news.abs-cbn.com/")
    
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=20.0,
            headers=get_headers()
        ) as client:
            
            response = client.get("https://news.abs-cbn.com/")
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for article links
                links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href and '/news/' in href and 'abs-cbn.com' in href:
                        links.append(href)
                        
                print(f"   ✅ Found {len(links)} article links")
                if links:
                    print(f"   Sample links:")
                    for link in links[:3]:
                        print(f"     - {link}")
                return True
            else:
                print(f"   ❌ Homepage not accessible")
                return False
                
    except Exception as e:
        print(f"   ❌ Homepage error: {e}")
        return False

def main():
    print("🚀 ABS-CBN Scraping Test")
    print("=" * 50)
    
    # Test homepage access
    homepage_ok = test_homepage()
    
    # Test static URLs
    print(f"\n📋 Testing {len(TEST_URLS)} static URLs:")
    working_urls = 0
    
    for i, url in enumerate(TEST_URLS):
        if test_url(url):
            working_urls += 1
        time.sleep(random.uniform(2, 4))  # Be nice to their servers
        
    # Summary
    print(f"\n📊 Test Results Summary:")
    print(f"   Homepage accessible: {'✅' if homepage_ok else '❌'}")
    print(f"   Static URLs working: {working_urls}/{len(TEST_URLS)}")
    
    if working_urls > 0 or homepage_ok:
        print(f"\n✅ ABS-CBN scraping appears to be working!")
        print(f"   Recommendation: Safe to add to scheduler")
    else:
        print(f"\n❌ ABS-CBN scraping is not working")
        print(f"   Recommendation: Need to investigate blocking/rate limiting")
        
    return working_urls > 0 or homepage_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
