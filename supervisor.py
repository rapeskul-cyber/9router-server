#!/usr/bin/env python3
"""
9Router 24/7 Linux Server Supervisor (Railway Compatible)
-------------------------------------------------------
Runs 9Router + optional Cloudflare tunnel + sync to Hugging Face panel/backup.
Safe for Linux VPS, Railway, Docker, and systemd.
"""

import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path
import urllib.request

# ----------------------------- CONFIGURATION ---------------------------------
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
PANEL_REPO = os.environ.get("PANEL_REPO", "sekenhwu/9router-static").strip()
BACKUP_REPO = os.environ.get("BACKUP_REPO", "sekenhwu/9router-backup").strip()
BACKUP_BRANCH = os.environ.get("BACKUP_BRANCH", "backup").strip()

# Railway menginjeksi PORT secara otomatis
APP_PORT = int(os.environ.get("PORT", "20128"))
APP_URL = f"http://127.0.0.1:{APP_PORT}"
ENABLE_TUNNEL = os.environ.get("ENABLE_TUNNEL", "1").strip() != "0"

HOME = Path.home()
DATA_DIR = Path(os.environ.get("ROUTER_DATA", HOME / ".9router" if platform.system() != "Windows" else HOME / "AppData" / "Roaming" / "9router"))
DB_PATH = DATA_DIR / "db" / "data.sqlite"

BASE = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE / ("cloudflared.exe" if platform.system() == "Windows" else "cloudflared")
STATE_FILE = BASE / "tunnel-state.json"
LOG_FILE = BASE / "supervisor.log"

