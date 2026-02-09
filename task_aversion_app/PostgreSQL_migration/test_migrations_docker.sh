#!/bin/bash
# Bash script to test PostgreSQL migrations locally with Docker
# This script starts a PostgreSQL container, runs all migrations, and cleans up

# Save original directory to restore later if needed
ORIGINAL_DIR=$(pwd)

# Note: We use set -e carefully - some commands may fail but we handle them explicitly
set -e  # Exit on error

echo "=============================================================================="
echo "PostgreSQL Migration Testing with Docker"
echo "=============================================================================="
echo ""

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running or not installed!"
    echo "Please start Docker and try again."
    exit 1
fi

# Set variables
CONTAINER_NAME="test-postgres-migration"
DB_NAME="task_aversion_test"
DB_USER="task_aversion_user"
DB_PASSWORD="testpassword"
DB_URL="postgresql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}"

# Step 1: Check if container already exists
echo "[1/7] Checking for existing PostgreSQL container..."
if docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "  Found existing container. Stopping and removing..."
    docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
    docker rm -v "$CONTAINER_NAME" > /dev/null 2>&1 || true
    sleep 2
fi

# Step 2: Start PostgreSQL container
echo ""
echo "[2/7] Starting PostgreSQL container (14-alpine to match server version 14.2)..."
docker run --name "$CONTAINER_NAME" \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_DB="$DB_NAME" \
    -p 5432:5432 \
    -d postgres:14-alpine
# Using PostgreSQL 14 to match server version (14.2) for accurate testing

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to start PostgreSQL container!"
    exit 1
fi

echo "  [OK] Container started: $CONTAINER_NAME (PostgreSQL 14)"

# Step 3: Wait for PostgreSQL to be ready
echo ""
echo "[3/7] Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0
ready=false

while [ $attempt -lt $max_attempts ] && [ "$ready" = false ]; do
    if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
        ready=true
        echo "  [OK] PostgreSQL is ready!"
    else
        attempt=$((attempt + 1))
        echo "  Waiting... (attempt $attempt/$max_attempts)"
        sleep 2
    fi
done

if [ "$ready" = false ]; then
    echo "[ERROR] PostgreSQL did not become ready in time!"
    docker stop "$CONTAINER_NAME" > /dev/null 2>&1 || true
    docker rm -v "$CONTAINER_NAME" > /dev/null 2>&1 || true
    exit 1
fi

# Step 4: Set DATABASE_URL environment variable
echo ""
echo "[4/7] Setting DATABASE_URL environment variable..."
export DATABASE_URL="$DB_URL"
echo "  DATABASE_URL=$DB_URL"

# Step 5: Check migration status
echo ""
echo "[5/7] Checking current migration status..."

# Navigate to task_aversion_app directory
# Script is located at: task_aversion_app/PostgreSQL_migration/test_migrations_docker.sh
# We need to be in task_aversion_app directory to run migrations
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_BASENAME="$(basename "$SCRIPT_DIR")"

# Temporarily disable set -e for directory navigation (handled explicitly below)
set +e

# Determine the task_aversion_app directory based on script location
NAVIGATED=false

if [ "$SCRIPT_BASENAME" = "PostgreSQL_migration" ] && echo "$SCRIPT_DIR" | grep -q "task_aversion_app"; then
    # Script is in task_aversion_app/PostgreSQL_migration, go up one level to task_aversion_app
    TASK_AVERSION_APP_DIR="$(dirname "$SCRIPT_DIR")"
    if [ -d "$TASK_AVERSION_APP_DIR" ] && [ -d "$TASK_AVERSION_APP_DIR/PostgreSQL_migration" ]; then
        if cd "$TASK_AVERSION_APP_DIR" 2>/dev/null; then
            echo "  [INFO] Changed to task_aversion_app directory: $TASK_AVERSION_APP_DIR"
            NAVIGATED=true
        else
            echo "  [ERROR] Could not change to task_aversion_app directory: $TASK_AVERSION_APP_DIR" >&2
            exit 1
        fi
    fi
