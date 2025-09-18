#!/bin/bash

echo "🚀 Starting PH-Eye Frontend..."

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Check if backend is running
echo "🔍 Checking backend status..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend is running"
else
    echo "⚠️  Backend not detected. Make sure to run:"
    echo "   ./start_ph_eye.sh"
    echo ""
    echo "   Or with Docker:"
    echo "   docker-compose up -d"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🎨 Starting Next.js development server..."
echo "📱 Frontend will be available at: http://localhost:3000"
echo "🔗 Backend API: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the frontend"
echo ""

npm run dev
