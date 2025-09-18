#!/bin/bash

# Senior Dev ML Analysis Script
# Comprehensive ML pipeline for Philippine news analysis

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE="http://localhost:8000"
WORKER_CONTAINER="ph-eye-worker"

echo -e "${BLUE}🚀 Philippine News ML Analysis Pipeline${NC}"
echo "=================================================="

# Function to check if services are running
check_services() {
    echo -e "${YELLOW}📋 Checking services...${NC}"
    
    # Check if API is running
    if ! curl -s "$API_BASE/health" > /dev/null; then
        echo -e "${RED}❌ API server is not running${NC}"
        echo "Start with: docker-compose up -d"
        exit 1
    fi
    
    # Check if worker is running
    if ! docker-compose ps worker | grep -q "Up"; then
        echo -e "${RED}❌ Celery worker is not running${NC}"
        echo "Start with: docker-compose up -d worker"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All services are running${NC}"
}

# Function to analyze recent articles
analyze_recent() {
    local hours=${1:-24}
    echo -e "${YELLOW}📊 Analyzing articles from last $hours hours...${NC}"
    
    response=$(curl -s -X POST "$API_BASE/ml/political-bias/analyze" \
        -H "Content-Type: application/json" \
        -d "{\"hours_back\": $hours}")
    
    if echo "$response" | grep -q '"ok": true'; then
        echo -e "${GREEN}✅ Analysis queued successfully${NC}"
        echo "$response" | python3 -m json.tool
    else
        echo -e "${RED}❌ Failed to queue analysis${NC}"
        echo "$response"
    fi
}

# Function to analyze specific articles
analyze_specific() {
    local article_ids="$1"
    echo -e "${YELLOW}📊 Analyzing specific articles: $article_ids${NC}"
    
    response=$(curl -s -X POST "$API_BASE/ml/political-bias/analyze" \
        -H "Content-Type: application/json" \
        -d "{\"article_ids\": [$article_ids]}")
    
    if echo "$response" | grep -q '"ok": true'; then
        echo -e "${GREEN}✅ Analysis queued successfully${NC}"
        echo "$response" | python3 -m json.tool
    else
        echo -e "${RED}❌ Failed to queue analysis${NC}"
        echo "$response"
    fi
}

# Function to get bias trends
get_trends() {
    local period=${1:-7d}
    echo -e "${YELLOW}📈 Getting bias trends for period: $period${NC}"
    
    response=$(curl -s "$API_BASE/ml/political-bias/trends?period=$period")
    
    if echo "$response" | grep -q '"ok": true'; then
        echo -e "${GREEN}✅ Trends retrieved successfully${NC}"
        echo "$response" | python3 -m json.tool
    else
        echo -e "${RED}❌ Failed to get trends${NC}"
        echo "$response"
    fi
}

# Function to get source comparison
get_source_comparison() {
    echo -e "${YELLOW}📊 Getting source bias comparison...${NC}"
    
    response=$(curl -s "$API_BASE/ml/political-bias/source-comparison")
    
    if echo "$response" | grep -q '"ok": true'; then
        echo -e "${GREEN}✅ Source comparison retrieved successfully${NC}"
        echo "$response" | python3 -m json.tool
    else
        echo -e "${RED}❌ Failed to get source comparison${NC}"
        echo "$response"
    fi
}

# Function to monitor worker logs
monitor_worker() {
    echo -e "${YELLOW}👀 Monitoring worker logs (Ctrl+C to stop)...${NC}"
    docker-compose logs -f worker | grep -E "(bias|political|analysis|task)"
}

# Function to run comprehensive analysis
run_comprehensive() {
    echo -e "${YELLOW}🔄 Running comprehensive ML analysis...${NC}"
    
    # Get recent articles
    echo -e "${BLUE}Step 1: Getting recent articles...${NC}"
    recent_response=$(curl -s "$API_BASE/articles/recent?limit=100")
    article_count=$(echo "$recent_response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('articles', [])))")
    
    if [ "$article_count" -eq 0 ]; then
        echo -e "${RED}❌ No recent articles found${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Found $article_count recent articles${NC}"
    
    # Run analysis
    echo -e "${BLUE}Step 2: Running ML analysis...${NC}"
    analyze_recent 24
    
    # Wait a bit for processing
    echo -e "${BLUE}Step 3: Waiting for analysis to complete...${NC}"
    sleep 10
    
    # Get results
    echo -e "${BLUE}Step 4: Getting analysis results...${NC}"
    get_trends 1d
    get_source_comparison
}

# Function to show help
show_help() {
    echo -e "${BLUE}Philippine News ML Analysis Script${NC}"
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  recent [hours]     - Analyze articles from last N hours (default: 24)"
    echo "  specific <ids>     - Analyze specific article IDs (comma-separated)"
    echo "  trends [period]    - Get bias trends (1d, 7d, 30d)"
    echo "  sources            - Get source bias comparison"
    echo "  monitor            - Monitor worker logs"
    echo "  comprehensive      - Run full analysis pipeline"
    echo "  check              - Check if services are running"
    echo "  help               - Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 recent 48                    # Analyze last 48 hours"
    echo "  $0 specific 1,2,3,4,5          # Analyze specific articles"
    echo "  $0 trends 7d                    # Get 7-day trends"
    echo "  $0 comprehensive               # Run full pipeline"
}

# Main script logic
case "${1:-help}" in
    "recent")
        check_services
        analyze_recent "${2:-24}"
        ;;
    "specific")
        if [ -z "$2" ]; then
            echo -e "${RED}❌ Please provide article IDs${NC}"
            exit 1
        fi
        check_services
        analyze_specific "$2"
        ;;
    "trends")
        check_services
        get_trends "${2:-7d}"
        ;;
    "sources")
        check_services
        get_source_comparison
        ;;
    "monitor")
        monitor_worker
        ;;
    "comprehensive")
        check_services
        run_comprehensive
        ;;
    "check")
        check_services
        ;;
    "help"|*)
        show_help
        ;;
esac
