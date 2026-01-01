# PowerShell script to start the app with FULL-WIDTH initialization card layout
# This shows pause notes in a full-width section below the task description

# Set DATABASE_URL to use SQLite (relative to task_aversion_app directory)
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Set initialization card layout to full-width
$env:INIT_CARD_LAYOUT = "full"

# Print confirmation
Write-Host "Starting app with FULL-WIDTH initialization card layout..." -ForegroundColor Green
Write-Host "INIT_CARD_LAYOUT = $env:INIT_CARD_LAYOUT" -ForegroundColor Cyan
Write-Host ""
Write-Host "Pause notes will appear in a full-width section below the task description." -ForegroundColor Yellow
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
