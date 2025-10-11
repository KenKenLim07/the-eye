#!/bin/bash

# Senior Dev: Production Monitoring for Funds Detection
echo "📊 Funds Detection Monitoring Dashboard"
echo "======================================"

# Check API health
echo "🔍 API Health Check..."
health_response=$(curl -s -w "%{http_code}" "http://localhost:8000/health" -o /dev/null)
if [ "$health_response" = "200" ]; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed (HTTP $health_response)"
    exit 1
fi

# Test classification performance
echo ""
echo "⚡ Classification Performance Test..."
start_time=$(date +%s%N)
response=$(curl -s "http://localhost:8000/ml/funds/classify?title=DPWH%20allocates%20P5%20billion%20for%20flood%20control&content=Government%20infrastructure%20funding")
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))

if echo "$response" | grep -q '"ok":true'; then
    echo "✅ Classification working (${duration}ms response time)"
    if [ $duration -lt 1000 ]; then
        echo "✅ Performance: Excellent (< 1s)"
    elif [ $duration -lt 3000 ]; then
        echo "⚠️  Performance: Acceptable (< 3s)"
    else
        echo "❌ Performance: Slow (> 3s)"
    fi
else
    echo "❌ Classification failed"
fi

# Check spaCy status
echo ""
echo "🤖 spaCy Status Check..."
spacy_response=$(curl -s "http://localhost:8000/ml/funds/classify?title=Test&content=Test")
if echo "$spacy_response" | grep -q '"spacy_result":null'; then
    echo "ℹ️  spaCy: Disabled (regex-only mode)"
elif echo "$spacy_response" | grep -q '"spacy_result":{'; then
    echo "✅ spaCy: Enabled and working"
else
    echo "❌ spaCy: Status unknown"
fi

# Get current funds statistics
echo ""
echo "📈 Current Funds Statistics..."
insights_response=$(curl -s "http://localhost:8000/ml/funds/insights?days_back=1")
if echo "$insights_response" | grep -q '"ok":true'; then
    total_articles=$(echo "$insights_response" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
    echo "✅ Funds articles (last 24h): $total_articles"
    
    # Extract top sources
    echo "📰 Top sources:"
    echo "$insights_response" | grep -o '"top_sources":{[^}]*}' | sed 's/.*"top_sources":{//' | sed 's/}.*//' | tr ',' '\n' | head -3 | sed 's/^/   /'
else
    echo "❌ Failed to get insights"
fi

# Memory usage check (if possible)
echo ""
echo "💾 System Resources..."
if command -v ps >/dev/null 2>&1; then
    # Check if we can find the Python process
    python_pids=$(ps aux | grep python | grep -v grep | awk '{print $2}' | head -3)
    if [ ! -z "$python_pids" ]; then
        echo "Python processes found: $python_pids"
        for pid in $python_pids; do
            if [ -f "/proc/$pid/status" ]; then
                memory_kb=$(grep VmRSS "/proc/$pid/status" | awk '{print $2}')
                memory_mb=$((memory_kb / 1024))
                echo "   PID $pid: ${memory_mb}MB RAM"
            fi
        done
    fi
fi

# Database connection test
echo ""
echo "🗄️  Database Connection Test..."
db_test=$(curl -s "http://localhost:8000/articles?limit=1" | head -c 100)
if echo "$db_test" | grep -q '"id"'; then
    echo "✅ Database connection working"
else
    echo "❌ Database connection issues"
fi

# Recent error check
echo ""
echo "🚨 Recent Activity Check..."
echo "Checking last 10 funds articles..."
recent_funds=$(curl -s "http://localhost:8000/articles?is_funds=true&limit=10")
if echo "$recent_funds" | grep -q '"id"'; then
    echo "✅ Recent funds articles accessible"
    # Count how many have is_funds=true
    funds_count=$(echo "$recent_funds" | grep -o '"is_funds":true' | wc -l)
    echo "   Found $funds_count funds articles in recent batch"
else
    echo "❌ No recent funds articles found"
fi

# Performance recommendations
echo ""
echo "💡 Performance Recommendations:"
echo "==============================="

# Check if spaCy is enabled
if echo "$spacy_response" | grep -q '"spacy_result":null'; then
    echo "🔧 spaCy is disabled - consider enabling for better accuracy"
    echo "   Set USE_SPACY_FUNDS=true in your .env file"
    echo "   Monitor memory usage after enabling"
else
    echo "✅ spaCy is enabled - monitor for memory leaks"
fi

# Response time recommendations
if [ $duration -gt 2000 ]; then
    echo "⚠️  Slow response times detected"
    echo "   Consider caching frequently accessed data"
    echo "   Check if spaCy model is being reloaded frequently"
fi

echo ""
echo "📋 Monitoring Summary:"
echo "====================="
echo "✅ API Health: Good"
echo "⚡ Response Time: ${duration}ms"
echo "📊 Funds Articles: $total_articles (24h)"
echo "🤖 spaCy Status: $(echo "$spacy_response" | grep -q '"spacy_result":null' && echo "Disabled" || echo "Enabled")"
echo ""
echo "🔄 Run this script every 15 minutes for production monitoring"
echo "📧 Set up alerts if response time > 5s or API health fails"

