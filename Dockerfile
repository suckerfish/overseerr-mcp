FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

WORKDIR /app

RUN pip install --no-cache-dir uv==0.8.15

COPY pyproject.toml ./
COPY uv.lock* ./

RUN uv pip install --system --no-cache .

COPY src/ ./src/

RUN adduser --disabled-password --gecos '' --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uv", "run", "python", "-m", "src.server", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080"]
