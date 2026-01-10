# PostgreSQL Migration Scripts

This folder contains migration scripts for PostgreSQL production deployment.

## Purpose

These scripts convert the SQLite migrations to PostgreSQL-compatible SQL for server deployment.

## Migration Strategy

1. **Local Testing**: Test PostgreSQL migrations using Docker PostgreSQL before deploying to server
2. **Sequential Execution**: Run migrations in order (001, 002, 003, etc.)
3. **Idempotent**: All migrations should be safe to run multiple times

## Local Testing with Docker

### Automated Testing Scripts (Recommended)

The easiest way to test migrations is using the automated test scripts:

**Windows PowerShell:**
```powershell
cd task_aversion_app
.\PostgreSQL_migration\test_migrations_docker.ps1
```

**Linux/macOS:**
```bash
cd task_aversion_app
chmod +x PostgreSQL_migration/test_migrations_docker.sh
./PostgreSQL_migration/test_migrations_docker.sh
```

These scripts will:
1. Check for existing containers and clean them up
2. Start a fresh PostgreSQL 14 container (matches server version 14.2)
3. Wait for PostgreSQL to be ready
4. Set DATABASE_URL environment variable automatically
5. Check current migration status
6. Run all 10 migrations in order (001-010)
7. Perform final status check
8. Keep container running for further testing

**Cleanup when done:**
```bash
# Stop and remove the test container
docker stop test-postgres-migration
docker rm test-postgres-migration
```

### Manual Testing with Docker Compose

Alternatively, you can use docker-compose:

```bash
# From project root directory
docker-compose up -d postgres

# Wait for PostgreSQL to be ready
docker-compose ps postgres

# Set DATABASE_URL (PowerShell)
$env:DATABASE_URL = "postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test"

# Set DATABASE_URL (Bash)
export DATABASE_URL="postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test"

# Navigate to app directory
cd task_aversion_app

# Check migration status
python PostgreSQL_migration/check_migration_status.py

# Run migrations (see "How to Run Migrations" section below)

# Clean up when done
docker-compose down
```

### Manual Testing with Standalone Container

**Start PostgreSQL Container:**
```bash
docker run --name test-postgres \
  -e POSTGRES_PASSWORD=testpassword \
  -e POSTGRES_USER=task_aversion_user \
  -e POSTGRES_DB=task_aversion_test \
  -p 5432:5432 \
  -d postgres:14-alpine
# Using PostgreSQL 14 to match server version (14.2) for accurate testing
```

**Test Connection:**
```bash
# Set DATABASE_URL (PowerShell)
$env:DATABASE_URL = "postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test"

# Set DATABASE_URL (Bash)
export DATABASE_URL="postgresql://task_aversion_user:testpassword@localhost:5432/task_aversion_test"

# Navigate to app directory
cd task_aversion_app

# Run migrations (see "How to Run Migrations" section below)
```

**Clean Up:**
```bash
docker stop test-postgres
docker rm test-postgres
```

## Key Differences from SQLite

### Data Types
- SQLite `INTEGER PRIMARY KEY` → PostgreSQL `BIGSERIAL PRIMARY KEY`
- SQLite `TEXT` → PostgreSQL `TEXT` (same, but check constraints)
- SQLite `JSON` → PostgreSQL `JSONB` (better indexing and performance)

### Syntax Differences
- SQLite: `CREATE TABLE IF NOT EXISTS` → PostgreSQL: Same, but check for existing tables differently
- SQLite: No schema → PostgreSQL: Use `public` schema explicitly
- SQLite: Case-insensitive identifiers → PostgreSQL: Case-sensitive (use quotes if needed)

### Indexes
- PostgreSQL supports more index types (GIN for JSONB, etc.)
- Consider adding JSONB indexes for better query performance

## Migration Script Template

```python
#!/usr/bin/env python3
"""
PostgreSQL Migration: [Description]
Converts SQLite migration [XXX] to PostgreSQL.
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Get DATABASE_URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    print("Example: postgresql://user:password@localhost:5432/dbname")
    sys.exit(1)

if not DATABASE_URL.startswith('postgresql'):
    print("ERROR: This migration is for PostgreSQL only")
    print(f"Current DATABASE_URL: {DATABASE_URL}")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

def run_migration():
    """Run the migration."""
    with engine.connect() as conn:
        try:
            # Check if migration already applied
            # (Implementation depends on migration tracking method)
            
            # Run migration SQL
            # conn.execute(text("ALTER TABLE ..."))
            
            conn.commit()
            print("[SUCCESS] Migration completed")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Migration failed: {e}")
            raise

if __name__ == '__main__':
    run_migration()
```

## Migration Scripts

**All PostgreSQL migration scripts have been created and are ready for use.**

### Migration Order

