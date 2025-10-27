FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY sync-vector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY sync-vector/ ./sync-vector/
COPY scripts/ ./scripts/

# Make scripts executable
RUN chmod +x scripts/*.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV CONFIG_PATH=/app/sync-vector/config/app.yaml

# Expose metrics port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8090/health || exit 1

# Run the service
CMD ["python", "sync-vector/src/main.py"]
