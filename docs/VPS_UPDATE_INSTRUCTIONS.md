# VPS Update Instructions

Quick reference for updating the Task Aversion System on your VPS.

## Prerequisites

- SSH access to VPS
- App deployed at `/home/brandon/Task_aversion_system`

## One-command update (recommended)

From the repo root on the VPS (after `git pull` or already up to date):

```bash
cd ~/Task_aversion_system
bash deploy/update_vps.sh
```

The script runs the full workflow automatically. It **pauses once** before backup/migrations/restart and says: *"Press Enter to continue (then enter password when prompted)."* When you press Enter, it runs the backup, migration checks, all migrations (001–013), and `sudo systemctl restart`; enter your password when sudo (or PostgreSQL, if prompted) asks for it.

To use a different repo path:

```bash
REPO_ROOT=/path/to/Task_aversion_system bash deploy/update_vps.sh
```

## Update Workflow (manual steps)

### 1. SSH into VPS

```bash
ssh brandon@your-server-ip
```

### 2. Pull latest code

```bash
cd ~/Task_aversion_system
git pull origin main
```

### 3. Activate venv and update dependencies

```bash
cd task_aversion_app
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Load environment variables

The migration scripts need `DATABASE_URL` from your production environment:

```bash
set -a
source .env.production
set +a
```

### 5. Backup database (before migrations)

```bash
~/backup_task_aversion.sh
```

Or manually:

```bash
pg_dump -h localhost -U task_aversion_user task_aversion_system > ~/backups/backup_$(date +%Y%m%d_%H%M%S).sql
```

### 6. Check migration status

```bash
python PostgreSQL_migration/check_migration_status.py
```

### 7. Run any new migrations

Run any migrations that show as "not applied":

```bash
# Example for migrations 012 and 013
python PostgreSQL_migration/012_add_performance_indexes.py
python PostgreSQL_migration/013_add_factor_columns.py

# Verify
python PostgreSQL_migration/check_migration_status.py
```

### 8. Restart the service

```bash
sudo systemctl restart task-aversion-app
sudo systemctl status task-aversion-app
```

### 9. Smoke test

Visit the live site and verify:
- Dashboard loads
- Can create/complete tasks
- Analytics work
- No errors in logs

### Troubleshooting

**View logs:**
```bash
sudo journalctl -u task-aversion-app -f
```

**Check service config:**
```bash
sudo systemctl cat task-aversion-app
```

**If migrations fail:**
- Verify DATABASE_URL is set: `echo $DATABASE_URL`
- Check you're using venv Python: `which python`
- Migrations are idempotent (safe to re-run)

## Quick Copy-Paste Version (no script)

If you prefer to run steps manually instead of `deploy/update_vps.sh`:

```bash
# Full update sequence
cd ~/Task_aversion_system
git pull origin main
cd task_aversion_app
source venv/bin/activate
pip install -r requirements.txt
set -a && source .env.production && set +a
~/backup_task_aversion.sh
python PostgreSQL_migration/check_migration_status.py
# Run any needed migrations here
sudo systemctl restart task-aversion-app
sudo systemctl status task-aversion-app
```
