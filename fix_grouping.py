#!/usr/bin/env python3
"""
Fix the timeline grouping to count all articles per date, not just those with sentiment analysis
"""

# Read the current main.py
with open('backend/app/main.py', 'r') as f:
    content = f.read()

# Find and replace the problematic grouping section
old_section = '''        # Group by date - FIXED: Count ALL articles per date
        from collections import defaultdict
        daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        for analysis in all_analysis:
            article_id = analysis["article_id"]
            sentiment_label = analysis.get("sentiment_label", "neutral")
            sentiment_score = analysis.get("sentiment_score", 0)
            
            # Find the article to get its date
            article = next((a for a in articles if a["id"] == article_id), None)
            if article:
                date_str = article["published_at"][:10]  # YYYY-MM-DD
                daily_data[date_str]["total"] += 1
                daily_data[date_str]["sentiment_scores"].append(sentiment_score)
                
                if sentiment_label == "positive":
                    daily_data[date_str]["positive"] += 1
                elif sentiment_label == "negative":
                    daily_data[date_str]["negative"] += 1
                else:
                    daily_data[date_str]["neutral"] += 1'''

new_section = '''        # Group by date - FIXED: Count ALL articles per date, not just those with sentiment analysis
        from collections import defaultdict
        daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        # First, count all articles by date
        for article in articles:
            date_str = article["published_at"][:10]  # YYYY-MM-DD
            daily_data[date_str]["total"] += 1
        
        # Then, add sentiment analysis data
        for analysis in all_analysis:
            article_id = analysis["article_id"]
            sentiment_label = analysis.get("sentiment_label", "neutral")
            sentiment_score = analysis.get("sentiment_score", 0)
            
            # Find the article to get its date
            article = next((a for a in articles if a["id"] == article_id), None)
            if article:
                date_str = article["published_at"][:10]  # YYYY-MM-DD
                daily_data[date_str]["sentiment_scores"].append(sentiment_score)
                
                if sentiment_label == "positive":
                    daily_data[date_str]["positive"] += 1
                elif sentiment_label == "negative":
                    daily_data[date_str]["negative"] += 1
                else:
                    daily_data[date_str]["neutral"] += 1'''

# Replace the section
new_content = content.replace(old_section, new_section)

# Write back to file
with open('backend/app/main.py', 'w') as f:
    f.write(new_content)

print("✅ Fixed timeline grouping!")
print("🎯 Now counts ALL articles per date, not just those with sentiment analysis")
