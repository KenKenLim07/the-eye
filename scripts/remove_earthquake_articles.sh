#!/bin/bash

# Senior Dev: Remove specific earthquake articles from funds section
echo "🧹 Senior Dev: Removing Earthquake Articles from Funds Section"
echo "============================================================="

# List of article IDs that are earthquake/disaster related and should NOT be in funds
EARTHQUAKE_IDS=(
    "11465"  # Tsunami warning after magnitude 6.8 Davao Oriental earthquake lifted
    "11472"  # Strong quake jolts Davao
    "11476"  # Cebu, Davao, Baguio quakes 'not connected'
)

echo "📋 Removing earthquake/disaster articles from funds section..."

for ID in "${EARTHQUAKE_IDS[@]}"; do
    echo "Removing earthquake article ID: $ID"
    
    # Test the classification first
    TITLE=$(curl -s "http://localhost:8000/articles/$ID" | grep -o '"title":"[^"]*"' | cut -d: -f2- | tr -d '"')
    echo "  Title: $TITLE"
    
    # Test classification
    ENCODED_TITLE=$(echo "$TITLE" | sed 's/ /%20/g')
    RESULT=$(curl -s "http://localhost:8000/ml/funds/classify?title=$ENCODED_TITLE" | grep -o '"final_result":[^,}]*' | cut -d: -f2)
    echo "  Classification result: $RESULT"
    
    if [ "$RESULT" = "false" ]; then
        echo "  ✅ Correctly classified as non-funds - removing from funds section"
        # Use the recompute endpoint to update this specific article
        curl -sS -X POST "http://localhost:8000/maintenance/recompute_is_funds" \
          -H "Content-Type: application/json" \
          -d "{\"article_ids\": [$ID]}" > /dev/null
    else
        echo "  ⚠️  Still classified as funds - may need manual review"
    fi
    echo ""
done

echo "🎯 Earthquake article cleanup complete!"
echo ""
echo "📋 Checking updated funds articles..."
curl -s "http://localhost:8000/articles?is_funds=true&limit=10" | grep -o '"title":"[^"]*"' | head -10

echo ""
echo "✅ The funds page should now be much cleaner!"
echo "🔍 Check your funds page - earthquake/disaster content should be filtered out."

