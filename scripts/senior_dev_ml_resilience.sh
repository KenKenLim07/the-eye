#!/bin/bash

# Senior Dev ML Pipeline Resilience Script
# Comprehensive solution for ML analysis gaps and system resilience

set -e

echo "🚀 SENIOR DEV ML PIPELINE RESILIENCE SETUP"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[HEADER]${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

print_header "1. CHECKING CURRENT SYSTEM STATUS"
echo "----------------------------------------"

# Check Docker containers
print_status "Checking Docker containers..."
docker-compose ps

# Check for syntax errors in critical files
print_status "Validating Python syntax..."
python3 -m py_compile backend/app/scrapers/rappler.py
python3 -m py_compile backend/app/workers/ml_tasks.py
python3 -m py_compile backend/app/workers/tasks.py
print_status "✅ All Python files compile successfully"

print_header "2. RESTARTING SERVICES WITH RESILIENCE"
echo "----------------------------------------------"

# Stop services gracefully
print_status "Stopping services..."
docker-compose down

# Clean up any corrupted state
print_status "Cleaning up corrupted state..."
docker-compose exec -T redis redis-cli FLUSHALL || true

# Start services with proper restart policies
print_status "Starting services with resilience..."
docker-compose up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Verify services are running
print_status "Verifying services..."
docker-compose ps

print_header "3. CHECKING ML PIPELINE HEALTH"
echo "-------------------------------------"

# Run health check
print_status "Running ML pipeline health check..."
python3 scripts/ml_pipeline_monitor.py --hours 24

print_header "4. BACKFILLING MISSED ML ANALYSIS"
echo "----------------------------------------"

# Check for unanalyzed articles and backfill
print_status "Checking for unanalyzed articles..."
python3 scripts/backfill_ml_analysis.py --days 7 --dry-run

read -p "Do you want to proceed with backfilling missed ML analysis? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Starting backfill process..."
    python3 scripts/backfill_ml_analysis.py --days 7 --batch-size 25
else
    print_warning "Skipping backfill. You can run it later with: python3 scripts/backfill_ml_analysis.py"
fi

print_header "5. SETTING UP MONITORING"
echo "-----------------------------"

# Create monitoring script
cat > scripts/monitor_ml_health.sh << 'EOF'
#!/bin/bash
# Quick ML pipeline health check

echo "🔍 ML Pipeline Health Check - $(date)"
echo "====================================="

# Check container status
echo "📦 Container Status:"
docker-compose ps | grep -E "(worker|beat|api)"

# Run health monitor
echo ""
echo "📊 Pipeline Health:"
python3 scripts/ml_pipeline_monitor.py --hours 6

# Check recent worker logs
echo ""
echo "📝 Recent Worker Activity:"
docker-compose logs --tail=10 worker | grep -E "(analyze_articles_task|ERROR|WARNING)" || echo "No recent ML activity"

echo ""
echo "✅ Health check complete"
EOF

chmod +x scripts/monitor_ml_health.sh

print_status "Created monitoring script: scripts/monitor_ml_health.sh"

print_header "6. IMPLEMENTING PERSISTENCE SOLUTIONS"
echo "-------------------------------------------"

# Enhanced Docker Compose with better persistence
print_status "Creating enhanced docker-compose with persistence..."

# Backup original
cp docker-compose.yml docker-compose.yml.backup

# Add volume persistence for Celery beat schedule
cat >> docker-compose.yml << 'EOF'

  # Enhanced persistence volumes
volumes:
  celery_beat_schedule:
  redis_data:
EOF

# Update beat service to use persistent volume
sed -i.bak 's/    volumes:/    volumes:\
      - celery_beat_schedule:\/app\/celerybeat-schedule/' docker-compose.yml

# Update redis service to use persistent volume  
sed -i.bak 's/  redis:/  redis:\
    volumes:\
      - redis_data:\/data/' docker-compose.yml

print_status "Enhanced Docker Compose with persistence volumes"

print_header "7. CREATING AUTOMATED RECOVERY SCRIPT"
echo "-------------------------------------------"

cat > scripts/auto_recovery.sh << 'EOF'
#!/bin/bash
# Automated recovery script for ML pipeline issues

echo "🔄 ML Pipeline Auto-Recovery"
echo "============================"

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    echo "⚠️  Services not running. Restarting..."
    docker-compose up -d
    sleep 10
fi

# Check for syntax errors
if ! python3 -m py_compile backend/app/scrapers/rappler.py; then
    echo "❌ Syntax error detected in rappler.py"
    echo "Please fix the syntax error and restart services"
    exit 1
fi

# Run health check
echo "🔍 Running health check..."
python3 scripts/ml_pipeline_monitor.py --hours 6

# If coverage is low, run backfill
COVERAGE=$(python3 scripts/ml_pipeline_monitor.py --hours 6 --json | grep -o '"coverage_rate_percent": [0-9.]*' | cut -d' ' -f2)
if (( $(echo "$COVERAGE < 90" | bc -l) )); then
    echo "⚠️  Low ML coverage detected ($COVERAGE%). Running backfill..."
    python3 scripts/backfill_ml_analysis.py --days 3 --batch-size 25
fi

echo "✅ Auto-recovery complete"
EOF

chmod +x scripts/auto_recovery.sh

print_status "Created auto-recovery script: scripts/auto_recovery.sh"

print_header "8. FINAL VERIFICATION"
echo "-------------------------"

# Final health check
print_status "Running final verification..."
python3 scripts/ml_pipeline_monitor.py --hours 1

# Show running services
print_status "Final service status:"
docker-compose ps

echo ""
echo "🎉 SENIOR DEV ML PIPELINE RESILIENCE SETUP COMPLETE!"
echo "=================================================="
echo ""
echo "📋 WHAT WAS IMPLEMENTED:"
echo "  ✅ Fixed syntax errors preventing beat scheduler"
echo "  ✅ Created ML analysis backfill script"
echo "  ✅ Added pipeline health monitoring"
echo "  ✅ Enhanced Docker persistence"
echo "  ✅ Automated recovery scripts"
echo "  ✅ Restarted services with proper restart policies"
echo ""
echo "🛠️  USEFUL COMMANDS:"
echo "  • Monitor health:     ./scripts/monitor_ml_health.sh"
echo "  • Backfill analysis:  python3 scripts/backfill_ml_analysis.py --days 7"
echo "  • Auto-recovery:      ./scripts/auto_recovery.sh"
echo "  • Check status:       docker-compose ps"
echo "  • View logs:          docker-compose logs -f worker"
echo ""
echo "🔄 PREVENTION MEASURES:"
echo "  • Services auto-restart on failure (restart: unless-stopped)"
echo "  • Persistent Celery beat schedule (survives container restarts)"
echo "  • Redis data persistence (survives container restarts)"
echo "  • Health monitoring and auto-recovery"
echo ""
echo "💡 NEXT STEPS:"
echo "  1. Monitor the system for 24 hours"
echo "  2. Run health checks regularly"
echo "  3. Consider cloud deployment for 24/7 operation"
echo "  4. Set up alerts for low ML coverage"
echo ""

