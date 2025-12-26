#!/usr/bin/env python3
"""
Comprehensive test script to verify Phase 2 migration is complete.
Tests all CRUD operations migrated in Phase 2.
"""
import os
import sys
import json

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'task_aversion_app'))

# Set DATABASE_URL for testing
os.environ['DATABASE_URL'] = 'sqlite:///test_phase2_complete.db'

def test_phase2_methods():
    """Test all Phase 2 migrated methods."""
    print("=" * 70)
    print("Phase 2 Complete Migration Test")
    print("=" * 70)
    print()
    
    from backend.instance_manager import InstanceManager
    
    # Initialize InstanceManager
    print("[TEST] Initializing InstanceManager...")
    im = InstanceManager()
    assert im.use_db == True, "Should use database backend"
    print("[PASS] InstanceManager initialized with database backend")
    print()
    
    test_results = []
    
    # Test 1: create_instance
    print("[TEST 1] Testing create_instance()...")
    try:
        instance_id = im.create_instance(
            task_id='t1234567890',
            task_name='Test Task',
            task_version=1,
            predicted={'time_estimate_minutes': 30, 'expected_relief': 50}
        )
        assert instance_id is not None, "Should return instance_id"
        assert instance_id.startswith('i'), "instance_id should start with 'i'"
        print(f"[PASS] create_instance() returned: {instance_id}")
        test_results.append(("create_instance", True))
    except Exception as e:
        print(f"[FAIL] create_instance() failed: {e}")
        test_results.append(("create_instance", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 2: get_instance
    print("[TEST 2] Testing get_instance()...")
    try:
        instance = im.get_instance(instance_id)
        assert instance is not None, "Should retrieve instance"
        assert instance['instance_id'] == instance_id, "Should return correct instance"
        assert instance['task_id'] == 't1234567890', "Should have correct task_id"
        print(f"[PASS] get_instance() retrieved instance: {instance_id}")
        test_results.append(("get_instance", True))
    except Exception as e:
        print(f"[FAIL] get_instance() failed: {e}")
        test_results.append(("get_instance", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 3: add_prediction_to_instance
    print("[TEST 3] Testing add_prediction_to_instance()...")
    try:
        im.add_prediction_to_instance(instance_id, {
            'time_estimate_minutes': 45,
            'expected_relief': 60,
            'expected_difficulty': 30
        })
        instance = im.get_instance(instance_id)
        assert instance['initialized_at'] != '', "Should set initialized_at"
        print(f"[PASS] add_prediction_to_instance() updated instance")
        test_results.append(("add_prediction_to_instance", True))
    except Exception as e:
        print(f"[FAIL] add_prediction_to_instance() failed: {e}")
        test_results.append(("add_prediction_to_instance", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 4: start_instance
    print("[TEST 4] Testing start_instance()...")
    try:
        im.start_instance(instance_id)
        instance = im.get_instance(instance_id)
        assert instance['started_at'] != '', "Should set started_at"
        print(f"[PASS] start_instance() updated instance")
        test_results.append(("start_instance", True))
    except Exception as e:
        print(f"[FAIL] start_instance() failed: {e}")
        test_results.append(("start_instance", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 5: list_active_instances
    print("[TEST 5] Testing list_active_instances()...")
    try:
        active = im.list_active_instances()
        assert isinstance(active, list), "Should return list"
        assert len(active) > 0, "Should have at least one active instance"
        assert any(i['instance_id'] == instance_id for i in active), "Should include our instance"
        print(f"[PASS] list_active_instances() returned {len(active)} active instance(s)")
        test_results.append(("list_active_instances", True))
    except Exception as e:
        print(f"[FAIL] list_active_instances() failed: {e}")
        test_results.append(("list_active_instances", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 6: get_instances_by_task_id
    print("[TEST 6] Testing get_instances_by_task_id()...")
    try:
        instances = im.get_instances_by_task_id('t1234567890', include_completed=True)
        assert isinstance(instances, list), "Should return list"
        assert len(instances) > 0, "Should have at least one instance"
        assert any(i['instance_id'] == instance_id for i in instances), "Should include our instance"
        print(f"[PASS] get_instances_by_task_id() returned {len(instances)} instance(s)")
        test_results.append(("get_instances_by_task_id", True))
    except Exception as e:
        print(f"[FAIL] get_instances_by_task_id() failed: {e}")
        test_results.append(("get_instances_by_task_id", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 7: cancel_instance (create a new instance to cancel)
    print("[TEST 7] Testing cancel_instance()...")
    try:
        cancel_id = im.create_instance('t1234567891', 'Cancel Test', 1)
        im.cancel_instance(cancel_id, {'reason': 'test cancellation'})
        cancelled = im.get_instance(cancel_id)
        assert cancelled['status'] == 'cancelled', "Should set status to cancelled"
        assert cancelled['is_completed'] == 'True', "Should mark as completed"
        assert cancelled['cancelled_at'] != '', "Should set cancelled_at"
        print(f"[PASS] cancel_instance() cancelled instance")
        test_results.append(("cancel_instance", True))
    except Exception as e:
        print(f"[FAIL] cancel_instance() failed: {e}")
        test_results.append(("cancel_instance", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 8: delete_instance
    print("[TEST 8] Testing delete_instance()...")
    try:
        delete_id = im.create_instance('t1234567892', 'Delete Test', 1)
        result = im.delete_instance(delete_id)
        assert result == True, "Should return True on success"
        deleted = im.get_instance(delete_id)
        assert deleted is None, "Instance should be deleted (not found)"
        print(f"[PASS] delete_instance() deleted instance")
        test_results.append(("delete_instance", True))
    except Exception as e:
        print(f"[FAIL] delete_instance() failed: {e}")
        test_results.append(("delete_instance", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Test 9: list_recent_completed (will be empty, but should work)
    print("[TEST 9] Testing list_recent_completed()...")
    try:
        completed = im.list_recent_completed(limit=10)
        assert isinstance(completed, list), "Should return list"
        print(f"[PASS] list_recent_completed() returned {len(completed)} completed instance(s)")
        test_results.append(("list_recent_completed", True))
    except Exception as e:
        print(f"[FAIL] list_recent_completed() failed: {e}")
        test_results.append(("list_recent_completed", False))
        import traceback
        traceback.print_exc()
    print()
    
    # Cleanup
    try:
        if os.path.exists('test_phase2_complete.db'):
            os.remove('test_phase2_complete.db')
            print("[CLEANUP] Test database removed")
    except:
        pass
    
    # Summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for method_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {method_name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print()
        print("[SUCCESS] All Phase 2 methods work correctly!")
        print("=" * 70)
        return True
    else:
        print()
        print(f"[WARNING] {total - passed} test(s) failed. Review errors above.")
        print("=" * 70)
        return False

if __name__ == '__main__':
    try:
        success = test_phase2_methods()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Test script crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

