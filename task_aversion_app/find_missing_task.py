#!/usr/bin/env python
"""Find tasks that might be missing from database."""
import os
import sys
import pandas as pd

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("Finding Missing Tasks")
print("=" * 70)

# Check CSV for all tasks
csv_file = os.path.join('data', 'tasks.csv')
if os.path.exists(csv_file):
    csv_df = pd.read_csv(csv_file, dtype=str).fillna('')
    print(f"\n1. All tasks in CSV: {len(csv_df)}")
    
    # Find all "dev sql" related tasks
    dev_sql_tasks = csv_df[csv_df['name'].astype(str).str.lower().str.contains('dev.*sql|sql.*dev', na=False, regex=True)]
    print(f"\n2. 'Dev SQL' related tasks in CSV: {len(dev_sql_tasks)}")
    for idx, row in dev_sql_tasks.iterrows():
        print(f"   - {row.get('name', 'N/A')} (ID: {row.get('task_id', 'N/A')})")
        print(f"     Created: {row.get('created_at', 'N/A')}")
    
    # Show all tasks created today
    print(f"\n3. All tasks created today (2025-12-21):")
    today_tasks = csv_df[csv_df['created_at'].astype(str).str.startswith('2025-12-21', na=False)]
    print(f"   Found {len(today_tasks)} tasks")
    for idx, row in today_tasks.iterrows():
        print(f"   - {row.get('name', 'N/A')} (ID: {row.get('task_id', 'N/A')})")
        print(f"     Created: {row.get('created_at', 'N/A')}")

# Check database
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
from backend.database import get_session, Task, init_db

init_db()
print(f"\n4. Tasks in DATABASE:")
with get_session() as session:
    db_tasks = session.query(Task).all()
    print(f"   Total: {len(db_tasks)} tasks")
    
    # Find all "dev sql" related tasks
    dev_sql_db = [t for t in db_tasks if 'dev' in t.name.lower() and 'sql' in t.name.lower()]
    print(f"\n   'Dev SQL' related tasks in database: {len(dev_sql_db)}")
    for task in dev_sql_db:
        print(f"   - {task.name} (ID: {task.task_id})")
        print(f"     Created: {task.created_at}")
    
    # Show all tasks created today
    from datetime import datetime
    today_start = datetime(2025, 12, 21, 0, 0, 0)
    today_end = datetime(2025, 12, 21, 23, 59, 59)
    today_db = [t for t in db_tasks if t.created_at and today_start <= t.created_at <= today_end]
    print(f"\n   Tasks created today in database: {len(today_db)}")
    for task in today_db:
        print(f"   - {task.name} (ID: {task.task_id})")
        print(f"     Created: {task.created_at}")

# Compare
print(f"\n5. Comparison:")
if os.path.exists(csv_file):
    csv_ids = set(csv_df['task_id'].tolist())
    db_ids = {t.task_id for t in db_tasks}
    
    only_csv = csv_ids - db_ids
    if only_csv:
        print(f"   Tasks in CSV but NOT in database: {len(only_csv)}")
        for task_id in only_csv:
            task_row = csv_df[csv_df['task_id'] == task_id]
            if not task_row.empty:
                print(f"     - {task_row.iloc[0].get('name', 'N/A')} (ID: {task_id})")
                print(f"       Created: {task_row.iloc[0].get('created_at', 'N/A')}")
    else:
        print("   [OK] All CSV tasks are in database")

print("\n" + "=" * 70)