state = {
    "app_running": False,
    "tunnel_url": None,
    "last_check": None,
    "last_backup": None,
    "app_restarts": 0,
    "tunnel_restarts": 0,
    "db_size_bytes": 0,
    "version": "linux-1.0.0",
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def http_get(url: str, timeout: float = 6) -> tuple[int, bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "9Router-Supervisor"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def http_put(url: str, body: bytes, headers: dict, timeout: float = 30) -> int:
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


# ----------------------------- CLOUDFLARED ----------------------------------
def ensure_cloudflared() -> Path:
    if shutil.which("cloudflared"):
        return Path(shutil.which("cloudflared"))
    if CLOUDFLARED_BIN.exists() and os.access(CLOUDFLARED_BIN, os.X_OK):
        return CLOUDFLARED_BIN

    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "amd64" if machine in ("x86_64", "amd64") else "arm64" if "arm" in machine or "aarch" in machine else "386"
    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-{system}-{arch}"
    if system == "windows":
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

    log(f"Downloading cloudflared from {url}...")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(CLOUDFLARED_BIN, "wb") as f:
            f.write(r.read())
        CLOUDFLARED_BIN.chmod(0o755)
        log(f"cloudflared saved: {CLOUDFLARED_BIN}")
        return CLOUDFLARED_BIN
    except Exception as e:
        log(f"Failed downloading cloudflared: {e}")
        return CLOUDFLARED_BIN


def is_app_alive() -> bool:
    code, _ = http_get(f"{APP_URL}/api/health", timeout=6)
    return code == 200


def start_app():
    """Start 9Router if it is not answering."""
    if is_app_alive():
        return None
    exe = shutil.which("9router")
    if not exe:
        exe = str(BASE / "node_modules" / ".bin" / "9router")
        if not Path(exe).exists():
            log("9router binary not found. Install it: npm install -g 9router")
            return None
            
    log(f"Starting 9Router on port {APP_PORT} (host 0.0.0.0)...")
    env = os.environ.copy()
    env["PORT"] = str(APP_PORT)
    env["HOST"] = "0.0.0.0"
    
    try:
        # Menghubungkan stdout/stderr langsung agar terbaca di logs Railway
        proc = subprocess.Popen(
            [exe],
            env=env,
            start_new_session=True,
        )
        state["app_restarts"] += 1
        return proc
    except Exception as e:
        log(f"Failed starting 9Router: {e}")
        return None


def run_tunnel():
    if not ENABLE_TUNNEL:
        log("Tunnel disabled via ENABLE_TUNNEL=0")
        return

    bin_path = ensure_cloudflared()
    tunnel_log = BASE / "tunnel.log"
    url_re = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    while True:
        log("Starting cloudflared tunnel...")
        state["tunnel_restarts"] += 1
        state["tunnel_url"] = None

        try:
            p = subprocess.Popen(
                [str(bin_path), "tunnel", "--url", APP_URL, "--no-autoupdate"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            log(f"Failed launching cloudflared: {e}")
            time.sleep(15)
            continue

        with open(tunnel_log, "a", encoding="utf-8") as lf:
            for line in p.stdout:
                lf.write(line)
                lf.flush()
                m = url_re.search(line)
                if m and not state["tunnel_url"]:
                    u = m.group(0)
                    state["tunnel_url"] = u
                    log(f"Cloudflare Tunnel ONLINE: {u}")
                    try:
                        with open(STATE_FILE, "w", encoding="utf-8") as sf:
                            json.dump({"url": u, "updated_at": datetime.now().isoformat()}, sf, indent=2)
                    except Exception:
                        pass
                    publish_status()

        log("cloudflared exited, restarting in 5s...")
        time.sleep(5)


def publish_status():
    if not HF_TOKEN or not PANEL_REPO:
        return
    body = json.dumps({
        "tunnel_url": state["tunnel_url"],
        "app_running": state["app_running"],
        "port": APP_PORT,
        "updated_at": datetime.now().isoformat(),
        "restarts": state["app_restarts"],
        "db_size": state["db_size_bytes"],
    }, indent=2).encode("utf-8")

    url = f"https://huggingface.co/api/spaces/{PANEL_REPO}/raw/main/status.json"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    status = http_put(url, body, headers)
    log(f"Published status to HF Space ({status})")


def backup_database():
    if not HF_TOKEN or not BACKUP_REPO or not DB_PATH.exists():
        return
    try:
        state["db_size_bytes"] = DB_PATH.stat().st_size
        snap = BASE / "backup-temp.sqlite"
        with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as src, sqlite3.connect(snap) as dst:
            src.backup(dst)

        zip_path = BASE / "9router-backup.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, arcname="db/data.sqlite")

        snap.unlink(missing_ok=True)
        body = zip_path.read_bytes()
        zip_path.unlink(missing_ok=True)

        url = f"https://huggingface.co/api/datasets/{BACKUP_REPO}/raw/{BACKUP_BRANCH}/backup.zip"
        headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/zip"}
        res = http_put(url, body, headers)
        state["last_backup"] = datetime.now().isoformat()
        log(f"Database backed up to HF dataset ({res})")
    except Exception as e:
        log(f"Backup failed: {e}")


def main():
    log("=== 9Router 24/7 Supervisor Started ===")
    log(f"Platform: {platform.system()} {platform.machine()}")
    log(f"App target: {APP_URL}")
    log(f"Data directory: {DATA_DIR}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if ENABLE_TUNNEL:
        t_thread = threading.Thread(target=run_tunnel, daemon=True)
        t_thread.start()

    app_proc = None
    last_backup_time = 0

    while True:
        alive = is_app_alive()
        state["app_running"] = alive
        state["last_check"] = datetime.now().isoformat()

        if not alive:
            log("9Router NOT responding, restarting...")
            if app_proc:
                try:
                    app_proc.terminate()
                    app_proc.wait(timeout=5)
                except Exception:
                    pass
            app_proc = start_app()
            time.sleep(8)
            alive = is_app_alive()
            state["app_running"] = alive
            log(f"9Router status after restart: {'OK' if alive else 'FAIL'}")

        publish_status()

        if time.time() - last_backup_time > 300:
            backup_database()
            last_backup_time = time.time()

        time.sleep(15)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Supervisor stopped by user.")
