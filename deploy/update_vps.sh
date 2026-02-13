#!/usr/bin/env bash
#
# VPS update script: pull code, install deps, backup DB, run migrations, restart app.
# Run on the VPS after SSH (e.g. bash deploy/update_vps.sh or ~/Task_aversion_system/deploy/update_vps.sh).
# Pauses once so you can enter your password when prompted (backup/migrations/sudo).
#
set -e

REPO_ROOT="${REPO_ROOT:-$HOME/Task_aversion_system}"
APP_DIR="$REPO_ROOT/task_aversion_app"
MIGRATION_DIR="$APP_DIR/PostgreSQL_migration"

echo "=== Task Aversion System - VPS Update ==="
echo ""

# 1. Pull latest code
echo "[1/6] Pulling latest code..."
cd "$REPO_ROOT"
git pull origin main
echo ""

# 2. Activate venv and update dependencies
echo "[2/6] Activating venv and installing dependencies..."
cd "$APP_DIR"
source venv/bin/activate
pip install -q -r requirements.txt
echo ""

# 3. Load environment (for migrations)
echo "[3/6] Loading .env.production..."
set -a
# shellcheck source=/dev/null
source .env.production
set +a
echo ""

# 4. Pause before steps that may prompt for password
echo "[4/6] About to run database backup, migration checks, and service restart."
echo "      You may be prompted for your password (e.g. sudo, or PostgreSQL)."
echo ""
read -r -p "Press Enter to continue (then enter password when prompted)..."
echo ""

# 5. Backup, migration status, run all migrations, restart
echo "[5/6] Backup and migrations..."
if [ -x "$HOME/backup_task_aversion.sh" ]; then
  "$HOME/backup_task_aversion.sh" || true
else
  echo "      (Skipping backup: ~/backup_task_aversion.sh not found or not executable)"
fi

echo ""
echo "      Migration status (before):"
python "$MIGRATION_DIR/check_migration_status.py" || true
echo ""

echo "      Running migrations 001-013 (idempotent)..."
for m in 001_initial_schema 002_add_routine_scheduling_fields 003_create_task_instances_table \
         004_create_emotions_table 005_add_indexes_and_foreign_keys 006_add_notes_column \
         007_create_user_preferences_table 008_create_survey_responses_table 009_create_users_table \
         010_add_user_id_foreign_keys 011_add_user_id_to_emotions 012_add_performance_indexes \
         013_add_factor_columns; do
  f="$MIGRATION_DIR/${m}.py"
  if [ -f "$f" ]; then
    echo "        Running $m..."
    python "$f" || true
  fi
done
echo "      Migration status (after):"
python "$MIGRATION_DIR/check_migration_status.py" || true
echo ""

# 6. Restart service (sudo will prompt for password here if needed)
echo "[6/6] Restarting task-aversion-app..."
sudo systemctl restart task-aversion-app
sudo systemctl status task-aversion-app --no-pager
echo ""
echo "=== Update complete. Visit the site to smoke test. ==="
