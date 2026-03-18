import sys
sys.path.append('backend')

# Test the Rappler category extraction directly
from urllib.parse import urlparse
from bs4 import BeautifulSoup

def test_rappler_category_extraction():
    # Simulate the _extract_rappler_category method
    def extract_rappler_category(url, soup=None):
        raw_category = None
        
        # 1. Try to extract from URL structure first (most reliable)
        if url:
            try:
                parsed = urlparse(url)
                path_parts = [p for p in parsed.path.split('/') if p]
                
                if path_parts:
                    first_segment = path_parts[0].lower()
                    category_map = {
                        'technology': 'Technology',
                        'tech': 'Technology', 
                        'business': 'Business',
                        'sports': 'Sports',
                        'world': 'World',
                        'entertainment': 'Entertainment',
                        'nation': 'Nation',
                        'newsbreak': 'News',
                        'latest': 'News',
                        'politics': 'Politics',
                        'lifestyle': 'Lifestyle',
                        'opinion': 'Opinion'
                    }
                    
                    if first_segment in category_map:
                        raw_category = category_map[first_segment]
                    
                    # For newsbreak URLs, check second segment
                    if first_segment == 'newsbreak' and len(path_parts) > 1:
                        second_segment = path_parts[1].lower()
                        if second_segment in category_map:
                            raw_category = category_map[second_segment]
            except Exception:
                pass
        
        # Normalize the category
        if raw_category:
            normalized = raw_category
        else:
            normalized = 'General'
            raw_category = None
        
        return normalized, raw_category
    
    # Test URLs
    test_urls = [
        "https://www.rappler.com/technology/mistral-ai-fundraising-asml-top-shareholder-september-9-2025/",
        "https://www.rappler.com/newsbreak/fact-check/dotr-order-shutdown-online-shopping-platforms/",
        "https://www.rappler.com/sports/volleyball/alas-pilipinas-takes-humble-approach-fivb-men-world-championship-september-2025/",
        "https://www.rappler.com/world/asia-pacific/thailand-former-pm-thaksin-shinawatra-jailed-september-9-2025/",
        "https://www.rappler.com/entertainment/music/best-buddies-bistro-group-benefit-concert-september-2025/"
    ]
    
    print("Testing Rappler category extraction:")
    print("=" * 50)
    
    for url in test_urls:
        normalized, raw = extract_rappler_category(url)
        print(f"URL: {url}")
        print(f"Expected: Based on path segment")
        print(f"Got: {normalized} (raw: {raw})")
        print("-" * 40)

if __name__ == "__main__":
    test_rappler_category_extraction()
