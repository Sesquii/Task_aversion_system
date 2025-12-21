#!/usr/bin/env python
"""Show ALL tasks so you can identify which one you're seeing."""
import os
import sys

os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.task_manager import TaskManager

tm = TaskManager()
print("=" * 70)
print("ALL TASKS (as the app sees them)")
print("=" * 70)
print(f"\nBackend: {'DATABASE' if tm.use_db else 'CSV'}\n")

all_tasks = tm.get_all()

if not all_tasks.empty:
    print(f"Total: {len(all_tasks)} tasks\n")
    
    # Group by date
    from collections import defaultdict
    by_date = defaultdict(list)
    
    for idx, row in all_tasks.iterrows():
        created = row.get('created_at', 'Unknown')
        date_part = created.split()[0] if ' ' in str(created) else created
        by_date[date_part].append(row)
    
    # Show today's tasks first
    print("=" * 70)
    print("TODAY'S TASKS (2025-12-21):")
    print("=" * 70)
    if '2025-12-21' in by_date:
        for i, row in enumerate(by_date['2025-12-21'], 1):
            print(f"\n{i}. {row.get('name', 'N/A')}")
            print(f"   ID: {row.get('task_id', 'N/A')}")
            print(f"   Created: {row.get('created_at', 'N/A')}")
            print(f"   Type: {row.get('type', 'N/A')}")
    else:
        print("No tasks created today")
    
    print("\n" + "=" * 70)
    print("ALL TASKS (sorted by creation date):")
    print("=" * 70)
    
    for date in sorted(by_date.keys(), reverse=True):
        print(f"\n{date}:")
        for row in by_date[date]:
            name = row.get('name', 'N/A')
            task_id = row.get('task_id', 'N/A')
            created = row.get('created_at', 'N/A')
            print(f"  - {name} (ID: {task_id})")
            print(f"    Created: {created}")

print("\n" + "=" * 70)
print("Which task are you referring to?")
print("Please tell me the exact name of the third 'Dev SQL' task you see.")
print("=" * 70)

