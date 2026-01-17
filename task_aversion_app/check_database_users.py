#!/usr/bin/env python3
"""
Diagnostic script to check database for users and data with missing user_id.
"""
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.database import get_session, User, Task, TaskInstance, init_db
from sqlalchemy import func, or_

def check_database():
    """Check database for users and data with missing user_id."""
    print("=" * 80)
    print("DATABASE USER AND DATA DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # Initialize database
    init_db()
    
    with get_session() as session:
        # Check all users
        print("USERS IN DATABASE:")
        print("-" * 80)
        users = session.query(User).order_by(User.user_id).all()
        if not users:
            print("  [INFO] No users found in database")
        else:
            print(f"  Total users: {len(users)}")
            for user in users:
                print(f"  User ID: {user.user_id}")
                print(f"    Email: {user.email}")
                print(f"    Username: {user.username or '(none)'}")
                print(f"    Google ID: {user.google_id or '(none)'}")
                print(f"    Created: {user.created_at}")
                print(f"    Last Login: {user.last_login or '(never)'}")
                print()
        
        # Check tasks with NULL user_id
        print("TASKS WITH NULL/MISSING user_id:")
        print("-" * 80)
        null_tasks = session.query(Task).filter(Task.user_id.is_(None)).all()
        if not null_tasks:
            print("  [INFO] No tasks with NULL user_id found")
        else:
            print(f"  Total tasks with NULL user_id: {len(null_tasks)}")
            for task in null_tasks[:10]:  # Show first 10
                print(f"  Task ID: {task.task_id}")
                print(f"    Name: {task.name}")
                print(f"    Created: {task.created_at}")
                print()
            if len(null_tasks) > 10:
                print(f"  ... and {len(null_tasks) - 10} more tasks with NULL user_id")
            print()
        
        # Check tasks by user_id
        print("TASKS BY USER_ID:")
        print("-" * 80)
        task_counts = session.query(
            Task.user_id,
            func.count(Task.task_id).label('count')
        ).group_by(Task.user_id).all()
        
        for user_id, count in task_counts:
            if user_id is None:
                print(f"  NULL user_id: {count} tasks")
            else:
                print(f"  User {user_id}: {count} tasks")
        print()
        
        # Check task instances with NULL user_id
        print("TASK INSTANCES WITH NULL/MISSING user_id:")
        print("-" * 80)
        null_instances = session.query(TaskInstance).filter(TaskInstance.user_id.is_(None)).all()
        if not null_instances:
            print("  [INFO] No task instances with NULL user_id found")
        else:
            print(f"  Total instances with NULL user_id: {len(null_instances)}")
            # Show most recent ones
            recent_null = session.query(TaskInstance).filter(
                TaskInstance.user_id.is_(None)
            ).order_by(TaskInstance.created_at.desc()).limit(10).all()
            
            for instance in recent_null:
                print(f"  Instance ID: {instance.instance_id}")
                print(f"    Task: {instance.task_name} ({instance.task_id})")
                print(f"    Created: {instance.created_at}")
                print(f"    Status: ", end="")
                if instance.completed_at:
                    print("Completed")
                elif instance.cancelled_at:
                    print("Cancelled")
                elif instance.started_at:
                    print("Started")
                elif instance.initialized_at:
                    print("Initialized")
                else:
                    print("Created")
                print()
            if len(null_instances) > 10:
                print(f"  ... and {len(null_instances) - 10} more instances with NULL user_id")
            print()
        
        # Check task instances by user_id
        print("TASK INSTANCES BY USER_ID:")
        print("-" * 80)
        instance_counts = session.query(
            TaskInstance.user_id,
            func.count(TaskInstance.instance_id).label('count')
        ).group_by(TaskInstance.user_id).all()
        
        for user_id, count in instance_counts:
            if user_id is None:
                print(f"  NULL user_id: {count} instances")
            else:
                print(f"  User {user_id}: {count} instances")
        print()
        
        # Check recent activity (last 24 hours)
        print("RECENT ACTIVITY (LAST 24 HOURS):")
        print("-" * 80)
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        recent_tasks = session.query(Task).filter(
            Task.created_at >= yesterday
        ).order_by(Task.created_at.desc()).all()
        
        recent_instances = session.query(TaskInstance).filter(
            TaskInstance.created_at >= yesterday
        ).order_by(TaskInstance.created_at.desc()).all()
        
        print(f"  Tasks created in last 24 hours: {len(recent_tasks)}")
        for task in recent_tasks[:5]:
            print(f"    [{task.created_at}] Task '{task.name}' (ID: {task.task_id}, user_id: {task.user_id})")
        
        print(f"  Instances created in last 24 hours: {len(recent_instances)}")
        for instance in recent_instances[:5]:
            print(f"    [{instance.created_at}] Instance '{instance.task_name}' (ID: {instance.instance_id}, user_id: {instance.user_id})")
        print()
        
        # Summary
        print("SUMMARY:")
        print("-" * 80)
        total_users = session.query(func.count(User.user_id)).scalar()
        total_tasks = session.query(func.count(Task.task_id)).scalar()
        total_instances = session.query(func.count(TaskInstance.instance_id)).scalar()
        null_task_count = session.query(func.count(Task.task_id)).filter(Task.user_id.is_(None)).scalar()
        null_instance_count = session.query(func.count(TaskInstance.instance_id)).filter(TaskInstance.user_id.is_(None)).scalar()
        
        print(f"  Total users: {total_users}")
        print(f"  Total tasks: {total_tasks} (of which {null_task_count} have NULL user_id)")
        print(f"  Total instances: {total_instances} (of which {null_instance_count} have NULL user_id)")
        
        if null_task_count > 0 or null_instance_count > 0:
            print()
            print("  [WARNING] Found data with NULL user_id!")
            print("  This may indicate:")
            print("    - Data created before OAuth was implemented")
            print("    - Data created when authentication failed")
            print("    - Edge browser creating data without proper authentication")
        
        print()
        print("=" * 80)

if __name__ == "__main__":
    check_database()