1. **001_initial_schema.py** - Creates the initial database schema (all tables)
2. **002_add_routine_scheduling_fields.py** - Adds routine scheduling fields to tasks table
3. **003_create_task_instances_table.py** - Creates the task_instances table for storing task execution instances
4. **004_create_emotions_table.py** - Creates the emotions table for storing available emotions
5. **005_add_indexes_and_foreign_keys.py** - Adds performance indexes and foreign key constraints
6. **006_add_notes_column.py** - Adds notes column to tasks table
7. **007_create_user_preferences_table.py** - Creates the user_preferences table for storing user settings and preferences
8. **008_create_survey_responses_table.py** - Creates the survey_responses table for storing survey question responses
9. **009_create_users_table.py** - Creates the users table for OAuth authentication (Google, etc.)
10. **010_add_user_id_foreign_keys.py** - Adds user_id foreign keys to existing tables for user data isolation

### Utility Scripts

- **check_migration_status.py** - Check which migrations have been applied to your PostgreSQL database

## How to Check Migration Status

Before running migrations, check what's already been applied:

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/task_aversion_system"
python PostgreSQL_migration/check_migration_status.py
```

**Bash/Linux:**
```bash
cd task_aversion_app
export DATABASE_URL="postgresql://user:password@localhost:5432/task_aversion_system"
python PostgreSQL_migration/check_migration_status.py
```

This will show you which migrations have been applied and which are still needed.

## How to Run Migrations

### Prerequisites
- Set `DATABASE_URL` environment variable to your PostgreSQL connection string
- Example: `postgresql://user:password@localhost:5432/task_aversion_system`

### Running a Migration

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/task_aversion_system"
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

**Bash/Linux:**
```bash
cd task_aversion_app
export DATABASE_URL="postgresql://user:password@localhost:5432/task_aversion_system"
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

## Important Notes

### Data Import Goes to Database (Not CSV)

**The CSV import functionality (`backend/csv_import.py`) writes data to the DATABASE, not CSV files.**

Despite the name "csv_import", the import process:
- Reads data FROM CSV/ZIP files
- Writes data TO the database using SQLAlchemy models (`session.add()`, `session.commit()`)
- Does NOT modify or write CSV files

This is intentional - all data operations use the database backend by default. CSV files are only used as:
- Export format for data portability
- Import source for data migration

### Migration 010 Notes

Migration 010 adds `user_id` foreign keys to existing tables. Important points:
- New tables (tasks, task_instances, notes) get INTEGER `user_id` columns
- Tables with existing VARCHAR `user_id` (survey_responses, popup_triggers, etc.) get `user_id_new` INTEGER columns
- The `user_preferences` table has VARCHAR `user_id` as PRIMARY KEY - requires special migration (010b) for conversion
- All new `user_id` columns are nullable initially to allow existing anonymous data to remain
- A separate data migration script will populate INTEGER `user_id` from VARCHAR `user_id` values

## PostgreSQL-Specific Features

### Key Conversions from SQLite

1. **JSON Columns**: Uses `JSONB` instead of `TEXT` for JSON storage
   - Better performance and indexing
   - GIN indexes added for efficient JSON queries (Migration 005)

2. **Auto-incrementing IDs**: Uses `SERIAL` or `BIGSERIAL` instead of `INTEGER PRIMARY KEY`
   - PostgreSQL-native auto-increment support

3. **Foreign Key Constraints**: Properly enforced at database level
   - Migration 005 adds foreign key constraint: `task_instances.task_id -> tasks.task_id`
   - Enforced with `ON DELETE RESTRICT` to prevent orphaned records

4. **Indexes**: PostgreSQL-specific index types
   - GIN indexes on JSONB columns for efficient JSON queries
   - Composite indexes for common query patterns

5. **Data Types**: PostgreSQL-native types
   - `VARCHAR(n)` with explicit length constraints
   - `TEXT` for unlimited-length text
   - `JSONB` for JSON data with indexing support

## Status

- ✅ **Complete**: All PostgreSQL migration scripts have been created
- ✅ **Ready for Testing**: Migrations can be tested locally with Docker PostgreSQL
- ✅ **Ready for Deployment**: Migrations can be run on production server after testing

## Migration Safety

- All migrations are **idempotent** - safe to run multiple times
- Migrations check if columns/tables already exist before adding them
- Each migration includes verification steps
- Always backup your database before running migrations:
  ```bash
  pg_dump -U user -d task_aversion_system > backup_$(date +%Y%m%d_%H%M%S).sql
  ```

## Notes

- **SQLite migrations preserved**: Original SQLite migration scripts in `SQLite_migration/` folder are kept as backup
- **Separate scripts**: PostgreSQL migrations are separate from SQLite migrations for clarity
- **Test locally first**: Use Docker PostgreSQL to test migrations before deploying to production
- **Always backup**: Always backup database before running migrations on production
- **Future consideration**: Consider using Alembic for more complex migration management in the future
