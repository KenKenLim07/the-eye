#!/bin/bash

# Senior Dev: Complete Database Analysis Script
# Analyzes ALL articles in database with pagination support

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# Configuration
API_BASE="http://localhost:8000"
BATCH_SIZE=100
MAX_ARTICLES=10000

echo -e "${BLUE}🚀 Complete Database Analysis Pipeline${NC}"
echo "=================================================="

# Function to get total article count
get_total_count() {
    echo -e "${YELLOW}📊 Getting total article count...${NC}"
    
    # Use the dashboard endpoint to get total count
    response=$(curl -s "$API_BASE/dashboard/comprehensive?period=30d")
    
    if echo "$response" | grep -q '"ok": true'; then
        total=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['articles']['total'])
")
        echo -e "${GREEN}✅ Total articles: $total${NC}"
        return $total
    else
        echo -e "${RED}❌ Failed to get article count${NC}"
        return 0
    fi
}

# Function to analyze all articles in batches
analyze_all_articles() {
    local total=$1
    local batch_size=${2:-100}
    
    echo -e "${YELLOW}🔄 Starting comprehensive analysis of $total articles...${NC}"
    echo -e "${BLUE}Batch size: $batch_size articles${NC}"
    
    # Calculate number of batches
    local batches=$(( (total + batch_size - 1) / batch_size ))
    echo -e "${PURPLE}Total batches: $batches${NC}"
    
    local processed=0
    local successful=0
    local failed=0
    
    for ((i=0; i<batches; i++)); do
        local offset=$((i * batch_size))
        local current_batch_size=$batch_size
        
        # Adjust last batch size
        if [ $((offset + batch_size)) -gt $total ]; then
            current_batch_size=$((total - offset))
        fi
        
        echo -e "${YELLOW}📦 Processing batch $((i+1))/$batches (articles $((offset+1))-$((offset+current_batch_size)))...${NC}"
        
        # Queue analysis for this batch
        response=$(curl -s -X POST "$API_BASE/ml/political-bias/analyze" \
            -H "Content-Type: application/json" \
            -d "{\"offset\": $offset, \"limit\": $current_batch_size}")
        
        if echo "$response" | grep -q '"ok": true'; then
            echo -e "${GREEN}✅ Batch $((i+1)) queued successfully${NC}"
            successful=$((successful + 1))
        else
            echo -e "${RED}❌ Batch $((i+1)) failed${NC}"
            failed=$((failed + 1))
        fi
        
        processed=$((processed + current_batch_size))
        
        # Progress update
        local progress=$(( (processed * 100) / total ))
        echo -e "${BLUE}Progress: $progress% ($processed/$total articles)${NC}"
        
        # Small delay between batches to avoid overwhelming the system
        sleep 2
    done
    
    echo -e "${GREEN}🎉 Analysis queuing completed!${NC}"
    echo -e "${BLUE}Summary:${NC}"
    echo -e "  Total batches: $batches"
    echo -e "  Successful: $successful"
    echo -e "  Failed: $failed"
    echo -e "  Total articles: $processed"
}

# Function to monitor progress
monitor_progress() {
    echo -e "${YELLOW}👀 Monitoring analysis progress...${NC}"
    echo -e "${BLUE}Press Ctrl+C to stop monitoring${NC}"
    
    while true; do
        # Get current analysis count
        response=$(curl -s "$API_BASE/dashboard/comprehensive?period=30d")
        
        if echo "$response" | grep -q '"ok": true'; then
            bias_count=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['political_bias']['total_analyses'])
")
            
            total_articles=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['articles']['total'])
")
            
            progress=$(( (bias_count * 100) / total_articles ))
            echo -e "${GREEN}📊 Progress: $progress% ($bias_count/$total_articles analyses completed)${NC}"
        else
            echo -e "${RED}❌ Failed to get progress${NC}"
        fi
        
        sleep 10
    done
}

# Function to get final results
get_final_results() {
    echo -e "${YELLOW}📈 Getting final analysis results...${NC}"
    
    # Get comprehensive dashboard data
    response=$(curl -s "$API_BASE/dashboard/comprehensive?period=30d")
    
    if echo "$response" | grep -q '"ok": true'; then
        echo -e "${GREEN}✅ Final Results:${NC}"
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)

