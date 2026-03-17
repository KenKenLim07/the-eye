#!/bin/bash
# Senior Dev: spaCy Installation Script
# Solves dependency conflicts and installs spaCy properly

set -e

echo "🚀 Senior Dev spaCy Installation"
echo "================================="

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider using: python3 -m venv venv && source venv/bin/activate"
fi

# Install spaCy with specific approach to avoid conflicts
echo "📦 Installing spaCy with conflict resolution..."

# Method 1: Install spaCy first, then FastAPI without CLI
pip install --no-cache-dir spacy==3.7.4

# Install FastAPI without CLI to avoid typer conflict
pip install --no-cache-dir "fastapi==0.104.1" --no-deps
pip install --no-cache-dir starlette==0.27.0
pip install --no-cache-dir typing-extensions>=4.8.0
pip install --no-cache-dir anyio<4.0.0,>=3.7.1

# Install other dependencies
pip install --no-cache-dir uvicorn[standard]==0.30.1
pip install --no-cache-dir celery==5.3.6
pip install --no-cache-dir redis==5.0.4
pip install --no-cache-dir python-dotenv==1.0.1
pip install --no-cache-dir pydantic==2.7.4
pip install --no-cache-dir httpx==0.27.0
pip install --no-cache-dir beautifulsoup4==4.12.3
pip install --no-cache-dir lxml==5.2.2
pip install --no-cache-dir playwright==1.46.0
pip install --no-cache-dir supabase==2.6.0
pip install --no-cache-dir nltk==3.9.1
pip install --no-cache-dir scikit-learn==1.5.1
pip install --no-cache-dir pandas==2.2.2
pip install --no-cache-dir numpy==2.0.1
pip install --no-cache-dir celery-redbeat==2.3.3
pip install --no-cache-dir brotli>=1.0.9

echo "✅ Dependencies installed successfully"

# Download spaCy model
echo "📥 Downloading spaCy English model..."
python -m spacy download en_core_web_sm

echo "🧪 Testing spaCy installation..."
python -c "
import spacy
nlp = spacy.load('en_core_web_sm')
doc = nlp('DPWH allocates P5 billion for flood control projects.')
print('✅ spaCy working!')
print(f'Entities: {[(ent.text, ent.label_) for ent in doc.ents]}')
"

echo ""
echo "🎉 spaCy installation complete!"
echo "   You can now enable spaCy analytics with:"
echo "   export USE_SPACY_ANALYTICS=true"
echo "   spaCy is used for NER; no feature flag is required."













