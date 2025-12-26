# PowerShell script to start the app with SQLite database
# This sets the DATABASE_URL environment variable for this session only
# 
# Phase 1 Status: Database infrastructure initialized, but methods still use CSV
# This script initializes the database backend but allows CSV fallback for methods not yet migrated

# Set DATABASE_URL to use SQLite (relative to task_aversion_app directory)
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Allow CSV fallback during migration phases (Phase 1-5)
# Set to "true" only when all methods are migrated and you want to test strict database-only mode
$env:DISABLE_CSV_FALLBACK = "false"

# Print confirmation
Write-Host "Starting app with SQLite database (CSV fallback ENABLED)..." -ForegroundColor Green
Write-Host "DATABASE_URL = $env:DATABASE_URL" -ForegroundColor Cyan
Write-Host "DISABLE_CSV_FALLBACK = $env:DISABLE_CSV_FALLBACK" -ForegroundColor Yellow
Write-Host ""
Write-Host "Phase 1: Database infrastructure initialized." -ForegroundColor Magenta
Write-Host "         InstanceManager methods still use CSV backend (will be migrated in Phase 2+)." -ForegroundColor Gray

# Change to the app directory
Set-Location $PSScriptRoot

# Use virtual environment Python if it exists, otherwise use system Python
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "Using virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" app.py
} else {
    python app.py
}

