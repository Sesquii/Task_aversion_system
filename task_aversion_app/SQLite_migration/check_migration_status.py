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
    
    # Check for task_instances table (Migration 003)
    print("Migration 003: Task Instances Table")
    print("-" * 70)
    
    if check_table_exists('task_instances'):
        print("  [OK] task_instances table exists")
    else:
        print("  [MISSING] task_instances table does not exist")
        print("  -> Run: python SQLite_migration/003_create_task_instances_table.py")
    
    print()
    
    # Check for emotions table (Migration 004)
    print("Migration 004: Emotions Table")
    print("-" * 70)
    
    if check_table_exists('emotions'):
        print("  [OK] emotions table exists")
    else:
        print("  [MISSING] emotions table does not exist")
        print("  -> Run: python SQLite_migration/004_create_emotions_table.py")
    
    print()
    
    # Check for indexes on task_instances (Migration 005)
    print("Migration 005: Indexes and Foreign Keys")
    print("-" * 70)
    
    if check_table_exists('task_instances'):
        try:
            inspector = inspect(engine)
            indexes = inspector.get_indexes('task_instances')
            index_names = [idx['name'] for idx in indexes]
            
            expected_indexes = [
                'idx_task_instances_task_status',
                'idx_task_instances_created_at',
                'idx_task_instances_is_completed',
                'idx_task_instances_is_deleted'
            ]
            
            for idx_name in expected_indexes:
                if idx_name in index_names:
                    print(f"  [OK] Index '{idx_name}' exists")
                else:
                    print(f"  [MISSING] Index '{idx_name}' does not exist")
        except Exception as e:
            print(f"  [ERROR] Could not check indexes: {e}")
    else:
        print("  [SKIP] task_instances table does not exist (run migration 003 first)")
    
    print()
    
    # Check for notes column (Migration 006)
    print("Migration 006: Notes Column")
    print("-" * 70)
    
    if check_column_exists('tasks', 'notes'):
        print("  [OK] notes column exists")
        print("  [OK] Migration 006 appears to be complete")
    else:
        print("  [MISSING] notes column does not exist")
        print("  -> Run: python SQLite_migration/006_add_notes_column.py")
    
    print()
    
    # Check for user_preferences table (Migration 007)
    print("Migration 007: User Preferences Table")
    print("-" * 70)
    
    if check_table_exists('user_preferences'):
        print("  [OK] user_preferences table exists")
        
        # Check key columns
        try:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('user_preferences')]
            key_columns = ['user_id', 'tutorial_completed', 'created_at', 'productivity_settings']
            
            for col in key_columns:
                exists = col in columns
                status = "[OK]" if exists else "[MISSING]"
                print(f"  {status} Column '{col}': {'exists' if exists else 'MISSING'}")
        except Exception as e:
            print(f"  [ERROR] Could not check columns: {e}")
    else:
        print("  [MISSING] user_preferences table does not exist")
        print("  -> Run: python SQLite_migration/007_create_user_preferences_table.py")
    
    print()
    
    # Check for survey_responses table (Migration 008)
    print("Migration 008: Survey Responses Table")
    print("-" * 70)
    
    if check_table_exists('survey_responses'):
        print("  [OK] survey_responses table exists")
        
        # Check key columns
        try:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('survey_responses')]
            key_columns = ['response_id', 'user_id', 'question_category', 'timestamp']
            
            for col in key_columns:
                exists = col in columns
                status = "[OK]" if exists else "[MISSING]"
                print(f"  {status} Column '{col}': {'exists' if exists else 'MISSING'}")
        except Exception as e:
            print(f"  [ERROR] Could not check columns: {e}")
    else:
        print("  [MISSING] survey_responses table does not exist")
        print("  -> Run: python SQLite_migration/008_create_survey_responses_table.py")
    
    print()
    
    # Check for users table (Migration 009)
    print("Migration 009: Users Table (OAuth Authentication)")
    print("-" * 70)
    
    if check_table_exists('users'):
        print("  [OK] users table exists")
        
        # Check key columns
        try:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            key_columns = ['user_id', 'email', 'google_id', 'oauth_provider']
            
            for col in key_columns:
                exists = col in columns
                status = "[OK]" if exists else "[MISSING]"
                print(f"  {status} Column '{col}': {'exists' if exists else 'MISSING'}")
        except Exception as e:
            print(f"  [ERROR] Could not check columns: {e}")
    else:
        print("  [MISSING] users table does not exist")
        print("  -> Run: python SQLite_migration/009_create_users_table.py")
    
    print()
    
    # Check for user_id foreign keys (Migration 010)
    print("Migration 010: User ID Foreign Keys")
    print("-" * 70)
    
    tables_to_check = ['tasks', 'task_instances', 'survey_responses', 'popup_triggers', 'notes']
    all_have_user_id = True
    
    for table_name in tables_to_check:
        if check_table_exists(table_name):
            has_user_id = check_column_exists(table_name, 'user_id') or check_column_exists(table_name, 'user_id_new')
            status = "[OK]" if has_user_id else "[MISSING]"
            print(f"  {status} {table_name}.user_id: {'exists' if has_user_id else 'MISSING'}")
            if not has_user_id:
                all_have_user_id = False
        else:
            print(f"  [SKIP] {table_name} table does not exist (run earlier migrations first)")
    
    if all_have_user_id:
        print("  [OK] Migration 010 appears to be complete")
    else:
        print("  [INCOMPLETE] Migration 010 needs to be run")
        print("  -> Run: python SQLite_migration/010_add_user_id_foreign_keys.py")
        print("  NOTE: Some tables may have 'user_id_new' columns that need data migration")
    
    print()
    
    # Check for emotions.user_id (Migration 011)
    print("Migration 011: Emotions User ID (Data Isolation)")
    print("-" * 70)
    
    if check_table_exists('emotions'):
        has_user_id = check_column_exists('emotions', 'user_id')
        status = "[OK]" if has_user_id else "[MISSING]"
        print(f"  {status} emotions.user_id: {'exists' if has_user_id else 'MISSING'}")
        if not has_user_id:
            print("  -> Run: python SQLite_migration/011_add_user_id_to_emotions.py")
    else:
        print("  [SKIP] emotions table does not exist (run migration 004 first)")
    
    print()
    print("=" * 70)
    print("\nSummary: Run migrations in order (001, 002, 003, 004, 005, 006, 007, 008, 009, 010, 011)")
    print("All migrations are idempotent - safe to run multiple times.")
    print("=" * 70)

if __name__ == "__main__":
    main()

