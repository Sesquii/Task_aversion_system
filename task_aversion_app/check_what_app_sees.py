#!/usr/bin/env python
"""Check what the app actually sees - simulate what the UI would show."""
import os
import sys

# Set DATABASE_URL (same as app)
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.task_manager import TaskManager

print("=" * 70)
print("What the App Actually Sees")
print("=" * 70)

# Create TaskManager (same as app.py does)
tm = TaskManager()

print(f"\n1. TaskManager Backend: {'DATABASE' if tm.use_db else 'CSV'}")

# Get all tasks (what dashboard uses)
print("\n2. All Tasks (tm.get_all() - what dashboard uses):")
all_tasks = tm.get_all()
print(f"   Total tasks: {len(all_tasks)}")

if not all_tasks.empty:
    # Show all tasks, especially any with "dev" or "sql" in name
    print("\n   All tasks:")
    for idx, row in all_tasks.iterrows():
        name = row.get('name', 'N/A')
        task_id = row.get('task_id', 'N/A')
        created = row.get('created_at', 'N/A')
        print(f"     - {name} (ID: {task_id})")
        print(f"       Created: {created}")
    
    # Filter for dev/sql related
    dev_sql = all_tasks[
        all_tasks['name'].astype(str).str.lower().str.contains('dev|sql', na=False, regex=True)
    ]
    print(f"\n   Tasks with 'dev' or 'sql' in name: {len(dev_sql)}")
    for idx, row in dev_sql.iterrows():
        print(f"     - {row.get('name', 'N/A')} (ID: {row.get('task_id', 'N/A')})")

# List tasks (what some UI components use)
print("\n3. Task Names (tm.list_tasks() - what dropdowns use):")
task_names = tm.list_tasks()
print(f"   Total: {len(task_names)} tasks")
print(f"   Names: {task_names}")

# Check for any task with "dev" or "sql"
dev_sql_names = [n for n in task_names if 'dev' in n.lower() or 'sql' in n.lower()]
print(f"\n   Tasks with 'dev' or 'sql': {len(dev_sql_names)}")
for name in dev_sql_names:
    print(f"     - {name}")

# Direct database query for comparison
print("\n4. Direct Database Query (for comparison):")
from backend.database import get_session, Task
with get_session() as session:
    db_tasks = session.query(Task).order_by(Task.created_at.desc()).all()
    print(f"   Total in database: {len(db_tasks)}")
    
    # Show all task names
    print("\n   All task names in database:")
    for task in db_tasks:
        print(f"     - {task.name} (ID: {task.task_id}, Created: {task.created_at})")
    
    # Filter for dev/sql
    dev_sql_db = [t for t in db_tasks if 'dev' in t.name.lower() or 'sql' in t.name.lower()]
    print(f"\n   Tasks with 'dev' or 'sql' in database: {len(dev_sql_db)}")
    for task in dev_sql_db:
        print(f"     - {task.name} (ID: {task.task_id})")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print(f"App sees {len(all_tasks)} tasks via get_all()")
print(f"App sees {len(task_names)} tasks via list_tasks()")
print(f"Database has {len(db_tasks)} tasks directly")

if len(all_tasks) != len(db_tasks) and tm.use_db:
    print("\n[WARNING] Mismatch! App and database have different counts.")
    print("This suggests get_all() might be using CSV instead of database.")

print("\n" + "=" * 70)

