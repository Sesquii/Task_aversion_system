#!/usr/bin/env python
"""Comprehensive check of SQLite database and CSV files to verify data is saved."""
import os
import sys
import json

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_session, Task, init_db
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager

print("=" * 70)
print("Comprehensive Data Verification")
print("=" * 70)

# Initialize database
init_db()

# Check TaskManager backend
print("\n1. Checking TaskManager backend...")
tm = TaskManager()
if tm.use_db:
    print("   [OK] TaskManager is using DATABASE backend")
    backend_type = "DATABASE"
else:
    print("   [WARNING] TaskManager is using CSV backend")
    print("   Make sure DATABASE_URL is set: sqlite:///data/task_aversion.db")
    backend_type = "CSV"

# Check tasks in database
print("\n2. Tasks in DATABASE:")
try:
    with get_session() as session:
        db_tasks = session.query(Task).order_by(Task.created_at.desc()).all()
        if db_tasks:
            print(f"   Found {len(db_tasks)} task(s) in database:")
            for task in db_tasks:
                print(f"\n   Task ID: {task.task_id}")
                print(f"   Name: {task.name}")
                print(f"   Description: {task.description or '(empty)'}")
                print(f"   Type: {task.type}")
                print(f"   Created: {task.created_at}")
                print(f"   Version: {task.version}")
                print(f"   Categories: {task.categories}")
        else:
            print("   [NO TASKS] Database is empty")
except Exception as e:
    print(f"   [ERROR] Could not query database: {e}")

# Check tasks via TaskManager
print("\n3. Tasks via TaskManager:")
all_tasks = tm.get_all()
if not all_tasks.empty:
    print(f"   Found {len(all_tasks)} task(s):")
    for idx, row in all_tasks.iterrows():
        print(f"\n   Task ID: {row['task_id']}")
        print(f"   Name: {row['name']}")
        print(f"   Created: {row.get('created_at', 'N/A')}")
else:
    print("   [NO TASKS] TaskManager returned no tasks")

# Check CSV file (for comparison)
print("\n4. Tasks in CSV file (for comparison):")
csv_file = os.path.join('data', 'tasks.csv')
if os.path.exists(csv_file):
    import pandas as pd
    try:
        csv_df = pd.read_csv(csv_file, dtype=str).fillna('')
        if not csv_df.empty:
            print(f"   Found {len(csv_df)} task(s) in CSV:")
            # Show most recent 5
            if 'created_at' in csv_df.columns:
                csv_df = csv_df.sort_values('created_at', ascending=False)
            for idx, row in csv_df.head(5).iterrows():
                print(f"     - {row.get('name', 'N/A')} (ID: {row.get('task_id', 'N/A')})")
        else:
            print("   CSV file is empty")
    except Exception as e:
        print(f"   [ERROR] Could not read CSV: {e}")
else:
    print("   CSV file does not exist")

# Check task instances (still in CSV - not migrated yet)
print("\n5. Task Instances (NOTE: Still using CSV, not migrated yet):")
im = InstanceManager()
instances = im.list_active_instances()
completed_instances = im.df[im.df['is_completed'].astype(str).str.lower() == 'true']
all_instances = im.df

print(f"   Active instances: {len(instances)}")
print(f"   Completed instances: {len(completed_instances)}")
print(f"   Total instances: {len(all_instances)}")

if not all_instances.empty:
    print("\n   Recent instances (last 5):")
    if 'created_at' in all_instances.columns:
        recent = all_instances.sort_values('created_at', ascending=False).head(5)
    else:
        recent = all_instances.head(5)
    
    for idx, row in recent.iterrows():
        instance_id = row.get('instance_id', 'N/A')
        task_id = row.get('task_id', 'N/A')
        task_name = row.get('task_name', 'N/A')
        status = row.get('status', 'N/A')
        completed = row.get('is_completed', 'False')
        completed_at = row.get('completed_at', '')
        
        print(f"\n     Instance ID: {instance_id}")
        print(f"     Task: {task_name} ({task_id})")
        print(f"     Status: {status}")
        print(f"     Completed: {completed}")
        if completed_at:
            print(f"     Completed at: {completed_at}")

# Check database file
print("\n6. Database file info:")
db_file = os.path.join('data', 'task_aversion.db')
if os.path.exists(db_file):
    import os
    stat = os.stat(db_file)
    print(f"   File exists: Yes")
    print(f"   File size: {stat.st_size} bytes")
    print(f"   Last modified: {stat.st_mtime}")
else:
    print(f"   [WARNING] Database file does not exist at: {db_file}")

# Summary
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"TaskManager backend: {backend_type}")
print(f"Tasks in database: {len(db_tasks) if 'db_tasks' in locals() else 0}")
print(f"Tasks in CSV: {len(csv_df) if 'csv_df' in locals() and not csv_df.empty else 0}")
print(f"Total instances: {len(all_instances) if not all_instances.empty else 0}")

if backend_type == "DATABASE" and len(db_tasks) == 0:
    print("\n[NOTE] Database backend is active but no tasks found.")
    print("This could mean:")
    print("  1. The task was created before DATABASE_URL was set")
    print("  2. The app wasn't restarted after setting DATABASE_URL")
    print("  3. The task was created in a different session")

print("\n" + "=" * 70)

