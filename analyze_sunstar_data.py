#!/usr/bin/env python3
"""
Analyze Sunstar scraped data
"""

import json
from collections import Counter
from datetime import datetime

def analyze_sunstar_data():
    try:
        with open('sunstar_articles.json', 'r', encoding='utf-8') as f:
            articles = json.load(f)
        
        print("🔍 SUNSTAR DATA ANALYSIS")
        print("=" * 50)
        print(f"📊 Total articles: {len(articles)}")
        
        # Analyze categories
        all_categories = []
        for article in articles:
            all_categories.extend(article.get('categories', []))
        
        category_counts = Counter(all_categories)
        print(f"\n📂 Top categories:")
        for cat, count in category_counts.most_common(10):
            print(f"  {cat}: {count} articles")
        
        # Analyze authors
        authors = [article.get('author', 'Unknown') for article in articles]
        author_counts = Counter(authors)
        print(f"\n✍️  Top authors:")
        for author, count in author_counts.most_common(5):
            print(f"  {author}: {count} articles")
        
        # Analyze content length
        content_lengths = []
        for article in articles:
            if 'content_clean' in article:
                content_lengths.append(len(article['content_clean']))
        
        if content_lengths:
            avg_length = sum(content_lengths) / len(content_lengths)
            print(f"\n📝 Content analysis:")
            print(f"  Average content length: {avg_length:.0f} characters")
            print(f"  Shortest article: {min(content_lengths)} characters")
            print(f"  Longest article: {max(content_lengths)} characters")
        
        # Show sample data structure
        if articles:
            print(f"\n📋 Sample article structure:")
            sample = articles[0]
            for key, value in sample.items():
                if key == 'content_clean':
                    print(f"  {key}: {str(value)[:100]}...")
                else:
                    print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"❌ Error analyzing data: {e}")

if __name__ == "__main__":
    analyze_sunstar_data()
