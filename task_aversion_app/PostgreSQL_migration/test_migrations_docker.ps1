# PowerShell script to test PostgreSQL migrations locally with Docker
# This script starts a PostgreSQL container, runs all migrations, and cleans up

# Save original directory to restore later if needed
$originalDirectory = Get-Location

Write-Host ("=" * 70)
Write-Host "PostgreSQL Migration Testing with Docker"
Write-Host ("=" * 70)
Write-Host ""

# Check if Docker is running
try {
    docker ps | Out-Null
} catch {
    Write-Host "[ERROR] Docker is not running or not installed!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

# Set variables
$CONTAINER_NAME = "test-postgres-migration"
$DB_NAME = "task_aversion_test"
$DB_USER = "task_aversion_user"
$DB_PASSWORD = "testpassword"
$DB_URL = "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"

# Step 1: Check if container already exists
Write-Host "[1/7] Checking for existing PostgreSQL container..." -ForegroundColor Cyan
$existing = docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}"
if ($existing -eq $CONTAINER_NAME) {
    Write-Host "  Found existing container. Stopping and removing..." -ForegroundColor Yellow
    docker stop $CONTAINER_NAME 2>$null | Out-Null
    docker rm $CONTAINER_NAME 2>$null | Out-Null
    Start-Sleep -Seconds 2
}

# Step 2: Start PostgreSQL container
Write-Host ""
Write-Host "[2/7] Starting PostgreSQL container (14-alpine to match server version 14.2)..." -ForegroundColor Cyan
docker run --name $CONTAINER_NAME `
    -e POSTGRES_PASSWORD=$DB_PASSWORD `
    -e POSTGRES_USER=$DB_USER `
    -e POSTGRES_DB=$DB_NAME `
    -p 5432:5432 `
    -d postgres:14-alpine
# Using PostgreSQL 14 to match server version (14.2) for accurate testing

# Check if docker command succeeded
if (-not $?) {
    Write-Host "[ERROR] Failed to start PostgreSQL container!" -ForegroundColor Red
    exit 1
}

Write-Host "  [OK] Container started: $CONTAINER_NAME (PostgreSQL 14)" -ForegroundColor Green

# Step 3: Wait for PostgreSQL to be ready
Write-Host ""
Write-Host "[3/7] Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
$maxAttempts = 30
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts -and -not $ready) {
    try {
        $result = docker exec $CONTAINER_NAME pg_isready -U $DB_USER -d $DB_NAME 2>&1
        if ($result -match "accepting connections") {
            $ready = $true
            Write-Host "  [OK] PostgreSQL is ready!" -ForegroundColor Green
        } else {
            $attempt++
            Write-Host "  Waiting... (attempt $attempt/$maxAttempts)" -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    } catch {
        $attempt++
        Write-Host "  Waiting... (attempt $attempt/$maxAttempts)" -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "[ERROR] PostgreSQL did not become ready in time!" -ForegroundColor Red
    docker stop $CONTAINER_NAME | Out-Null
    docker rm $CONTAINER_NAME | Out-Null
    exit 1
}

# Step 4: Set DATABASE_URL environment variable
Write-Host ""
Write-Host "[4/7] Setting DATABASE_URL environment variable..." -ForegroundColor Cyan
$env:DATABASE_URL = $DB_URL
Write-Host "  DATABASE_URL=$DB_URL" -ForegroundColor Gray

# Step 5: Check migration status
Write-Host ""
Write-Host "[5/7] Checking current migration status..." -ForegroundColor Cyan

# Navigate to task_aversion_app directory
# Script is located at: task_aversion_app/PostgreSQL_migration/test_migrations_docker.ps1
# We need to be in task_aversion_app directory to run migrations
$scriptPath = $PSScriptRoot  # This is the directory containing the script (PostgreSQL_migration)

if ($scriptPath -match "task_aversion_app[\\/]PostgreSQL_migration$") {
    # Script is in task_aversion_app/PostgreSQL_migration, go up one level to task_aversion_app
    $taskAversionAppPath = Split-Path $scriptPath -Parent
    Set-Location -Path $taskAversionAppPath
    Write-Host "  [INFO] Changed to task_aversion_app directory: $taskAversionAppPath" -ForegroundColor Gray
} elseif (Test-Path (Join-Path $originalDirectory "task_aversion_app")) {
    # We're in project root, navigate to task_aversion_app
    Set-Location -Path (Join-Path $originalDirectory "task_aversion_app")
    Write-Host "  [INFO] Changed to task_aversion_app directory" -ForegroundColor Gray
} elseif (Test-Path "PostgreSQL_migration") {
    # Already in task_aversion_app (PostgreSQL_migration folder exists here)
    Write-Host "  [INFO] Already in task_aversion_app directory" -ForegroundColor Gray
} else {
    Write-Host "  [WARNING] Could not find task_aversion_app directory structure" -ForegroundColor Yellow
    Write-Host "  [WARNING] Script may fail if PostgreSQL_migration folder is not accessible" -ForegroundColor Yellow
}

python PostgreSQL_migration/check_migration_status.py

# Check if check_migration_status command succeeded (warn but don't fail)
if (-not $?) {
    Write-Host "[WARNING] Migration status check returned non-zero exit code" -ForegroundColor Yellow
}

# Step 6: Run migrations in order
Write-Host ""
Write-Host "[6/7] Running migrations in order (001-013)..." -ForegroundColor Cyan
Write-Host ""

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

$migrationErrors = 0
foreach ($migration in $migrations) {
    Write-Host "  Running: $migration..." -ForegroundColor Cyan
    python "PostgreSQL_migration/$migration"
    
    # Check if migration command succeeded
    if (-not $?) {
        Write-Host "  [FAIL] Migration $migration failed!" -ForegroundColor Red
        $migrationErrors++
    } else {
        Write-Host "  [OK] Migration $migration completed" -ForegroundColor Green
    }
    Write-Host ""
}

if ($migrationErrors -gt 0) {
    Write-Host "[ERROR] $migrationErrors migration(s) failed!" -ForegroundColor Red
} else {
    Write-Host "[OK] All migrations completed successfully!" -ForegroundColor Green
}

# Step 7: Final status check
Write-Host ""
Write-Host "[7/7] Final migration status check..." -ForegroundColor Cyan
python PostgreSQL_migration/check_migration_status.py

Write-Host ""
Write-Host ("=" * 70)
Write-Host "Migration Testing Complete"
Write-Host ("=" * 70)
Write-Host ""
Write-Host "PostgreSQL container is still running: $CONTAINER_NAME" -ForegroundColor Yellow
Write-Host ""
Write-Host "To connect to the database:" -ForegroundColor Cyan
Write-Host "  DATABASE_URL=$DB_URL" -ForegroundColor Gray
Write-Host ""
Write-Host "To stop and remove the container:" -ForegroundColor Cyan
Write-Host "  docker stop $CONTAINER_NAME" -ForegroundColor Gray
Write-Host "  docker rm $CONTAINER_NAME" -ForegroundColor Gray
Write-Host ""
Write-Host "To keep testing, you can now run migrations individually or run this script again."
Write-Host ""

# Restore original directory if we changed it
if ((Get-Location).Path -ne $originalDirectory.Path) {
    Set-Location -Path $originalDirectory
}
