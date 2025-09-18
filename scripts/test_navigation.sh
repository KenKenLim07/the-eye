#!/bin/bash

echo "🧪 Testing Navigation Fix"
echo "========================"

echo "🔍 Testing all pages:"

pages=("/" "/dashboard" "/trends" "/bias-analysis")

for page in "${pages[@]}"; do
    echo "  📄 Testing $page..."
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000$page")
    if [ "$response" = "200" ]; then
        echo "    ✅ $page - OK"
    else
        echo "    ❌ $page - Error ($response)"
    fi
done

echo ""
echo "🎯 Navigation should now be consistent across all pages!"
echo "📊 All pages should use the same MainLayout with navigation"
