#!/usr/bin/env python3
"""
PostgreSQL Migration 002: Add Routine Scheduling Fields to Tasks Table

This migration adds the following columns to the tasks table:
- routine_frequency (VARCHAR, default 'none')
- routine_days_of_week (JSONB, default '[]')
- routine_time (VARCHAR, default '00:00')
- completion_window_hours (INTEGER, nullable)
- completion_window_days (INTEGER, nullable)

PostgreSQL-specific conversions:
- JSON column type uses JSONB (better performance and indexing)
- VARCHAR used for string fields (PostgreSQL recommendation)

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
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
    print("PostgreSQL Migration 002: Add Routine Scheduling Fields")
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
        print("Example: export DATABASE_URL='postgresql://user:password@localhost:5432/task_aversion_system'")
        return False
    
    if not database_url.startswith('postgresql'):
        print(f"[ERROR] This migration is designed for PostgreSQL only.")
        print(f"Current DATABASE_URL: {database_url}")
        print("For SQLite migrations, use the scripts in SQLite_migration/ folder.")
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
            
            # List of columns to add (PostgreSQL-specific syntax)
            columns_to_add = [
                {
                    'name': 'routine_frequency',
                    'type': 'VARCHAR(50)',
                    'default': "'none'",
                    'nullable': False,
                    'description': 'Frequency of routine: none, daily, weekly'
                },
                {
                    'name': 'routine_days_of_week',
                    'type': 'JSONB',  # PostgreSQL uses JSONB for better performance
                    'default': "'[]'::jsonb",  # JSONB default syntax
                    'nullable': False,
                    'description': 'Days of week for weekly routine (JSON array)'
                },
                {
                    'name': 'routine_time',
                    'type': 'VARCHAR(5)',
                    'default': "'00:00'",
                    'nullable': False,
                    'description': 'Time of day for routine (HH:MM format)'
                },
                {
                    'name': 'completion_window_hours',
                    'type': 'INTEGER',
                    'default': None,
                    'nullable': True,
                    'description': 'Hours to complete task after initialization without penalty'
                },
                {
                    'name': 'completion_window_days',
                    'type': 'INTEGER',
                    'default': None,
                    'nullable': True,
                    'description': 'Days to complete task after initialization without penalty'
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
                    # Build ALTER TABLE statement for PostgreSQL
                    if col_def['nullable']:
                        # Nullable column
                        if col_def['default']:
                            alter_sql = f"ALTER TABLE tasks ADD COLUMN {column_name} {col_def['type']} DEFAULT {col_def['default']}"
                        else:
                            alter_sql = f"ALTER TABLE tasks ADD COLUMN {column_name} {col_def['type']}"
                    else:
                        # Non-nullable column with default
                        alter_sql = f"ALTER TABLE tasks ADD COLUMN {column_name} {col_def['type']} NOT NULL DEFAULT {col_def['default']}"
                    
                    try:
                        session.execute(text(alter_sql))
                        session.commit()
                        print(f"   [OK] Added column '{column_name}' ({col_def['description']})")
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
