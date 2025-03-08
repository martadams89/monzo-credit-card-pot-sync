# Stage 1: Build environment
FROM python:3.11-slim-bullseye as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production environment
FROM python:3.11-slim-bullseye

# Set non-root user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# Set working directory and assign ownership
WORKDIR /app
RUN chown appuser:appuser /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appuser . .

# Install runtime dependencies and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Security: Set no-root policy
USER appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-persistent directories for runtime
RUN mkdir -p /tmp/app/logs && \
    chmod 755 /tmp/app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-5000}/main/health || exit 1

# Add metadata
LABEL org.opencontainers.image.title="Monzo Credit Card Pot Sync" \
      org.opencontainers.image.description="Application to sync Monzo pots with credit card balances" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="Your Name <your.email@example.com>" \
      org.opencontainers.image.source="https://github.com/yourusername/monzo-credit-card-pot-sync"

# Expose port
EXPOSE ${PORT:-5000}

# Run with Gunicorn for production
CMD gunicorn 'app:create_app()' \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers=${GUNICORN_WORKERS:-2} \
    --threads=${GUNICORN_THREADS:-4} \
    --worker-class=gthread \
    --worker-tmp-dir=/dev/shm \
    --log-level=${LOG_LEVEL:-info} \
    --access-logfile=- \
    --error-logfile=- \
    --timeout=${GUNICORN_TIMEOUT:-120} \
    --keep-alive=${GUNICORN_KEEP_ALIVE:-5} \
    --max-requests=${GUNICORN_MAX_REQUESTS:-1000} \
    --max-requests-jitter=${GUNICORN_MAX_REQUESTS_JITTER:-100}