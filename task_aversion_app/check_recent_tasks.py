#!/usr/bin/env python
"""Check recent tasks in both database and CSV to see what's missing."""
import os
import sys
import pandas as pd
from datetime import datetime, timedelta

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_session, Task, init_db
from backend.task_manager import TaskManager

print("=" * 70)
print("Recent Tasks Check")
print("=" * 70)

# Initialize database
init_db()

# Check TaskManager backend
print("\n1. TaskManager Backend:")
tm = TaskManager()
if tm.use_db:
    print("   [OK] Using DATABASE backend")
else:
    print("   [WARNING] Using CSV backend!")
    print("   This means DATABASE_URL is not set or database failed")

# Get tasks from database
print("\n2. Tasks in DATABASE (sorted by creation time):")
with get_session() as session:
    db_tasks = session.query(Task).order_by(Task.created_at.desc()).all()
    print(f"   Total: {len(db_tasks)} tasks")
    
    # Show last 10 tasks
    print("\n   Last 10 tasks created:")
    for task in db_tasks[:10]:
        print(f"     - {task.name} (ID: {task.task_id})")
        print(f"       Created: {task.created_at}")
        print(f"       Version: {task.version}")
    
    # Look for all "dev sql" tasks
    dev_sql_tasks = [t for t in db_tasks if 'dev sql' in t.name.lower() or 'devsql' in t.name.lower()]
    print(f"\n   'Dev SQL' tasks found: {len(dev_sql_tasks)}")
    for task in dev_sql_tasks:
        print(f"     - {task.name} (ID: {task.task_id})")
        print(f"       Created: {task.created_at}")

# Get tasks from CSV for comparison
print("\n3. Tasks in CSV (for comparison):")
csv_file = os.path.join('data', 'tasks.csv')
if os.path.exists(csv_file):
    csv_df = pd.read_csv(csv_file, dtype=str).fillna('')
    
    # Sort by created_at if available
    if 'created_at' in csv_df.columns:
        csv_df['created_at_dt'] = pd.to_datetime(csv_df['created_at'], errors='coerce')
        csv_df = csv_df.sort_values('created_at_dt', ascending=False, na_position='last')
    
    print(f"   Total: {len(csv_df)} tasks")
    
    # Show last 10 tasks
    print("\n   Last 10 tasks in CSV:")
    for idx, row in csv_df.head(10).iterrows():
        name = row.get('name', 'N/A')
        task_id = row.get('task_id', 'N/A')
        created = row.get('created_at', 'N/A')
        print(f"     - {name} (ID: {task_id})")
        print(f"       Created: {created}")
    
    # Look for all "dev sql" tasks in CSV
    dev_sql_csv = csv_df[csv_df['name'].astype(str).str.lower().str.contains('dev sql|devsql', na=False)]
    print(f"\n   'Dev SQL' tasks in CSV: {len(dev_sql_csv)}")
    for idx, row in dev_sql_csv.iterrows():
        print(f"     - {row.get('name', 'N/A')} (ID: {row.get('task_id', 'N/A')})")

# Compare
print("\n4. Comparison:")
db_task_ids = {t.task_id for t in db_tasks}
csv_task_ids = set(csv_df['task_id'].tolist()) if 'task_id' in csv_df.columns else set()

only_in_csv = csv_task_ids - db_task_ids
only_in_db = db_task_ids - csv_task_ids

if only_in_csv:
    print(f"\n   Tasks ONLY in CSV (not in database): {len(only_in_csv)}")
    for task_id in list(only_in_csv)[:5]:
        task_row = csv_df[csv_df['task_id'] == task_id]
        if not task_row.empty:
            print(f"     - {task_row.iloc[0].get('name', 'N/A')} (ID: {task_id})")

if only_in_db:
    print(f"\n   Tasks ONLY in database (not in CSV): {len(only_in_db)}")
    for task_id in list(only_in_db)[:5]:
        task = next((t for t in db_tasks if t.task_id == task_id), None)
        if task:
            print(f"     - {task.name} (ID: {task_id})")

if not only_in_csv and not only_in_db:
    print("\n   [OK] Database and CSV are in sync")

# Check for very recent tasks (last 30 minutes)
print("\n5. Very Recent Tasks (last 30 minutes):")
recent_time = datetime.now() - timedelta(minutes=30)

recent_db = [t for t in db_tasks if t.created_at and t.created_at >= recent_time]
recent_csv = []
if 'created_at' in csv_df.columns:
    for idx, row in csv_df.iterrows():
        try:
            created_str = row.get('created_at', '')
            if created_str:
                created_dt = pd.to_datetime(created_str, errors='coerce')
                if created_dt and created_dt >= recent_time:
                    recent_csv.append(row)
        except:
            pass

print(f"   In database: {len(recent_db)}")
for task in recent_db:
    print(f"     - {task.name} (ID: {task.task_id}) at {task.created_at}")

print(f"   In CSV: {len(recent_csv)}")
for row in recent_csv[:5]:
    print(f"     - {row.get('name', 'N/A')} (ID: {row.get('task_id', 'N/A')}) at {row.get('created_at', 'N/A')}")

print("\n" + "=" * 70)
print("Check Complete")
print("=" * 70)

