# PostgreSQL Migration Scripts

This folder contains migration scripts for PostgreSQL production deployment.

## Purpose

These scripts convert the SQLite migrations to PostgreSQL-compatible SQL for server deployment.

## Migration Strategy

1. **Local Testing**: Test PostgreSQL migrations using Docker PostgreSQL before deploying to server
2. **Sequential Execution**: Run migrations in order (001, 002, 003, etc.)
3. **Idempotent**: All migrations should be safe to run multiple times

## Local Testing with Docker

### Start PostgreSQL Container
```bash
docker run --name test-postgres \
  -e POSTGRES_PASSWORD=testpassword \
  -e POSTGRES_DB=task_aversion_test \
  -p 5432:5432 \
  -d postgres:15
```

### Test Connection
```bash
# Set DATABASE_URL
export DATABASE_URL="postgresql://postgres:testpassword@localhost:5432/task_aversion_test"

# Run migrations
python PostgreSQL_migration/001_initial_schema.py
```

### Clean Up
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

## Status

- ⏳ **Not Started**: PostgreSQL migrations need to be created
- 📝 **Next Step**: Review SQLite migrations and create PostgreSQL equivalents

## Notes

- Migrations should be tested locally before running on production server
- Always backup database before running migrations
- Consider using Alembic for more complex migration management in the future
