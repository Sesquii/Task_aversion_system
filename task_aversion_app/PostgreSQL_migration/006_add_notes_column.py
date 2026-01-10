#!/usr/bin/env python3
"""
PostgreSQL Migration 006: Add Notes Column to Tasks Table

This migration adds the following column to the tasks table:
- notes (TEXT, default '')

The notes field allows users to add runtime notes to task templates,
separate from the description which is set at task creation.

PostgreSQL-specific:
- Uses TEXT type (PostgreSQL's unlimited-length text type)
- Default empty string

Run this migration after updating database.py with the notes field.

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
    """Add notes column to tasks table if it doesn't exist."""
    print("=" * 70)
    print("PostgreSQL Migration 006: Add Notes Column to Tasks Table")
    print("=" * 70)
    print("\nThis migration adds the notes field to the tasks table.")
    print("The notes field allows users to add runtime notes to task templates.")
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
            
            # Column to add (PostgreSQL-specific syntax)
            column_name = 'notes'
            
            if column_exists('tasks', column_name):
                print(f"   [SKIP] Column '{column_name}' already exists")
                print("\n[NOTE] Notes column already exists. No migration needed.")
                return True
            else:
                # Build ALTER TABLE statement for PostgreSQL
                # TEXT type with default empty string, NOT NULL constraint
                alter_sql = "ALTER TABLE tasks ADD COLUMN notes TEXT NOT NULL DEFAULT ''"
                
                try:
                    session.execute(text(alter_sql))
                    session.commit()
                    print(f"   [OK] Added column '{column_name}'")
                except Exception as e:
                    session.rollback()
                    error_msg = f"Failed to add column '{column_name}': {e}"
                    print(f"   [ERROR] {error_msg}")
                    return False
            
            # Verification
            print("\n" + "=" * 70)
            print("Verification")
            print("=" * 70)
            exists = column_exists('tasks', column_name)
            status = "[OK]" if exists else "[MISSING]"
            print(f"   {status} {column_name}: {'exists' if exists else 'MISSING'}")
            
            if exists:
                # Check column type
                inspector = inspect(engine)
                columns = inspector.get_columns('tasks')
                notes_col = next((col for col in columns if col['name'] == 'notes'), None)
                if notes_col:
                    col_type = str(notes_col['type'])
                    print(f"   [OK] Column type: {col_type}")
                    print(f"   [OK] Nullable: {notes_col.get('nullable', 'unknown')}")
                    print(f"   [OK] Default: {notes_col.get('default', 'unknown')}")
                
                print("\n[SUCCESS] Migration complete!")
                print("Your database now supports the notes field on tasks.")
                print("\nYou can now use the append_task_notes and get_task_notes methods.")
                return True
            else:
                print("\n[WARNING] Column is missing. Migration may have failed.")
                return False
            
        except Exception as e:
            session.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
