#!/bin/bash

# Senior Dev: Production spaCy Funds Detection Deployment
echo "🚀 Deploying spaCy Funds Detection - Senior Dev Approach"
echo "========================================================"

# Phase 1: Install spaCy (if not already installed)
echo "📦 Phase 1: Installing spaCy dependencies..."
cd /Users/mac/ph-eye/backend

# Check if spaCy is already installed
if ! python3 -c "import spacy" 2>/dev/null; then
    echo "Installing spaCy..."
    pip3 install spacy==3.7.4
    
    echo "Downloading English model..."
    python3 -m spacy download en_core_web_sm
else
    echo "✅ spaCy already installed"
fi

# Phase 2: Test the installation
echo ""
echo "🧪 Phase 2: Testing spaCy integration..."
python3 -c "
import spacy
try:
    nlp = spacy.load('en_core_web_sm')
    print('✅ spaCy model loaded successfully')
    
    # Test basic NER
    doc = nlp('DPWH allocates P5 billion for flood control projects')
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    print(f'✅ NER test: {entities}')
except Exception as e:
    print(f'❌ spaCy test failed: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ spaCy installation failed. Exiting."
    exit 1
fi

# Phase 3: Environment Configuration
echo ""
echo "⚙️  Phase 3: Environment Configuration"
echo "Add these to your .env file:"
echo ""
echo "# spaCy Funds Detection"
echo "USE_SPACY_FUNDS=false  # Start with false for safety"
echo ""
echo "Current recommendation:"
echo "1. Deploy with USE_SPACY_FUNDS=false (regex only)"
echo "2. Test in staging with USE_SPACY_FUNDS=true"
echo "3. Enable in production after validation"

# Phase 4: Database Migration Check
echo ""
echo "🗄️  Phase 4: Database Schema Check"
echo "Checking if is_funds column exists..."

# Test the API to see if is_funds column is working
response=$(curl -s "http://localhost:8000/articles?is_funds=true&limit=1" 2>/dev/null)
if echo "$response" | grep -q "is_funds"; then
    echo "✅ is_funds column is working"
else
    echo "⚠️  is_funds column may need to be added to database"
    echo "Run this SQL in Supabase:"
    echo "ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_funds BOOLEAN;"
    echo "CREATE INDEX IF NOT EXISTS idx_articles_is_funds ON articles(is_funds);"
fi

# Phase 5: Test API Endpoints
echo ""
echo "🔌 Phase 5: Testing API Endpoints"

echo "Testing funds classification..."
response=$(curl -s "http://localhost:8000/ml/funds/classify?title=DPWH%20allocates%20P5%20billion&content=Government%20funds%20allocation")
if echo "$response" | grep -q '"ok":true'; then
    echo "✅ Classification API working"
else
    echo "❌ Classification API failed"
fi

echo "Testing funds insights..."
response=$(curl -s "http://localhost:8000/ml/funds/insights?days_back=1")
if echo "$response" | grep -q '"ok":true'; then
    echo "✅ Insights API working"
else
    echo "❌ Insights API failed"
fi

# Phase 6: Performance Baseline
echo ""
echo "📊 Phase 6: Performance Baseline"
echo "Testing classification speed..."

start_time=$(date +%s%N)
for i in {1..10}; do
    curl -s "http://localhost:8000/ml/funds/classify?title=Test%20title%20$i&content=Test%20content" > /dev/null
done
end_time=$(date +%s%N)
duration=$(( (end_time - start_time) / 1000000 ))

echo "10 classifications took ${duration}ms (avg: $((duration/10))ms per request)"

# Phase 7: Deployment Recommendations
echo ""
echo "🎯 Phase 7: Senior Dev Deployment Strategy"
echo "=========================================="
echo ""
echo "1. IMMEDIATE (Safe Deploy):"
echo "   - Deploy with USE_SPACY_FUNDS=false"
echo "   - Test all existing functionality"
echo "   - Monitor performance"
echo ""
echo "2. STAGING (Validation):"
echo "   - Set USE_SPACY_FUNDS=true in staging"
echo "   - Run: curl -X POST 'http://localhost:8000/maintenance/recompute_is_funds'"
echo "   - Compare regex vs spaCy results"
echo "   - Validate precision improvements"
echo ""
echo "3. PRODUCTION (Rollout):"
echo "   - Enable USE_SPACY_FUNDS=true"
echo "   - Run recompute during low-traffic hours"
echo "   - Monitor for 24-48 hours"
echo "   - Rollback if issues detected"
echo ""
echo "4. MONITORING:"
echo "   - Watch API response times"
echo "   - Monitor memory usage (spaCy model ~50MB)"
echo "   - Check classification accuracy"
echo ""
echo "✅ Deployment script complete!"
echo ""
echo "Next steps:"
echo "1. Add USE_SPACY_FUNDS=false to your .env"
echo "2. Restart your backend service"
echo "3. Test the /funds page"
echo "4. When ready, enable spaCy in staging first"

