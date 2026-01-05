#!/usr/bin/env python3
"""
Script to delete completed task instances in dev and test related categories.

This script identifies tasks with categories containing "dev" or "test" (case-insensitive)
and deletes all completed instances of those tasks to prevent them from skewing data.
"""

import os
import sys
from typing import List, Set

# Add parent directory to path to import backend modules
script_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(script_dir, '..')
sys.path.insert(0, app_dir)

# Change to app directory so relative paths work correctly
os.chdir(app_dir)

# Set DATABASE_URL if not already set (use relative path from app directory)
if not os.getenv('DATABASE_URL'):
    db_path = os.path.join('data', 'task_aversion.db')
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

from backend.database import get_session, Task, TaskInstance, init_db, DATABASE_URL
from sqlalchemy import or_


def find_dev_test_tasks(session) -> Set[str]:
    """
    Find all task_ids that have categories or names containing 'dev' or 'test' (case-insensitive).
    
    Returns:
        Set of task_id strings
    """
    dev_test_task_ids = set()
    
    # Get all tasks
    all_tasks = session.query(Task).all()
    
    print(f"[DEBUG] Total tasks in database: {len(all_tasks)}")
    
    for task in all_tasks:
        task_name_lower = task.name.lower()
        task_matches = False
        match_reason = []
        
        # Check task name for dev/test patterns
        if 'dev' in task_name_lower or 'test' in task_name_lower:
            task_matches = True
            match_reason.append(f"name contains 'dev' or 'test'")
        
        # Check categories
        categories = task.categories
        if categories:
            # Categories is stored as JSON (list of strings)
            categories_lower = [str(cat).lower() for cat in categories]
            if any('dev' in cat or 'test' in cat for cat in categories_lower):
                task_matches = True
                match_reason.append(f"categories: {categories}")
        else:
            # Debug: show tasks with no categories
            if len(all_tasks) <= 20:  # Only show if not too many tasks
                print(f"[DEBUG] Task '{task.name}' (ID: {task.task_id}) has no categories")
        
        if task_matches:
            dev_test_task_ids.add(task.task_id)
            print(f"[FOUND] Task '{task.name}' (ID: {task.task_id}) - {', '.join(match_reason)}")
    
    return dev_test_task_ids


def find_completed_instances(session, task_ids: Set[str]) -> List[TaskInstance]:
    """
    Find all completed instances for the given task_ids.
    
    Args:
        session: Database session
        task_ids: Set of task_id strings to filter by
        
    Returns:
        List of TaskInstance objects that are completed
    """
    if not task_ids:
        return []
    
    # Query for completed instances
    # is_completed=True OR status='completed'
    instances = session.query(TaskInstance).filter(
        TaskInstance.task_id.in_(task_ids)
    ).filter(
        or_(
            TaskInstance.is_completed == True,
            TaskInstance.status == 'completed'
        )
    ).all()
    
    return instances


def delete_instances(session, instances: List[TaskInstance], dry_run: bool = True) -> int:
    """
    Delete the given instances.
    
    Args:
        session: Database session
        instances: List of TaskInstance objects to delete
        dry_run: If True, only print what would be deleted without actually deleting
        
    Returns:
        Number of instances deleted (or would be deleted in dry_run mode)
    """
    if not instances:
        return 0
    
    print(f"\n[{'DRY RUN' if dry_run else 'DELETING'}] Found {len(instances)} completed instances to delete:")
    
    deleted_count = 0
    for instance in instances:
        print(f"  - Instance {instance.instance_id}: Task '{instance.task_name}' "
              f"(completed_at: {instance.completed_at}, status: {instance.status})")
        
        if not dry_run:
            session.delete(instance)
            deleted_count += 1
        else:
            deleted_count += 1
    
    if not dry_run:
        session.commit()
        print(f"\n[SUCCESS] Deleted {deleted_count} completed instances")
    else:
        print(f"\n[DRY RUN] Would delete {deleted_count} completed instances")
    
    return deleted_count


def main():
    """Main function to delete completed dev/test task instances."""
    # Print database connection info
    print(f"[INFO] Database URL: {DATABASE_URL}")
    
    # Check if database file exists (for SQLite)
    if DATABASE_URL.startswith('sqlite'):
        db_path = DATABASE_URL.replace('sqlite:///', '')
        if os.path.exists(db_path):
            file_size = os.path.getsize(db_path)
            print(f"[INFO] Database file exists: {db_path} ({file_size:,} bytes)")
        else:
            print(f"[WARNING] Database file not found: {db_path}")
            print("[INFO] The database will be created if it doesn't exist.")
    
    # Initialize database
    init_db()
    
    # Check for dry-run flag
    dry_run = '--execute' not in sys.argv
    if dry_run:
        print("[INFO] Running in DRY RUN mode. Use --execute to actually delete instances.")
    else:
        print("[WARNING] Running in EXECUTE mode. Instances will be permanently deleted!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("[CANCELLED] Operation cancelled by user.")
            return
    
    print("\n[STEP 1] Finding tasks with dev/test categories or names...")
    with get_session() as session:
        dev_test_task_ids = find_dev_test_tasks(session)
        
        if not dev_test_task_ids:
            print("[INFO] No tasks found with dev/test categories or names.")
            print("[INFO] The script checks both task names and categories for 'dev' or 'test' patterns.")
            return
        
        print(f"\n[INFO] Found {len(dev_test_task_ids)} tasks with dev/test categories")
        
        print("\n[STEP 2] Finding completed instances of these tasks...")
        completed_instances = find_completed_instances(session, dev_test_task_ids)
        
        if not completed_instances:
            print("[INFO] No completed instances found for dev/test tasks.")
            return
        
        print(f"\n[INFO] Found {len(completed_instances)} completed instances")
        
        print("\n[STEP 3] Deleting instances...")
        deleted_count = delete_instances(session, completed_instances, dry_run=dry_run)
        
        if dry_run:
            print("\n[INFO] This was a dry run. Run with --execute to actually delete.")
        else:
            print(f"\n[SUCCESS] Deletion complete. {deleted_count} instances deleted.")


if __name__ == '__main__':
    main()
