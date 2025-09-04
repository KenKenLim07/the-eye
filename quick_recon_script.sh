#!/bin/bash

# BLACK HAT QUICK RECONNAISSANCE SCRIPT
# Usage: ./quick_recon_script.sh TARGET_DOMAIN

if [ $# -eq 0 ]; then
    echo "Usage: $0 TARGET_DOMAIN"
    echo "Example: $0 example.com"
    exit 1
fi

TARGET_DOMAIN=$1
echo "🎯 TARGET: $TARGET_DOMAIN"
echo "=================================="

echo "📋 PHASE 1: INITIAL RECONNAISSANCE"
echo "----------------------------------"
echo "Basic site structure:"
curl -s "https://$TARGET_DOMAIN" | head -20
echo ""

echo "Internal links:"
curl -s "https://$TARGET_DOMAIN" | grep -E 'href="[^"]*'$TARGET_DOMAIN'[^"]*"' | head -5
echo ""

echo "📋 PHASE 2: RSS/XML FEED DISCOVERY"
echo "----------------------------------"
echo "Checking /feed/:"
curl -s "https://$TARGET_DOMAIN/feed/" | head -10
echo ""

echo "Checking /rss.xml:"
curl -s "https://$TARGET_DOMAIN/rss.xml" | head -10
echo ""

echo "Checking /feed.xml:"
curl -s "https://$TARGET_DOMAIN/feed.xml" | head -10
echo ""

echo "📋 PHASE 3: API ENDPOINT DISCOVERY"
echo "----------------------------------"
echo "API references in HTML:"
curl -s "https://$TARGET_DOMAIN" | grep -i "api\|rss\|feed\|xml" | head -5
echo ""

echo "Testing common API patterns:"
echo "  /api/v1/collections/home.rss:"
curl -s "https://$TARGET_DOMAIN/api/v1/collections/home.rss" | head -5
echo ""

echo "  /api/feed:"
curl -s "https://$TARGET_DOMAIN/api/feed" | head -5
echo ""

echo "📋 PHASE 4: ADVANCED RECONNAISSANCE"
echo "----------------------------------"
echo "Sitemap:"
curl -s "https://$TARGET_DOMAIN/sitemap.xml" | head -10
echo ""

echo "Robots.txt:"
curl -s "https://$TARGET_DOMAIN/robots.txt"
echo ""

echo "📋 PHASE 5: CONTENT EXTRACTION TEST"
echo "----------------------------------"
echo "Testing RSS content extraction:"
RSS_URL="https://$TARGET_DOMAIN/api/v1/collections/home.rss"
if curl -s "$RSS_URL" | grep -q "<item>"; then
    echo "✅ RSS feed found at: $RSS_URL"
    echo "Sample titles:"
    curl -s "$RSS_URL" | sed -n 's/<title>\(.*\)<\/title>/\1/p' | grep -v "$TARGET_DOMAIN" | head -5
else
    echo "❌ No RSS feed found at standard API endpoint"
fi
echo ""

echo "🎯 RECONNAISSANCE COMPLETE"
echo "=================================="
echo "Check the output above for:"
echo "- Working RSS/API endpoints"
echo "- Data structure patterns"
echo "- Rate limiting indicators"
echo "- Authentication requirements"
