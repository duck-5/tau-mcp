FROM python:3.12-slim

# Install system dependencies & curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency definitions first for caching
COPY requirements.txt pyproject.toml /app/

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser and system dependencies
RUN playwright install --with-deps chromium

# Copy application source code
COPY . /app/

# Install package in editable mode
RUN pip install --no-cache-dir -e .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8001/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    PORT=8001 \
    HOST=0.0.0.0

CMD ["python", "-m", "tau_mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8001"]
