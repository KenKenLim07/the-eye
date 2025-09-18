#!/bin/bash

# Senior Dev Tool: Adjust API limits for better performance
# Usage: ./scripts/adjust_limits.sh [limit_value]

LIMIT=${1:-500}

echo "🔧 Adjusting API limits to $LIMIT..."

# Update main.py
sed -i '' "s/limit([0-9]*)/limit($LIMIT)/g" backend/app/main.py

# Update dashboard_data.py
sed -i '' "s/limit([0-9]*)/limit($LIMIT)/g" backend/app/dashboard_data.py

echo "✅ Limits updated to $LIMIT"
echo "🔄 Restarting API..."

docker restart ph-eye-api

echo "⏳ Waiting for API to start..."
sleep 5

echo "🧪 Testing API..."
curl -m 10 "http://localhost:8000/health" && echo "✅ API is healthy!"

echo "📊 Testing trends endpoint..."
curl -m 15 "http://localhost:8000/ml/trends?period=7d" | grep -o '"total_articles":[0-9]*' | head -1

echo "🎉 Done! Your analytics now show up to $LIMIT articles per query."
