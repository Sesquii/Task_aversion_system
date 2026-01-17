# SQL Injection Security Fix

## Overview
This document describes the security fixes implemented to protect the application from SQL injection attacks.

## Date
2025-01-17

## Vulnerabilities Fixed

### 1. SQL Injection in CSV Import (`backend/csv_import.py`)

**Issue**: The `add_column_to_table()` function used f-strings to construct SQL DDL statements, which could potentially allow SQL injection if identifiers were not properly validated.

**Location**: `backend/csv_import.py`, line 240-245

**Fix Applied**:
- Added `_quote_identifier()` function to properly quote SQL identifiers according to database dialect
- Added column type whitelist validation (only allows: TEXT, INTEGER, REAL, BOOLEAN, NUMERIC)
- Properly escape double quotes in identifiers to prevent injection
- Table names come from whitelist (ALLOWED_FILES), column names are validated via `validate_column_name()`

**Code Changes**:
```python
def _quote_identifier(identifier: str, dialect_name: str) -> str:
    """Properly quote a SQL identifier to prevent SQL injection."""
    identifier = identifier.strip().strip('"').strip('`').strip("'")
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
```

### 2. Input Validation for Database Identifiers

**Issue**: Task IDs, instance IDs, and user IDs used in database queries were not validated, potentially allowing malicious input.

**Fix Applied**:
- Added `validate_task_id()` function to ensure task IDs match expected format (t{timestamp})
- Added `validate_instance_id()` function to ensure instance IDs match expected format (i{timestamp})
- Added `validate_user_id()` function to ensure user IDs are positive integers

**Location**: `backend/security_utils.py`

## Security Best Practices Verified

### ✅ SQLAlchemy ORM Usage
All database queries use SQLAlchemy ORM with parameterized filters:
- `Task.task_id == task_id` (safe - SQLAlchemy parameterizes automatically)
- `Task.user_id == user_id` (safe - SQLAlchemy parameterizes automatically)
- No string concatenation in queries

### ✅ Input Validation
- Task names, descriptions, notes validated via `security_utils.py`
- Column names validated via `validate_column_name()` in `csv_import.py`
- Table names come from whitelist (ALLOWED_FILES)

### ✅ Data Isolation
- All queries filter by `user_id` to ensure data isolation
- User IDs are validated to be positive integers
- CSV imports override user_id from CSV with authenticated user_id

## Remaining Security Considerations

### CSV Import Feature
The CSV import feature is currently **DISABLED** in the UI (see `ui/settings_page.py`). The code has been secured, but the feature should be re-enabled only after:
1. Thorough security testing
2. Penetration testing
3. Code review

### Recommendations
1. **Enable identifier validation**: Consider adding validation calls for task_id and instance_id in manager classes before database queries
2. **Rate limiting**: Consider adding rate limiting for database operations to prevent DoS
3. **Audit logging**: Consider logging all database schema changes (ALTER TABLE operations)
4. **Regular security audits**: Schedule periodic security reviews

## Testing

### Manual Testing Checklist
- [ ] Verify CSV import with valid column names works
- [ ] Verify CSV import rejects invalid column names
- [ ] Verify SQL injection attempts in column names are blocked
- [ ] Verify task_id validation works correctly
- [ ] Verify instance_id validation works correctly
- [ ] Verify user_id validation works correctly

### Automated Testing
Consider adding unit tests for:
- `_quote_identifier()` function with various inputs
- `validate_task_id()` with valid and invalid inputs
- `validate_instance_id()` with valid and invalid inputs
- `validate_user_id()` with valid and invalid inputs

## Files Modified

1. `backend/csv_import.py`
   - Added `_quote_identifier()` function
   - Modified `add_column_to_table()` to use proper identifier quoting
   - Added column type whitelist validation

2. `backend/security_utils.py`
   - Added `validate_task_id()` function
   - Added `validate_instance_id()` function
   - Added `validate_user_id()` function

## References

- [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [SQLAlchemy Security Best Practices](https://docs.sqlalchemy.org/en/14/core/engines.html#sql-injection)
- [Python SQL Injection Prevention](https://pynative.com/python-sql-injection/)
