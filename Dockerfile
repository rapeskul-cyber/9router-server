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

# 9Router installed globally
RUN npm install -g 9router@latest

COPY supervisor.py ./

RUN mkdir -p /data && chmod 777 /data

# Catatan: Baris VOLUME dihapus karena Railway tidak mengizinkannya di Dockerfile.
# Jika butuh data tersimpan permanen, buat Volume langsung via Dashboard Railway ke path /data

CMD ["python3", "supervisor.py"]