fi

if [ "$NAVIGATED" = false ] && [ -d "$ORIGINAL_DIR/task_aversion_app" ]; then
    # We're in project root, navigate to task_aversion_app
    if cd "$ORIGINAL_DIR/task_aversion_app" 2>/dev/null; then
        echo "  [INFO] Changed to task_aversion_app directory"
        NAVIGATED=true
    fi
fi

if [ "$NAVIGATED" = false ] && [ -d "PostgreSQL_migration" ]; then
    # Already in task_aversion_app (PostgreSQL_migration folder exists here)
    echo "  [INFO] Already in task_aversion_app directory"
    NAVIGATED=true
fi

if [ "$NAVIGATED" = false ]; then
    echo "  [WARNING] Could not automatically determine task_aversion_app directory" >&2
    echo "  [WARNING] Script location: $SCRIPT_DIR" >&2
    echo "  [WARNING] Current directory: $(pwd)" >&2
    echo "  [WARNING] Attempting to continue from current directory..." >&2
    # Don't exit - let it try to run and fail naturally if PostgreSQL_migration doesn't exist
fi

# Re-enable set -e after directory navigation
set -e

# Temporarily disable set -e for status check (may fail on empty database)
set +e
python PostgreSQL_migration/check_migration_status.py
status_check_result=$?
set -e

# Check if check_migration_status command succeeded (warn but don't fail)
if [ $status_check_result -ne 0 ]; then
    echo "[WARNING] Migration status check returned non-zero exit code" >&2
fi

# Step 6: Run migrations in order
echo ""
echo "[6/7] Running migrations in order (001-011)..."
echo ""

migrations=(
    "001_initial_schema.py"
    "002_add_routine_scheduling_fields.py"
    "003_create_task_instances_table.py"
    "004_create_emotions_table.py"
    "005_add_indexes_and_foreign_keys.py"
    "006_add_notes_column.py"
    "007_create_user_preferences_table.py"
    "008_create_survey_responses_table.py"
    "009_create_users_table.py"
    "010_add_user_id_foreign_keys.py"
    "011_add_user_id_to_emotions.py"
)

migration_errors=0
for migration in "${migrations[@]}"; do
    echo "  Running: $migration..."
    python "PostgreSQL_migration/$migration"
    
    if [ $? -ne 0 ]; then
        echo "  [FAIL] Migration $migration failed!"
        migration_errors=$((migration_errors + 1))
    else
        echo "  [OK] Migration $migration completed"
    fi
    echo ""
done

if [ $migration_errors -gt 0 ]; then
    echo "[ERROR] $migration_errors migration(s) failed!"
else
    echo "[OK] All migrations completed successfully!"
fi

# Step 7: Final status check
echo ""
echo "[7/7] Final migration status check..."
# Temporarily disable set -e for final status check (warnings are acceptable)
set +e
python PostgreSQL_migration/check_migration_status.py
final_status_result=$?
set -e

if [ $final_status_result -ne 0 ]; then
    echo "[WARNING] Final status check returned non-zero exit code (warnings may be acceptable)" >&2
fi

echo ""
echo "=============================================================================="
echo "Migration Testing Complete"
echo "=============================================================================="
echo ""
echo "PostgreSQL container is still running: $CONTAINER_NAME"
echo ""
echo "To connect to the database:"
echo "  export DATABASE_URL=$DB_URL"
echo ""
echo "To stop and remove the container:"
echo "  docker stop $CONTAINER_NAME"
echo "  docker rm -v $CONTAINER_NAME"
echo ""
echo "To keep testing, you can now run migrations individually or run this script again."
echo ""

# Restore original directory if we changed it
if [ "$(pwd)" != "$ORIGINAL_DIR" ]; then
    cd "$ORIGINAL_DIR" || true
fi
