# Local Testing Guide: SQLite and Docker PostgreSQL

This guide helps you test migrations locally before deploying to production.

## Overview

**Testing Strategy:**
1. **Test SQLite migrations locally first** (faster, easier to debug)
2. **Test PostgreSQL migrations with Docker** (verify PostgreSQL-specific features work)
3. **Test OAuth authentication** (after migrations work)
4. **Test authenticated import** (final step)

This approach isolates issues and makes debugging easier.

## Part 1: Test SQLite Migrations Locally

### Prerequisites
- Python 3.x installed
- SQLite database (created automatically)

### Step 1: Check Current Migration Status

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"
python SQLite_migration/check_migration_status.py
```

**Bash/Linux:**
```bash
cd task_aversion_app
export DATABASE_URL="sqlite:///data/task_aversion.db"
python SQLite_migration/check_migration_status.py
```

### Step 2: Run SQLite Migrations in Order

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"

# Run all migrations in order
python SQLite_migration/001_initial_schema.py
python SQLite_migration/002_add_routine_scheduling_fields.py
python SQLite_migration/003_create_task_instances_table.py
python SQLite_migration/004_create_emotions_table.py
python SQLite_migration/005_add_indexes_and_foreign_keys.py
python SQLite_migration/006_add_notes_column.py
python SQLite_migration/007_create_user_preferences_table.py
python SQLite_migration/008_create_survey_responses_table.py
python SQLite_migration/009_create_users_table.py
python SQLite_migration/010_add_user_id_foreign_keys.py
```

**Bash/Linux:**
```bash
cd task_aversion_app
export DATABASE_URL="sqlite:///data/task_aversion.db"

# Run all migrations in order
python SQLite_migration/001_initial_schema.py
python SQLite_migration/002_add_routine_scheduling_fields.py
python SQLite_migration/003_create_task_instances_table.py
python SQLite_migration/004_create_emotions_table.py
python SQLite_migration/005_add_indexes_and_foreign_keys.py
python SQLite_migration/006_add_notes_column.py
python SQLite_migration/007_create_user_preferences_table.py
python SQLite_migration/008_create_survey_responses_table.py
python SQLite_migration/009_create_users_table.py
python SQLite_migration/010_add_user_id_foreign_keys.py
```

### Step 3: Verify SQLite Migrations

```powershell
python SQLite_migration/check_migration_status.py
```

All migrations should show `[OK]` status.

## Part 2: Test PostgreSQL Migrations with Docker

### Prerequisites
- Docker installed and running
- docker-compose installed

### Step 1: Start Docker PostgreSQL Container

**From project root directory:**

```powershell
# Start PostgreSQL container
docker-compose -f docker-compose.test.yml up -d

# Check if it's running
docker ps | Select-String "test-postgres"
```

**Bash/Linux:**
```bash
# Start PostgreSQL container
docker-compose -f docker-compose.test.yml up -d

# Check if it's running
docker ps | grep test-postgres
```

### Step 2: Run PostgreSQL Migrations

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "postgresql://testuser:testpassword@localhost:5433/task_aversion_test"

# Run all migrations in order
python PostgreSQL_migration/001_initial_schema.py
python PostgreSQL_migration/002_add_routine_scheduling_fields.py
python PostgreSQL_migration/003_create_task_instances_table.py
python PostgreSQL_migration/004_create_emotions_table.py
python PostgreSQL_migration/005_add_indexes_and_foreign_keys.py
python PostgreSQL_migration/006_add_notes_column.py
python PostgreSQL_migration/007_create_user_preferences_table.py
python PostgreSQL_migration/008_create_survey_responses_table.py
python PostgreSQL_migration/009_create_users_table.py
python PostgreSQL_migration/010_add_user_id_foreign_keys.py
```

**Or use the automated test script:**

**PowerShell:**
```powershell
cd task_aversion_app
.\PostgreSQL_migration\test_local_migrations.ps1
```

**Bash/Linux:**
```bash
cd task_aversion_app
bash PostgreSQL_migration/test_local_migrations.sh
```

### Step 3: Verify PostgreSQL Migrations

```powershell
python PostgreSQL_migration/check_migration_status.py
```

### Step 4: Test Database Operations

Create a simple test script to verify database operations work:

```python
# test_db_operations.py
import os
os.environ['DATABASE_URL'] = 'postgresql://testuser:testpassword@localhost:5433/task_aversion_test'

