# SQLite Migration Scripts

This folder contains migration scripts to update your SQLite database schema as new features are added.

## Migration Order

**IMPORTANT**: Run migrations in the order listed below. Each migration script is numbered and should be run sequentially.

### Migration Scripts

1. **001_initial_schema.py** - Creates the initial database schema (if not already done)
2. **002_add_routine_scheduling_fields.py** - Adds routine scheduling fields to tasks table

### Utility Scripts

- **check_migration_status.py** - Check which migrations have been applied to your database

## How to Check Migration Status

Before running migrations, check what's already been applied:

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"
python SQLite_migration/check_migration_status.py
```

This will show you which migrations have been applied and which are still needed.

## How to Run Migrations

### Prerequisites
- Set `DATABASE_URL` environment variable to your SQLite database path
- Example: `sqlite:///data/task_aversion.db`

### Running a Migration

**PowerShell:**
```powershell
cd task_aversion_app
$env:DATABASE_URL = "sqlite:///data/task_aversion.db"
python SQLite_migration/002_add_routine_scheduling_fields.py
```

**Command Prompt:**
```cmd
cd task_aversion_app
set DATABASE_URL=sqlite:///data/task_aversion.db
python SQLite_migration\002_add_routine_scheduling_fields.py
```

**Python (direct):**
```python
import os
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
exec(open('SQLite_migration/002_add_routine_scheduling_fields.py').read())
```

## Migration Safety

- All migrations are **idempotent** - safe to run multiple times
- Migrations check if columns already exist before adding them
- Each migration includes verification steps
- Always backup your database before running migrations:
  ```powershell
  Copy-Item data\task_aversion.db data\task_aversion.db.backup
  ```

## Future: PostgreSQL Migration

Once all SQLite migrations are complete and tested, we will:
1. Review all migration scripts
2. Create a unified migration script
3. Convert it to PostgreSQL-compatible syntax
4. Test on a PostgreSQL database

## Troubleshooting

### "Column already exists" errors
- This is normal if you've already run the migration
- The script will skip existing columns

### "Table does not exist" errors
- Run `001_initial_schema.py` first (or use `migrate_csv_to_database.py`)

### Database locked errors
- Close any applications using the database (including the app itself)
- Make sure no other processes have the database file open

