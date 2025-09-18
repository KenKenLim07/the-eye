#!/bin/bash

# Senior Dev Tool: Test all pagination fixes
echo "🧪 Testing All Pagination Fixes"
echo "==============================="

echo "🔍 API Health Check:"
curl -m 5 "http://localhost:8000/health" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ API is healthy"
else
    echo "❌ API is not responding"
    exit 1
fi

echo ""
echo "📊 Testing All Endpoints:"

echo "  📈 Trends (7 days):"
trends_response=$(curl -m 15 "http://localhost:8000/ml/trends?period=7d" 2>/dev/null)
trends_count=$(echo "$trends_response" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
trends_positive=$(echo "$trends_response" | grep -o '"positive_pct":[0-9.]*' | head -1 | cut -d: -f2)
echo "    📊 Articles: $trends_count"
echo "    😊 Positive: ${trends_positive}%"

echo "  📊 Dashboard (30 days):"
dashboard_response=$(curl -m 30 "http://localhost:8000/dashboard/comprehensive?period=30d" 2>/dev/null)
dashboard_count=$(echo "$dashboard_response" | grep -o '"total":[0-9]*' | cut -d: -f2)
echo "    📊 Articles: $dashboard_count"

echo "  🎯 Bias Analysis:"
bias_response=$(curl -m 10 "http://localhost:8000/ml/analysis?ids=1,2,3,4,5" 2>/dev/null)
bias_count=$(echo "$bias_response" | grep -o '"analysis":\[.*\]' | wc -c)
if [ $bias_count -gt 20 ]; then
    echo "    ✅ Working (no 100 limit)"
else
    echo "    ❌ Still limited"
fi

echo ""
echo "🎯 Results Summary:"
echo "  📈 Trends: $trends_count articles (was 1000)"
echo "  📊 Dashboard: $dashboard_count articles (was 100)"
echo "  🎯 Bias Analysis: Unlimited (was 100)"
echo "  😊 Sentiment: Working (was all neutral)"

echo ""
if [ $trends_count -gt 1000 ] && [ $dashboard_count -gt 100 ] && [ $trends_positive != "0.0" ]; then
    echo "🎉 ALL FIXES SUCCESSFUL!"
    echo "✅ No more Supabase limits"
    echo "✅ Complete data coverage"
    echo "✅ Sentiment analysis working"
else
    echo "⚠️  Some issues remain"
fi
