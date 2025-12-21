#!/usr/bin/env python
"""Verify the new dev sql2 task is accessible."""
import os
import sys

os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.task_manager import TaskManager

print("=" * 70)
print("Verifying New Task: dev sql2")
print("=" * 70)

tm = TaskManager()
print(f"\n1. TaskManager Backend: {'DATABASE' if tm.use_db else 'CSV'}")

# Get the specific task
print("\n2. Looking for 'dev sql2':")
task = tm.find_by_name("dev sql2")
if task:
    print("   [SUCCESS] Found via find_by_name():")
    print(f"     Name: {task.get('name', 'N/A')}")
    print(f"     ID: {task.get('task_id', 'N/A')}")
    print(f"     Created: {task.get('created_at', 'N/A')}")
else:
    print("   [FAIL] Not found via find_by_name()")

# Get by ID
print("\n3. Getting by ID (t1766324594):")
task_by_id = tm.get_task("t1766324594")
if task_by_id:
    print("   [SUCCESS] Found via get_task():")
    print(f"     Name: {task_by_id.get('name', 'N/A')}")
    print(f"     ID: {task_by_id.get('task_id', 'N/A')}")
else:
    print("   [FAIL] Not found via get_task()")

# Check if it's in the list
print("\n4. Checking if it's in list_tasks():")
all_names = tm.list_tasks()
if "dev sql2" in all_names:
    print("   [SUCCESS] Found in list_tasks()")
else:
    print("   [FAIL] Not in list_tasks()")
    print(f"   Available tasks: {all_names}")

# Check get_all()
print("\n5. Checking get_all():")
all_tasks = tm.get_all()
dev_sql2 = all_tasks[all_tasks['name'].astype(str).str.lower() == 'dev sql2']
if not dev_sql2.empty:
    print("   [SUCCESS] Found in get_all():")
    row = dev_sql2.iloc[0]
    print(f"     Name: {row.get('name', 'N/A')}")
    print(f"     ID: {row.get('task_id', 'N/A')}")
else:
    print("   [FAIL] Not found in get_all()")

print("\n" + "=" * 70)
if task and task_by_id and "dev sql2" in all_names and not dev_sql2.empty:
    print("[SUCCESS] All checks passed! Task is fully accessible.")
else:
    print("[WARNING] Some checks failed. Task may not be fully accessible.")
print("=" * 70)

