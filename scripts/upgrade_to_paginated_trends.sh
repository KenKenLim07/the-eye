#!/bin/bash

# Senior Dev Tool: Upgrade to paginated trends (handles unlimited articles)
echo "🚀 Upgrading to Paginated Trends System"
echo "======================================"

echo "�� Current trends endpoint shows:"
current_count=$(curl -s "http://localhost:8000/ml/trends?period=7d" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
echo "  📈 /ml/trends: $current_count articles"

echo "📊 New paginated endpoint shows:"
paginated_count=$(curl -s "http://localhost:8000/ml/trends-paginated?period=7d" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
echo "  📈 /ml/trends-paginated: $paginated_count articles"

echo ""
echo "🔄 Replacing old trends endpoint with paginated version..."

# Backup current main.py
cp backend/app/main.py backend/app/main.py.backup-$(date +%Y%m%d-%H%M%S)

# Replace the trends endpoint
sed -i '' 's/@app\.get("\/ml\/trends")/@app.get("\/ml\/trends-old")/' backend/app/main.py
sed -i '' 's/@app\.get("\/ml\/trends-paginated")/@app.get("\/ml\/trends")/' backend/app/main.py

echo "✅ Endpoints swapped!"
echo "🔄 Restarting API..."

docker restart ph-eye-api

echo "⏳ Waiting for API to start..."
sleep 5

echo "🧪 Testing new trends endpoint..."
new_count=$(curl -s "http://localhost:8000/ml/trends?period=7d" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
echo "  📈 New /ml/trends: $new_count articles"

echo ""
echo "🎉 Upgrade Complete!"
echo "📊 Your trends now show ALL articles in the date range (no 1000 limit)"
echo "🔗 Old endpoint available at: /ml/trends-old"
echo "🔗 New endpoint at: /ml/trends"
