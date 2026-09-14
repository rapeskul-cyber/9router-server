FROM node:22-bookworm-slim

ENV PORT=20128 \
    ROUTER_DATA=/data \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl bsdutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN npm install -g 9router@latest
RUN mkdir -p /data && chmod 777 /data

EXPOSE 20128

# Trik TTY virtual resmi bawaan Linux (bsdutils) biar 9router gak 'Exiting...'
CMD ["script", "-qefc", "9router --host 0.0.0.0 --port 20128", "/dev/null"]
