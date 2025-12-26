# PowerShell script to monitor database usage after app starts
# Checks every 10 seconds whether InstanceManager is using database backend

$separator = "============================================================"
Write-Host $separator -ForegroundColor Cyan
Write-Host "Database Usage Monitor" -ForegroundColor Cyan
Write-Host $separator -ForegroundColor Cyan
Write-Host ""
Write-Host "This script will check database usage every 10 seconds after app loads." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop monitoring." -ForegroundColor Yellow
Write-Host ""

# Wait for app to start (give it 10 seconds)
Write-Host "[INFO] Waiting 10 seconds for app to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 10

$checkCount = 0
$maxChecks = 60  # Monitor for up to 10 minutes (60 checks * 10 seconds)

while ($checkCount -lt $maxChecks) {
    $checkCount++
    $timestamp = Get-Date -Format "HH:mm:ss"
    
    Write-Host ""
    Write-Host "[$timestamp] Check #$checkCount - Checking database status..." -ForegroundColor Cyan
    
    try {
        # Try to import and check InstanceManager
        $scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
        Push-Location $scriptPath
        
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
        
        $result = python temp_check_db.py 2>&1
        
        Remove-Item "temp_check_db.py" -ErrorAction SilentlyContinue
        
        Pop-Location
        
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

