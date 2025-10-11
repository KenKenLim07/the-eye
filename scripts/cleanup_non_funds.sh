#!/bin/bash

# Senior Dev: Clean up non-funds articles from funds page
echo "🧹 Senior Dev: Cleaning Up Non-Funds Articles"
echo "============================================="

# List of article IDs that should NOT be in funds (based on the examples you showed)
NON_FUNDS_IDS=(
    "11507"  # China hits back on US port fees
    "11508"  # White House lays off thousands
    # Add more IDs as needed
)

echo "📋 Removing non-funds articles..."

for ID in "${NON_FUNDS_IDS[@]}"; do
    echo "Removing article ID: $ID"
    # Update article to set is_funds = false
    curl -sS -X PATCH "http://localhost:8000/articles/$ID" \
      -H "Content-Type: application/json" \
      -d '{"is_funds": false}' > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully removed article $ID from funds"
    else
        echo "❌ Failed to remove article $ID"
    fi
done

echo ""
echo "🎯 Manual cleanup complete!"

# Now let's trigger a more comprehensive backfill
echo "🔄 Triggering comprehensive backfill..."
curl -sS -X POST "http://localhost:8000/maintenance/backfill_is_funds" \
  -H "Content-Type: application/json" \
  -d '{"batch_size": 100, "dry_run": false}' > /dev/null

echo "✅ Backfill triggered. The funds page should be cleaner now."
echo ""
echo "📋 Check your funds page - it should now show only legitimate government funds content."

