#!/usr/bin/env python
"""
Migration 008: Create SurveyResponse Table

This migration creates the survey_responses table to store individual survey
question responses from users. This table is migrated from survey_responses.csv.

Run this migration after adding the SurveyResponse model to backend/database.py.

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine, SurveyResponse
from sqlalchemy import inspect

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def migrate():
    """Create survey_responses table if it doesn't exist."""
    print("=" * 70)
    print("Migration 008: Create SurveyResponse Table")
    print("=" * 70)
    print("\nThis migration creates the survey_responses table.")
    print("The table stores individual survey question responses from users.")
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
    
    # Check if survey_responses table already exists
    if table_exists('survey_responses'):
        print("[NOTE] Survey responses table already exists.")
        print("If you've already run this migration, this is expected.")
        response = input("Continue anyway (will skip if table exists)? (y/N): ")
        if response.lower() != 'y':
            print("[SKIP] Migration cancelled.")
            return True
    
    try:
        print("\nCreating survey_responses table...")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        SurveyResponse.__table__.create(engine, checkfirst=True)
        
        print("[OK] Survey responses table created successfully")
        
        # Verify the table was created
        if table_exists('survey_responses'):
            print("[OK] Verification: survey_responses table exists")
            
            # Check key columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('survey_responses')]
            
            required_columns = [
                'response_id', 'user_id', 'question_category', 'question_id',
                'response_value', 'response_text', 'timestamp'
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
            
            # Check indexes
            print("\nChecking indexes...")
            indexes = inspector.get_indexes('survey_responses')
            index_names = [idx['name'] for idx in indexes]
            
            expected_indexes = [
                'ix_survey_responses_user_id',
                'ix_survey_responses_question_category',
                'ix_survey_responses_timestamp',
                'idx_survey_user_category',
                'idx_survey_user_timestamp'
            ]
            
            for idx_name in expected_indexes:
                if idx_name in index_names:
                    print(f"   [OK] Index '{idx_name}' exists")
                else:
                    # Some indexes might not be created yet, that's okay
                    pass
            
            print("\n[SUCCESS] Migration complete!")
            print("The survey_responses table is ready to use.")
            print("\nNext steps:")
            print("  1. Run migrate_csv_to_database.py or a data migration script to migrate existing CSV data")
            print("  2. Update SurveyManager to use database backend (if not already done)")
            
            return True
        else:
            print("[ERROR] Verification failed: survey_responses table was not created")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
