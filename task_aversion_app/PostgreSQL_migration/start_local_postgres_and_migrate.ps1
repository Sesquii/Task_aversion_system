# Option A: Start PostgreSQL locally (Docker) and run all migrations.
# Keeps CSV and SQLite as backup; use DATABASE_URL in .env to switch the app to Postgres.
# Run from project root or from task_aversion_app.

$ErrorActionPreference = "Stop"

$ProjectRoot = $null
$AppDir = $null

if (Test-Path "docker-compose.yml") {
    $ProjectRoot = Get-Location
    $AppDir = Join-Path $ProjectRoot "task_aversion_app"
} elseif (Test-Path (Join-Path (Get-Location) "..\docker-compose.yml")) {
    $AppDir = Get-Location
    $ProjectRoot = (Resolve-Path "..").Path
} else {
    Write-Host "[ERROR] Run this script from project root or from task_aversion_app" -ForegroundColor Red
    exit 1
}

# Default DATABASE_URL matching docker-compose postgres service
$DB_USER = "task_aversion_user"
$DB_PASSWORD = "testpassword"
$DB_NAME = "task_aversion_test"
$DefaultDbUrl = "postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}"

Write-Host ("=" * 70)
Write-Host "Option A: Local PostgreSQL - Start DB and run migrations"
Write-Host ("=" * 70)
Write-Host ""

# 1. Start Postgres with docker-compose (persistent volume)
Write-Host "[1/5] Starting PostgreSQL (docker-compose)..." -ForegroundColor Cyan
try {
    docker ps 2>&1 | Out-Null
    if (-not $?) {
        Write-Host "[ERROR] Docker is not running. Start Docker Desktop and try again." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "[ERROR] Docker is not available. Install and start Docker Desktop." -ForegroundColor Red
    exit 1
}
Push-Location $ProjectRoot
try {
    # docker-compose writes "Creating" etc. to stderr; PowerShell treats that as error. Use exit code only.
    $ErrorActionPreferencePrev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & docker-compose up -d postgres 2>&1 | Out-Null
    $ErrorActionPreference = $ErrorActionPreferencePrev
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] docker-compose failed (exit code $LASTEXITCODE). Is Docker running?" -ForegroundColor Red
        Pop-Location
        exit 1
    }
} finally {
    Pop-Location
}
Write-Host "  [OK] Postgres service started" -ForegroundColor Green
Write-Host ""

# 2. Wait for Postgres to be ready
Write-Host "[2/5] Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
$maxAttempts = 30
$attempt = 0
$ready = $false
while ($attempt -lt $maxAttempts) {
    try {
        $result = docker exec task-aversion-postgres pg_isready -U $DB_USER -d $DB_NAME 2>&1
        if ($result -match "accepting connections") {
            $ready = $true
            break
        }
    } catch {
        # container name might differ
        $result = docker run --rm --network host postgres:14-alpine pg_isready -U $DB_USER -d $DB_NAME -h localhost 2>&1
        if ($result -match "accepting connections") {
            $ready = $true
            break
        }
    }
    $attempt++
    Write-Host "  Waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    Write-Host "[ERROR] PostgreSQL did not become ready. Check: docker-compose logs postgres" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] PostgreSQL is ready" -ForegroundColor Green
Write-Host ""

# 3. Set DATABASE_URL (use .env if present, else default)
if (Test-Path (Join-Path $AppDir ".env")) {
    $envLines = Get-Content (Join-Path $AppDir ".env")
    $urlFromEnv = $null
    foreach ($line in $envLines) {
        if ($line -match '^\s*DATABASE_URL\s*=\s*(.+)$' -and $Matches[1] -match 'postgresql://') {
            $urlFromEnv = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
    if ($urlFromEnv) {
        $env:DATABASE_URL = $urlFromEnv
        Write-Host "[3/5] Using DATABASE_URL from .env" -ForegroundColor Cyan
    } else {
        $env:DATABASE_URL = $DefaultDbUrl
        Write-Host "[3/5] Using default DATABASE_URL (no postgres URL in .env)" -ForegroundColor Cyan
    }
} else {
    $env:DATABASE_URL = $DefaultDbUrl
    Write-Host "[3/5] Using default DATABASE_URL (no .env)" -ForegroundColor Cyan
}
Write-Host "  DATABASE_URL=$env:DATABASE_URL" -ForegroundColor Gray
Write-Host ""

# 4. Run migrations from task_aversion_app
Write-Host "[4/5] Running migrations 001-011..." -ForegroundColor Cyan
Push-Location $AppDir
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
    "011_add_user_id_to_emotions.py"
)
$migrationErrors = 0
foreach ($migration in $migrations) {
    Write-Host "  Running: $migration..." -ForegroundColor Gray
    $ErrorActionPreferencePrev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = python "PostgreSQL_migration/$migration" 2>&1
    $ErrorActionPreference = $ErrorActionPreferencePrev
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        Write-Host "  [FAIL] $migration" -ForegroundColor Red
        Write-Host $out -ForegroundColor Red
        $migrationErrors++
    } else {
        Write-Host "  [OK] $migration" -ForegroundColor Green
    }
}
Pop-Location
if ($migrationErrors -gt 0) {
    Write-Host "[ERROR] $migrationErrors migration(s) failed." -ForegroundColor Red
    exit 1
}
Write-Host ""

# 5. Status check
Write-Host "[5/5] Migration status check..." -ForegroundColor Cyan
Push-Location $AppDir
python PostgreSQL_migration/check_migration_status.py
Pop-Location

Write-Host ""
Write-Host ("=" * 70)
Write-Host "Option A setup complete"
Write-Host ("=" * 70)
Write-Host ""
Write-Host "PostgreSQL is running (docker-compose). Data persists in volume postgres-data." -ForegroundColor Yellow
Write-Host ""
Write-Host "To use the app with PostgreSQL:" -ForegroundColor Cyan
Write-Host "  1. Copy .env.example to .env in task_aversion_app (if you have not already)" -ForegroundColor Gray
Write-Host "  2. In .env set: DATABASE_URL=$DefaultDbUrl" -ForegroundColor Gray
Write-Host "  3. Run the app from task_aversion_app (e.g. python app.py)" -ForegroundColor Gray
Write-Host ""
Write-Host "To roll back to CSV/SQLite: remove or comment out DATABASE_URL in .env." -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop Postgres: from project root run  docker-compose stop postgres" -ForegroundColor Gray
Write-Host ""
