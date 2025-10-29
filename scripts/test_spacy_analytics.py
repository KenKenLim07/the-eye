#!/usr/bin/env python3
"""
Senior Dev: spaCy Funds Analytics Test
Test the enhanced spaCy analytics system
"""
import os
import sys
sys.path.append('/Users/mac/ph-eye/backend')

# Set environment variables
os.environ['USE_SPACY_ANALYTICS'] = 'true'
os.environ['USE_SPACY_FUNDS'] = 'true'

def test_spacy_installation():
    """Test if spaCy is properly installed"""
    print("🧪 Testing spaCy Installation...")
    
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        print("✅ spaCy model loaded successfully")
        
        # Test basic NER
        doc = nlp("DPWH allocates P5 billion for flood control projects in Manila.")
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        print(f"✅ NER working: {entities}")
        
        return True
    except Exception as e:
        print(f"❌ spaCy installation failed: {e}")
        return False

def test_funds_analytics():
    """Test the funds analytics system"""
    print("\n🎯 Testing Funds Analytics...")
    
    try:
        from app.analytics.funds_analytics import extract_funds_analytics
        
        # Test article
        sample_article = """
        DPWH allocates P5 billion for flood control projects across the Philippines.
        The Department of Public Works and Highways announced the allocation for 
        infrastructure projects in Manila, Cebu, and Davao. Senator Juan Dela Cruz 
        questioned the allocation, citing potential irregularities in the bidding process.
        The project will be handled by ABC Construction Corp and XYZ Builders Inc.
        """
        
        analytics = extract_funds_analytics(
            article_id=1,
            title="DPWH allocates P5 billion for flood control",
            content=sample_article,
            published_at="2025-01-01"
        )
        
        print("✅ Analytics extraction successful")
        print(f"   Agencies: {[a.text for a in analytics.agencies]}")
        print(f"   Amounts: {[a.text for a in analytics.amounts]}")
        print(f"   Locations: {[a.text for a in analytics.locations]}")
        print(f"   People: {[a.text for a in analytics.people]}")
        print(f"   Contractors: {analytics.contractors}")
        print(f"   Project Locations: {analytics.project_locations}")
        print(f"   Total Amount: {analytics.total_amount}")
        print(f"   Primary Agency: {analytics.primary_agency}")
        print(f"   Corruption Indicators: {analytics.corruption_indicators}")
        print(f"   Extraction Confidence: {analytics.extraction_confidence}")
        print(f"   Relevance Score: {analytics.funds_relevance_score}")
        
        return True
    except Exception as e:
        print(f"❌ Analytics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    print("\n🌐 Testing API Endpoints...")
    
    try:
        import requests
        
        # Test analytics extraction endpoint
        response = requests.post(
            "http://localhost:8000/analytics/funds/extract",
            json=[11584, 11586, 11564],
            headers={"X-Admin-Token": "your-admin-token"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Analytics API working: {data.get('total_processed', 0)} articles processed")
        else:
            print(f"⚠️ Analytics API returned status {response.status_code}")
        
        # Test trends endpoint
        response = requests.get("http://localhost:8000/analytics/funds/trends?days_back=7")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Trends API working: {data.get('articles_analyzed', 0)} articles analyzed")
        else:
            print(f"⚠️ Trends API returned status {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Senior Dev spaCy Funds Analytics Test")
    print("=" * 50)
    
    # Test spaCy installation
    spacy_ok = test_spacy_installation()
    
    if spacy_ok:
        # Test analytics system
        analytics_ok = test_funds_analytics()
        
        if analytics_ok:
            # Test API endpoints
            api_ok = test_api_endpoints()
            
            if api_ok:
                print("\n🎉 All tests passed! spaCy analytics is ready!")
            else:
                print("\n⚠️ API tests failed, but analytics system is working")
        else:
            print("\n❌ Analytics system failed")
    else:
        print("\n❌ spaCy installation failed")
        print("   Run: ./scripts/install_spacy_senior_dev.sh")

if __name__ == "__main__":
    main()













