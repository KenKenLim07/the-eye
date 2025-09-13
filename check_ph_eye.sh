#!/bin/bash
echo "🔍 PH Eye Service Status Check"
echo "================================"

# Check API
echo -n "�� FastAPI Server: "
if curl -s "http://localhost:8000/health" > /dev/null 2>&1; then
    echo "✅ Running (http://localhost:8000)"
else
    echo "❌ Not running"
fi

# Check Celery Worker
echo -n "⚙️ Celery Worker: "
if pgrep -f "celery.*worker" > /dev/null; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# Check Celery Beat
echo -n "⏰ Celery Beat: "
if pgrep -f "celery.*beat" > /dev/null; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

# Check recent VADER analysis
echo -n "🤖 VADER Analysis: "
RECENT=$(curl -s "http://localhost:8000/ml/trends?period=1d" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['summary']['total_articles'])" 2>/dev/null)
if [ "$RECENT" != "" ] && [ "$RECENT" -gt 0 ]; then
    echo "✅ $RECENT articles analyzed today"
else
    echo "❌ No recent analysis"
fi

echo ""
echo "📝 Log files:"
echo "  - API: backend/api.log"
echo "  - Worker: backend/worker.log" 
echo "  - Beat: backend/beat.log"
