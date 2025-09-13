#!/bin/bash
echo "🛑 Stopping PH Eye Services..."

# Kill all processes
pkill -f "uvicorn app.main:app"
pkill -f "celery.*worker"
pkill -f "celery.*beat"

echo "✅ All services stopped!"
