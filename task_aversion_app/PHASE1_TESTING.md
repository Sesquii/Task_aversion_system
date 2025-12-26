# Phase 1 Testing Guide

## Overview

Phase 1 adds database infrastructure to InstanceManager but doesn't migrate any methods yet. All existing functionality still uses CSV backend.

## Testing Options

### Option 1: Test CSV Backend (Recommended for Phase 1)

Test that Phase 1 changes don't break existing CSV functionality:

**PowerShell:**
```powershell
cd task_aversion_app
.\start_csv_only.ps1
```

**Command Prompt:**
```cmd
cd task_aversion_app
start_csv_only.bat
```

**Expected output:**
```
[InstanceManager] Using CSV backend
```

All methods (create_instance, get_instance, etc.) will use CSV as before.

### Option 2: Test Database Initialization

Test that database backend initializes correctly (but methods still use CSV):

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

**Expected output:**
```
[Database] Initialized database at sqlite:///data/task_aversion.db
[TaskManager] Using database backend
[InstanceManager] Using database backend
```

**Important:** Even though database backend is initialized, InstanceManager methods still use CSV until Phase 2+ migration. This is expected behavior for Phase 1.

## What to Test

1. **App starts without errors** ✅
2. **Dashboard loads** ✅
3. **Create a task instance** ✅
4. **Initialize a task** ✅
5. **Complete a task** ✅
6. **View tasks** ✅
7. **All existing functionality works** ✅

## Expected Behavior

- **CSV mode:** Everything works exactly as before Phase 1
- **Database mode:** Database initializes, but InstanceManager methods still use CSV (no database operations yet)

## Verification Checklist

- [ ] App starts successfully
- [ ] No console errors
- [ ] Can create task instances
- [ ] Can complete tasks
- [ ] Data persists correctly
- [ ] All UI pages load

## Monitoring Database Usage

### Option 1: Start App and Monitor Together (Recommended)

**PowerShell:**
```powershell
cd task_aversion_app
.\start_and_monitor.ps1
```

**Command Prompt:**
```cmd
cd task_aversion_app
start_and_monitor.bat
```

This script will:
- Start the app with SQLite database in the background
- Wait 10 seconds for the app to initialize
- Check database status every 10 seconds
- Display clear status messages with timestamps
- Run for up to 10 minutes (60 checks)

**Expected output (Phase 1):**
```
[14:30:20] [STATUS] Database backend is INITIALIZED
[14:30:20] [NOTE] Phase 1: Methods still use CSV (expected until Phase 2+)
```

### Option 2: Monitor Existing App

If the app is already running, use the monitor script separately:

**PowerShell:**
```powershell
# In a separate terminal window, after starting the app:
cd task_aversion_app
.\test_database_usage.ps1
```

**Command Prompt:**
```cmd
# In a separate terminal window, after starting the app:
cd task_aversion_app
test_database_usage.bat
```

## Next Steps

Once Phase 1 is verified, proceed to Phase 2 where CRUD methods will be migrated to use the database backend.


