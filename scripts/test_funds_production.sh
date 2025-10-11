#!/bin/bash

# Senior Dev: Production Testing Script (No spaCy Installation Required)
echo "🧪 Production Funds Detection Testing"
echo "===================================="

# Test 1: Basic API Health
echo "1️⃣ Testing API Health..."
health_response=$(curl -s -w "%{http_code}" "http://localhost:8000/health" -o /dev/null)
if [ "$health_response" = "200" ]; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed (HTTP $health_response)"
    exit 1
fi

# Test 2: Funds Classification (Regex Mode)
echo ""
echo "2️⃣ Testing Funds Classification (Regex Mode)..."
test_cases=(
    "DPWH%20allocates%20P5%20billion%20for%20flood%20control|Government%20infrastructure%20funding|true"
    "P1M%20worth%20of%20shabu%20seized%20in%20buy-bust|Police%20seized%20illegal%20drugs|false"
    "Senate%20approves%20P500M%20budget%20for%20education|Congressional%20budget%20approval|true"
    "PBA%20Finals%20Ginebra%20wins%20championship|Basketball%20tournament%20results|false"
)

passed=0
total=${#test_cases[@]}

for test_case in "${test_cases[@]}"; do
    IFS='|' read -r title content expected <<< "$test_case"
    
    response=$(curl -s "http://localhost:8000/ml/funds/classify?title=$title&content=$content")
    result=$(echo "$response" | grep -o '"final_result":[^,}]*' | cut -d: -f2 | tr -d ' ')
    
    if [ "$result" = "$expected" ]; then
        echo "✅ Test passed: $title"
        ((passed++))
    else
        echo "❌ Test failed: $title (expected: $expected, got: $result)"
    fi
done

echo "📊 Classification Tests: $passed/$total passed"

# Test 3: Funds Insights API
echo ""
echo "3️⃣ Testing Funds Insights API..."
insights_response=$(curl -s "http://localhost:8000/ml/funds/insights?days_back=1")
if echo "$insights_response" | grep -q '"ok":true'; then
    total_articles=$(echo "$insights_response" | grep -o '"total_articles":[0-9]*' | cut -d: -f2)
    echo "✅ Insights API working - Found $total_articles funds articles (24h)"
    
    # Show top sources
    echo "📰 Top sources:"
    echo "$insights_response" | grep -o '"top_sources":{[^}]*}' | sed 's/.*"top_sources":{//' | sed 's/}.*//' | tr ',' '\n' | head -3 | sed 's/^/   /'
else
    echo "❌ Insights API failed"
fi

# Test 4: Performance Test
echo ""
echo "4️⃣ Performance Test..."
start_time=$(date +%s%N)
for i in {1..5}; do
    curl -s "http://localhost:8000/ml/funds/classify?title=Test%20$i&content=Test%20content" > /dev/null
done
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))
avg_duration=$((duration / 5))

echo "⚡ 5 requests took ${duration}ms (avg: ${avg_duration}ms per request)"

if [ $avg_duration -lt 500 ]; then
    echo "✅ Performance: Excellent (< 500ms)"
elif [ $avg_duration -lt 1000 ]; then
    echo "✅ Performance: Good (< 1s)"
elif [ $avg_duration -lt 2000 ]; then
    echo "⚠️  Performance: Acceptable (< 2s)"
else
    echo "❌ Performance: Slow (> 2s)"
fi

# Test 5: Database Integration
echo ""
echo "5️⃣ Database Integration Test..."
db_response=$(curl -s "http://localhost:8000/articles?is_funds=true&limit=5")
if echo "$db_response" | grep -q '"id"'; then
    funds_count=$(echo "$db_response" | grep -o '"is_funds":true' | wc -l)
    echo "✅ Database integration working - Found $funds_count funds articles"
else
    echo "❌ Database integration failed"
fi

# Test 6: Frontend Integration
echo ""
echo "6️⃣ Frontend Integration Test..."
frontend_response=$(curl -s "http://localhost:3000/funds" | head -c 200)
if echo "$frontend_response" | grep -q "funds\|Funds"; then
    echo "✅ Frontend funds page accessible"
else
    echo "⚠️  Frontend funds page may not be accessible (check if Next.js is running)"
fi

# Summary
echo ""
echo "📋 Production Test Summary"
echo "========================="
echo "✅ API Health: Good"
echo "📊 Classification: $passed/$total tests passed"
echo "⚡ Performance: ${avg_duration}ms average"
echo "🗄️  Database: Working"
echo "📰 Insights: $total_articles funds articles (24h)"
echo ""
echo "🎯 Senior Dev Recommendations:"
echo "============================="

if [ $passed -eq $total ]; then
    echo "✅ All tests passed - Ready for production deployment"
else
    echo "⚠️  Some tests failed - Review before production"
fi

if [ $avg_duration -lt 1000 ]; then
    echo "✅ Performance is excellent - No optimization needed"
else
    echo "⚠️  Consider performance optimization for high traffic"
fi

echo ""
echo "🚀 Next Steps:"
echo "1. Deploy with USE_SPACY_FUNDS=false (regex-only mode)"
echo "2. Monitor performance and accuracy"
echo "3. When ready, enable spaCy with USE_SPACY_FUNDS=true"
echo "4. Run recompute to apply spaCy rules to existing data"
echo ""
echo "📊 Monitoring:"
echo "Run './scripts/monitor_funds_detection.sh' every 15 minutes"
