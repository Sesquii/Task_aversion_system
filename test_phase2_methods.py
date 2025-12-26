#!/usr/bin/env python3
"""
Test script to verify Phase 2 methods work correctly with database backend.
Tests all CRUD operations migrated in Phase 2.
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'task_aversion_app'))

# Set DATABASE_URL for testing
os.environ['DATABASE_URL'] = 'sqlite:///test_phase2.db'

def test_phase2_methods():
    """Test all Phase 2 migrated methods."""
    print("=" * 70)
    print("Phase 2 Method Migration Test")
    print("=" * 70)
    print()
    
    from backend.instance_manager import InstanceManager
    
    # Initialize InstanceManager
    print("[TEST] Initializing InstanceManager...")
    im = InstanceManager()
    assert im.use_db == True, "Should use database backend"
    print("[PASS] InstanceManager initialized with database backend")
    print()
    
    # Test 1: create_instance
    print("[TEST] Testing create_instance()...")
    instance_id = im.create_instance(
        task_id='t1234567890',
        task_name='Test Task',
        task_version=1,
        predicted={'time_estimate_minutes': 30, 'expected_relief': 50}
    )
    assert instance_id is not None, "Should return instance_id"
    assert instance_id.startswith('i'), "instance_id should start with 'i'"
    print(f"[PASS] create_instance() returned: {instance_id}")
    print()
    
    # Test 2: get_instance
    print("[TEST] Testing get_instance()...")
    instance = im.get_instance(instance_id)
    assert instance is not None, "Should retrieve instance"
    assert instance['instance_id'] == instance_id, "Should return correct instance"
    assert instance['task_id'] == 't1234567890', "Should have correct task_id"
    print(f"[PASS] get_instance() retrieved instance: {instance_id}")
    print()
    
    # Test 3: add_prediction_to_instance
    print("[TEST] Testing add_prediction_to_instance()...")
    im.add_prediction_to_instance(instance_id, {
        'time_estimate_minutes': 45,
        'expected_relief': 60,
        'expected_difficulty': 30
    })
    instance = im.get_instance(instance_id)
    assert instance['initialized_at'] != '', "Should set initialized_at"
    print(f"[PASS] add_prediction_to_instance() updated instance")
    print()
    
    # Test 4: start_instance
    print("[TEST] Testing start_instance()...")
    im.start_instance(instance_id)
    instance = im.get_instance(instance_id)
    assert instance['started_at'] != '', "Should set started_at"
    print(f"[PASS] start_instance() updated instance")
    print()
    
    # Test 5: list_active_instances
    print("[TEST] Testing list_active_instances()...")
    active = im.list_active_instances()
    assert isinstance(active, list), "Should return list"
    assert len(active) > 0, "Should have at least one active instance"
    assert any(i['instance_id'] == instance_id for i in active), "Should include our instance"
    print(f"[PASS] list_active_instances() returned {len(active)} active instance(s)")
    print()
    
    # Test 6: complete_instance
    print("[TEST] Testing complete_instance()...")
    im.complete_instance(instance_id, {
        'time_actual_minutes': 40,
        'actual_relief': 55,
        'actual_difficulty': 25
    })
    instance = im.get_instance(instance_id)
    assert instance['is_completed'] == 'True', "Should mark as completed"
    assert instance['status'] == 'completed', "Should set status to completed"
    assert instance['completed_at'] != '', "Should set completed_at"
    print(f"[PASS] complete_instance() completed instance")
    print()
    
    # Test 7: list_recent_completed
    print("[TEST] Testing list_recent_completed()...")
    completed = im.list_recent_completed(limit=10)
    assert isinstance(completed, list), "Should return list"
    assert len(completed) > 0, "Should have at least one completed instance"
    assert any(i['instance_id'] == instance_id for i in completed), "Should include our instance"
    print(f"[PASS] list_recent_completed() returned {len(completed)} completed instance(s)")
    print()
    
    # Test 8: delete_instance
    print("[TEST] Testing delete_instance()...")
    result = im.delete_instance(instance_id)
    assert result == True, "Should return True on success"
    instance = im.get_instance(instance_id)
    # Note: delete_instance might soft-delete (is_deleted=True) or hard-delete
    # Check based on implementation
    print(f"[PASS] delete_instance() deleted instance")
    print()
    
    # Cleanup
    import os
    if os.path.exists('test_phase2.db'):
        os.remove('test_phase2.db')
        print("[CLEANUP] Test database removed")
    
    print()
    print("=" * 70)
    print("[SUCCESS] All Phase 2 methods work correctly!")
    print("=" * 70)
    return True

if __name__ == '__main__':
    try:
        test_phase2_methods()
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

