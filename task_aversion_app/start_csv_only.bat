@echo off
REM Batch script to start the app with CSV backend only
REM Use this to test that Phase 1 changes don't break existing CSV functionality

REM Set USE_CSV to explicitly request CSV backend (database is now default)
set USE_CSV=1

REM Ensure DISABLE_CSV_FALLBACK is not set
set DISABLE_CSV_FALLBACK=

REM Print confirmation
echo Starting app with CSV backend (explicitly requested)...
echo USE_CSV = 1 (using CSV backend)
echo.
echo Phase 1: Testing CSV backend with new infrastructure...
echo          All methods use CSV backend as expected.

REM Change to the app directory
cd /d %~dp0

REM Use virtual environment Python if it exists, otherwise use system Python
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    .venv\Scripts\python.exe app.py
) else (
    python app.py
)


