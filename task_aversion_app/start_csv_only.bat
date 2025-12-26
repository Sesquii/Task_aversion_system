@echo off
REM Batch script to start the app with CSV backend only (default)
REM Use this to test that Phase 1 changes don't break existing CSV functionality

REM Ensure DATABASE_URL is not set (use CSV backend)
set DATABASE_URL=

REM Ensure DISABLE_CSV_FALLBACK is not set
set DISABLE_CSV_FALLBACK=

REM Print confirmation
echo Starting app with CSV backend (default mode)...
echo DATABASE_URL = (not set - using CSV)
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


