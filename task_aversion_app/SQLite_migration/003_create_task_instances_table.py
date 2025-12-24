#!/usr/bin/env python
"""
Migration 003: Create TaskInstance Table

This migration creates the task_instances table to store individual task execution instances.
This table is migrated from task_instances.csv.

Run this migration after adding the TaskInstance model to backend/database.py.

Prerequisites:
- Migration 001 (initial schema) must be completed
- Migration 002 (routine scheduling fields) must be completed
- DATABASE_URL environment variable must be set
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine, TaskInstance
from sqlalchemy import inspect, text

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def migrate():
    """Create task_instances table if it doesn't exist."""
    print("=" * 70)
    print("Migration 003: Create TaskInstance Table")
    print("=" * 70)
    print("\nThis migration creates the task_instances table.")
    print("The table stores individual task execution instances with all attributes.")
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
    
    # Check if tasks table exists (prerequisite)
    if not table_exists('tasks'):
        print("[ERROR] Tasks table does not exist!")
        print("Please run migration 001 (initial schema) first.")
        return False
    
    print("[OK] Tasks table exists (prerequisite check passed)")
    
    # Check if task_instances table already exists
    if table_exists('task_instances'):
        print("[NOTE] Task instances table already exists.")
        print("If you've already run this migration, this is expected.")
        response = input("Continue anyway (will skip if table exists)? (y/N): ")
        if response.lower() != 'y':
            print("[SKIP] Migration cancelled.")
            return True
    
    try:
        print("\nCreating task_instances table...")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        TaskInstance.__table__.create(engine, checkfirst=True)
        
        print("[OK] Task instances table created successfully")
        
        # Verify the table was created
        if table_exists('task_instances'):
            print("[OK] Verification: task_instances table exists")
            
            # Check key columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('task_instances')]
            
            required_columns = [
                'instance_id', 'task_id', 'task_name', 'task_version',
                'created_at', 'initialized_at', 'started_at', 'completed_at', 'cancelled_at',
                'predicted', 'actual', 'status', 'is_completed', 'is_deleted'
            ]
            
            print("\nChecking key columns...")
            missing_columns = []
            for col in required_columns:
                if col in columns:
                    print(f"   [OK] Column '{col}' exists")
                else:
                    print(f"   [MISSING] Column '{col}' not found")
                    missing_columns.append(col)
            
            if missing_columns:
                print(f"\n[WARNING] Some required columns are missing: {missing_columns}")
                return False
            
            print("\n[SUCCESS] Migration complete!")
            print("The task_instances table is ready to use.")
            print("\nNext steps:")
            print("  1. Run migrate_csv_to_database.py to migrate existing CSV data")
            print("  2. Update InstanceManager to use database backend")
            
            return True
        else:
            print("[ERROR] Verification failed: task_instances table was not created")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

