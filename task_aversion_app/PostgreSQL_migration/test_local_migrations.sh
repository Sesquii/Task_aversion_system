#!/bin/bash
# Test PostgreSQL Migrations Locally with Docker
#
# This script:
# 1. Starts Docker PostgreSQL container
# 2. Tests all PostgreSQL migrations (001-010)
# 3. Verifies schema is correct
# 4. Optionally cleans up Docker container
#
# Usage: bash test_local_migrations.sh

set -e  # Exit on error

# Get script directory and root directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "PostgreSQL Migration Local Testing"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running or not accessible"
    echo "Please start Docker and try again"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "[ERROR] docker-compose is not installed"
    echo "Please install docker-compose and try again"
    exit 1
fi

echo "[OK] Docker is running"
echo ""

# Start PostgreSQL container
echo "Starting Docker PostgreSQL container..."
cd "$ROOT_DIR" || exit 1
docker-compose -f docker-compose.test.yml up -d

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 3

max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec test-postgres pg_isready -U testuser -d task_aversion_test > /dev/null 2>&1; then
        echo "[OK] PostgreSQL is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo "[ERROR] PostgreSQL failed to start within timeout"
    docker-compose -f docker-compose.test.yml down
    exit 1
fi

echo ""

# Set DATABASE_URL
export DATABASE_URL="postgresql://testuser:testpassword@localhost:5433/task_aversion_test"

# Change to task_aversion_app directory
cd "$APP_DIR" || exit 1

echo "Testing PostgreSQL migrations..."
echo "DATABASE_URL: $DATABASE_URL"
echo ""

# Test migrations in order
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
    "012_add_performance_indexes.py"
    "013_add_factor_columns.py"
)

failed=0
for migration in "${migrations[@]}"; do
    echo "Testing migration: $migration"
    # Run migration non-interactively (it will skip if already applied)
    if python PostgreSQL_migration/"$migration" <<< "y" 2>&1 | grep -q "\[SUCCESS\]\|\[NOTE\]\|\[OK\]"; then
        echo "[OK] $migration passed"
    else
        # Check exit code instead
        if python PostgreSQL_migration/"$migration" <<< "y" > /dev/null 2>&1; then
            echo "[OK] $migration passed"
        else
            echo "[FAIL] $migration failed"
            failed=$((failed + 1))
        fi
    fi
    echo ""
done

# Check migration status
echo "Checking migration status..."
python PostgreSQL_migration/check_migration_status.py

echo ""

# Summary
if [ $failed -eq 0 ]; then
    echo "=========================================="
    echo "[SUCCESS] All migrations passed!"
    echo "=========================================="
    echo ""
    echo "To keep the container running for further testing:"
    echo "  cd $ROOT_DIR"
    echo "  docker-compose -f docker-compose.test.yml stop"
    echo ""
    echo "To remove the container:"
    echo "  cd $ROOT_DIR"
    echo "  docker-compose -f docker-compose.test.yml down"
    echo ""
    echo "To clean up volumes (deletes all test data):"
    echo "  cd $ROOT_DIR"
    echo "  docker-compose -f docker-compose.test.yml down -v"
else
    echo "=========================================="
    echo "[FAILED] $failed migration(s) failed"
    echo "=========================================="
    echo ""
    echo "Container is still running for debugging."
    echo "To remove the container:"
    echo "  cd $ROOT_DIR"
    echo "  docker-compose -f docker-compose.test.yml down"
    exit 1
fi
