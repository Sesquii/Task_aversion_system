# Quick Guide: Running SQL Injection Tests

## ⚠️ Safety First: Your Main Database is Protected

The test suite **automatically uses a separate test database** - your main database will NOT be affected. No need to shut down your server!

## Test on SQLite (Default - Safest)

```bash
cd task_aversion_app
python tests/test_sql_injection.py
```

**What happens:**
- Uses `data/test_task_aversion.db` (separate from your main `task_aversion.db`)
- Your main database is completely untouched
- Tests create temporary tables and clean up after themselves

## Test on PostgreSQL

### ⚠️ Important: Use a Test Database!

**Never point tests at your production database!** Always use a separate test database.

### Option 1: Local PostgreSQL (Create Test Database)

```bash
# Create a SEPARATE test database (not your main database!)
createdb test_task_aversion

# Set DATABASE_URL to the TEST database
export DATABASE_URL="postgresql://username:password@localhost/test_task_aversion"

# Run tests
cd task_aversion_app
python tests/test_sql_injection.py

# The script will warn you if DATABASE_URL doesn't contain "test"
```

### Option 2: Docker PostgreSQL (Recommended - Most Isolated)

**This is the safest option** - completely isolated from your main database.

```bash
# Start PostgreSQL container
docker run --name postgres-test \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=test_task_aversion \
  -p 5432:5432 \
  -d postgres:15

# Set DATABASE_URL
export DATABASE_URL="postgresql://postgres:testpass@localhost/test_task_aversion"

# Run tests
cd task_aversion_app
python tests/test_sql_injection.py

# Cleanup when done
docker stop postgres-test
docker rm postgres-test
```

### Option 3: PowerShell (Windows)

```powershell
# Start PostgreSQL container
docker run --name postgres-test `
  -e POSTGRES_PASSWORD=testpass `
  -e POSTGRES_DB=test_task_aversion `
  -p 5432:5432 `
  -d postgres:15

# Set DATABASE_URL
$env:DATABASE_URL="postgresql://postgres:testpass@localhost/test_task_aversion"

# Run tests
cd task_aversion_app
python tests/test_sql_injection.py

# Cleanup when done
docker stop postgres-test
docker rm postgres-test
```

## What the Tests Check

1. ✅ Column name validation rejects SQL injection attempts
2. ✅ Identifier quoting properly escapes special characters
3. ✅ Task ID validation rejects invalid formats
4. ✅ User ID validation rejects invalid values
5. ✅ ORM queries are safe from SQL injection
6. ✅ Add column operation is protected
7. ✅ CSV import handles malicious column names safely

## Expected Output

If all tests pass, you'll see:
```
[SUCCESS] All SQL injection tests passed!
The application appears to be protected from SQL injection attacks.
```

If tests fail, you'll see which specific tests failed and why.

## Safety Features

✅ **Automatic test database** - SQLite uses separate `test_task_aversion.db` file  
✅ **Warning system** - Script warns if DATABASE_URL doesn't contain "test"  
✅ **Isolated tests** - Tests create temporary tables and clean up after  
✅ **No server shutdown needed** - Tests run alongside your main app  

## Troubleshooting

### ImportError: No module named 'backend'
Make sure you're in the `task_aversion_app` directory when running the tests.

### Database connection errors
- Check that PostgreSQL is running (if testing on PostgreSQL)
- Verify DATABASE_URL is correct
- Check that the database exists
- Verify credentials are correct

### Permission errors
Make sure you have read/write permissions to the database and test files.

### "Database is locked" (SQLite)
- Close any connections to `test_task_aversion.db`
- Or delete it: `rm data/test_task_aversion.db` (tests will recreate it)

### Worried about your main database?
- Check `DATABASE_URL` before running: `echo $DATABASE_URL`
- For SQLite, verify it uses `test_task_aversion.db`, not `task_aversion.db`
- For PostgreSQL, verify database name contains "test"

## More Details

See `docs/SQL_INJECTION_TESTING_GUIDE.md` for comprehensive testing documentation.
