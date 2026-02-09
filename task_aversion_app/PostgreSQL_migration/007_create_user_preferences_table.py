#!/usr/bin/env python3
"""
PostgreSQL Migration 007: Create UserPreferences Table

This migration creates the user_preferences table to store user settings,
preferences, and state information. This table is migrated from user_preferences.csv.

PostgreSQL-specific conversions:
- JSON columns use JSONB (better performance and indexing)
- VARCHAR with explicit length constraints
- Proper indexes for query performance

Run this migration after adding the UserPreferences model to backend/database.py.

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine, UserPreferences
from sqlalchemy import inspect

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def migrate():
    """Create user_preferences table if it doesn't exist."""
    print("=" * 70)
    print("PostgreSQL Migration 007: Create UserPreferences Table")
    print("=" * 70)
    print("\nThis migration creates the user_preferences table for PostgreSQL.")
    print("The table stores user settings, preferences, and state information.")
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
    
    # Check if user_preferences table already exists (idempotent: skip if already done)
    if table_exists('user_preferences'):
        print("[NOTE] User preferences table already exists. Skipping (idempotent).")
        return True
    
    try:
        print("\nCreating user_preferences table for PostgreSQL...")
        print("This will use JSONB for JSON columns (better performance).")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        # SQLAlchemy will automatically use PostgreSQL-compatible types when DATABASE_URL is PostgreSQL
        UserPreferences.__table__.create(engine, checkfirst=True)
        
        print("[OK] User preferences table created successfully")
        
        # Verify the table was created
        if table_exists('user_preferences'):
            print("[OK] Verification: user_preferences table exists")
            
            # Check key columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('user_preferences')]
            
            required_columns = [
                'user_id', 'tutorial_completed', 'tutorial_choice', 'tutorial_auto_show',
                'tooltip_mode_enabled', 'survey_completed', 'created_at', 'last_active',
                'gap_handling', 'persistent_emotion_values', 'productivity_history',
                'productivity_goal_settings', 'monitored_metrics_config',
                'execution_score_chunk_state', 'productivity_settings'
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
            column_types = {col['name']: str(col['type']) for col in inspector.get_columns('user_preferences')}
            
            json_columns = ['persistent_emotion_values', 'productivity_history', 
                          'productivity_goal_settings', 'monitored_metrics_config',
                          'execution_score_chunk_state', 'productivity_settings']
            
            all_jsonb = True
            for col_name in json_columns:
                if col_name in column_types:
                    col_type = column_types[col_name].upper()
                    if 'JSONB' in col_type:
                        print(f"   [OK] '{col_name}' column uses JSONB type")
                    elif 'JSON' in col_type:
                        print(f"   [OK] '{col_name}' column uses JSON type (acceptable)")
                    else:
                        print(f"   [WARNING] '{col_name}' column type: {column_types[col_name]}")
                        all_jsonb = False
                else:
                    print(f"   [MISSING] '{col_name}' column not found")
                    all_jsonb = False
            
            if all_jsonb:
                print("\n[OK] All JSON columns use JSON/JSONB types")
            
            # Check indexes
            print("\nChecking indexes...")
            indexes = inspector.get_indexes('user_preferences')
            index_names = [idx['name'] for idx in indexes]
            
            if 'ix_user_preferences_created_at' in index_names:
                print("   [OK] Index on 'created_at' exists")
            else:
                print("   [NOTE] Index on 'created_at' not found (may be created automatically)")
            
            print("\n[SUCCESS] Migration complete!")
            print("The user_preferences table is ready to use.")
            print("\nNext steps:")
            print("  1. Run migrate_csv_to_database.py or a data migration script to migrate existing CSV data")
            print("  2. Update UserStateManager to use database backend (if not already done)")
            print("  3. Consider adding GIN indexes on JSONB columns for efficient JSON queries")
            
            return True
        else:
            print("[ERROR] Verification failed: user_preferences table was not created")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
