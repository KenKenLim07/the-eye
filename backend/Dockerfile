# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app

# Copy backend
COPY backend /app/backend

# Install Python deps (Playwright and browsers already in base image)
# Install Python deps with spaCy support
RUN pip install --no-cache-dir -r /app/backend/requirements.txt && \
    python -m spacy download en_core_web_sm && \
    python -c "print('Installed deps OK')"

ENV PYTHONUNBUFFERED=1

# Default command will be overridden by docker-compose for worker/beat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 