#!/bin/bash
echo "🚀 Starting PH Eye Services..."

# Kill any existing processes
pkill -f "uvicorn app.main:app"
pkill -f "celery.*worker"
pkill -f "celery.*beat"

# Wait a moment
sleep 2

# Navigate to backend
cd /Users/mac/ph-eye/backend

# Activate virtual environment
source venv/bin/activate

# Start services in background with nohup
echo "📡 Starting FastAPI server..."
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > api.log 2>&1 &

echo "⚙️ Starting Celery worker..."
nohup celery -A app.celery worker --loglevel=info > worker.log 2>&1 &

echo "⏰ Starting Celery beat..."
nohup celery -A app.celery beat --loglevel=info > beat.log 2>&1 &

# Wait for services to start
sleep 3

echo "✅ PH Eye services started!"
echo "🌐 API: http://localhost:8000"
echo "📊 Trends: http://localhost:8000/ml/trends"
echo "📝 Logs: api.log, worker.log, beat.log"
echo ""
echo "To stop services: ./stop_ph_eye.sh"
