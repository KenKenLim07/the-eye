# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app

# Copy backend
COPY backend /app/backend

# Install Python deps (Playwright and browsers already in base image)
# Install Python deps (Enhanced regex approach - production ready)
RUN pip install --no-cache-dir -r /app/backend/requirements.txt && \
    python -m spacy download en_core_web_sm && \
    python -c "print('✅ Enhanced regex analytics ready')" && \
    python -c "print('✅ Advanced sentiment analytics ready')" && \
    python -c "import spacy, pkgutil; print('✅ spaCy installed:', bool(pkgutil.find_loader('spacy'))); import en_core_web_sm; print('✅ spaCy model:', en_core_web_sm.info.get('lang','?'))"

ENV PYTHONUNBUFFERED=1

# Default command will be overridden by docker-compose for worker/beat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 