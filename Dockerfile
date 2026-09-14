FROM node:22-bookworm-slim

ENV PORT=20128 \
    ROUTER_DATA=/data \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN npm install -g 9router@latest
RUN mkdir -p /data && chmod 777 /data

EXPOSE 20128

# Jalankan 9router di background, lalu tahan container agar tidak exit
CMD ["sh", "-c", "9router --host 0.0.0.0 --port 20128 < /dev/null & tail -f /dev/null"]
