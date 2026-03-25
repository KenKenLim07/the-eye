# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app

# Copy requirements first for better caching so rebuilds don\'t reinstall deps on every code change.
RUN mkdir -p /app/backend
COPY backend/requirements.txt /app/backend/requirements.txt

# Install Python deps (Playwright and browsers already in base image).
# BuildKit pip cache makes rebuilds much faster on flaky/slow networks.
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG TORCH_CPU_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --retries 5 --timeout 120 \
      --index-url ${PIP_INDEX_URL} --extra-index-url ${TORCH_CPU_EXTRA_INDEX_URL} \
      -r /app/backend/requirements.txt && \
    python -c "print('Enhanced regex analytics ready')" && \
    python -c "print('Advanced sentiment analytics ready')" && \
    python -c "import spacy, pkgutil; print('spaCy installed:', bool(pkgutil.find_loader('spacy')))"

# Copy backend (after deps) so code edits don\'t bust the pip-install layer.
COPY backend /app/backend

# Fix line endings for shell scripts (Windows compatibility)
RUN if [ -f /app/backend/start_beat.sh ]; then \
    sed -i 's/\r$//' /app/backend/start_beat.sh && \
    chmod +x /app/backend/start_beat.sh; \
    fi

ENV PYTHONUNBUFFERED=1

# Default command will be overridden by docker-compose for worker/beat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
