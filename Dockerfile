# 9Router 24/7 — Linux server image
# Runs 9Router (Node) + supervisor (Python) + auto cloudflared tunnel.
# Build:  docker build -t 9router-server .
# Run:    docker run -d --name 9router --restart unless-stopped -p 20128:20128 \
#           -e HF_TOKEN=*** -v 9router-data:/data 9router-server

FROM node:22-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=20128 \
    ROUTER_DATA=/data \
    ENABLE_TUNNEL=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 9Router installed globally so `npx` never needs a network round-trip at runtime
RUN npm install -g 9router@latest

COPY supervisor.py ./

RUN mkdir -p /data && chmod 777 /data

VOLUME ["/data"]
EXPOSE 20128

HEALTHCHECK --interval=60s --timeout=10s --start-period=90s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

CMD ["python3", "supervisor.py"]
