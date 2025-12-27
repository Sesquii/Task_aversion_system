# PowerShell script to start the app with MULTI-COLUMN initialization card layout
# This shows pause notes in a separate column next to the task info

# Set DATABASE_URL to use SQLite (relative to task_aversion_app directory)
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Set initialization card layout to multi-column
$env:INIT_CARD_LAYOUT = "columns"

# Print confirmation
Write-Host "Starting app with MULTI-COLUMN initialization card layout..." -ForegroundColor Green
Write-Host "INIT_CARD_LAYOUT = $env:INIT_CARD_LAYOUT" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pause notes will appear in a separate column next to the task info." -ForegroundColor Yellow
Write-Host ""

# Change to the app directory
Set-Location $PSScriptRoot

# Use virtual environment Python if it exists, otherwise use system Python
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "Using virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" app.py
} else {
    python app.py
}
