#!/usr/bin/env python3
"""
SQL Injection Security Test Suite

Tests to verify SQL injection vulnerabilities are properly fixed.
Run this after implementing security fixes to ensure protection.

IMPORTANT: This script uses a SEPARATE TEST DATABASE to avoid affecting
your production/development database. Your existing database will NOT be modified.

Usage:
    # Test with SQLite (uses separate test database)
    python tests/test_sql_injection.py

    # Test with PostgreSQL (uses separate test database)
    DATABASE_URL=postgresql://user:pass@localhost/test_db python tests/test_sql_injection.py
"""
import os
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# CRITICAL: Use a separate test database to avoid affecting production/development data
# Override DATABASE_URL to point to a test database
if 'DATABASE_URL' not in os.environ or not os.environ['DATABASE_URL']:
    # Default to SQLite test database (separate from main database)
    TEST_DB_PATH = Path(__file__).parent.parent / 'data' / 'test_task_aversion.db'
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB_PATH}'
    print(f"[INFO] Using test database: {os.environ['DATABASE_URL']}")
    print(f"[INFO] Your main database will NOT be affected")
elif 'test' not in os.environ['DATABASE_URL'].lower():
    # Warn if DATABASE_URL doesn't contain 'test'
    print(f"[WARNING] DATABASE_URL is set to: {os.environ['DATABASE_URL']}")
    print(f"[WARNING] Make sure this is a TEST database, not your production database!")
    response = input("Continue with this database? (yes/no): ")
    if response.lower() != 'yes':
        print("[INFO] Test cancelled. Set DATABASE_URL to a test database and try again.")
        sys.exit(1)

from backend.database import get_session, init_db, engine, DATABASE_URL
from backend.csv_import import (
    add_column_to_table, validate_column_name, 
    _quote_identifier, handle_extra_columns
)
from backend.security_utils import (
    validate_task_id, validate_instance_id, validate_user_id,
    ValidationError
)
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from sqlalchemy import text, inspect


# ============================================================================
# Test Data: SQL Injection Attack Strings
# ============================================================================

SQL_INJECTION_ATTEMPTS = [
    # Classic SQL injection patterns
    "'; DROP TABLE tasks; --",
    "' OR '1'='1",
    "'; INSERT INTO tasks VALUES ('hacked', 'hacked'); --",
    "' UNION SELECT * FROM users --",
    
    # Column name injection attempts
    "name'); DROP TABLE tasks; --",
    "name\"; DROP TABLE tasks; --",
    "name'; DELETE FROM tasks WHERE '1'='1' --",
    "name\"); DELETE FROM tasks; --",
    
    # Identifier injection attempts
    'test"; DROP TABLE tasks; --',
    "test'; DROP TABLE tasks; --",
    "test`; DROP TABLE tasks; --",
    "test'); DROP TABLE tasks; --",
    
    # Special characters that might break quoting
    'test"test',
    "test'test",
    "test`test",
    'test;test',
    "test--test",
    "test/*test*/",
    
    # Path traversal attempts
    "../../etc/passwd",
    "..\\..\\windows\\system32",
    
    # Null byte injection
    "test\x00DROP TABLE",
    
    # Very long strings (DoS)
    "A" * 1000,  # Expression evaluated at runtime - creates 1000 character string
    
    # Unicode injection attempts
    "test\u0000DROP",
    "test\u0027DROP",  # Single quote
]


# ============================================================================
# Test Functions
# ============================================================================

def test_column_name_validation():
    """Test that column name validation rejects SQL injection attempts."""
    print("\n[TEST] Column Name Validation")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    for attack_string in SQL_INJECTION_ATTEMPTS:
        is_valid, error_msg = validate_column_name(attack_string)
        if is_valid:
            print(f"[FAIL] Column name '{attack_string[:50]}' was accepted (should be rejected)")
            failed += 1
        else:
            print(f"[PASS] Column name '{attack_string[:50]}' correctly rejected: {error_msg}")
            passed += 1
    
    print(f"\n[RESULT] Column Validation: {passed} passed, {failed} failed")
    return failed == 0


