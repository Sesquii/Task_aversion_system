#!/usr/bin/env python
"""Migrate existing CSV task instances to SQLite database."""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_session, TaskInstance

print("=" * 70)
print("Task Instances CSV to Database Migration")
print("=" * 70)

# Initialize database
print("\n1. Initializing database...")
init_db()
print("   [OK] Database initialized")

# Load CSV instances
print("\n2. Loading task instances from CSV...")
csv_file = os.path.join('data', 'task_instances.csv')
if not os.path.exists(csv_file):
    print(f"   [ERROR] CSV file not found: {csv_file}")
    sys.exit(1)

csv_df = pd.read_csv(csv_file, dtype=str).fillna('')
print(f"   Found {len(csv_df)} instance(s) in CSV")

# Check what's already in database
print("\n3. Checking existing database instances...")
with get_session() as session:
    existing_instances = session.query(TaskInstance).all()
    existing_instance_ids = {instance.instance_id for instance in existing_instances}
    print(f"   Found {len(existing_instances)} instance(s) already in database")

# Migrate instances
print("\n4. Migrating instances to database...")
migrated = 0
skipped = 0
errors = 0

def parse_datetime(csv_str):
    """Parse CSV datetime string to datetime object."""
    if not csv_str or str(csv_str).strip() == '':
        return None
    try:
        return datetime.strptime(str(csv_str).strip(), "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None

def parse_json_field(json_str):
    """Parse JSON string to dict."""
    if not json_str or str(json_str).strip() == '':
        return {}
    try:
        parsed = json.loads(str(json_str))
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}

def parse_float(csv_str):
    """Parse CSV string to float, returning None for empty values."""
    if not csv_str or str(csv_str).strip() == '':
        return None
    try:
        return float(csv_str)
    except (ValueError, TypeError):
        return None

def parse_bool(csv_str):
    """Parse CSV string to boolean."""
    return str(csv_str).lower() == 'true'

for idx, row in csv_df.iterrows():
    instance_id = row.get('instance_id', '').strip()
    if not instance_id:
        print(f"   [SKIP] Row {idx}: No instance_id")
        skipped += 1
        continue
    
    # Skip if already in database
    if instance_id in existing_instance_ids:
        print(f"   [SKIP] {instance_id}: Already in database")
        skipped += 1
        continue
    
    try:
        # Parse all fields
        task_id = row.get('task_id', '').strip()
        task_name = row.get('task_name', '').strip()
        task_version = int(row.get('task_version', 1)) if row.get('task_version') else 1
        
        # Parse timestamps
        created_at = parse_datetime(row.get('created_at'))
        initialized_at = parse_datetime(row.get('initialized_at'))
        started_at = parse_datetime(row.get('started_at'))
        completed_at = parse_datetime(row.get('completed_at'))
        cancelled_at = parse_datetime(row.get('cancelled_at'))
        
        # Parse JSON fields
        predicted = parse_json_field(row.get('predicted'))
        actual = parse_json_field(row.get('actual'))
        
        # Parse numeric fields
        procrastination_score = parse_float(row.get('procrastination_score'))
        proactive_score = parse_float(row.get('proactive_score'))
        behavioral_score = parse_float(row.get('behavioral_score'))
        net_relief = parse_float(row.get('net_relief'))
        duration_minutes = parse_float(row.get('duration_minutes'))
        delay_minutes = parse_float(row.get('delay_minutes'))
        relief_score = parse_float(row.get('relief_score'))
        cognitive_load = parse_float(row.get('cognitive_load'))
        mental_energy_needed = parse_float(row.get('mental_energy_needed'))
        task_difficulty = parse_float(row.get('task_difficulty'))
        emotional_load = parse_float(row.get('emotional_load'))
        environmental_effect = parse_float(row.get('environmental_effect'))
        
        # Parse boolean fields
        is_completed = parse_bool(row.get('is_completed', 'False'))
        is_deleted = parse_bool(row.get('is_deleted', 'False'))
        
        # Parse status
        status = row.get('status', 'active').strip() or 'active'
        
        # Parse skills_improved (text field)
        skills_improved = str(row.get('skills_improved', '')).strip()
        
        # Create instance in database
        with get_session() as session:
            instance = TaskInstance(
                instance_id=instance_id,
                task_id=task_id,
                task_name=task_name,
                task_version=task_version,
                created_at=created_at or datetime.now(),  # Default to now if missing
                initialized_at=initialized_at,
                started_at=started_at,
                completed_at=completed_at,
                cancelled_at=cancelled_at,
                predicted=predicted,
                actual=actual,
                procrastination_score=procrastination_score,
                proactive_score=proactive_score,
                behavioral_score=behavioral_score,
                net_relief=net_relief,
                is_completed=is_completed,
                is_deleted=is_deleted,
                status=status,
                duration_minutes=duration_minutes,
                delay_minutes=delay_minutes,
                relief_score=relief_score,
                cognitive_load=cognitive_load,
                mental_energy_needed=mental_energy_needed,
                task_difficulty=task_difficulty,
                emotional_load=emotional_load,
                environmental_effect=environmental_effect,
                skills_improved=skills_improved
            )
            session.add(instance)
            session.commit()
        
        print(f"   [OK] Migrated: {instance_id} ({task_name})")
        migrated += 1
        
    except Exception as e:
        print(f"   [ERROR] Failed to migrate {instance_id}: {e}")
        import traceback
        traceback.print_exc()
        errors += 1

# Summary
print("\n" + "=" * 70)
print("Migration Summary")
print("=" * 70)
print(f"Instances migrated: {migrated}")
print(f"Instances skipped: {skipped}")
print(f"Errors: {errors}")

# Verify
print("\n5. Verifying migration...")
with get_session() as session:
    db_instances = session.query(TaskInstance).all()
    print(f"   Total instances in database: {len(db_instances)}")
    print(f"   Total instances in CSV: {len(csv_df)}")

if migrated > 0:
    print("\n[SUCCESS] Migration complete!")
    print("\nYou can now use the app with database backend.")
    print("Your CSV file is still there as a backup.")
else:
    print("\n[NOTE] No new instances were migrated.")
    if skipped > 0:
        print("All instances were already in the database.")

print("\n" + "=" * 70)

