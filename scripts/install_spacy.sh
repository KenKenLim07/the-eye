#!/bin/bash

# Senior Dev: Install spaCy to fix accuracy issues
echo "🔧 Installing spaCy to Fix Funds Detection Accuracy"
echo "=================================================="

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install spaCy
echo "🤖 Installing spaCy..."
pip install spacy==3.7.4

# Download English model
echo "📥 Downloading English model..."
python -m spacy download en_core_web_sm

# Test installation
echo "🧪 Testing spaCy installation..."
python -c "
import spacy
try:
    nlp = spacy.load('en_core_web_sm')
    print('✅ spaCy model loaded successfully')
    
    # Test NER on funds-related text
    doc = nlp('DPWH allocates P5 billion for flood control projects')
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    print(f'✅ NER test: {entities}')
    
    # Test on disaster text
    doc2 = nlp('6.9 magnitude earthquake hits Cebu P40M in damages')
    entities2 = [(ent.text, ent.label_) for ent in doc2.ents]
    print(f'✅ Disaster NER test: {entities2}')
    
except Exception as e:
    print(f'❌ spaCy test failed: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ spaCy installation successful!"
    echo ""
    echo "🎯 Next Steps:"
    echo "1. Add to your .env file: USE_SPACY_FUNDS=true"
    echo "2. Restart your backend service"
    echo "3. Test accuracy improvements"
    echo ""
    echo "📊 Expected Improvements:"
    echo "- Filter out earthquake/typhoon disasters"
    echo "- Better government entity recognition"
    echo "- Higher precision in funds detection"
else
    echo "❌ spaCy installation failed"
    exit 1
fi





