#!/usr/bin/env python3
"""
Test script to verify the optimizations work correctly
"""

import time
import requests
import json

def test_endpoint_performance(endpoint, params=None):
    """Test endpoint performance"""
    base_url = "http://localhost:8000"
    url = f"{base_url}{endpoint}"
    
    print(f"\n🧪 Testing {endpoint}")
    print(f"📡 URL: {url}")
    if params:
        print(f"📋 Params: {params}")
    
    start_time = time.time()
    
    try:
        response = requests.get(url, params=params, timeout=30)
        end_time = time.time()
        
        duration = end_time - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {duration:.2f}s")
            
            # Show key metrics
            if 'summary' in data:
                summary = data['summary']
                print(f"📊 Total articles: {summary.get('total_articles', 0)}")
                print(f"📈 Timeline entries: {len(data.get('timeline', []))}")
            elif 'daily_buckets' in data:
                print(f"📊 Daily buckets: {len(data.get('daily_buckets', []))}")
                print(f"📈 Distribution: {data.get('distribution', {})}")
            
            return duration, True
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return duration, False
            
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout after 30s")
        return 30, False
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0, False

def main():
    print("🚀 Testing Optimized Endpoints")
    print("=" * 50)
    
    # Test different periods and sources
    test_cases = [
        ("/ml/trends", {"period": "7d"}),
        ("/ml/trends", {"period": "30d"}),
        ("/ml/trends", {"period": "30d", "source": "GMA"}),
        ("/bias/summary", {"days": 7}),
        ("/bias/summary", {"days": 30}),
    ]
    
    results = []
    
    for endpoint, params in test_cases:
        duration, success = test_endpoint_performance(endpoint, params)
        results.append({
            'endpoint': endpoint,
            'params': params,
            'duration': duration,
            'success': success
        })
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 50)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    if successful_tests:
        avg_duration = sum(r['duration'] for r in successful_tests) / len(successful_tests)
        max_duration = max(r['duration'] for r in successful_tests)
        min_duration = min(r['duration'] for r in successful_tests)
        
        print(f"✅ Successful tests: {len(successful_tests)}/{len(results)}")
        print(f"⏱️  Average duration: {avg_duration:.2f}s")
        print(f"⚡ Fastest: {min_duration:.2f}s")
        print(f"🐌 Slowest: {max_duration:.2f}s")
        
        # Performance assessment
        if avg_duration < 2:
            print("🎯 EXCELLENT: All endpoints under 2s")
        elif avg_duration < 5:
            print("✅ GOOD: Most endpoints under 5s")
        else:
            print("⚠️  NEEDS IMPROVEMENT: Some endpoints still slow")
    
    if failed_tests:
        print(f"\n❌ Failed tests: {len(failed_tests)}")
        for test in failed_tests:
            print(f"   - {test['endpoint']} {test['params']}")
    
    print("\n🎯 Next steps:")
    print("1. If tests pass, your optimizations are working!")
    print("2. If still slow, add the database indexes from the previous script")
    print("3. Monitor your app logs for any errors")

if __name__ == "__main__":
    main()