print(f'📊 Total Articles: {data[\"articles\"][\"total\"]}')
print(f'📊 Sentiment Analyses: {data[\"sentiment\"][\"total_analyses\"]}')
print(f'📊 Political Bias Analyses: {data[\"political_bias\"][\"total_analyses\"]}')
print(f'📊 Sources Analyzed: {len(data[\"source_comparison\"])}')

print(f'\\n🎯 Political Bias Summary:')
print(f'  Average Bias Score: {data[\"political_bias\"][\"avg_bias_score\"]}')
print(f'  Average Confidence: {data[\"political_bias\"][\"avg_confidence\"]}')

print(f'\\n📈 Bias Distribution:')
for direction, count in data[\"political_bias\"][\"distribution\"].items():
    print(f'  {direction}: {count}')

print(f'\\n📰 Source Comparison:')
for source in data[\"source_comparison\"][:5]:  # Top 5
    print(f'  {source[\"source\"]}: {source[\"political_bias\"][\"avg_bias_score\"]} bias, {source[\"article_count\"]} articles')
"
    else
        echo -e "${RED}❌ Failed to get final results${NC}"
    fi
}

# Function to create frontend-ready data export
export_frontend_data() {
    echo -e "${YELLOW}📤 Exporting frontend-ready data...${NC}"
    
    # Get comprehensive data
    response=$(curl -s "$API_BASE/dashboard/comprehensive?period=30d")
    
    if echo "$response" | grep -q '"ok": true'; then
        # Save to file
        echo "$response" | python3 -m json.tool > frontend_data.json
        
        echo -e "${GREEN}✅ Frontend data exported to frontend_data.json${NC}"
        echo -e "${BLUE}File size: $(wc -c < frontend_data.json) bytes${NC}"
        
        # Create a summary file
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)

summary = {
    'total_articles': data['articles']['total'],
    'total_analyses': data['political_bias']['total_analyses'],
    'avg_bias_score': data['political_bias']['avg_bias_score'],
    'avg_confidence': data['political_bias']['avg_confidence'],
    'bias_distribution': data['political_bias']['distribution'],
    'top_sources': [
        {
            'source': s['source'],
            'bias_score': s['political_bias']['avg_bias_score'],
            'article_count': s['article_count']
        }
        for s in data['source_comparison'][:10]
    ],
    'generated_at': data['generated_at']
}

with open('frontend_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
" > /dev/null
        
        echo -e "${GREEN}✅ Summary exported to frontend_summary.json${NC}"
    else
        echo -e "${RED}❌ Failed to export data${NC}"
    fi
}

# Main script logic
case "${1:-help}" in
    "count")
        get_total_count
        ;;
    "analyze")
        total=$(get_total_count)
        if [ $total -gt 0 ]; then
            analyze_all_articles $total "${2:-100}"
        fi
        ;;
    "monitor")
        monitor_progress
        ;;
    "results")
        get_final_results
        ;;
    "export")
        export_frontend_data
        ;;
    "full")
        echo -e "${PURPLE}🚀 Running FULL analysis pipeline...${NC}"
        total=$(get_total_count)
        if [ $total -gt 0 ]; then
            analyze_all_articles $total "${2:-100}"
            echo -e "${YELLOW}⏳ Waiting for analysis to complete...${NC}"
            sleep 30
            get_final_results
            export_frontend_data
        fi
        ;;
    "help"|*)
        echo -e "${BLUE}Complete Database Analysis Script${NC}"
        echo "Usage: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  count              - Get total article count"
        echo "  analyze [batch]     - Analyze all articles (batch size: 100)"
        echo "  monitor            - Monitor analysis progress"
        echo "  results            - Get final analysis results"
        echo "  export             - Export frontend-ready data"
        echo "  full [batch]       - Run complete pipeline"
        echo "  help               - Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 count                    # Check total articles"
        echo "  $0 analyze 50               # Analyze with batch size 50"
        echo "  $0 full 200                 # Complete pipeline with batch size 200"
        echo "  $0 monitor                  # Watch progress"
        echo "  $0 export                   # Export for frontend"
        ;;
esac
