@echo off
REM Batch script to start the app with SQLite and monitor database usage
REM Starts the app in background, then monitors database status every 10 seconds

echo ============================================================
echo Starting App with Database Monitoring
echo ============================================================
echo.

REM Set DATABASE_URL to use SQLite (relative to task_aversion_app directory)
set DATABASE_URL=sqlite:///data/task_aversion.db

REM Allow CSV fallback during migration phases (Phase 1-5)
set DISABLE_CSV_FALLBACK=false

echo Configuration:
echo   DATABASE_URL = %DATABASE_URL%
echo   DISABLE_CSV_FALLBACK = %DISABLE_CSV_FALLBACK%
echo.
echo Phase 1: Database infrastructure initialized.
echo          InstanceManager methods still use CSV backend (will be migrated in Phase 2+).
echo.

REM Change to the app directory
cd /d %~dp0

REM Determine Python executable
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    set PYTHON_EXE=.venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

REM Start the app in background
echo Starting app in background...
start "Task Aversion App" %PYTHON_EXE% app.py

echo App process started
echo.

REM Wait for app to initialize
echo [INFO] Waiting 10 seconds for app to initialize...
timeout /t 10 /nobreak >nul

echo.
echo ============================================================
echo Database Usage Monitor
echo ============================================================
echo.
echo Monitoring database usage every 10 seconds...
echo Press Ctrl+C to stop monitoring (app will continue running)
echo.

set checkCount=0
set maxChecks=60

:loop
set /a checkCount+=1

for /f "tokens=1-2 delims=: " %%a in ('time /t') do set timestamp=%%a:%%b

echo.
echo [%timestamp%] Check #%checkCount% - Checking database status...

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

%PYTHON_EXE% temp_check_db.py > temp_result.txt 2>&1

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
echo.
echo App is still running in background.
echo To stop the app, close the "Task Aversion App" window or kill the process.