from backend.database import get_session, User, Task
from backend.task_manager import TaskManager

# Test User creation
with get_session() as session:
    # Create a test user
    user = User(
        email='test@example.com',
        google_id='test_google_id_123',
        username='testuser'
    )
    session.add(user)
    session.commit()
    print(f"[OK] Created user: {user.user_id}, {user.email}")

# Test Task creation with user_id
with get_session() as session:
    task = Task(
        task_id='t1234567890',
        name='Test Task',
        user_id=1  # Link to user created above
    )
    session.add(task)
    session.commit()
    print(f"[OK] Created task: {task.task_id}, user_id: {task.user_id}")

# Test TaskManager queries with user_id
tm = TaskManager()
print("[OK] TaskManager initialized")
```

### Step 5: Clean Up Docker Container (Optional)

**To stop container (keep data):**
```powershell
cd ..  # Go to project root
docker-compose -f docker-compose.test.yml stop
```

**To remove container (keep data):**
```powershell
docker-compose -f docker-compose.test.yml down
```

**To remove container and volumes (delete all test data):**
```powershell
docker-compose -f docker-compose.test.yml down -v
```

## Troubleshooting

### SQLite Issues

**"Database is locked" error:**
- Close any applications using the database (including the app itself)
- Make sure no other processes have the database file open
- On Windows, check if OneDrive is syncing the database file

**"Table already exists" warnings:**
- This is normal if you've already run the migration
- Migrations are idempotent and will skip existing tables/columns

### Docker PostgreSQL Issues

**"Connection refused" error:**
- Wait a few seconds for PostgreSQL to start (it takes ~10-15 seconds)
- Check if container is running: `docker ps | grep test-postgres`
- Check container logs: `docker logs test-postgres`

**"Port 5433 already in use" error:**
- Another PostgreSQL instance might be using port 5433
- Change port in `docker-compose.test.yml` to a different port (e.g., 5434)
- Update DATABASE_URL accordingly

**"Container name already in use" error:**
- Remove existing container: `docker rm -f test-postgres`
- Or change container name in `docker-compose.test.yml`

### Migration Issues

**"Foreign key constraint failed" error:**
- This is expected if tables don't exist yet
- Run migrations in order (001, 002, 003, etc.)
- Check prerequisite tables exist before running migration

**"Column already exists" warnings:**
- This is normal if migration was already run
- Migrations check for existing columns and skip them

## Next Steps After Testing

Once SQLite and PostgreSQL migrations are tested:

1. ✅ **Migrations tested locally** (SQLite + Docker PostgreSQL)
2. ⏳ **Implement OAuth authentication** (backend/auth.py)
3. ⏳ **Test OAuth flow locally** (with localhost callback)
4. ⏳ **Modify import to require authentication**
5. ⏳ **Test authenticated import with user isolation**
6. ⏳ **Deploy to production server** (Phase 3 & 4)

## Quick Reference

### SQLite Testing
```powershell
cd task_aversion_app
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"
python SQLite_migration/check_migration_status.py
```

### Docker PostgreSQL Testing
```powershell
# Start container (from project root)
docker-compose -f docker-compose.test.yml up -d

# Run migrations (from task_aversion_app)
cd task_aversion_app
$env:DATABASE_URL = "postgresql://testuser:testpassword@localhost:5433/task_aversion_test"
python PostgreSQL_migration/check_migration_status.py

# Or use automated script
.\PostgreSQL_migration\test_local_migrations.ps1
```

### Clean Up
```powershell
# Stop container
docker-compose -f docker-compose.test.yml stop

# Remove container
docker-compose -f docker-compose.test.yml down

# Remove container and volumes (delete test data)
docker-compose -f docker-compose.test.yml down -v
```
