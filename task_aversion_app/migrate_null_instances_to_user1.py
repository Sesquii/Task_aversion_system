#!/usr/bin/env python3
"""
Migration script to COPY (not move) all instances with NULL user_id to user 1.

This preserves the original NULL instances for the dev branch while giving
user 1 access to all historical data.

IMPORTANT: This COPIES instances, so the original NULL instances remain unchanged.

Usage:
    python migrate_null_instances_to_user1.py          # Interactive (asks for confirmation)
    python migrate_null_instances_to_user1.py --yes    # Non-interactive (auto-confirms)
"""
import os
import sys
import argparse
from datetime import datetime

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_session, TaskInstance, User
from sqlalchemy import text
import json

def copy_null_instances_to_user1(auto_confirm=False):
    """Copy all instances with NULL user_id to user 1."""
    print("\n" + "="*70)
    print("MIGRATION: Copy NULL user_id instances to User 1")
    print("="*70)
    print("[INFO] This will COPY instances (original NULL instances will remain)")
    print("[INFO] Original instances are preserved for dev branch")
    print()
    
    try:
        with get_session() as session:
            # Verify user 1 exists
            user1 = session.query(User).filter(User.user_id == 1).first()
            if not user1:
                print("[ERROR] User 1 does not exist!")
                print("[INFO] Please create user 1 first or specify a different user_id")
                return False
            
            print(f"[INFO] Target user: User 1 ({user1.email})")
            
            # Find all instances with NULL user_id
            null_instances = session.query(TaskInstance).filter(
                TaskInstance.user_id.is_(None)
            ).all()
            
            print(f"\n[INFO] Found {len(null_instances)} instances with NULL user_id")
            
            if len(null_instances) == 0:
                print("[SUCCESS] No NULL instances found - nothing to copy")
                return True
            
            # Show preview
            print("\n[INFO] Preview of instances to copy (first 10):")
            for i, inst in enumerate(null_instances[:10]):
                status = "completed" if inst.is_completed else ("started" if inst.started_at else ("initialized" if inst.initialized_at else "created"))
                print(f"  {i+1}. {inst.instance_id}: {inst.task_name} [{status}]")
            if len(null_instances) > 10:
                print(f"  ... and {len(null_instances) - 10} more")
            
            # Ask for confirmation
            print("\n" + "-"*70)
            response = input(f"[CONFIRM] Copy {len(null_instances)} instances to User 1? (yes/no): ").strip().lower()
            if response not in ('yes', 'y'):
                print("[CANCELLED] Migration cancelled by user")
                return False
            
            print("\n[INFO] Starting copy operation...")
            
            # Copy each instance
            copied_count = 0
            skipped_count = 0
            error_count = 0
            
            for inst in null_instances:
                try:
                    # Create a new instance with user_id = 1
                    # Generate new instance_id to avoid conflicts
                    new_instance_id = f"i{int(datetime.now().timestamp() * 1000000) + copied_count}"
                    
                    # Create copy with all original data
                    new_instance = TaskInstance(
                        instance_id=new_instance_id,
                        task_id=inst.task_id,
                        task_name=inst.task_name,
                        task_version=inst.task_version,
                        created_at=inst.created_at,
                        initialized_at=inst.initialized_at,
                        started_at=inst.started_at,
                        completed_at=inst.completed_at,
                        cancelled_at=inst.cancelled_at,
                        predicted=inst.predicted.copy() if inst.predicted else {},
                        actual=inst.actual.copy() if inst.actual else {},
                        procrastination_score=inst.procrastination_score,
                        proactive_score=inst.proactive_score,
                        behavioral_score=inst.behavioral_score,
                        net_relief=inst.net_relief,
                        is_completed=inst.is_completed,
                        is_deleted=inst.is_deleted,
                        status=inst.status,
                        duration_minutes=inst.duration_minutes,
                        delay_minutes=inst.delay_minutes,
                        relief_score=inst.relief_score,
                        cognitive_load=inst.cognitive_load,
                        mental_energy_needed=inst.mental_energy_needed,
                        task_difficulty=inst.task_difficulty,
                        emotional_load=inst.emotional_load,
                        environmental_effect=inst.environmental_effect,
                        skills_improved=inst.skills_improved,
                        user_id=1  # CRITICAL: Set to user 1
                    )
                    
                    session.add(new_instance)
                    copied_count += 1
                    
                    # Progress indicator
                    if copied_count % 50 == 0:
                        print(f"[PROGRESS] Copied {copied_count}/{len(null_instances)} instances...")
                        session.commit()  # Commit in batches
                
                except Exception as e:
                    error_count += 1
                    print(f"[ERROR] Failed to copy instance {inst.instance_id}: {e}")
                    session.rollback()
                    continue
            
            # Final commit
            if copied_count > 0:
                session.commit()
                print(f"\n[SUCCESS] Committed {copied_count} copied instances to database")
            
            # Verify the copy
            print("\n[INFO] Verifying copy operation...")
            user1_instances = session.query(TaskInstance).filter(
                TaskInstance.user_id == 1
            ).count()
            
            null_instances_after = session.query(TaskInstance).filter(
                TaskInstance.user_id.is_(None)
            ).count()
            
            print(f"[VERIFY] User 1 now has {user1_instances} instances")
            print(f"[VERIFY] NULL user_id instances remaining: {null_instances_after} (should be {len(null_instances)})")
            
            if null_instances_after == len(null_instances):
                print("[SUCCESS] Original NULL instances preserved correctly")
            else:
                print(f"[WARNING] NULL instance count changed! Expected {len(null_instances)}, found {null_instances_after}")
            
            # Summary
            print("\n" + "="*70)
            print("MIGRATION SUMMARY")
            print("="*70)
            print(f"Total NULL instances found: {len(null_instances)}")
            print(f"Successfully copied: {copied_count}")
            print(f"Skipped: {skipped_count}")
            print(f"Errors: {error_count}")
            print(f"User 1 total instances: {user1_instances}")
            print(f"NULL instances remaining: {null_instances_after}")
            print("\n[SUCCESS] Migration completed!")
            print("[INFO] Original NULL instances are preserved for dev branch")
            print("[INFO] User 1 now has copies of all historical data")
            
            return True
                
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Copy NULL user_id instances to User 1 (preserves originals)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Auto-confirm without prompting (for non-interactive use)'
    )
    args = parser.parse_args()
    
    success = copy_null_instances_to_user1(auto_confirm=args.yes)
    sys.exit(0 if success else 1)
