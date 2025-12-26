@echo off
REM Batch script to start the app with SQLite database
REM This sets the DATABASE_URL environment variable for this session only
REM 
REM Phase 1 Status: Database infrastructure initialized, but methods still use CSV
REM This script initializes the database backend but allows CSV fallback for methods not yet migrated

REM Set DATABASE_URL to use SQLite (relative to task_aversion_app directory)
set DATABASE_URL=sqlite:///data/task_aversion.db

REM Allow CSV fallback during migration phases (Phase 1-5)
REM Set to "true" only when all methods are migrated and you want to test strict database-only mode
set DISABLE_CSV_FALLBACK=false

REM Print confirmation
echo Starting app with SQLite database (CSV fallback ENABLED)...
echo DATABASE_URL = %DATABASE_URL%
echo DISABLE_CSV_FALLBACK = %DISABLE_CSV_FALLBACK%
echo.
echo Phase 1: Database infrastructure initialized.
echo          InstanceManager methods still use CSV backend (will be migrated in Phase 2+).

REM Change to the app directory
cd /d %~dp0

REM Use virtual environment Python if it exists, otherwise use system Python
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    .venv\Scripts\python.exe app.py
) else (
    python app.py
)

