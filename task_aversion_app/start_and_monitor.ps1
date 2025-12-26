# PowerShell script to start the app with SQLite and monitor database usage
# Starts the app in background, then monitors database status every 10 seconds

$separator = "============================================================"
Write-Host $separator -ForegroundColor Cyan
Write-Host "Starting App with Database Monitoring" -ForegroundColor Cyan
Write-Host $separator -ForegroundColor Cyan
Write-Host ""

# Set DATABASE_URL to use SQLite (relative to task_aversion_app directory)
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Allow CSV fallback during migration phases (Phase 1-5)
$env:DISABLE_CSV_FALLBACK = "false"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  DATABASE_URL = $env:DATABASE_URL" -ForegroundColor Cyan
Write-Host "  DISABLE_CSV_FALLBACK = $env:DISABLE_CSV_FALLBACK" -ForegroundColor Cyan
Write-Host ""
Write-Host "Phase 1: Database infrastructure initialized." -ForegroundColor Magenta
Write-Host "         InstanceManager methods still use CSV backend (will be migrated in Phase 2+)." -ForegroundColor Gray
Write-Host ""

# Change to the app directory
Set-Location $PSScriptRoot

# Determine Python executable
$pythonExe = if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host "Using virtual environment..." -ForegroundColor Yellow
    ".venv\Scripts\python.exe"
} else {
    "python"
}

# Start the app in background
Write-Host "Starting app in background..." -ForegroundColor Green
$appProcess = Start-Process -FilePath $pythonExe -ArgumentList "app.py" -PassThru -NoNewWindow

Write-Host "App process started (PID: $($appProcess.Id))" -ForegroundColor Green
Write-Host ""

# Wait for app to initialize
Write-Host "[INFO] Waiting 10 seconds for app to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 10

Write-Host ""
Write-Host $separator -ForegroundColor Cyan
Write-Host "Database Usage Monitor" -ForegroundColor Cyan
Write-Host $separator -ForegroundColor Cyan
Write-Host ""
Write-Host "Monitoring database usage every 10 seconds..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop monitoring (app will continue running)" -ForegroundColor Yellow
Write-Host ""

$checkCount = 0
$maxChecks = 60  # Monitor for up to 10 minutes (60 checks * 10 seconds)

while ($checkCount -lt $maxChecks) {
    # Check if app process is still running
    if ($appProcess.HasExited) {
        Write-Host ""
        Write-Host "[WARNING] App process has exited (exit code: $($appProcess.ExitCode))" -ForegroundColor Red
        break
    }
    
    $checkCount++
    $timestamp = Get-Date -Format "HH:mm:ss"
    
    Write-Host ""
    Write-Host "[$timestamp] Check #$checkCount - Checking database status..." -ForegroundColor Cyan
    
    try {
        # Create a temporary Python script to check status
        $checkScript = @"
import sys
import os
sys.path.insert(0, '.')

try:
    from backend.instance_manager import InstanceManager
    
    im = InstanceManager()
    
    status = {
        'use_db': im.use_db,
        'has_db_session': hasattr(im, 'db_session'),
        'has_taskinstance': hasattr(im, 'TaskInstance'),
        'backend': 'database' if im.use_db else 'CSV'
    }
    
    print(f"BACKEND_STATUS: {status['backend']}")
    print(f"USE_DB: {status['use_db']}")
    print(f"HAS_DB_SESSION: {status['has_db_session']}")
    print(f"HAS_TASKINSTANCE: {status['has_taskinstance']}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
"@
        
        $checkScript | Out-File -FilePath "temp_check_db.py" -Encoding UTF8
        
        $result = & $pythonExe temp_check_db.py 2>&1
        
        Remove-Item "temp_check_db.py" -ErrorAction SilentlyContinue
        
        # Parse results
        $backendStatus = ($result | Select-String "BACKEND_STATUS:").ToString() -replace "BACKEND_STATUS: ", ""
        $useDb = ($result | Select-String "USE_DB:").ToString() -replace "USE_DB: ", ""
        
        if ($result -match "ERROR") {
            Write-Host "[$timestamp] [ERROR] Could not check status: $result" -ForegroundColor Red
        } else {
            if ($useDb -eq "True") {
                Write-Host "[$timestamp] [STATUS] Database backend is INITIALIZED" -ForegroundColor Green
                Write-Host "[$timestamp] [NOTE] Phase 1: Methods still use CSV (expected until Phase 2+)" -ForegroundColor Yellow
            } else {
                Write-Host "[$timestamp] [STATUS] Using CSV backend (DATABASE_URL not set)" -ForegroundColor Yellow
            }
        }
        
    } catch {
        Write-Host "[$timestamp] [ERROR] Failed to check: $_" -ForegroundColor Red
    }
    
    # Wait 10 seconds before next check
    if ($checkCount -lt $maxChecks) {
        Write-Host "[$timestamp] Next check in 10 seconds..." -ForegroundColor Gray
        Start-Sleep -Seconds 10
    }
}

Write-Host ""
Write-Host "[INFO] Monitoring complete (checked $checkCount times)" -ForegroundColor Cyan
Write-Host ""
Write-Host "App is still running in background (PID: $($appProcess.Id))" -ForegroundColor Yellow
Write-Host "To stop the app, find and kill the process or close the terminal window." -ForegroundColor Yellow

