# PowerShell script to start the app with CSV backend only
# Use this to test that Phase 1 changes don't break existing CSV functionality

# Set USE_CSV to explicitly request CSV backend (database is now default)
$env:USE_CSV = "1"

# Ensure DISABLE_CSV_FALLBACK is not set
if ($env:DISABLE_CSV_FALLBACK) {
    Remove-Item Env:\DISABLE_CSV_FALLBACK
}

# Print confirmation
Write-Host "Starting app with CSV backend (explicitly requested)..." -ForegroundColor Green
Write-Host "USE_CSV = 1 (using CSV backend)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Phase 1: Testing CSV backend with new infrastructure..." -ForegroundColor Magenta
Write-Host "         All methods use CSV backend as expected." -ForegroundColor Gray

# Change to the app directory
Set-Location $PSScriptRoot

# Use virtual environment Python if it exists, otherwise use system Python
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "Using virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" app.py
} else {
    python app.py
}


