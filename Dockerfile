# BIP - Build-in-Public Automation System
# Multi-stage Docker build

FROM python:3.12-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gnupg \
    tzdata \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 18
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium browser
RUN playwright install chromium \
    && playwright install-deps chromium

# Copy MCP server files and build
COPY mcp-servers/social-media-mcp/package*.json ./mcp-servers/social-media-mcp/
WORKDIR /app/mcp-servers/social-media-mcp
RUN npm ci

COPY mcp-servers/social-media-mcp/src ./src
COPY mcp-servers/social-media-mcp/tsconfig.json .
COPY mcp-servers/social-media-mcp/direct-post.js .
RUN npm run build \
    && npm prune --production

# Copy application source
WORKDIR /app
COPY src/ ./src/
COPY templates/ ./templates/
COPY bip ./bip

# Create directories for volume mounts
RUN mkdir -p /app/data /app/config /app/logs /projects

# Set permissions
RUN chmod +x /app/bip

# Default command
ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["--help"]
