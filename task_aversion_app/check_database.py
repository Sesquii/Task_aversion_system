#!/usr/bin/env python
"""Check what's in the SQLite database."""
import os
import sys

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_session, Task, init_db
from backend.task_manager import TaskManager

print("=" * 60)
print("Database Check")
print("=" * 60)

# Initialize database (creates tables if needed)
init_db()

# Check using TaskManager
print("\n1. Checking via TaskManager...")
tm = TaskManager()
if tm.use_db:
    print("   [OK] TaskManager is using database backend")
else:
    print("   [WARNING] TaskManager fell back to CSV!")
    print("   Make sure DATABASE_URL is set: sqlite:///data/task_aversion.db")
    sys.exit(1)

# List all tasks
print("\n2. Tasks in database:")
tasks = tm.list_tasks()
if tasks:
    print(f"   Found {len(tasks)} task(s):")
    for task_name in tasks:
        print(f"     - {task_name}")
else:
    print("   No tasks found")

# Get all tasks with details
print("\n3. Task details:")
all_tasks = tm.get_all()
if not all_tasks.empty:
    print(f"   Total tasks: {len(all_tasks)}")
    print("\n   Task Details:")
    for idx, row in all_tasks.iterrows():
        print(f"\n   Task ID: {row['task_id']}")
        print(f"   Name: {row['name']}")
        print(f"   Description: {row.get('description', 'N/A')}")
        print(f"   Type: {row.get('type', 'N/A')}")
        print(f"   Created: {row.get('created_at', 'N/A')}")
        print(f"   Version: {row.get('version', 'N/A')}")
else:
    print("   No tasks in database")

# Check database directly
print("\n4. Direct database query:")
try:
    with get_session() as session:
        db_tasks = session.query(Task).all()
        print(f"   Found {len(db_tasks)} task(s) in database")
        if db_tasks:
            for task in db_tasks:
                print(f"\n   Task ID: {task.task_id}")
                print(f"   Name: {task.name}")
                print(f"   Description: {task.description or '(empty)'}")
                print(f"   Type: {task.type}")
                print(f"   Created: {task.created_at}")
                print(f"   Version: {task.version}")
                print(f"   Categories: {task.categories}")
except Exception as e:
    print(f"   [ERROR] Could not query database: {e}")

print("\n" + "=" * 60)
print("Check complete!")
print("=" * 60)

