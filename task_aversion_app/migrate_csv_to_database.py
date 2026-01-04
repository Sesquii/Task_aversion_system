#!/usr/bin/env python
"""Migrate existing CSV tasks to SQLite database."""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_session, Task, Note
from backend.task_manager import TaskManager
from backend.csv_export import export_all_data_to_csv, get_export_summary

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
    print("\n[SUCCESS] Tasks migration complete!")
    print("\nYou can now use the app with database backend.")
    print("Your CSV file is still there as a backup.")
else:
    print("\n[NOTE] No new tasks were migrated.")
    if skipped > 0:
        print("All tasks were already in the database.")

# Migrate notes
print("\n" + "=" * 70)
print("Migrating Notes")
print("=" * 70)

notes_csv_file = os.path.join('data', 'notes.csv')
if os.path.exists(notes_csv_file):
    print(f"\n1. Loading notes from CSV...")
    notes_df = pd.read_csv(notes_csv_file, dtype=str).fillna('')
    print(f"   Found {len(notes_df)} note(s) in CSV")
    
    # Check what's already in database
    print("\n2. Checking existing database notes...")
    with get_session() as session:
        existing_notes = session.query(Note).all()
        existing_note_ids = {note.note_id for note in existing_notes}
        print(f"   Found {len(existing_notes)} note(s) already in database")
    
    # Migrate notes
    print("\n3. Migrating notes to database...")
    notes_migrated = 0
    notes_skipped = 0
    notes_errors = 0
    
    for idx, row in notes_df.iterrows():
        note_id = row.get('note_id', '').strip()
        if not note_id:
            print(f"   [SKIP] Row {idx}: No note_id")
            notes_skipped += 1
            continue
        
        # Skip if already in database
        if note_id in existing_note_ids:
            print(f"   [SKIP] {note_id}: Already in database")
            notes_skipped += 1
            continue
        
        try:
            content = row.get('content', '').strip()
            if not content:
                print(f"   [SKIP] {note_id}: Empty content")
                notes_skipped += 1
                continue
            
            # Parse timestamp
            timestamp_str = row.get('timestamp', '').strip()
            try:
                if timestamp_str:
                    # Try ISO format first
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        # Fallback to other formats if needed
                        timestamp = datetime.utcnow()
                else:
                    timestamp = datetime.utcnow()
            except (ValueError, TypeError):
                timestamp = datetime.utcnow()
            
            # Create note in database
            with get_session() as session:
                note = Note(
                    note_id=note_id,
                    content=content,
                    timestamp=timestamp
                )
                session.add(note)
                session.commit()
            
            print(f"   [OK] Migrated note: {note_id[:20]}...")
            notes_migrated += 1
            
        except Exception as e:
            print(f"   [ERROR] Failed to migrate {note_id}: {e}")
            notes_errors += 1
    
    # Notes summary
    print("\n" + "=" * 70)
    print("Notes Migration Summary")
    print("=" * 70)
    print(f"Notes migrated: {notes_migrated}")
    print(f"Notes skipped: {notes_skipped}")
    print(f"Errors: {notes_errors}")
    
    # Verify notes
    print("\n4. Verifying notes migration...")
    with get_session() as session:
        db_notes = session.query(Note).all()
        print(f"   Total notes in database: {len(db_notes)}")
        print(f"   Total notes in CSV: {len(notes_df)}")
    
    if notes_migrated > 0:
        print("\n[SUCCESS] Notes migration complete!")
    else:
        print("\n[NOTE] No new notes were migrated.")
        if notes_skipped > 0:
            print("All notes were already in the database.")
else:
    print("\n[NOTE] No notes.csv file found. Skipping notes migration.")

# Export database to CSV (backup/verification)
print("\n" + "=" * 70)
print("Exporting Database to CSV (Backup)")
print("=" * 70)

try:
    data_dir = os.path.join('data')
    export_counts, exported_files = export_all_data_to_csv(
        data_dir=data_dir,
        include_user_preferences=True
    )
    
    summary = get_export_summary(export_counts)
    print(f"\n{summary}")
    print(f"\n[SUCCESS] Database exported to CSV files in: {data_dir}")
    print("\nExported files:")
    for file_path in exported_files:
        print(f"  - {os.path.basename(file_path)}")
    
except Exception as e:
    print(f"\n[WARNING] Failed to export database to CSV: {e}")
    print("Migration completed, but CSV export failed. You can export manually from Settings.")

print("\n" + "=" * 70)

