FROM python:3.12-slim

# Install curl for health checks
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and data directory
RUN useradd -m -u 1000 -s /bin/bash app \
    && mkdir -p /data \
    && chown -R app:app /data

WORKDIR /app

# Install dependencies as root (system-wide), leveraging layer cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app app /app/app/
COPY --chown=app:app config.yaml /app/config.yaml
COPY --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh

# Switch to non-root user
USER app

VOLUME ["/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["api"]