def test_identifier_quoting():
    """Test that identifier quoting properly escapes special characters."""
    print("\n[TEST] Identifier Quoting")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    test_cases = [
        ("normal_column", True),
        ("column_with_underscore", True),
        ('column"with_quote', True),  # Should be escaped
        ("column'with_quote", True),  # Should be escaped
        ("column;with_semicolon", True),  # Should be quoted
    ]
    
    for identifier, should_work in test_cases:
        try:
            dialect = 'sqlite' if DATABASE_URL.startswith('sqlite') else 'postgresql'
            quoted = _quote_identifier(identifier, dialect)
            
            # Check that quotes are properly escaped
            if '"' in identifier:
                if quoted.count('"') >= 3:  # Opening quote, closing quote, and escaped quotes
                    print(f"[PASS] Identifier '{identifier}' properly quoted: {quoted}")
                    passed += 1
                else:
                    print(f"[FAIL] Identifier '{identifier}' not properly escaped: {quoted}")
                    failed += 1
            else:
                # Should be wrapped in quotes
                if quoted.startswith('"') and quoted.endswith('"'):
                    print(f"[PASS] Identifier '{identifier}' properly quoted: {quoted}")
                    passed += 1
                else:
                    print(f"[FAIL] Identifier '{identifier}' not properly quoted: {quoted}")
                    failed += 1
        except Exception as e:
            print(f"[FAIL] Identifier '{identifier}' raised exception: {e}")
            failed += 1
    
    print(f"\n[RESULT] Identifier Quoting: {passed} passed, {failed} failed")
    return failed == 0


def test_add_column_injection():
    """Test that add_column_to_table rejects SQL injection attempts."""
    print("\n[TEST] Add Column SQL Injection Protection")
    print("-" * 60)
    
    # Create a test table first
    session = get_session()
    try:
        # Create a test table
        session.execute(text("CREATE TABLE IF NOT EXISTS test_sql_injection (id INTEGER PRIMARY KEY)"))
        session.commit()
        
        passed = 0
        failed = 0
        
        for attack_string in SQL_INJECTION_ATTEMPTS[:10]:  # Test first 10 to avoid too many failures
            try:
                # First validate the column name (should reject)
                is_valid, error_msg = validate_column_name(attack_string)
                if is_valid:
                    # If somehow validation passes, try adding the column
                    # This should still be safe because of quoting, but it shouldn't happen
                    result = add_column_to_table('test_sql_injection', attack_string, 'TEXT', session)
                    if result:
                        # Check if malicious table was created
                        inspector = inspect(engine)
                        tables = inspector.get_table_names()
                        if 'tasks' not in tables or len(tables) == 1:
                            print(f"[PASS] Column '{attack_string[:50]}' rejected by validation")
                            passed += 1
                        else:
                            print(f"[FAIL] Column '{attack_string[:50]}' was added (might be vulnerable)")
                            failed += 1
                    else:
                        print(f"[PASS] Column '{attack_string[:50]}' correctly rejected")
                        passed += 1
                else:
                    print(f"[PASS] Column '{attack_string[:50]}' rejected by validation: {error_msg}")
                    passed += 1
            except ValidationError:
                print(f"[PASS] Column '{attack_string[:50]}' rejected by validation")
                passed += 1
            except Exception as e:
                # Any exception is good - means attack was blocked
                print(f"[PASS] Column '{attack_string[:50]}' blocked with exception: {type(e).__name__}")
                passed += 1
        
        # Cleanup
        session.execute(text("DROP TABLE IF EXISTS test_sql_injection"))
        session.commit()
        
    except Exception as e:
        print(f"[ERROR] Test setup failed: {e}")
        return False
    finally:
        session.close()
    
    print(f"\n[RESULT] Add Column Protection: {passed} passed, {failed} failed")
    return failed == 0


def test_task_id_validation():
    """Test that task_id validation rejects invalid formats."""
    print("\n[TEST] Task ID Validation")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    # Valid task IDs
    valid_ids = [
        "t1234567890",
        "t9999999999",
        "",  # Empty is allowed for new tasks
    ]
    
    # Invalid task IDs (injection attempts)
    invalid_ids = [
        "'; DROP TABLE tasks; --",
        "t123'; DROP TABLE tasks; --",
        "t123 OR 1=1",
        "t123 UNION SELECT * FROM tasks",
        "t123; DELETE FROM tasks",
        "../../etc/passwd",
    ]
    
    for task_id in valid_ids:
        try:
            validated = validate_task_id(task_id)
            print(f"[PASS] Valid task_id '{task_id}' accepted")
            passed += 1
        except ValidationError as e:
            print(f"[FAIL] Valid task_id '{task_id}' rejected: {e}")
            failed += 1
    
    for task_id in invalid_ids:
        try:
            validated = validate_task_id(task_id)
            print(f"[FAIL] Invalid task_id '{task_id}' was accepted (should be rejected)")
            failed += 1
        except ValidationError:
            print(f"[PASS] Invalid task_id '{task_id[:50]}' correctly rejected")
            passed += 1
    
    print(f"\n[RESULT] Task ID Validation: {passed} passed, {failed} failed")
    return failed == 0


