#!/usr/bin/env python3
"""
PostgreSQL Migration 001: Initial Database Schema

This migration creates the initial database schema if it doesn't exist.
It's equivalent to running init_db() from backend.database, but specifically
for PostgreSQL with proper data types.

Key PostgreSQL conversions from SQLite:
- Uses init_db() which handles PostgreSQL correctly via SQLAlchemy
- All tables created with PostgreSQL-compatible schema
- JSON columns use JSONB for better performance and indexing

Note: If you've already run migrate_csv_to_database.py, this migration
is not needed as the schema was created during that process.

This script is provided for completeness and can be used to initialize
a fresh PostgreSQL database without migrating from CSV.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, engine
from sqlalchemy import inspect

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception as e:
        print(f"   [ERROR] Failed to check table existence: {e}")
        return False

def migrate():
    """Initialize database schema for PostgreSQL."""
    print("=" * 70)
    print("PostgreSQL Migration 001: Initial Database Schema")
    print("=" * 70)
    print("\nThis migration creates the initial database schema for PostgreSQL.")
    print("If tables already exist, this migration will skip them.")
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
    
    # Check if tasks table already exists
    if table_exists('tasks'):
        print("[NOTE] Tasks table already exists.")
        print("If you've already migrated from CSV, this migration is not needed.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("[SKIP] Migration cancelled.")
            return True
    
    try:
        print("Initializing database schema for PostgreSQL...")
        print("This will create all tables with PostgreSQL-compatible data types.")
        print()
        
        init_db()
        print("\n[SUCCESS] Database schema initialized!")
        
        # Verify
        print("\nVerifying created tables...")
        expected_tables = ['tasks', 'task_instances', 'emotions', 'popup_triggers', 
                          'popup_responses', 'notes']
        
        all_exist = True
        for table in expected_tables:
            exists = table_exists(table)
            status = "[OK]" if exists else "[MISSING]"
            print(f"   {status} {table}: {'exists' if exists else 'MISSING'}")
            if not exists:
                all_exist = False
        
        if all_exist:
            print("\n[OK] All tables verified successfully!")
        else:
            print("\n[WARNING] Some tables are missing. Migration may have failed.")
            return False
        
        if table_exists('tasks'):
            print("\n[OK] Tasks table created successfully")
            
            # Check key columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('tasks')]
            required_columns = ['task_id', 'name', 'description', 'type', 'version']
            
            print("\nChecking key columns in tasks table...")
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
        else:
            print("[WARNING] Tasks table was not created")
            return False
        
        print("\n[SUCCESS] Migration 001 complete!")
        print("Your PostgreSQL database is ready for the next migrations.")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
