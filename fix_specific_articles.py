#!/usr/bin/env python3
"""
Fix specific articles that are incorrectly classified as funds
"""
import requests
import json

# Articles that should be marked as non-funds
article_ids = [11584, 11586, 11564, 11566, 11543]

# Update each article
for article_id in article_ids:
    try:
        # Get the article first
        response = requests.get(f"http://localhost:8000/articles/{article_id}")
        if response.status_code == 200:
            article = response.json()
            print(f"Article {article_id}: {article.get('title', 'No title')[:50]}...")
            
            # Update is_funds to false
            update_response = requests.patch(
                f"http://localhost:8000/articles/{article_id}",
                json={"is_funds": False}
            )
            
            if update_response.status_code == 200:
                print(f"✅ Updated article {article_id}")
            else:
                print(f"❌ Failed to update article {article_id}: {update_response.text}")
        else:
            print(f"❌ Could not fetch article {article_id}")
    except Exception as e:
        print(f"❌ Error processing article {article_id}: {e}")

print("Done!")

