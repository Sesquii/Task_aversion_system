# Deployment Configuration (Phase 3)

Templates for production deployment. See `docs/server_migration_checklist.md` for the full deployment guide.

## Contents

| File | Purpose |
|------|---------|
| `env.production.example` | Environment variables template. Copy to `task_aversion_app/.env.production` and fill in real values. |
| `systemd/task-aversion-app.service` | systemd unit file. Copy to `/etc/systemd/system/` and edit `APP_DIR`, `YOUR_USER`. |
| `nginx/task-aversion-system.conf` | Nginx reverse proxy config. Copy to `/etc/nginx/sites-available/` and edit `server_name`. |

## Quick Setup

### 1. Environment

```bash
cp deploy/env.production.example task_aversion_app/.env.production
# Edit .env.production - set DATABASE_URL, STORAGE_SECRET, OAuth credentials, etc.
chmod 600 task_aversion_app/.env.production
```

### 2. systemd

```bash
# Edit the service file: replace APP_DIR and YOUR_USER
sudo cp deploy/systemd/task-aversion-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable task-aversion-app
sudo systemctl start task-aversion-app
```

### 3. Nginx

```bash
sudo cp deploy/nginx/task-aversion-system.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/task-aversion-system.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 4. TLS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d TaskAversionSystem.com -d www.TaskAversionSystem.com
```

## Deployment Method

For systemd vs Docker comparison, see `docs/deployment_systemd_vs_docker.md`.
