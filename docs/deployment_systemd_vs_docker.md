# Deployment: systemd vs Docker

Production uses **PostgreSQL**. Choose one deployment method: **systemd + venv** or **Docker Compose**.

## Where must Docker be installed?

| Deployment method | Docker on server? | Docker on your PC? |
|-------------------|-------------------|--------------------|
| **Docker Compose** | **Yes, required** | No (unless you build images locally and push to a registry) |
| **systemd + venv** | No | No |

**Docker deployment:** The app runs inside containers *on the server*. Docker must be installed **on the server**. Your local PC does not need Docker unless you build images locally and push to a registry (e.g. GitHub Container Registry). Typically you SSH to the server, run `git pull`, then `docker compose up -d --build` there.

**systemd deployment:** No Docker anywhere. You install Python + venv on the server and run the app directly.

---

## systemd + venv

### How it works
- Python 3.11 and venv on the server
- App runs as `python app.py` inside the venv
- systemd keeps it running and restarts on crash
- nginx proxies to the app
- PostgreSQL runs as a separate system service

### Pros
- No Docker to install or maintain
- Direct access to logs via `journalctl`
- Easier to debug (same process model as local dev)
- Lower memory footprint
- Fewer moving parts

### Cons
- Must manage Python version and venv yourself
- Dependencies installed on host (potential conflicts)
- Slightly more manual setup for first deploy

### Update workflow (typical 5–15 min)
```bash
cd /opt/task-aversion-system
# Backup DB first (pg_dump or copy)
git pull
source venv/bin/activate
pip install -r requirements.txt  # if requirements changed
# Run migrations if schema changed
sudo systemctl restart task-aversion-app
sudo journalctl -u task-aversion-app -f  # smoke test
```

---

## Docker Compose

### How it works
- `docker-compose.yml` defines app + PostgreSQL containers
- App and DB run in containers on the server
- Volumes persist data
- nginx proxies to the app container

### Pros
- Consistent environment (same image everywhere)
- PostgreSQL and app versioned together
- Easy rollback: `git checkout <prev>` then `docker compose up -d --build`
- Isolated from host (no Python/dep conflicts)

### Cons
- Must install and maintain Docker on the server
- More disk and memory usage
- Debugging slightly more indirect (logs via `docker logs`)

### Update workflow (typical 5–15 min)
```bash
cd /opt/task-aversion-system
# Backup DB volume / pg_dump first
git pull
docker compose up -d --build
docker compose logs -f  # smoke test
```

---

## Recommendation

| Use case | Recommended |
|----------|-------------|
| Single VPS, familiar with Python/venv | systemd + venv |
| Prefer reproducible builds, want isolation | Docker Compose |
| Already have PostgreSQL on host | systemd + venv |
| Want app + DB fully containerized | Docker Compose |

Both approaches support the same PostgreSQL production setup and sub-hour update cycles. Choose based on your preference for simplicity (systemd) vs. isolation/reproducibility (Docker).

---

## Verifying deployments

Log in with your usual Google account after each deploy. Use nginx or firewall IP allowlisting to restrict access to your IP until you have verified the update (see `docs/server_migration_checklist.md` Phase 5).
