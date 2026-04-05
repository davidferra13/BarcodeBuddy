# Python 3.12 pinned for reproducibility (supports 3.10-3.13).
# This image runs the web application only. The ingestion service (main.py)
# requires local filesystem access to hot-folder directories and should be
# run separately on the host or in a companion container with volume mounts.
FROM python:3.12-slim

# System dependencies for OpenCV, PyMuPDF, and zxing-cpp
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY stats.py main.py config.json ./

# Runtime data directories (will be a mounted volume in production)
RUN mkdir -p data/input data/processing data/output data/rejected data/logs

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "stats.py", "--host", "0.0.0.0", "--port", "8080"]
