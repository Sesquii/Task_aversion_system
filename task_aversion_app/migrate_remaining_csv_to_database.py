#!/usr/bin/env python
"""
Temporary migration script to migrate remaining CSV data to database.

This script checks what CSV data exists and migrates it to the database
if corresponding tables exist.

Currently migrates:
- emotions.csv → emotions table (Emotion model exists in database)
- Other CSV files are noted but not migrated (no corresponding tables yet)
"""
import os
import sys
import json
import pandas as pd
from datetime import datetime

# Set DATABASE_URL
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///data/task_aversion.db')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_session, Emotion, Task, TaskInstance

print("=" * 70)
print("Remaining CSV to Database Migration")
print("=" * 70)

# Initialize database
print("\n1. Initializing database...")
init_db()
print("   [OK] Database initialized")

# Check what's already in database
print("\n2. Checking existing database records...")
with get_session() as session:
    existing_tasks = session.query(Task).count()
    existing_instances = session.query(TaskInstance).count()
    existing_emotions = session.query(Emotion).count()
    print(f"   Tasks: {existing_tasks}")
    print(f"   Task Instances: {existing_instances}")
    print(f"   Emotions: {existing_emotions}")

# Track overall migration results
total_migrated = 0
total_skipped = 0
total_errors = 0

# ============================================================================
# Migrate emotions.csv → emotions table
# ============================================================================
print("\n3. Migrating emotions from CSV...")
emotions_csv = os.path.join('data', 'emotions.csv')
if os.path.exists(emotions_csv):
    try:
        csv_df = pd.read_csv(emotions_csv, dtype=str).fillna('')
        # Remove empty emotions
        csv_df = csv_df[csv_df['emotion'].str.strip() != '']
        print(f"   Found {len(csv_df)} emotion(s) in CSV")
        
        with get_session() as session:
            # Get existing emotions (case-insensitive comparison)
            existing_emotions_db = {e.emotion.lower() for e in session.query(Emotion).all()}
            
            migrated = 0
            skipped = 0
            errors = 0
            
            for idx, row in csv_df.iterrows():
                emotion_name = str(row.get('emotion', '')).strip()
                if not emotion_name:
                    continue
                
                # Check if already exists (case-insensitive)
                if emotion_name.lower() in existing_emotions_db:
                    skipped += 1
                    continue
                
                try:
                    # Check for duplicate in database (case-sensitive check)
                    existing = session.query(Emotion).filter(
                        Emotion.emotion == emotion_name
                    ).first()
                    
                    if existing:
                        skipped += 1
                        continue
                    
                    # Create new emotion
                    emotion = Emotion(emotion=emotion_name)
                    session.add(emotion)
                    session.commit()
                    
                    # Add to existing set for faster lookup
                    existing_emotions_db.add(emotion_name.lower())
                    migrated += 1
                    
                except Exception as e:
                    session.rollback()
                    print(f"   [ERROR] Failed to migrate emotion '{emotion_name}': {e}")
                    errors += 1
            
            print(f"   Emotions migrated: {migrated}")
            print(f"   Emotions skipped: {skipped}")
            print(f"   Errors: {errors}")
            total_migrated += migrated
            total_skipped += skipped
            total_errors += errors
            
    except Exception as e:
        print(f"   [ERROR] Failed to read emotions.csv: {e}")
        total_errors += 1
else:
    print("   [SKIP] emotions.csv not found")

# ============================================================================
# Check other CSV files (informational only - no tables exist yet)
# ============================================================================
print("\n4. Checking other CSV files...")
csv_files_to_check = [
    ('user_preferences.csv', 'User preferences - no database table yet'),
    ('survey_responses.csv', 'Survey responses - no database table yet'),
    ('logs.csv', 'Logs - deprecated/old format'),
    ('productivity_weight_configs.csv', 'Productivity configs - no database table yet'),
    ('formula_settings.csv', 'Formula settings - no database table yet'),
]

for csv_file, description in csv_files_to_check:
    csv_path = os.path.join('data', csv_file)
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, dtype=str)
            row_count = len(df)
            print(f"   {csv_file}: {row_count} row(s) - {description}")
        except Exception as e:
            print(f"   {csv_file}: Error reading file - {e}")
    else:
        print(f"   {csv_file}: Not found")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("Migration Summary")
print("=" * 70)
print(f"Total migrated: {total_migrated}")
print(f"Total skipped: {total_skipped}")
print(f"Total errors: {total_errors}")
print("=" * 70)

# Final database counts
print("\n5. Final database record counts...")
with get_session() as session:
    final_tasks = session.query(Task).count()
    final_instances = session.query(TaskInstance).count()
    final_emotions = session.query(Emotion).count()
    print(f"   Tasks: {final_tasks}")
    print(f"   Task Instances: {final_instances}")
    print(f"   Emotions: {final_emotions}")

if total_errors > 0:
    print("\n[WARNING] Some migrations had errors. Check the output above for details.")
    sys.exit(1)
elif total_migrated > 0:
    print("\n[SUCCESS] Migration completed successfully!")
    print("\nNote: Some CSV files (user_preferences, survey_responses, etc.)")
    print("do not have corresponding database tables yet and were not migrated.")
    sys.exit(0)
else:
    print("\n[NOTE] No new data was migrated.")
    print("All data was already in the database or CSV files are empty.")
    sys.exit(0)

