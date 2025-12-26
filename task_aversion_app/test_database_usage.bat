@echo off
REM Batch script to monitor database usage after app starts
REM Checks every 10 seconds whether InstanceManager is using database backend

echo ============================================================
echo Database Usage Monitor
echo ============================================================
echo.
echo This script will check database usage every 10 seconds after app loads.
echo Press Ctrl+C to stop monitoring.
echo.

REM Wait for app to start (give it 10 seconds)
echo [INFO] Waiting 10 seconds for app to initialize...
timeout /t 10 /nobreak >nul

set checkCount=0
set maxChecks=60

:loop
set /a checkCount+=1

for /f "tokens=1-2 delims=: " %%a in ('time /t') do set timestamp=%%a:%%b

echo.
echo [%timestamp%] Check #%checkCount% - Checking database status...

cd /d %~dp0

REM Create temporary Python script to check status
(
echo import sys
echo import os
echo sys.path.insert(0, '.'
echo.
echo try:
echo     from backend.instance_manager import InstanceManager
echo.
echo     im = InstanceManager()
echo.
echo     status = {
echo         'use_db': im.use_db,
echo         'has_db_session': hasattr(im, 'db_session'),
echo         'has_taskinstance': hasattr(im, 'TaskInstance'),
echo         'backend': 'database' if im.use_db else 'CSV'
echo     }
echo.
echo     print(f"BACKEND_STATUS: {status['backend']}")
echo     print(f"USE_DB: {status['use_db']}")
echo     print(f"HAS_DB_SESSION: {status['has_db_session']}")
echo     print(f"HAS_TASKINSTANCE: {status['has_taskinstance']}")
echo.
echo except Exception as e:
echo     print(f"ERROR: {e}")
echo     import traceback
echo     traceback.print_exc()
) > temp_check_db.py

python temp_check_db.py > temp_result.txt 2>&1

REM Parse results
findstr /C:"BACKEND_STATUS:" temp_result.txt >nul
if %errorlevel% equ 0 (
    for /f "tokens=2 delims=: " %%a in ('findstr /C:"BACKEND_STATUS:" temp_result.txt') do set backendStatus=%%a
    for /f "tokens=2 delims=: " %%a in ('findstr /C:"USE_DB:" temp_result.txt') do set useDb=%%a
    
    if "%useDb%"=="True" (
        echo [%timestamp%] [STATUS] Database backend is INITIALIZED
        echo [%timestamp%] [NOTE] Phase 1: Methods still use CSV (expected until Phase 2+)
    ) else (
        echo [%timestamp%] [STATUS] Using CSV backend (DATABASE_URL not set)
    )
) else (
    echo [%timestamp%] [ERROR] Could not check status
    type temp_result.txt
)

del temp_check_db.py temp_result.txt 2>nul

if %checkCount% lss %maxChecks% (
    echo [%timestamp%] Next check in 10 seconds...
    timeout /t 10 /nobreak >nul
    goto loop
)

echo.
echo [INFO] Monitoring complete (checked %checkCount% times)