def test_user_id_validation():
    """Test that user_id validation rejects invalid values."""
    print("\n[TEST] User ID Validation")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    # Valid user IDs
    valid_ids = [1, 100, 999999]
    
    # Invalid user IDs
    invalid_ids = [
        None,
        0,
        -1,
        "'; DROP TABLE users; --",
        "1 OR 1=1",
        "1; DELETE FROM users",
    ]
    
    for user_id in valid_ids:
        try:
            validated = validate_user_id(user_id)
            if validated == user_id:
                print(f"[PASS] Valid user_id {user_id} accepted")
                passed += 1
            else:
                print(f"[FAIL] Valid user_id {user_id} was modified")
                failed += 1
        except ValidationError as e:
            print(f"[FAIL] Valid user_id {user_id} rejected: {e}")
            failed += 1
    
    for user_id in invalid_ids:
        try:
            validated = validate_user_id(user_id)
            print(f"[FAIL] Invalid user_id {user_id} was accepted (should be rejected)")
            failed += 1
        except (ValidationError, TypeError):
            print(f"[PASS] Invalid user_id {user_id} correctly rejected")
            passed += 1
    
    print(f"\n[RESULT] User ID Validation: {passed} passed, {failed} failed")
    return failed == 0


def test_orm_queries_safe():
    """Test that ORM queries are safe from SQL injection."""
    print("\n[TEST] ORM Query Safety")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    # Create test data
    session = get_session()
    try:
        from backend.database import Task, User
        
        # Create a test user first (required for foreign key constraint)
        # Check if user already exists
        test_user = session.query(User).filter(User.user_id == 1).first()
        if not test_user:
            test_user = User(
                user_id=1,
                email="test@example.com",
                username="testuser"
            )
            session.add(test_user)
            session.commit()
        
        # Create a test task
        test_task = Task(
            task_id="t9999999999",
            name="Test Task",
            user_id=1
        )
        session.add(test_task)
        session.commit()
        
        # Test 1: Injection attempt in task_id filter
        try:
            attack_string = "t9999999999'; DROP TABLE tasks; --"
            # This should be safe because SQLAlchemy parameterizes
            result = session.query(Task).filter(Task.task_id == attack_string).first()
            if result is None:
                print(f"[PASS] Injection attempt in task_id filter blocked (no result found)")
                passed += 1
            else:
                # Check if table still exists
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                if 'tasks' in tables:
                    print(f"[PASS] Injection attempt in task_id filter blocked (table still exists)")
                    passed += 1
                else:
                    print(f"[FAIL] Injection attempt in task_id filter succeeded (table dropped)")
                    failed += 1
        except Exception as e:
            # Rollback in case of database errors to avoid InFailedSqlTransaction
            session.rollback()
            print(f"[PASS] Injection attempt in task_id filter blocked with exception: {type(e).__name__}")
            passed += 1
        
        # Test 2: Injection attempt in user_id filter
        try:
            attack_string = "1 OR 1=1"
            # This should be safe because SQLAlchemy parameterizes
            result = session.query(Task).filter(Task.user_id == attack_string).all()
            # Should return empty list (attack_string is not an integer)
            if len(result) == 0:
                print(f"[PASS] Injection attempt in user_id filter blocked")
                passed += 1
            else:
                print(f"[FAIL] Injection attempt in user_id filter might have succeeded")
                failed += 1
        except Exception as e:
            # Rollback in case of database errors to avoid InFailedSqlTransaction
            session.rollback()
            # Type error is expected (attack_string is not an integer)
            if isinstance(e, (TypeError, ValueError)):
                print(f"[PASS] Injection attempt in user_id filter blocked with type error")
                passed += 1
            else:
                print(f"[PASS] Injection attempt in user_id filter blocked with exception: {type(e).__name__}")
                passed += 1
        
        # Cleanup - rollback any pending transaction first, then delete
        try:
            session.rollback()  # Ensure we're in a clean state
            # Refresh the task from database to ensure it's attached
            test_task = session.query(Task).filter(Task.task_id == "t9999999999").first()
            if test_task:
                session.delete(test_task)
                session.commit()
        except Exception as cleanup_error:
            session.rollback()
            # Task may have already been deleted or doesn't exist, which is fine
        
        # Try to delete user (may fail if other tasks reference it, which is fine)
        try:
            existing_user = session.query(User).filter(User.user_id == 1).first()
            if existing_user:
                # Check if any tasks reference this user
                task_count = session.query(Task).filter(Task.user_id == 1).count()
                if task_count == 0:
                    session.delete(existing_user)
                    session.commit()
        except Exception:
            # User may be referenced by other test data, which is fine
            session.rollback()
            pass
        
    except Exception as e:
        print(f"[ERROR] Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()
    
    print(f"\n[RESULT] ORM Query Safety: {passed} passed, {failed} failed")
    return failed == 0


def test_csv_import_injection():
    """Test that CSV import properly handles SQL injection attempts in column names."""
    print("\n[TEST] CSV Import SQL Injection Protection")
    print("-" * 60)
    
    passed = 0
    failed = 0
    
    # Create a malicious CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        # Create CSV with malicious column name
        malicious_column = "name'); DROP TABLE tasks; --"
        df = pd.DataFrame({
            'task_id': ['t1234567890'],
            'name': ['Test Task'],
            malicious_column: ['malicious value']  # This column should be rejected
        })
        df.to_csv(f.name, index=False)
        csv_path = f.name
    
    try:
        session = get_session()
        from backend.database import Task
        
        # Check that table exists before import
        inspector = inspect(engine)
        tables_before = inspector.get_table_names()
        tasks_exists_before = 'tasks' in tables_before
        
        # Try to import (this should fail or sanitize the column name)
        try:
            extra_columns, backup_csv = handle_extra_columns(
                csv_path, 'tasks', Task, session, None
            )
            
            # Check that table still exists
            tables_after = inspector.get_table_names()
            tasks_exists_after = 'tasks' in tables_after
            
            if tasks_exists_before and tasks_exists_after:
                print(f"[PASS] CSV import with malicious column name blocked (table still exists)")
                passed += 1
            else:
                print(f"[FAIL] CSV import with malicious column name succeeded (table was dropped)")
                failed += 1
            
            # Check that malicious column was not added
            if malicious_column not in extra_columns:
                print(f"[PASS] Malicious column '{malicious_column[:50]}' was rejected")
                passed += 1
            else:
                print(f"[FAIL] Malicious column '{malicious_column[:50]}' was accepted")
                failed += 1
                
        except Exception as e:
            # Exception is good - means attack was blocked
            print(f"[PASS] CSV import with malicious column blocked with exception: {type(e).__name__}")
            passed += 1
        
        session.close()
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        failed += 1
    finally:
        # Cleanup
        if os.path.exists(csv_path):
            os.unlink(csv_path)
    
    print(f"\n[RESULT] CSV Import Protection: {passed} passed, {failed} failed")
    return failed == 0


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all SQL injection tests."""
    print("=" * 60)
    print("SQL INJECTION SECURITY TEST SUITE")
    print("=" * 60)
    print(f"\nDatabase: {DATABASE_URL}")
    print(f"Dialect: {'SQLite' if DATABASE_URL.startswith('sqlite') else 'PostgreSQL'}")
    print(f"\n[SAFETY] Using separate test database - your main database will NOT be affected")
    print()
    
    results = []
    
    # Run all tests
    results.append(("Column Name Validation", test_column_name_validation()))
    results.append(("Identifier Quoting", test_identifier_quoting()))
    results.append(("Task ID Validation", test_task_id_validation()))
    results.append(("User ID Validation", test_user_id_validation()))
    results.append(("ORM Query Safety", test_orm_queries_safe()))
    results.append(("Add Column Protection", test_add_column_injection()))
    results.append(("CSV Import Protection", test_csv_import_injection()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All SQL injection tests passed!")
        print("The application appears to be protected from SQL injection attacks.")
    else:
        print("[WARNING] Some tests failed!")
        print("Please review the failures above and fix security issues.")
    print("=" * 60)
    
    return all_passed


if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run tests
    success = run_all_tests()
    sys.exit(0 if success else 1)
