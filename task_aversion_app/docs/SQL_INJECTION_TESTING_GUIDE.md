# SQL Injection Testing Guide

## Overview
This guide explains how to test for SQL injection vulnerabilities to verify the security fixes work correctly.

## Why Test on Both SQLite and PostgreSQL?

**YES, you should test on both databases** because:

1. **Different Quoting Mechanisms**: 
   - SQLite uses double quotes or backticks for identifiers
   - PostgreSQL uses double quotes only
   - The quoting implementation must work correctly for both

2. **Different SQL Dialects**:
   - Some SQL syntax differs between databases
   - What works on SQLite might not work on PostgreSQL and vice versa

3. **Production Environment**:
   - Your production server uses PostgreSQL
   - You want to catch any issues before deployment

## Testing Steps

### 1. Test on SQLite (Local Development)

```bash
# Navigate to the app directory
cd task_aversion_app

# Make sure SQLite is the default (or set it explicitly)
unset DATABASE_URL  # Or ensure it's not set

# Run the test suite
python tests/test_sql_injection.py
```

**Expected Output:**
```
============================================================
SQL INJECTION SECURITY TEST SUITE
============================================================

Database: sqlite:///data/task_aversion.db
Dialect: SQLite

[TEST] Column Name Validation
------------------------------------------------------------
[PASS] Column name ''; DROP TABLE tasks; --' correctly rejected: ...
[PASS] Column name '' OR '1'='1' correctly rejected: ...
...

[SUCCESS] All SQL injection tests passed!
```

### 2. Test on PostgreSQL (Production-like Environment)

#### Option A: Use Local PostgreSQL

```bash
# Install PostgreSQL (if not already installed)
# Windows: Download from https://www.postgresql.org/download/windows/
# macOS: brew install postgresql
# Linux: sudo apt-get install postgresql

# Create a test database
createdb test_task_aversion

# Set DATABASE_URL and run tests
export DATABASE_URL="postgresql://username:password@localhost/test_task_aversion"
# OR on Windows PowerShell:
$env:DATABASE_URL="postgresql://username:password@localhost/test_task_aversion"

# Run the test suite
python tests/test_sql_injection.py
```

#### Option B: Use Docker PostgreSQL (Easier)

```bash
# Start PostgreSQL in Docker
docker run --name postgres-test \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=test_task_aversion \
  -p 5432:5432 \
  -d postgres:15

# Set DATABASE_URL
export DATABASE_URL="postgresql://postgres:testpass@localhost/test_task_aversion"

# Run tests
python tests/test_sql_injection.py

# Cleanup (when done)
docker stop postgres-test
docker rm postgres-test
```

#### Option C: Test on Staging Server

If you have a staging server with PostgreSQL:

```bash
# Set DATABASE_URL to staging server
export DATABASE_URL="postgresql://user:pass@staging-server.com:5432/task_aversion"

# Run tests
python tests/test_sql_injection.py
```

## Manual Testing Checklist

### Test 1: Column Name Injection (CSV Import)

1. Create a CSV file with a malicious column name:
```csv
task_id,name,name'); DROP TABLE tasks; --
t1234567890,Test Task,malicious
```

2. Try to import the CSV (if CSV import is enabled)
3. **Expected**: Import should fail or reject the malicious column
4. **Verify**: Check that the `tasks` table still exists in the database

### Test 2: Task ID Injection

1. Try to access a task with malicious task_id:
```python
# In Python console
from backend.task_manager import TaskManager
tm = TaskManager()

# Try SQL injection
task_id = "t1234567890'; DROP TABLE tasks; --"
task = tm.get_task(task_id, user_id=1)  # Should fail validation
```

2. **Expected**: Should raise `ValidationError`
3. **Verify**: Check that `tasks` table still exists

### Test 3: User ID Injection

1. Try to query with malicious user_id:
```python
# This should fail type checking before it reaches SQL
user_id = "1 OR 1=1"
tasks = tm.get_all(user_id=user_id)  # Should raise ValidationError
```

2. **Expected**: Should raise `ValidationError` or `TypeError`
3. **Verify**: Check that no unauthorized data is returned

### Test 4: ORM Query Safety

1. Create a test script:
```python
from backend.database import get_session, Task

session = get_session()

# This should be safe - SQLAlchemy parameterizes automatically
attack_string = "t123'; DROP TABLE tasks; --"
result = session.query(Task).filter(Task.task_id == attack_string).first()

# Should return None (no task with that exact ID)
# Should NOT drop the table
assert result is None

# Verify table still exists
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
assert 'tasks' in tables

print("ORM query is safe from SQL injection!")
```

## What to Look For

### ✅ Good Signs (Tests Passing)

- All validation functions reject malicious input
- SQL injection attempts are blocked before reaching the database
- Database tables remain intact after injection attempts
- Error messages don't reveal database structure

### ❌ Bad Signs (Tests Failing)

- Injection attempts succeed in modifying data
- Tables are dropped or deleted
- Unauthorized data is returned
- Database errors reveal table/column names

## Common SQL Injection Attack Patterns

The test suite includes these attack patterns:

1. **Classic Injection**: `'; DROP TABLE tasks; --`
2. **Union Attacks**: `' UNION SELECT * FROM users --`
3. **Boolean Attacks**: `' OR '1'='1`
4. **Comment Attacks**: `'; DELETE FROM tasks --`
5. **Special Characters**: Quotes, semicolons, comments
6. **Path Traversal**: `../../etc/passwd`
7. **Null Byte Injection**: `test\x00DROP TABLE`
8. **Unicode Injection**: Various unicode characters

## Interpreting Test Results

### All Tests Pass ✅
- Your application is protected from SQL injection
- You can proceed with deployment
- Still maintain security best practices going forward

### Some Tests Fail ❌
1. Review the failed tests
2. Check which vulnerabilities were exposed
3. Fix the security issues
4. Re-run tests until all pass

### Tests Fail on PostgreSQL but Pass on SQLite
- This indicates a database-specific issue
- Review the `_quote_identifier()` function
- Ensure PostgreSQL-specific quoting is correct
- Update the code and re-test

## Continuous Testing

### Pre-Deployment Checklist

- [ ] Run test suite on SQLite
- [ ] Run test suite on PostgreSQL
- [ ] Manual testing of critical paths
- [ ] Review error logs for any suspicious activity
- [ ] Verify database schema is unchanged after tests

### Automated Testing in CI/CD

Consider adding SQL injection tests to your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Test SQL Injection Protection
  env:
    DATABASE_URL: postgresql://postgres:test@localhost/test_db
  run: |
    python tests/test_sql_injection.py
```

## Additional Security Testing

Beyond SQL injection, also test for:

1. **XSS (Cross-Site Scripting)**: Test HTML escaping in user input
2. **CSRF (Cross-Site Request Forgery)**: Test authentication tokens
3. **Authentication**: Test login/logout security
4. **Authorization**: Test user data isolation
5. **Input Validation**: Test length limits, type checking
6. **Rate Limiting**: Test DoS protection

## Resources

- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [SQLAlchemy Security Documentation](https://docs.sqlalchemy.org/en/14/core/engines.html#sql-injection)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)

## Questions?

If tests fail or you're unsure about results:
1. Review the error messages carefully
2. Check the database logs
3. Verify the security fix code is correct
4. Consult security documentation
5. Consider a security audit for production systems
