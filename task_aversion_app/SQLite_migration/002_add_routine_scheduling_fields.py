#!/usr/bin/env python
"""
Migration 002: Add Routine Scheduling Fields to Tasks Table

This migration adds the following columns to the tasks table:
- routine_frequency (VARCHAR, default 'none')
- routine_days_of_week (JSON, default '[]')
- routine_time (VARCHAR, default '00:00')
- completion_window_hours (INTEGER, nullable)
- completion_window_days (INTEGER, nullable)

Run this migration after updating database.py with routine scheduling fields.

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine
from sqlalchemy import text, inspect

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        print(f"   [ERROR] Failed to check column existence: {e}")
        return False

def migrate():
    """Add new routine scheduling columns to tasks table if they don't exist."""
    print("=" * 70)
    print("Migration 002: Add Routine Scheduling Fields")
    print("=" * 70)
    print("\nThis migration adds routine scheduling fields to the tasks table.")
    print("Fields: routine_frequency, routine_days_of_week, routine_time,")
    print("        completion_window_hours, completion_window_days")
    print()
    
    # Check DATABASE_URL
    database_url = os.getenv('DATABASE_URL', '')
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set!")
        print("Please set it before running this migration.")
        print("Example: export DATABASE_URL='sqlite:///data/task_aversion.db'")
        return False
    
    if not database_url.startswith('sqlite'):
        print(f"[WARNING] This migration is designed for SQLite.")
        print(f"Current DATABASE_URL: {database_url}")
        print("For PostgreSQL, use a different migration script.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    with get_session() as session:
        try:
            # Check if table exists
            inspector = inspect(engine)
            if 'tasks' not in inspector.get_table_names():
                print("[ERROR] Tasks table does not exist!")
                print("Please run migration 001 (initial schema) first.")
                return False
            
            print("[OK] Tasks table exists")
            
            # List of columns to add (SQLite-specific syntax)
            columns_to_add = [
                {
                    'name': 'routine_frequency',
                    'type': 'VARCHAR',
                    'default': "'none'",
                    'nullable': False
                },
                {
                    'name': 'routine_days_of_week',
                    'type': 'TEXT',  # SQLite uses TEXT for JSON
                    'default': "'[]'",
                    'nullable': False
                },
                {
                    'name': 'routine_time',
                    'type': 'VARCHAR',
                    'default': "'00:00'",
                    'nullable': False
                },
                {
                    'name': 'completion_window_hours',
                    'type': 'INTEGER',
                    'default': None,
                    'nullable': True
                },
                {
                    'name': 'completion_window_days',
                    'type': 'INTEGER',
                    'default': None,
                    'nullable': True
                },
            ]
            
            added_count = 0
            skipped_count = 0
            errors = []
            
            for col_def in columns_to_add:
                column_name = col_def['name']
                
                if column_exists('tasks', column_name):
                    print(f"   [SKIP] Column '{column_name}' already exists")
                    skipped_count += 1
                else:
                    # Build ALTER TABLE statement for SQLite
                    if col_def['nullable']:
                        # Nullable column
                        alter_sql = f"ALTER TABLE tasks ADD COLUMN {column_name} {col_def['type']}"
                    else:
                        # Non-nullable column with default
                        alter_sql = f"ALTER TABLE tasks ADD COLUMN {column_name} {col_def['type']} DEFAULT {col_def['default']}"
                    
                    try:
                        session.execute(text(alter_sql))
                        session.commit()
                        print(f"   [OK] Added column '{column_name}'")
                        added_count += 1
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to add column '{column_name}': {e}"
                        print(f"   [ERROR] {error_msg}")
                        errors.append(error_msg)
            
            # Summary
            print("\n" + "=" * 70)
            print("Migration Summary")
            print("=" * 70)
            print(f"Columns added: {added_count}")
            print(f"Columns skipped (already exist): {skipped_count}")
            
            if errors:
                print(f"\nErrors encountered: {len(errors)}")
                for error in errors:
                    print(f"  - {error}")
                return False
            
            if added_count > 0:
                print("\n[SUCCESS] Migration complete!")
                print("Your database now supports routine scheduling fields.")
                print("\nYou can now use routine scheduling features in the app.")
            else:
                print("\n[NOTE] All columns already exist. No migration needed.")
            
            # Verification
            print("\n" + "=" * 70)
            print("Verification")
            print("=" * 70)
            all_exist = True
            for col_def in columns_to_add:
                exists = column_exists('tasks', col_def['name'])
                status = "[OK]" if exists else "[MISSING]"
                print(f"   {status} {col_def['name']}: {'exists' if exists else 'MISSING'}")
                if not exists:
                    all_exist = False
            
            if all_exist:
                print("\n[OK] All columns verified successfully!")
            else:
                print("\n[WARNING] Some columns are missing. Migration may have failed.")
                return False
            
            return True
            
        except Exception as e:
            session.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

