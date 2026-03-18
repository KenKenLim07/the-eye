#!/usr/bin/env python3
"""
 SENIOR CYBER SEC & BLACK HAT VETERAN STEALTH TEST SCRIPT 🔥💀🚀
================================================================

Comprehensive test script to verify all scrapers work with advanced stealth features.
"""

import sys
import os
import asyncio
import time
import logging
from typing import List, Dict, Any

# Add backend to path
sys.path.append('backend')

# Import all scrapers
from app.scrapers.abs_cbn import ABSCBNScraper
from app.scrapers.gma import GMAScraper
from app.scrapers.inquirer import InquirerScraper
from app.scrapers.philstar import PhilStarScraper
from app.scrapers.rappler import RapplerScraper
from app.scrapers.sunstar import SunstarScraper
from app.scrapers.manila_bulletin import ManilaBulletinScraper
from app.scrapers.manila_bulletin_v2 import ManilaBulletinV2Scraper

# Import stealth utilities
from app.scrapers.utils import (
    get_random_user_agent, get_advanced_stealth_headers, 
    get_human_like_delay, is_valid_news_url, should_skip_article
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StealthTester:
    """Advanced stealth testing framework."""
    
    def __init__(self):
        self.results = {}
        self.start_time = time.time()
    
    def test_stealth_utilities(self) -> Dict[str, Any]:
        """Test all stealth utility functions."""
        logger.info("🔥 Testing Stealth Utilities...")
        
        results = {
            "user_agents": [],
            "headers": [],
            "delays": [],
            "url_validation": [],
            "content_validation": []
        }
        
        # Test User-Agent rotation
        for i in range(5):
            ua = get_random_user_agent()
            results["user_agents"].append(ua)
            logger.info(f"  User-Agent {i+1}: {ua[:50]}...")
        
        # Test stealth headers
        for i in range(3):
            headers = get_advanced_stealth_headers()
            results["headers"].append(headers)
            logger.info(f"  Headers {i+1}: {len(headers)} headers generated")
        
        # Test human-like delays
        for i in range(5):
            delay = get_human_like_delay()
            results["delays"].append(delay)
            logger.info(f"  Delay {i+1}: {delay:.2f}s")
        
        # Test URL validation
        test_urls = [
            "https://www.gmanetwork.com/news/lotto/results/test/",  # Should be blocked
            "https://www.gmanetwork.com/news/nation/metro/",        # Should be allowed
            "https://www.gmanetwork.com/news/videos/test/",         # Should be blocked
        ]
        
        for url in test_urls:
            is_valid = is_valid_news_url(url, "gmanetwork.com")
            results["url_validation"].append({"url": url, "valid": is_valid})
            logger.info(f"  URL Validation: {url} -> {'✅' if is_valid else '❌'}")
        
        # Test content validation
        test_content = [
            ("Short", False),
            ("This is a valid article with enough content to pass validation.", True),
            ("", False),
        ]
        
        for content, expected in test_content:
            should_skip, reason = should_skip_article("https://example.com/test", content, 50)
            results["content_validation"].append({
                "content": content[:30] + "...",
                "should_skip": should_skip,
                "reason": reason,
                "expected": expected
            })
            logger.info(f"  Content Validation: {content[:30]}... -> {'✅' if should_skip == expected else '❌'}")
        
        return results
    
    def test_scraper(self, scraper_name: str, scraper_class) -> Dict[str, Any]:
        """Test individual scraper with stealth features."""
        logger.info(f"🔥 Testing {scraper_name} Scraper...")
        
        start_time = time.time()
        results = {
            "scraper": scraper_name,
            "success": False,
            "articles": [],
            "errors": [],
            "performance": {},
            "stealth_features": {}
        }
        
        try:
            # Initialize scraper
            scraper = scraper_class()
            
            # Test stealth features
            if hasattr(scraper, 'USER_AGENTS'):
                results["stealth_features"]["user_agent_rotation"] = len(scraper.USER_AGENTS)
                logger.info(f"  ✅ User-Agent rotation: {len(scraper.USER_AGENTS)} agents")
            
            if hasattr(scraper, 'MIN_DELAY') and hasattr(scraper, 'MAX_DELAY'):
                results["stealth_features"]["delay_range"] = f"{scraper.MIN_DELAY}-{scraper.MAX_DELAY}s"
                logger.info(f"  ✅ Delay range: {scraper.MIN_DELAY}-{scraper.MAX_DELAY}s")
            
            # Run scraper
            if hasattr(scraper, 'scrape_latest'):
                result = scraper.scrape_latest(max_articles=2)
                
                results["success"] = True
                results["articles"] = [
                    {
                        "title": article.title[:50] + "..." if len(article.title) > 50 else article.title,
                        "url": article.url,
                        "content_length": len(article.content) if article.content else 0,
                        "category": article.category
                    }
                    for article in result.articles
                ]
                results["errors"] = result.errors
                results["performance"] = result.performance
                
                logger.info(f"  ✅ Success: {len(result.articles)} articles scraped")
                for article in result.articles:
                    logger.info(f"    📰 {article.title[:50]}...")
                
            else:
                results["errors"].append("No scrape_latest method found")
                logger.error(f"  ❌ No scrape_latest method found")
                
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"  ❌ Error: {e}")
        
        results["performance"]["total_time"] = time.time() - start_time
        return results
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test of all scrapers."""
        logger.info("🔥 SENIOR CYBER SEC & BLACK HAT VETERAN STEALTH TEST STARTING...")
        logger.info("=" * 80)
        
        # Test stealth utilities first
        self.results["stealth_utilities"] = self.test_stealth_utilities()
        
        # Test all scrapers
        scrapers = {
            "ABS-CBN": ABSCBNScraper,
            "GMA": GMAScraper,
            "Inquirer": InquirerScraper,
            "PhilStar": PhilStarScraper,
            "Rappler": RapplerScraper,
            "SunStar": SunstarScraper,
            "Manila Bulletin": ManilaBulletinScraper,
            "Manila Bulletin V2": ManilaBulletinV2Scraper,
        }
        
        for name, scraper_class in scrapers.items():
            try:
                self.results[name] = self.test_scraper(name, scraper_class)
                # Add delay between scrapers
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"❌ Failed to test {name}: {e}")
                self.results[name] = {
                    "scraper": name,
                    "success": False,
                    "errors": [str(e)],
                    "articles": [],
                    "performance": {}
                }
        
        # Generate summary
        self.results["summary"] = self.generate_summary()
        
        total_time = time.time() - self.start_time
        logger.info("=" * 80)
        logger.info(f"🔥 STEALTH TEST COMPLETED in {total_time:.2f}s")
        logger.info("=" * 80)
        
        return self.results
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        successful_scrapers = 0
        total_articles = 0
        total_errors = 0
        
        for name, result in self.results.items():
            if name in ["stealth_utilities", "summary"]:
                continue
            
            if result.get("success", False):
                successful_scrapers += 1
                total_articles += len(result.get("articles", []))
            
            total_errors += len(result.get("errors", []))
        
        return {
            "total_scrapers": len([k for k in self.results.keys() if k not in ["stealth_utilities", "summary"]]),
            "successful_scrapers": successful_scrapers,
            "total_articles": total_articles,
            "total_errors": total_errors,
            "success_rate": f"{(successful_scrapers / len([k for k in self.results.keys() if k not in ['stealth_utilities', 'summary']])) * 100:.1f}%"
        }

async def main():
    """Main test function."""
    tester = StealthTester()
    results = await tester.run_comprehensive_test()
    
    # Print summary
    summary = results["summary"]
    print("\n" + "=" * 80)
    print("🔥 SENIOR CYBER SEC & BLACK HAT VETERAN STEALTH TEST RESULTS")
    print("=" * 80)
    print(f"📊 Total Scrapers: {summary['total_scrapers']}")
    print(f"✅ Successful: {summary['successful_scrapers']}")
    print(f"�� Total Articles: {summary['total_articles']}")
    print(f"❌ Total Errors: {summary['total_errors']}")
    print(f"🎯 Success Rate: {summary['success_rate']}")
    print("=" * 80)
    
    # Print detailed results
    for name, result in results.items():
        if name in ["stealth_utilities", "summary"]:
            continue
        
        print(f"\n🔍 {name}:")
        if result.get("success", False):
            print(f"  ✅ Status: SUCCESS")
            print(f"  📰 Articles: {len(result.get('articles', []))}")
            print(f"  ⏱️  Time: {result.get('performance', {}).get('total_time', 0):.2f}s")
        else:
            print(f"  ❌ Status: FAILED")
            print(f"  🚨 Errors: {len(result.get('errors', []))}")
            for error in result.get('errors', []):
                print(f"    - {error}")

if __name__ == "__main__":
    asyncio.run(main())
