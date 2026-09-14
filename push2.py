import json, subprocess, sys

def cred():
    p = subprocess.run(["git","credential","fill"], input="protocol=https\nhost=github.com\n\n",
                       capture_output=True, text=True)
    for l in p.stdout.splitlines():
        if l.startswith("password="):
            return l[len("password="):]
    sys.exit("no github credential")

tok = cred()
WD = r"C:\Users\User\9router-server"
MSG = ("9Router 24/7 server: Docker + systemd supervisor, tunnel, HF panel/backup\n\n"
       "Linux port of the local Windows supervisor:\n"
       "- health loop restarts 9router (npm bin; no bogus 'start' subcommand)\n"
       "- auto-downloads the right cloudflared for the host architecture\n"
       "- publishes status.json to an HF Space and snapshots data.sqlite to a\n"
       "  private HF dataset via sqlite3.backup (online-consistent copy)\n"
       "- every integration optional: with no HF_TOKEN the app and tunnel still\n"
       "  run; secrets come from the environment and none are committed")

body = json.dumps({"name":"9router-server",
  "description":"Run 9Router 24/7 on your own server: Docker + systemd, auto-restart, cloudflared tunnel, HF status panel and DB backup. No secrets committed.",
  "private":False,"auto_init":False,"has_issues":False})
r = subprocess.run(["curl","-s","-w","%{http_code}","-o","-","-X","POST",
  "-H",f"Authorization: token {tok}","-H","Accept: application/vnd.github+json",
  "https://api.github.com/user/repos","-d",body], capture_output=True, text=True)
code = r.stdout[-3:]
print("create repo ->", code)
if code not in ("201","422"):
    print(r.stdout[:300]); sys.exit(1)

for c in (["git","init","-q"],["git","remote","remove","origin"],["git","add","-A"],
          ["git","-c","user.email=rapeskul@gmail.com","-c","user.name=rapeskul-cyber",
           "commit","-q","-m",MSG],["git","branch","-M","main"]):
    subprocess.run(c, cwd=WD, capture_output=True)
subprocess.run(["git","remote","add","origin",
  "https://rapeskul-cyber@github.com/rapeskul-cyber/9router-server.git"], cwd=WD, capture_output=True)
p = subprocess.run(["git","push","-q","-u","origin","main"], cwd=WD, capture_output=True, text=True)
print("PUSHED_OK" if not p.returncode else "PUSH FAILED: " + (p.stderr or p.stdout)[:300])
v = subprocess.run(["curl","-s","-H",f"Authorization: token {tok}",
  "https://api.github.com/repos/rapeskul-cyber/9router-server"], capture_output=True, text=True)
try:
    d = json.loads(v.stdout); print("repo:", d.get("html_url"), "| size:", d.get("size"), "KB")
except Exception: pass
