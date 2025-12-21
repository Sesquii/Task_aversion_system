#!/usr/bin/env python
"""Verify database is being used and check for completed tasks."""
import os
import sys

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_session, Task, init_db
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager

print("=" * 70)
print("Database Verification (CSV Disabled)")
print("=" * 70)

# Initialize database
init_db()

# Check TaskManager
print("\n1. TaskManager Backend Check:")
tm = TaskManager()
if tm.use_db:
    print("   [OK] TaskManager is using DATABASE backend")
else:
    print("   [FAIL] TaskManager is using CSV backend!")
    print("   DATABASE_URL is not set or database failed to initialize")
    sys.exit(1)

# Check tasks in database
print("\n2. Tasks in Database:")
with get_session() as session:
    db_tasks = session.query(Task).order_by(Task.created_at.desc()).all()
    print(f"   Found {len(db_tasks)} task(s) in database")
    
    # Look for "Dev SQL test" or "dev sql test"
    dev_sql_tasks = [t for t in db_tasks if 'dev sql' in t.name.lower()]
    if dev_sql_tasks:
        print(f"\n   Found {len(dev_sql_tasks)} 'Dev SQL test' task(s):")
        for task in dev_sql_tasks:
            print(f"     - {task.name} (ID: {task.task_id})")
            print(f"       Created: {task.created_at}")
            print(f"       Version: {task.version}")

# Check task instances (still in CSV, but let's verify)
print("\n3. Task Instances (NOTE: Still using CSV - not migrated yet):")
im = InstanceManager()

# Find instances for "Dev SQL test" tasks
if dev_sql_tasks:
    for task in dev_sql_tasks:
        task_id = task.task_id
        instances = im.df[im.df['task_id'] == task_id]
        
        if not instances.empty:
            print(f"\n   Instances for '{task.name}' ({task_id}):")
            for idx, inst_row in instances.iterrows():
                instance_id = inst_row.get('instance_id', 'N/A')
                status = inst_row.get('status', 'N/A')
                is_completed = inst_row.get('is_completed', 'False')
                completed_at = inst_row.get('completed_at', '')
                initialized_at = inst_row.get('initialized_at', '')
                
                print(f"     Instance ID: {instance_id}")
                print(f"     Status: {status}")
                print(f"     Completed: {is_completed}")
                if initialized_at:
                    print(f"     Initialized: {initialized_at}")
                if completed_at:
                    print(f"     Completed at: {completed_at}")
        else:
            print(f"\n   No instances found for '{task.name}' ({task_id})")

# Summary
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"TaskManager backend: {'DATABASE' if tm.use_db else 'CSV'}")
print(f"Tasks in database: {len(db_tasks)}")
print(f"Dev SQL test tasks found: {len(dev_sql_tasks)}")

if tm.use_db:
    print("\n[SUCCESS] App is using database backend!")
    print("Task definitions are stored in SQLite database.")
    print("\nNote: Task instances are still in CSV (not migrated yet).")
    print("This is expected - only TaskManager has been migrated so far.")
else:
    print("\n[WARNING] App is using CSV backend!")
    print("Check that DATABASE_URL is set correctly.")

print("\n" + "=" * 70)

