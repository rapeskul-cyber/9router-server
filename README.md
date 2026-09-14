# 9Router 24/7 — Self-Hosted Server

Run [9Router](https://www.npmjs.com/package/9router) 24/7 on **your own server**
(VPS / home server / Docker), with automatic restart, an optional public tunnel,
and periodic database backup.

This repository is the **Linux/server** port. It contains no secrets and no
Windows binaries — everything is configured through environment variables.

## What it does
- **Keeps 9Router alive** — polls `/api/health`, restarts the process if it dies.
- **Public access (optional)** — pulls `cloudflared` automatically and opens a
  quick tunnel, writing the current URL to `tunnel-state.json`.
- **Status panel (optional)** — publishes `status.json` to a Hugging Face Space.
- **Backup (optional)** — snapshots the SQLite DB every 5 minutes to a private
  Hugging Face dataset (online-consistent copy via `sqlite3.backup`, not a raw
  file copy of a live DB).

Every integration is optional: with no `HF_TOKEN` the app and tunnel still run.

## Quick start — Docker (recommended)

```bash
git clone https://github.com/rapeskul-cyber/9router-server.git
cd 9router-server

cp .env.example .env
nano .env                 # put your HF_TOKEN here (or leave empty)

docker compose up -d --build
docker compose logs -f
```

9Router is then on `http://<server-ip>:20128`.

Data survives container rebuilds in the `9router-data` volume (`/data`).

## Quick start — systemd (no Docker)

```bash
sudo apt update && sudo apt install -y python3 nodejs npm
sudo npm install -g 9router

sudo mkdir -p /opt/9router-server
sudo cp supervisor.py /opt/9router-server/
sudo chown -R ubuntu:ubuntu /opt/9router-server

# secrets live outside the unit file
sudo install -m 600 /dev/null /etc/9router.env
echo 'HF_TOKEN=' | sudo tee /etc/9router.env

sudo cp 9router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now 9router
journalctl -u 9router -f
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `20128` | Port 9Router listens on |
| `ROUTER_DATA` | `~/.9router` | 9Router data directory (contains `db/data.sqlite`) |
| `ENABLE_TUNNEL` | `1` | `1` = start a cloudflared quick tunnel, `0` = LAN only |
| `HF_TOKEN` | *(empty)* | Enables the status panel + backups. Leave empty to disable both |
| `PANEL_REPO` | `sekenhwu/9router-static` | HF Space receiving `status.json` |
| `BACKUP_REPO` | `sekenhwu/9router-backup` | HF dataset receiving `backup.zip` |
| `BACKUP_BRANCH` | `backup` | Branch of the backup dataset |

## Files
| File | Purpose |
|---|---|
| `supervisor.py` | The supervisor: health loop, tunnel, panel publish, backup |
| `Dockerfile` | Node 22 + Python 3 image, healthcheck built in |
| `docker-compose.yml` | One-command deploy with a persistent volume |
| `9router.service` | systemd unit alternative |
| `.env.example` | Documented template (copy to `.env`, never commit `.env`) |

## Security notes
- **No credentials in this repo.** The token is read from `HF_TOKEN` at runtime;
  `.env` is git-ignored, and container/systemd setups keep it outside the code.
- The cloudflared **quick tunnel URL is public and unauthenticated** — anyone
  with the link reaches your 9Router. Set a dashboard password in 9Router and
  prefer `ENABLE_TUNNEL=0` behind a VPN/reverse proxy with auth for real use.
- Backups go to a **private** HF dataset — verify the dataset is private before
  trusting it with `data.sqlite`.
- Deploying on a VPS: restrict `PORT` with a firewall
  (`ufw allow 22,20128/tcp`) and do not expose the dashboard to the world.

## Verify it is running
```bash
curl -fsS http://127.0.0.1:20128/api/health && echo " OK"
cat tunnel-state.json          # current public URL, when tunnel is enabled
tail -f supervisor.log         # what the supervisor is doing
```
