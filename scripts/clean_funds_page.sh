#!/bin/bash

# Senior Dev: Clean up funds page by removing non-funds articles
echo "🧹 Senior Dev: Cleaning Up Funds Page"
echo "====================================="

# Get all funds articles and check each one
echo "📋 Checking all funds articles for accuracy..."

# Get funds articles
FUNDS_ARTICLES=$(curl -s "http://localhost:8000/articles?is_funds=true&limit=100")

# Extract article IDs and titles
echo "$FUNDS_ARTICLES" | grep -o '"id":[0-9]*,"title":"[^"]*"' | while read -r line; do
    ID=$(echo "$line" | grep -o '"id":[0-9]*' | cut -d: -f2)
    TITLE=$(echo "$line" | grep -o '"title":"[^"]*"' | cut -d: -f2- | tr -d '"')
    
    # Test the classification
    ENCODED_TITLE=$(echo "$TITLE" | sed 's/ /%20/g')
    RESULT=$(curl -s "http://localhost:8000/ml/funds/classify?title=$ENCODED_TITLE" | grep -o '"final_result":[^,}]*' | cut -d: -f2)
    
    if [ "$RESULT" = "false" ]; then
        echo "❌ Removing non-funds article: $TITLE"
        # Update the article to set is_funds = false
        curl -sS -X PATCH "http://localhost:8000/articles/$ID" \
          -H "Content-Type: application/json" \
          -d '{"is_funds": false}' > /dev/null
    else
        echo "✅ Keeping funds article: $TITLE"
    fi
done

echo ""
echo "🎯 Funds page cleanup complete!"
echo "Check your funds page now - it should be much cleaner."

