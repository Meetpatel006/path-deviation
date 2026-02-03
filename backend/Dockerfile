# =============================================================================
# GPS Path Deviation Detection Backend - Dockerfile
# Multi-stage build for optimized image size
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and build wheels
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies for shapely (GEOS), numpy, and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgeos-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime - Minimal image with only runtime dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies (GEOS for shapely, PostgreSQL client library)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-c1v5 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy pre-built wheels from builder stage and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY ./app ./app

# Create directories for persistent data
RUN mkdir -p /app/data /app/logs \
    && chown -R appuser:appuser /app

# Switch to non-root user for security
USER appuser

# -----------------------------------------------------------------------------
# Environment Configuration
# -----------------------------------------------------------------------------
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DATABASE_PATH=/app/data/path_deviation.db
ENV LOG_FILE=/app/logs/app.log
ENV LOG_LEVEL=INFO

# Expose the application port
EXPOSE 8000

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# -----------------------------------------------------------------------------
# Start Command - 4 workers for production concurrency
# -----------------------------------------------------------------------------
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
