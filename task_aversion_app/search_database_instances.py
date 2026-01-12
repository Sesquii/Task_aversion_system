#!/usr/bin/env python3
"""
Script to search the database for task instances and check user_id assignments.
Helps diagnose data isolation issues and find missing instances.
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_session, TaskInstance, User
from sqlalchemy import func

def search_instances():
    """Search all instances in the database and show their user_id assignments."""
    print("\n" + "="*70)
    print("DATABASE INSTANCE SEARCH")
    print("="*70)
    
    try:
        with get_session() as session:
            # Get all instances
            all_instances = session.query(TaskInstance).all()
            
            print(f"\n[INFO] Total instances in database: {len(all_instances)}")
            
            # Group by user_id
            user_groups = {}
            null_user_instances = []
            
            for instance in all_instances:
                user_id = instance.user_id
                if user_id is None:
                    null_user_instances.append(instance)
                else:
                    if user_id not in user_groups:
                        user_groups[user_id] = []
                    user_groups[user_id].append(instance)
            
            print(f"\n[INFO] Instances by user_id:")
            for user_id, instances in sorted(user_groups.items()):
                print(f"  User {user_id}: {len(instances)} instances")
            
            if null_user_instances:
                print(f"\n[WARNING] Found {len(null_user_instances)} instances with NULL user_id (old data)")
            
            # Show detailed breakdown
            print("\n" + "-"*70)
            print("DETAILED BREAKDOWN BY USER")
            print("-"*70)
            
            for user_id, instances in sorted(user_groups.items()):
                print(f"\n[User {user_id}]")
                
                # Get user info
                user = session.query(User).filter(User.user_id == user_id).first()
                if user:
                    print(f"  Email: {user.email}")
                    print(f"  Username: {user.username or '(none)'}")
                
                # Count by status
                initialized = [i for i in instances if i.initialized_at is not None]
                started = [i for i in instances if i.started_at is not None]
                completed = [i for i in instances if i.is_completed]
                active = [i for i in instances if not i.is_completed and not i.is_deleted]
                
                print(f"  Total: {len(instances)}")
                print(f"  - Initialized: {len(initialized)}")
                print(f"  - Started: {len(started)}")
                print(f"  - Completed: {len(completed)}")
                print(f"  - Active (not completed/deleted): {len(active)}")
                
                # Show recent instances
                print(f"\n  Recent instances (last 10):")
                sorted_instances = sorted(instances, key=lambda x: x.created_at or x.initialized_at or datetime.min, reverse=True)
                for inst in sorted_instances[:10]:
                    status = "completed" if inst.is_completed else ("started" if inst.started_at else ("initialized" if inst.initialized_at else "created"))
                    print(f"    - {inst.instance_id}: {inst.task_name} [{status}]")
                    if inst.initialized_at:
                        print(f"      Initialized: {inst.initialized_at}")
                    if inst.completed_at:
                        print(f"      Completed: {inst.completed_at}")
            
            # Show NULL user_id instances
            if null_user_instances:
                print("\n" + "-"*70)
                print("INSTANCES WITH NULL user_id (need migration)")
                print("-"*70)
                for inst in null_user_instances[:20]:  # Show first 20
                    status = "completed" if inst.is_completed else ("started" if inst.started_at else ("initialized" if inst.initialized_at else "created"))
                    print(f"  - {inst.instance_id}: {inst.task_name} [{status}]")
                    if inst.initialized_at:
                        print(f"    Initialized: {inst.initialized_at}")
                    if inst.completed_at:
                        print(f"    Completed: {inst.completed_at}")
                if len(null_user_instances) > 20:
                    print(f"  ... and {len(null_user_instances) - 20} more")
            
            # Check for specific patterns
            print("\n" + "-"*70)
            print("DATA ISOLATION CHECKS")
            print("-"*70)
            
            # Check if any user can see another user's instances
            print("\n[INFO] Checking for potential data leakage...")
            for user_id, instances in sorted(user_groups.items()):
                # Check if instances have correct user_id
                mismatched = [i for i in instances if i.user_id != user_id]
                if mismatched:
                    print(f"[ERROR] User {user_id} has {len(mismatched)} instances with mismatched user_id!")
                else:
                    print(f"[OK] User {user_id}: All {len(instances)} instances have correct user_id")
            
            # Summary
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(f"Total instances: {len(all_instances)}")
            print(f"Users with instances: {len(user_groups)}")
            print(f"Instances with NULL user_id: {len(null_user_instances)}")
            
            if null_user_instances:
                print("\n[WARNING] Some instances have NULL user_id.")
                print("[INFO] These are likely old instances created before user_id was added.")
                print("[INFO] They should be migrated to a specific user or deleted.")
            
            return True
                
    except Exception as e:
        print(f"\n[ERROR] Database search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    from datetime import datetime
    success = search_instances()
    sys.exit(0 if success else 1)
