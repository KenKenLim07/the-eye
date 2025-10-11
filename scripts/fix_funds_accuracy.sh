#!/bin/bash

# Senior Dev: Fix funds detection accuracy by reclassifying existing articles
echo "🎯 Senior Dev: Fixing Funds Detection Accuracy"
echo "=============================================="

# Check current funds articles
echo "📋 Current funds articles (latest 10):"
curl -s "http://localhost:8000/articles?is_funds=true&limit=10" | grep -o '"title":"[^"]*"' | head -10

echo ""
echo "🔧 Reclassifying all articles with improved patterns..."

# Trigger backfill with improved patterns
echo "Starting backfill process..."
BACKFILL_RESPONSE=$(curl -sS -X POST "http://localhost:8000/maintenance/backfill_is_funds" \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 50, "dry_run": false}')

echo "Backfill response: $BACKFILL_RESPONSE"

# Wait a moment for processing
echo "⏳ Waiting for processing to complete..."
sleep 5

# Check updated funds articles
echo ""
echo "📋 Updated funds articles (latest 10):"
curl -s "http://localhost:8000/articles?is_funds=true&limit=10" | grep -o '"title":"[^"]*"' | head -10

echo ""
echo "🎯 Next steps:"
echo "1. Check your funds page - it should now be much cleaner"
echo "2. Verify that earthquake/disaster content is filtered out"
echo "3. Confirm that legitimate government funds are still showing"

# Test specific problematic cases
echo ""
echo "🧪 Testing problematic cases:"
echo "Testing earthquake article:"
curl -s "http://localhost:8000/ml/funds/classify?title=36%20courts%20reported%20damage%20from%20magnitude%207.4%20earthquake&content=The%20Supreme%20Court%20said%20that%2036%20courts%20had%20reported%20damage" | grep -o '"final_result":[^,}]*'

echo "Testing legitimate funds article:"
curl -s "http://localhost:8000/ml/funds/classify?title=PCO%20seeks%20P1.1B%20budget%20hike&content=The%20Presidential%20Communications%20Office%20has%20requested%20an%20additional%20P1.109%20billion" | grep -o '"final_result":[^,}]*'

