#!/usr/bin/env python
"""Cleanup test data for a specific user_id.

This script deletes all tasks and instances for a given user_id, useful for
cleaning up after large dataset testing.

Usage:
    python scripts/cleanup_test_data.py --user-id 2
    python scripts/cleanup_test_data.py --user-id 2 --confirm
"""

import os
import sys
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set database URL if not set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

from backend.database import get_session, Task, TaskInstance

def cleanup_user_data(user_id: int, confirm: bool = False):
    """Delete all tasks and instances for a specific user_id."""
    if not confirm:
        print(f"WARNING: This will delete ALL data for user_id={user_id}")
        print("This includes:")
        print("  - All tasks")
        print("  - All task instances")
        print("  - All related data")
        print()
        response = input(f"Type 'DELETE' to confirm deletion for user_id={user_id}: ")
        if response != 'DELETE':
            print("Cancelled. No data was deleted.")
            return
    
    print(f"Cleaning up data for user_id={user_id}...")
    
    with get_session() as session:
        # Count before deletion
        task_count = session.query(Task).filter(Task.user_id == user_id).count()
        instance_count = session.query(TaskInstance).filter(TaskInstance.user_id == user_id).count()
        
        print(f"Found {task_count} tasks and {instance_count} instances")
        
        if task_count == 0 and instance_count == 0:
            print("No data found for this user_id. Nothing to delete.")
            return
        
        # Delete instances first (foreign key constraint)
        print(f"Deleting {instance_count} instances...")
        deleted_instances = session.query(TaskInstance).filter(TaskInstance.user_id == user_id).delete()
        session.commit()
        print(f"  [OK] Deleted {deleted_instances} instances")
        
        # Delete tasks
        print(f"Deleting {task_count} tasks...")
        deleted_tasks = session.query(Task).filter(Task.user_id == user_id).delete()
        session.commit()
        print(f"  [OK] Deleted {deleted_tasks} tasks")
        
        # Verify deletion
        remaining_tasks = session.query(Task).filter(Task.user_id == user_id).count()
        remaining_instances = session.query(TaskInstance).filter(TaskInstance.user_id == user_id).count()
        
        if remaining_tasks == 0 and remaining_instances == 0:
            print("\n[SUCCESS] All data deleted successfully!")
            print(f"  - Tasks deleted: {deleted_tasks}")
            print(f"  - Instances deleted: {deleted_instances}")
        else:
            print(f"\n[WARNING] Some data may remain:")
            print(f"  - Remaining tasks: {remaining_tasks}")
            print(f"  - Remaining instances: {remaining_instances}")

def main():
    parser = argparse.ArgumentParser(description='Cleanup test data for a specific user_id')
    parser.add_argument('--user-id', type=int, required=True, help='User ID to cleanup')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Test Data Cleanup")
    print("=" * 70)
    print(f"User ID: {args.user_id}")
    print()
    
    cleanup_user_data(args.user_id, args.confirm)

if __name__ == '__main__':
    main()
