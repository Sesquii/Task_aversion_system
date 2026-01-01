#!/usr/bin/env python
"""
Migration 001: Initial Database Schema

This migration creates the initial database schema if it doesn't exist.
It's equivalent to running init_db() from backend.database.

Note: If you've already run migrate_csv_to_database.py, this migration
is not needed as the schema was created during that process.

This script is provided for completeness and can be used to initialize
a fresh database without migrating from CSV.
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
    except Exception:
        return False

def migrate():
    """Initialize database schema."""
    print("=" * 70)
    print("Migration 001: Initial Database Schema")
    print("=" * 70)
    print("\nThis migration creates the initial database schema.")
    print("If tables already exist, this migration will skip them.")
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
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
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
        print("Initializing database schema...")
        init_db()
        print("\n[SUCCESS] Database schema initialized!")
        
        # Verify
        if table_exists('tasks'):
            print("[OK] Tasks table created successfully")
        else:
            print("[WARNING] Tasks table was not created")
            return False
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

