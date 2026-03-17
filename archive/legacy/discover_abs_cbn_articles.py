#!/usr/bin/env python3
"""
BLACKHAT ABS-CBN Article Discovery
Uses the working scraper to discover more article URLs
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scrapers.abs_cbn import ABSCBNWorkingScraper
import time
import random
import httpx
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse

class ABSDiscoveryAgent:
    """Blackhat agent to discover more ABS-CBN articles"""
    
    def __init__(self):
        self.scraper = ABSCBNWorkingScraper()
        self.discovered_urls = set()
        self.working_urls = []
        
    def _get_stealth_headers(self):
        """Stealth headers that bypass their defense"""
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-GPC': '1',
            'Referer': 'https://www.google.com/',
        }
    
    def _stealth_delay(self):
        """Random delay to avoid detection"""
        delay = random.uniform(15, 30)
        print(f"🕐 Stealth delay: {delay:.1f}s")
        time.sleep(delay)
    
    def discover_from_working_articles(self):
        """Discover more URLs from the working articles"""
        print("🔍 BLACKHAT DISCOVERY: Analyzing working articles for more URLs...")
        
        for url in self.scraper.STATIC_ARTICLE_URLS:
            print(f"📰 Analyzing: {url}")
            
            try:
                # Use the scraper's stealth method
                html = self.scraper._fetch_with_stealth(url)
                if not html:
                    print(f"❌ Failed to fetch: {url}")
                    continue
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for related articles
                related_links = self._extract_related_links(soup, url)
                print(f"✅ Found {len(related_links)} related links")
                
                for link in related_links:
                    if link not in self.discovered_urls:
                        self.discovered_urls.add(link)
                        print(f"🆕 New URL: {link}")
                
                self._stealth_delay()
                
            except Exception as e:
                print(f"❌ Error analyzing {url}: {e}")
                continue
    
    def _extract_related_links(self, soup, base_url):
        """Extract related article links from page"""
        links = set()
        
        # Look for article links in various patterns
        selectors = [
            'a[href*="/news/"]',
            'a[href*="/article/"]',
            '.related-articles a',
            '.more-articles a',
            '.article-links a',
            '.news-links a'
        ]
        
        for selector in selectors:
            try:
                for link in soup.select(selector):
                    href = link.get('href')
                    if href:
                        # Convert relative URLs to absolute
                        full_url = urljoin(base_url, href)
                        
                        # Filter for ABS-CBN news URLs
                        if self._is_valid_abs_cbn_url(full_url):
                            links.add(full_url)
            except Exception:
                continue
        
        return list(links)
    
    def _is_valid_abs_cbn_url(self, url):
        """Check if URL is a valid ABS-CBN article URL"""
        if not url or 'news.abs-cbn.com' not in url:
            return False
        
        # Must be a news article URL
        if '/news/' not in url:
            return False
        
        # Skip non-article URLs
        skip_patterns = [
            '/category/',
            '/tag/',
            '/author/',
            '/search',
            '/rss',
            '/feed',
            '.xml',
            '.json',
            '#',
            '?'
        ]
        
        for pattern in skip_patterns:
            if pattern in url:
                return False
        
        return True
    
    def generate_potential_urls(self):
        """Generate potential URLs based on patterns"""
        print("🎯 BLACKHAT GENERATION: Creating potential URLs...")
        
        base_url = "https://news.abs-cbn.com"
        categories = ['nation', 'business', 'sports', 'entertainment', 'lifestyle', 'technology', 'world']
        
        # Generate URLs for recent dates
        from datetime import datetime, timedelta
        
        for days_ago in range(0, 7):  # Last 7 days
            date = datetime.now() - timedelta(days=days_ago)
            date_str = date.strftime("%Y/%m/%d")
            
            for category in categories:
                # Generate potential URL patterns
                potential_urls = [
                    f"{base_url}/news/{category}/{date_str}/article-{random.randint(1000, 9999)}",
                    f"{base_url}/news/{category}/{date_str}/breaking-{random.randint(100, 999)}",
                    f"{base_url}/news/{category}/{date_str}/update-{random.randint(100, 999)}",
                ]
                
                for url in potential_urls:
                    if url not in self.discovered_urls:
                        self.discovered_urls.add(url)
    
    def test_discovered_urls(self):
        """Test discovered URLs to see which ones work"""
        print("🧪 BLACKHAT TESTING: Testing discovered URLs...")
        
        test_urls = list(self.discovered_urls)[:20]  # Test first 20
        
        for i, url in enumerate(test_urls):
            print(f"🔬 Testing {i+1}/{len(test_urls)}: {url}")
            
            try:
                # Quick test with head request
                with httpx.Client(
                    follow_redirects=True,
                    timeout=10,
                    headers=self._get_stealth_headers(),
                    verify=False
                ) as client:
                    response = client.head(url)
                    
                    if response.status_code == 200:
                        print(f"✅ WORKING: {url}")
                        self.working_urls.append(url)
                    else:
                        print(f"❌ Failed ({response.status_code}): {url}")
                
                self._stealth_delay()
                
            except Exception as e:
                print(f"❌ Error testing {url}: {e}")
                continue
    
    def run_discovery(self):
        """Run the full discovery process"""
        print("🚀 BLACKHAT ABS-CBN DISCOVERY STARTING...")
        print("=" * 60)
        
        # Step 1: Discover from working articles
        self.discover_from_working_articles()
        
        # Step 2: Generate potential URLs
        self.generate_potential_urls()
        
        # Step 3: Test discovered URLs
        self.test_discovered_urls()
        
        print("=" * 60)
        print(f"🎯 DISCOVERY COMPLETE!")
        print(f"📊 Total URLs discovered: {len(self.discovered_urls)}")
        print(f"✅ Working URLs found: {len(self.working_urls)}")
        
        if self.working_urls:
            print("\n🔥 NEW WORKING URLs:")
            for url in self.working_urls:
                print(f"  ✅ {url}")
        
        return self.working_urls

if __name__ == "__main__":
    agent = ABSDiscoveryAgent()
    working_urls = agent.run_discovery()
    
    if working_urls:
        print(f"\n💾 SAVE THESE URLs TO YOUR SCRAPER:")
        for url in working_urls:
            print(f'        "{url}",')
