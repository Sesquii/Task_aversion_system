# Test Safety: Protecting Your Main Database

## ⚠️ Important: Test Database Isolation

The SQL injection test suite is designed to **NOT affect your main database**. Here's how it works:

## Automatic Test Database Selection

### SQLite (Default)
- **Test database**: `data/test_task_aversion.db` (separate file)
- **Your main database**: `data/task_aversion.db` (untouched)
- The test script automatically uses a different database file

### PostgreSQL
- **You must specify a test database** in `DATABASE_URL`
- The test script will warn you if the database name doesn't contain "test"
- **Never point tests at your production database!**

## Safe Testing Options

### Option 1: Use Default Test Database (SQLite) - Easiest

```bash
cd task_aversion_app
python tests/test_sql_injection.py
```

This automatically uses `data/test_task_aversion.db` - your main database is safe!

### Option 2: Create Separate PostgreSQL Test Database

```bash
# Create a test database (separate from your main database)
createdb test_task_aversion

# Run tests against test database
export DATABASE_URL="postgresql://username:password@localhost/test_task_aversion"
cd task_aversion_app
python tests/test_sql_injection.py
```

### Option 3: Use Docker Test Database (Safest)

```bash
# Start a completely isolated PostgreSQL container
docker run --name postgres-test \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=test_task_aversion \
  -p 5433:5432 \  # Different port to avoid conflicts
  -d postgres:15

# Run tests
export DATABASE_URL="postgresql://postgres:testpass@localhost:5433/test_task_aversion"
cd task_aversion_app
python tests/test_sql_injection.py

# Cleanup when done
docker stop postgres-test
docker rm postgres-test
```

## What the Tests Do

The tests:
1. ✅ Create temporary test tables (e.g., `test_sql_injection`)
2. ✅ Clean up test tables after each test
3. ✅ Never touch your main `tasks`, `task_instances`, or other production tables
4. ✅ Use separate database file/name for SQLite/PostgreSQL

## Verification: Your Database is Safe

### Before Running Tests
```bash
# Check your main database (SQLite)
ls -la data/task_aversion.db

# Or check PostgreSQL tables
psql -d your_main_database -c "\dt"
```

### After Running Tests
```bash
# Verify main database is unchanged
ls -la data/task_aversion.db  # Should have same size/timestamp

# Or check PostgreSQL tables
psql -d your_main_database -c "\dt"  # Should show same tables
```

## What If I Accidentally Point at Production?

The test script will:
1. ⚠️ Warn you if `DATABASE_URL` doesn't contain "test"
2. ⚠️ Ask for confirmation before proceeding
3. ✅ You can cancel with Ctrl+C or type "no"

## Best Practices

1. **Always use a test database** - never test against production
2. **Use different database names** - `test_task_aversion` vs `task_aversion`
3. **Use Docker for isolation** - completely separate environment
4. **Verify before testing** - check `DATABASE_URL` before running
5. **Clean up after** - remove test databases when done

## Troubleshooting

### "Database is locked" (SQLite)
- The test database might be in use
- Close any other connections to `test_task_aversion.db`
- Or delete it and let tests recreate it: `rm data/test_task_aversion.db`

### "Database already exists" (PostgreSQL)
- This is fine - tests will use existing test database
- Or drop and recreate: `dropdb test_task_aversion && createdb test_task_aversion`

### "Permission denied"
- Make sure you have permissions to create/drop test databases
- For PostgreSQL, you need `CREATEDB` privilege

## Summary

✅ **Your main database is safe** - tests use separate test databases  
✅ **No server shutdown needed** - tests run in isolation  
✅ **Automatic cleanup** - test tables are removed after tests  
✅ **Warning system** - script warns if pointing at non-test database  

Just run the tests - they're designed to be safe!
