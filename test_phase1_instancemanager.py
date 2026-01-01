#!/usr/bin/env python3
"""
Quick test script to verify Phase 1 implementation works correctly.
Tests that InstanceManager initializes properly with both CSV and database backends.
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'task_aversion_app'))

def test_csv_backend():
    """Test that CSV backend works (default, no DATABASE_URL)."""
    print("\n" + "="*60)
    print("TEST 1: CSV Backend (Default)")
    print("="*60)
    
    # Ensure DATABASE_URL is not set
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    if 'DISABLE_CSV_FALLBACK' in os.environ:
        del os.environ['DISABLE_CSV_FALLBACK']
    
    try:
        from backend.instance_manager import InstanceManager
        
        im = InstanceManager()
        assert hasattr(im, 'use_db'), "InstanceManager should have use_db attribute"
        assert im.use_db == False, "Should use CSV backend when DATABASE_URL is not set"
        assert hasattr(im, 'file'), "Should have file attribute for CSV"
        assert hasattr(im, 'df'), "Should have df attribute (DataFrame)"
        assert hasattr(im, '_csv_to_db_datetime'), "Should have helper method _csv_to_db_datetime"
        assert hasattr(im, '_db_to_csv_datetime'), "Should have helper method _db_to_csv_datetime"
        assert hasattr(im, '_parse_json_field'), "Should have helper method _parse_json_field"
        assert hasattr(im, '_csv_to_db_dict'), "Should have helper method _csv_to_db_dict"
        
        print("[PASS] CSV backend initialization: PASSED")
        print(f"   - use_db = {im.use_db}")
        print(f"   - file = {im.file}")
        
        # Test helper methods
        from datetime import datetime
        
        # Test datetime conversion
        test_dt_str = "2024-01-15 14:30"
        dt = im._csv_to_db_datetime(test_dt_str)
        assert dt is not None, "Should parse datetime string"
        assert isinstance(dt, datetime), "Should return datetime object"
        print(f"[PASS] _csv_to_db_datetime('{test_dt_str}') = {dt}")
        
        csv_str = im._db_to_csv_datetime(dt)
        assert csv_str == test_dt_str, "Should convert back to same string"
        print(f"[PASS] _db_to_csv_datetime() = '{csv_str}'")
        
        # Test JSON parsing
        test_json = '{"key": "value", "number": 42}'
        parsed = im._parse_json_field(test_json)
        assert isinstance(parsed, dict), "Should return dict"
        assert parsed['key'] == 'value', "Should parse JSON correctly"
        print(f"[PASS] _parse_json_field() = {parsed}")
        
        empty_json = im._parse_json_field('')
        assert empty_json == {}, "Should return empty dict for empty string"
        print(f"[PASS] _parse_json_field('') = {empty_json}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] CSV backend test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_backend():
    """Test that database backend initializes (if DATABASE_URL is set)."""
    print("\n" + "="*60)
    print("TEST 2: Database Backend (with DATABASE_URL)")
    print("="*60)
    
    # Set DATABASE_URL to SQLite for testing
    os.environ['DATABASE_URL'] = 'sqlite:///test_phase1_instancemanager.db'
    
    try:
        from backend.instance_manager import InstanceManager
        
        im = InstanceManager()
        assert hasattr(im, 'use_db'), "InstanceManager should have use_db attribute"
        assert im.use_db == True, "Should use database backend when DATABASE_URL is set"
        assert hasattr(im, 'db_session'), "Should have db_session attribute"
        assert hasattr(im, 'TaskInstance'), "Should have TaskInstance model"
        
        print("[PASS] Database backend initialization: PASSED")
        print(f"   - use_db = {im.use_db}")
        print(f"   - db_session = {im.db_session}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Database backend test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up environment
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        # Clean up test database (after connection is closed)
        # SQLite releases locks when process ends, so we'll skip manual cleanup
        # or try to close connection explicitly if needed
        try:
            import time
            time.sleep(0.1)  # Brief pause for SQLite to release lock
            if os.path.exists('test_phase1_instancemanager.db'):
                os.remove('test_phase1_instancemanager.db')
        except (PermissionError, OSError):
            # File might still be locked, that's okay for a test
            pass


def test_existing_methods_still_work():
    """Test that existing methods still work (they should use CSV for now)."""
    print("\n" + "="*60)
    print("TEST 3: Existing Methods Still Work")
    print("="*60)
    
    # Ensure CSV backend
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    
    try:
        from backend.instance_manager import InstanceManager
        
        im = InstanceManager()
        
        # Test that methods exist and are callable
        methods_to_test = [
            'create_instance',
            'get_instance',
            'list_active_instances',
            'complete_instance',
            'start_instance',
            'cancel_instance',
            'delete_instance',
            'add_prediction_to_instance',
        ]
        
        for method_name in methods_to_test:
            assert hasattr(im, method_name), f"Should have method {method_name}"
            assert callable(getattr(im, method_name)), f"{method_name} should be callable"
            print(f"[PASS] Method {method_name} exists and is callable")
        
        # Test that we can create an instance (basic functionality)
        # This should work because create_instance hasn't been migrated yet
        instance_id = im.create_instance(
            task_id='t1234567890',
            task_name='Test Task',
            task_version=1,
            predicted={'test': 'data'}
        )
        assert instance_id is not None, "Should return instance_id"
        assert instance_id.startswith('i'), "instance_id should start with 'i'"
        print(f"[PASS] create_instance() works: returned {instance_id}")
        
        # Test get_instance
        instance = im.get_instance(instance_id)
        assert instance is not None, "Should retrieve instance"
        assert instance['instance_id'] == instance_id, "Should return correct instance"
        print(f"[PASS] get_instance() works: retrieved instance {instance_id}")
        
        # Clean up test instance
        im.delete_instance(instance_id)
        print(f"[PASS] delete_instance() works: cleaned up test instance")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Existing methods test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("Testing Phase 1: InstanceManager Database Migration Infrastructure")
    print("="*60)
    
    results = []
    results.append(("CSV Backend", test_csv_backend()))
    results.append(("Database Backend", test_database_backend()))
    results.append(("Existing Methods", test_existing_methods_still_work()))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results:
        status = "[PASS] PASSED" if passed else "[FAIL] FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n[SUCCESS] All tests passed! Phase 1 is working correctly.")
        sys.exit(0)
    else:
        print("\n[WARNING] Some tests failed. Please review the errors above.")
        sys.exit(1)

