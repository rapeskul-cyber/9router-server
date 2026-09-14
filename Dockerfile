# 9Router 24/7 — Linux server image for Railway
FROM node:22-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ROUTER_DATA=/data \
    ENABLE_TUNNEL=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install 9Router secara global
RUN npm install -g 9router@latest

COPY supervisor.py ./

RUN mkdir -p /data && chmod 777 /data

# Catatan: Baris VOLUME dihapus agar tidak error di Railway.
# Persistent data bisa diset lewat menu Volume di Dashboard Railway (/data).

CMD ["python3", "supervisor.py"]
