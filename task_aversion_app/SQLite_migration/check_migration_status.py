#!/usr/bin/env python
"""
Check Migration Status

This script checks which migrations have been applied to your database.
Useful for verifying the current state before running new migrations.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine
from sqlalchemy import inspect, text

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def check_table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def main():
    print("=" * 70)
    print("Migration Status Check")
    print("=" * 70)
    print()
    
    # Check DATABASE_URL
    database_url = os.getenv('DATABASE_URL', '')
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set!")
        print("Please set it before running this check.")
        return
    
    print(f"Database: {database_url}")
    print()
    
    # Check if tasks table exists
    if not check_table_exists('tasks'):
        print("[MISSING] Tasks table does not exist")
        print("  -> Run migration 001_initial_schema.py")
        return
    
    print("[OK] Tasks table exists")
    print()
    
    # Check for routine scheduling fields (Migration 002)
    print("Migration 002: Routine Scheduling Fields")
    print("-" * 70)
    
    routine_fields = [
        'routine_frequency',
        'routine_days_of_week',
        'routine_time',
        'completion_window_hours',
        'completion_window_days',
    ]
    
    all_exist = True
    for field in routine_fields:
        exists = check_column_exists('tasks', field)
        status = "[OK]" if exists else "[MISSING]"
        print(f"  {status} {field}: {'exists' if exists else 'MISSING'}")
        if not exists:
            all_exist = False
    
    print()
    if all_exist:
        print("[OK] Migration 002 appears to be complete")
    else:
        print("[INCOMPLETE] Migration 002 needs to be run")
        print("  -> Run: python SQLite_migration/002_add_routine_scheduling_fields.py")
    
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()

