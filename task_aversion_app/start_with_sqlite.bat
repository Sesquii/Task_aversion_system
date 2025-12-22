@echo off
REM Batch script to start the app with SQLite database
REM This sets the DATABASE_URL environment variable for this session only

REM Set DATABASE_URL to use SQLite
set DATABASE_URL=sqlite:///data/task_aversion.db

REM Disable CSV fallback - fail loudly if database doesn't work
set DISABLE_CSV_FALLBACK=true

REM Print confirmation
echo Starting app with SQLite database (CSV fallback DISABLED)...
echo DATABASE_URL = %DATABASE_URL%
echo DISABLE_CSV_FALLBACK = %DISABLE_CSV_FALLBACK%

REM Change to the app directory
cd /d %~dp0

REM Use virtual environment Python if it exists, otherwise use system Python
if exist ".venv\Scripts\python.exe" (
    echo Using virtual environment...
    .venv\Scripts\python.exe app.py
) else (
    python app.py
)

