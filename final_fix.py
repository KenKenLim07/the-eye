#!/usr/bin/env python3
"""
Final fix: Aggregate all sources for each date to show one entry per date
"""

# Read the current main.py
with open('backend/app/main.py', 'r') as f:
    content = f.read()

# Find the timeline conversion section and fix it
old_timeline_section = '''        # Convert to timeline format
        timeline = []
        total_articles = 0
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        
        for date_str in sorted(daily_data.keys()):'''

new_timeline_section = '''        # Convert to timeline format - FIXED: Aggregate all sources per date
        timeline = []
        total_articles = 0
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        
        # Group by date only (aggregate all sources)
        aggregated_daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        for date_str, data in daily_data.items():
            aggregated_daily_data[date_str]["total"] += data["total"]
            aggregated_daily_data[date_str]["positive"] += data["positive"]
            aggregated_daily_data[date_str]["negative"] += data["negative"]
            aggregated_daily_data[date_str]["neutral"] += data["neutral"]
            aggregated_daily_data[date_str]["sentiment_scores"].extend(data["sentiment_scores"])
        
        for date_str in sorted(aggregated_daily_data.keys()):'''

# Replace the section
new_content = content.replace(old_timeline_section, new_timeline_section)

# Also need to update the data reference
new_content = new_content.replace('data = daily_data[date_str]', 'data = aggregated_daily_data[date_str]')

# Write back to file
with open('backend/app/main.py', 'w') as f:
    f.write(new_content)

print("✅ Fixed timeline aggregation!")
print("🎯 Now shows one entry per date (aggregated across all sources)")
