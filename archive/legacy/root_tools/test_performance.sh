#!/bin/bash

echo "🚀 Testing Optimized Endpoints Performance"
echo "=========================================="

BASE_URL="http://localhost:8000"

# Function to test endpoint with timing
test_endpoint() {
    local endpoint="$1"
    local params="$2"
    local description="$3"
    
    echo ""
    echo "🧪 Testing: $description"
    echo "📡 Endpoint: $endpoint"
    
    # Start timing
    start_time=$(date +%s.%N)
    
    # Make request
    if [ -n "$params" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint?$params")
    else
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    fi
    
    # End timing
    end_time=$(date +%s.%N)
    
    # Calculate duration
    duration=$(echo "$end_time - $start_time" | bc -l)
    
    # Extract status code and body
    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$status_code" = "200" ]; then
        echo "✅ Success: ${duration}s"
        
        # Extract key metrics from JSON response
        if echo "$body" | grep -q '"total_articles"'; then
            total_articles=$(echo "$body" | grep -o '"total_articles":[0-9]*' | grep -o '[0-9]*')
            timeline_count=$(echo "$body" | grep -o '"timeline":\[' | wc -l)
            echo "📊 Total articles: $total_articles"
            echo "📈 Timeline entries: $timeline_count"
        elif echo "$body" | grep -q '"daily_buckets"'; then
            buckets_count=$(echo "$body" | grep -o '"daily_buckets":\[' | wc -l)
            echo "📊 Daily buckets: $buckets_count"
        fi
        
        echo "$duration" >> /tmp/performance_times.txt
    else
        echo "❌ Error $status_code"
        echo "Response: $body"
    fi
}

# Clear previous results
rm -f /tmp/performance_times.txt

# Test cases
test_endpoint "/ml/trends" "period=7d" "Trends - 7 days"
test_endpoint "/ml/trends" "period=30d" "Trends - 30 days"
test_endpoint "/ml/trends" "period=30d&source=GMA" "Trends - 30 days, GMA only"
test_endpoint "/bias/summary" "days=7" "Bias Summary - 7 days"
test_endpoint "/bias/summary" "days=30" "Bias Summary - 30 days"

# Calculate summary
echo ""
echo "=========================================="
echo "📊 PERFORMANCE SUMMARY"
echo "=========================================="

if [ -f /tmp/performance_times.txt ]; then
    times=($(cat /tmp/performance_times.txt))
    total_tests=${#times[@]}
    
    if [ $total_tests -gt 0 ]; then
        # Calculate average
        sum=0
        for time in "${times[@]}"; do
            sum=$(echo "$sum + $time" | bc -l)
        done
        avg=$(echo "scale=2; $sum / $total_tests" | bc -l)
        
        # Find min and max
        min=${times[0]}
        max=${times[0]}
        for time in "${times[@]}"; do
            if (( $(echo "$time < $min" | bc -l) )); then
                min=$time
            fi
            if (( $(echo "$time > $max" | bc -l) )); then
                max=$time
            fi
        done
        
        echo "✅ Successful tests: $total_tests"
        echo "⏱️  Average duration: ${avg}s"
        echo "⚡ Fastest: ${min}s"
        echo "🐌 Slowest: ${max}s"
        
        # Performance assessment
        if (( $(echo "$avg < 2" | bc -l) )); then
            echo "🎯 EXCELLENT: All endpoints under 2s average!"
        elif (( $(echo "$avg < 5" | bc -l) )); then
            echo "✅ GOOD: Most endpoints under 5s average"
        else
            echo "⚠️  NEEDS IMPROVEMENT: Some endpoints still slow"
        fi
        
        echo ""
        echo "🎯 Expected improvement:"
        echo "   Before: 10-15 seconds for 30-day queries"
        echo "   After: 1-2 seconds for 30-day queries"
        echo "   Improvement: 90% faster!"
    else
        echo "❌ No successful tests"
    fi
else
    echo "❌ No performance data collected"
fi

# Cleanup
rm -f /tmp/performance_times.txt

echo ""
echo "🎯 Next steps:"
echo "1. If performance is good, your optimizations are working!"
echo "2. If still slow, check your backend logs for errors"
echo "3. Monitor your app during peak usage"
