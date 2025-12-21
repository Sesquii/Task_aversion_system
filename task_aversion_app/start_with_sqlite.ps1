# PowerShell script to start the app with SQLite database
# This sets the DATABASE_URL environment variable for this session only

# Set DATABASE_URL to use SQLite
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Disable CSV fallback - fail loudly if database doesn't work
$env:DISABLE_CSV_FALLBACK = "true"

# Print confirmation
Write-Host "Starting app with SQLite database (CSV fallback DISABLED)..." -ForegroundColor Green
Write-Host "DATABASE_URL = $env:DATABASE_URL" -ForegroundColor Cyan
Write-Host "DISABLE_CSV_FALLBACK = $env:DISABLE_CSV_FALLBACK" -ForegroundColor Yellow

# Change to the app directory
Set-Location $PSScriptRoot

# Use virtual environment Python if it exists, otherwise use system Python
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "Using virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" app.py
} else {
    python app.py
}

