#!/bin/bash

# Senior Dev Tool: Monitor analytics performance and data volume
echo "📊 PH Eye Analytics Performance Check"
echo "======================================"

echo "🔍 Testing API Health..."
curl -m 5 "http://localhost:8000/health" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ API is healthy"
else
    echo "❌ API is not responding"
    exit 1
fi

echo ""
echo "📈 Testing Trends Performance:"

echo "  📅 Daily trends (1 day):"
start_time=$(date +%s)
curl -m 15 "http://localhost:8000/ml/trends?period=1d" > /dev/null 2>&1
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "    ⏱️  Response time: ${duration}s"

echo "  📅 Weekly trends (7 days):"
start_time=$(date +%s)
response=$(curl -m 20 "http://localhost:8000/ml/trends?period=7d" 2>/dev/null)
end_time=$(date +%s)
duration=$((end_time - start_time))
article_count=$(echo "$response" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
echo "    ⏱️  Response time: ${duration}s"
echo "    📊 Articles analyzed: $article_count"

echo "  📅 Monthly trends (30 days):"
start_time=$(date +%s)
response=$(curl -m 30 "http://localhost:8000/ml/trends?period=30d" 2>/dev/null)
end_time=$(date +%s)
duration=$((end_time - start_time))
article_count=$(echo "$response" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
echo "    ⏱️  Response time: ${duration}s"
echo "    📊 Articles analyzed: $article_count"

echo ""
echo "🎯 Performance Summary:"
if [ $duration -lt 10 ]; then
    echo "✅ Excellent performance (< 10s)"
elif [ $duration -lt 20 ]; then
    echo "✅ Good performance (< 20s)"
elif [ $duration -lt 30 ]; then
    echo "⚠️  Acceptable performance (< 30s)"
else
    echo "❌ Slow performance (> 30s) - consider optimization"
fi

echo ""
echo "💡 Current Configuration:"
echo "  📊 Date-based analysis: ✅ Enabled"
echo "  🔢 Article limits: ❌ Removed (processes all articles in date range)"
echo "  ⚡ Performance: Optimized for complete data analysis"
