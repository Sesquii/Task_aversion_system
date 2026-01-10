#!/usr/bin/env python3
"""
PostgreSQL Migration 003: Create TaskInstance Table

This migration creates the task_instances table to store individual task execution instances.
This table is migrated from task_instances.csv.

PostgreSQL-specific conversions:
- JSON columns use JSONB for better performance and indexing
- Proper foreign key constraints (PostgreSQL enforces these)
- Indexes created for common query patterns

Run this migration after adding the TaskInstance model to backend/database.py.

Prerequisites:
- Migration 001 (initial schema) must be completed
- Migration 002 (routine scheduling fields) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
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
    print("PostgreSQL Migration 003: Create TaskInstance Table")
    print("=" * 70)
    print("\nThis migration creates the task_instances table for PostgreSQL.")
    print("The table stores individual task execution instances with all attributes.")
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
        print("\nCreating task_instances table for PostgreSQL...")
        print("This will use JSONB for JSON columns (better performance).")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        # SQLAlchemy will automatically use PostgreSQL-compatible types when DATABASE_URL is PostgreSQL
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
            
            # Check that JSON columns are using JSONB (PostgreSQL-specific)
            print("\nChecking data types...")
            column_types = {col['name']: str(col['type']) for col in inspector.get_columns('task_instances')}
            
            if 'predicted' in column_types:
                if 'JSONB' in column_types['predicted'].upper() or 'JSON' in column_types['predicted'].upper():
                    print("   [OK] 'predicted' column uses JSON/JSONB type")
                else:
                    print(f"   [WARNING] 'predicted' column type: {column_types['predicted']}")
            
            if 'actual' in column_types:
                if 'JSONB' in column_types['actual'].upper() or 'JSON' in column_types['actual'].upper():
                    print("   [OK] 'actual' column uses JSON/JSONB type")
                else:
                    print(f"   [WARNING] 'actual' column type: {column_types['actual']}")
            
            print("\n[SUCCESS] Migration complete!")
            print("The task_instances table is ready to use.")
            print("\nNext steps:")
            print("  1. Run migrate_csv_to_database.py to migrate existing CSV data")
            print("  2. Update InstanceManager to use database backend")
            print("  3. Run migration 005 to add indexes for better performance")
            
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
