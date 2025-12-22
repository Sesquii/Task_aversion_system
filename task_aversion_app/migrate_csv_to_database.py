#!/usr/bin/env python
"""Migrate existing CSV tasks to SQLite database."""
import os
import sys
import json
import pandas as pd

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_session, Task
from backend.task_manager import TaskManager

print("=" * 70)
print("CSV to Database Migration")
print("=" * 70)

# Initialize database
print("\n1. Initializing database...")
init_db()
print("   [OK] Database initialized")

# Load CSV tasks
print("\n2. Loading tasks from CSV...")
csv_file = os.path.join('data', 'tasks.csv')
if not os.path.exists(csv_file):
    print(f"   [ERROR] CSV file not found: {csv_file}")
    sys.exit(1)

csv_df = pd.read_csv(csv_file, dtype=str).fillna('')
print(f"   Found {len(csv_df)} task(s) in CSV")

# Check what's already in database
print("\n3. Checking existing database tasks...")
tm = TaskManager()
if not tm.use_db:
    print("   [ERROR] TaskManager is not using database backend!")
    print("   Make sure DATABASE_URL is set: sqlite:///data/task_aversion.db")
    sys.exit(1)

with get_session() as session:
    existing_tasks = session.query(Task).all()
    existing_task_ids = {task.task_id for task in existing_tasks}
    print(f"   Found {len(existing_tasks)} task(s) already in database")

# Migrate tasks
print("\n4. Migrating tasks to database...")
migrated = 0
skipped = 0
errors = 0

for idx, row in csv_df.iterrows():
    task_id = row.get('task_id', '').strip()
    if not task_id:
        print(f"   [SKIP] Row {idx}: No task_id")
        skipped += 1
        continue
    
    # Skip if already in database
    if task_id in existing_task_ids:
        print(f"   [SKIP] {task_id}: Already in database")
        skipped += 1
        continue
    
    try:
        # Parse categories
        categories_str = row.get('categories', '[]') or '[]'
        try:
            categories = json.loads(categories_str) if isinstance(categories_str, str) else categories_str
        except (json.JSONDecodeError, TypeError):
            categories = []
        
        # Parse other fields
        name = row.get('name', '').strip()
        description = row.get('description', '').strip()
        task_type = row.get('type', 'one-time').strip()
        version = int(row.get('version', 1)) if row.get('version') else 1
        is_recurring = str(row.get('is_recurring', 'False')).lower() == 'true'
        default_estimate = int(row.get('default_estimate_minutes', 0)) if row.get('default_estimate_minutes') else 0
        task_type_field = row.get('task_type', 'Work').strip() or 'Work'
        default_aversion = row.get('default_initial_aversion', '').strip()
        
        # Parse created_at
        created_at_str = row.get('created_at', '').strip()
        try:
            if created_at_str:
                from datetime import datetime
                created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M")
            else:
                created_at = None
        except (ValueError, TypeError):
            created_at = None
        
        # Create task in database
        with get_session() as session:
            task = Task(
                task_id=task_id,
                name=name,
                description=description,
                type=task_type,
                version=version,
                created_at=created_at,
                is_recurring=is_recurring,
                categories=categories,
                default_estimate_minutes=default_estimate,
                task_type=task_type_field,
                default_initial_aversion=default_aversion
            )
            session.add(task)
            session.commit()
        
        print(f"   [OK] Migrated: {name} ({task_id})")
        migrated += 1
        
    except Exception as e:
        print(f"   [ERROR] Failed to migrate {task_id}: {e}")
        errors += 1

# Summary
print("\n" + "=" * 70)
print("Migration Summary")
print("=" * 70)
print(f"Tasks migrated: {migrated}")
print(f"Tasks skipped: {skipped}")
print(f"Errors: {errors}")

# Verify
print("\n5. Verifying migration...")
with get_session() as session:
    db_tasks = session.query(Task).all()
    print(f"   Total tasks in database: {len(db_tasks)}")
    print(f"   Total tasks in CSV: {len(csv_df)}")

if migrated > 0:
    print("\n[SUCCESS] Migration complete!")
    print("\nYou can now use the app with database backend.")
    print("Your CSV file is still there as a backup.")
else:
    print("\n[NOTE] No new tasks were migrated.")
    if skipped > 0:
        print("All tasks were already in the database.")

print("\n" + "=" * 70)

