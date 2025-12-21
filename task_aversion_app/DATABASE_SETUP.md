# Database Setup Guide

## Quick Start: Using SQLite

You have **3 easy ways** to use SQLite instead of CSV:

### Option 1: Use the Startup Script (Easiest!)

**PowerShell:**
```powershell
cd task_aversion_app
.\start_with_sqlite.ps1
```

**Command Prompt:**
```cmd
cd task_aversion_app
start_with_sqlite.bat
```

This automatically sets `DATABASE_URL` and starts the app.

---

### Option 2: Set Environment Variable in PowerShell (Current Session)

Open PowerShell and run:

```powershell
# Set the environment variable
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Start the app
cd task_aversion_app
python app.py
```

**Note:** This only works for the current PowerShell window. Close it and you'll need to set it again.

---

### Option 3: Set Environment Variable Permanently (System-Wide)

**PowerShell (as Administrator):**

```powershell
# Set permanently for current user
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'sqlite:///data/task_aversion.db', 'User')

# Restart PowerShell, then run:
cd task_aversion_app
python app.py
```

**Or use Windows GUI:**
1. Press `Win + R`, type `sysdm.cpl`, press Enter
2. Click "Environment Variables"
3. Under "User variables", click "New"
4. Variable name: `DATABASE_URL`
5. Variable value: `sqlite:///data/task_aversion.db`
6. Click OK, restart your terminal/PowerShell

---

## How to Verify It's Working

When you start the app, you should see in the console:
```
[TaskManager] Using database backend
```

If you see:
```
[TaskManager] Using CSV backend
```

Then the environment variable isn't set. Check your method above.

---

## Database File Location

The SQLite database will be created at:
- `task_aversion_app/data/task_aversion.db`

The database file is created automatically the first time you run the app with `DATABASE_URL` set.

---

## Switching Back to CSV

To use CSV again (default), just:
1. Don't set `DATABASE_URL`, OR
2. Unset it: `$env:DATABASE_URL = $null` (PowerShell)

The app will automatically fall back to CSV if `DATABASE_URL` is not set.

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'sqlalchemy'"**
- Run: `python -m pip install sqlalchemy psycopg2-binary python-dotenv`

**Database file locked errors**
- Make sure no other instance of the app is running
- Close any database browser tools (DB Browser for SQLite, etc.)

**Still using CSV?**
- Check that `DATABASE_URL` is set: `echo $env:DATABASE_URL` (PowerShell)
- Make sure you're setting it in the same terminal window you run the app from

