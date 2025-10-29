#!/bin/bash
# Quick ML Analysis Backfill Script
# Usage: ./backfill_ml.sh [days] [batch_size]
# Example: ./backfill_ml.sh 7 100

DAYS=${1:-7}
BATCH_SIZE=${2:-100}

echo "🔄 Starting ML analysis backfill for last $DAYS days..."
echo "📦 Batch size: $BATCH_SIZE"
echo ""

# Run the backfill inside Docker
docker-compose exec api python /app/scripts/backfill_ml_analysis.py --days $DAYS --batch-size $BATCH_SIZE

echo ""
echo "✅ Backfill complete! Monitor progress with:"
echo "   docker-compose logs -f worker"
echo ""
echo "💡 Quick commands:"
echo "   ./backfill_ml.sh 7 50    # Last 7 days, small batches"
echo "   ./backfill_ml.sh 3 200   # Last 3 days, large batches"
echo "   ./backfill_ml.sh 1 10    # Yesterday only, tiny batches"

