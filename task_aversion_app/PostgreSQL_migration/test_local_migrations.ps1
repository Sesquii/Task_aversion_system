# Test PostgreSQL Migrations Locally with Docker (PowerShell)
#
# This script:
# 1. Starts Docker PostgreSQL container
# 2. Tests all PostgreSQL migrations (001-013)
# 3. Verifies schema is correct
# 4. Optionally cleans up Docker container
#
# Usage: .\test_local_migrations.ps1

$ErrorActionPreference = "Stop"

# Get script directory and root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path (Split-Path $ScriptDir)
$AppDir = Split-Path $ScriptDir

Write-Host "=========================================="
Write-Host "PostgreSQL Migration Local Testing"
Write-Host "=========================================="
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "[OK] Docker is running"
} catch {
    Write-Host "[ERROR] Docker is not running or not accessible"
    Write-Host "Please start Docker and try again"
    exit 1
}

# Check if docker-compose is available
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] docker-compose is not installed"
    Write-Host "Please install docker-compose and try again"
    exit 1
}

Write-Host ""

# Start PostgreSQL container
Write-Host "Starting Docker PostgreSQL container..."
Push-Location $RootDir
docker-compose -f docker-compose.test.yml up -d
Pop-Location

# Wait for PostgreSQL to be ready
Write-Host "Waiting for PostgreSQL to be ready..."
Start-Sleep -Seconds 3

$maxAttempts = 30
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        docker exec test-postgres pg_isready -U testuser -d task_aversion_test 2>&1 | Out-Null
        Write-Host "[OK] PostgreSQL is ready"
        break
    } catch {
        $attempt++
        Start-Sleep -Seconds 1
    }
}

if ($attempt -eq $maxAttempts) {
    Write-Host "[ERROR] PostgreSQL failed to start within timeout"
    Push-Location $RootDir
    docker-compose -f docker-compose.test.yml down
    Pop-Location
    exit 1
}

Write-Host ""

# Set DATABASE_URL
$env:DATABASE_URL = "postgresql://testuser:testpassword@localhost:5433/task_aversion_test"

# Change to task_aversion_app directory
Push-Location $AppDir

Write-Host "Testing PostgreSQL migrations..."
Write-Host "DATABASE_URL: $env:DATABASE_URL"
Write-Host ""

# Test migrations in order
$migrations = @(
    "001_initial_schema.py",
    "002_add_routine_scheduling_fields.py",
    "003_create_task_instances_table.py",
    "004_create_emotions_table.py",
    "005_add_indexes_and_foreign_keys.py",
    "006_add_notes_column.py",
    "007_create_user_preferences_table.py",
    "008_create_survey_responses_table.py",
    "009_create_users_table.py",
    "010_add_user_id_foreign_keys.py",
    "011_add_user_id_to_emotions.py",
    "012_add_performance_indexes.py",
    "013_add_factor_columns.py"
)

$failed = 0
foreach ($migration in $migrations) {
    Write-Host "Testing migration: $migration"
    $migrationPath = Join-Path "PostgreSQL_migration" $migration
    
    # Run migration (migrations are idempotent, so they can be run multiple times)
    # They will prompt if tables/columns already exist - this is expected behavior
    try {
        python $migrationPath
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -eq 0) {
            Write-Host "[OK] $migration completed (exit code: $exitCode)"
        } else {
            Write-Host "[FAIL] $migration failed (exit code: $exitCode)"
            $failed++
        }
    } catch {
        Write-Host "[FAIL] $migration failed with error: $_"
        $failed++
    }
    Write-Host ""
}

# Check migration status
Write-Host "Checking migration status..."
python PostgreSQL_migration\check_migration_status.py

Write-Host ""

# Summary
if ($failed -eq 0) {
    Write-Host "=========================================="
    Write-Host "[SUCCESS] All migrations passed!"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "To keep the container running for further testing:"
    Write-Host "  cd $RootDir"
    Write-Host "  docker-compose -f docker-compose.test.yml stop"
    Write-Host ""
    Write-Host "To remove the container:"
    Write-Host "  cd $RootDir"
    Write-Host "  docker-compose -f docker-compose.test.yml down"
    Write-Host ""
    Write-Host "To clean up volumes (deletes all test data):"
    Write-Host "  cd $RootDir"
    Write-Host "  docker-compose -f docker-compose.test.yml down -v"
} else {
    Write-Host "=========================================="
    Write-Host "[FAILED] $failed migration(s) failed"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Container is still running for debugging."
    Write-Host "To remove the container:"
    Write-Host "  cd $RootDir"
    Write-Host "  docker-compose -f docker-compose.test.yml down"
    exit 1
}

Pop-Location
