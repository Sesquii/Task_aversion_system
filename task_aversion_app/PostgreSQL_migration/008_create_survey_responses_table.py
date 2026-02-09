#!/usr/bin/env python3
"""
PostgreSQL Migration 008: Create SurveyResponse Table

This migration creates the survey_responses table to store individual survey
question responses from users. This table is migrated from survey_responses.csv.

PostgreSQL-specific conversions:
- Proper indexes including composite indexes
- VARCHAR with explicit length constraints
- Foreign key constraints (if user_id references users table in future)

Run this migration after adding the SurveyResponse model to backend/database.py.

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
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
    print("PostgreSQL Migration 008: Create SurveyResponse Table")
    print("=" * 70)
    print("\nThis migration creates the survey_responses table for PostgreSQL.")
    print("The table stores individual survey question responses from users.")
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
    
    # Check if survey_responses table already exists (idempotent: skip if already done)
    if table_exists('survey_responses'):
        print("[NOTE] Survey responses table already exists. Skipping (idempotent).")
        return True
    
    try:
        print("\nCreating survey_responses table for PostgreSQL...")
        print("This will use proper indexes for efficient queries.")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        # SQLAlchemy will automatically use PostgreSQL-compatible types when DATABASE_URL is PostgreSQL
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
            
            # Check data types
            print("\nChecking data types...")
            column_types = {col['name']: str(col['type']) for col in inspector.get_columns('survey_responses')}
            
            # Verify key column types
            if 'response_id' in column_types:
                print(f"   [OK] 'response_id' column type: {column_types['response_id']}")
            if 'user_id' in column_types:
                print(f"   [OK] 'user_id' column type: {column_types['user_id']}")
            if 'timestamp' in column_types:
                col_type = column_types['timestamp'].upper()
                if 'TIMESTAMP' in col_type or 'TIMESTAMPTZ' in col_type:
                    print(f"   [OK] 'timestamp' column uses TIMESTAMP type")
                else:
                    print(f"   [WARNING] 'timestamp' column type: {column_types['timestamp']}")
            
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
            
            found_indexes = []
            missing_indexes = []
            for idx_name in expected_indexes:
                if idx_name in index_names:
                    print(f"   [OK] Index '{idx_name}' exists")
                    found_indexes.append(idx_name)
                else:
                    missing_indexes.append(idx_name)
            
            if missing_indexes:
                print(f"\n   [NOTE] Some indexes not found: {missing_indexes}")
                print("   These may be created automatically by SQLAlchemy or can be added manually.")
            
            # Check composite indexes (these are defined in __table_args__)
            print("\nChecking composite indexes...")
            # Note: SQLAlchemy may create these with different names or combine them
            # We check if the columns are indexed in composite indexes
            composite_indexes = [idx for idx in indexes if len(idx.get('column_names', [])) > 1]
            if composite_indexes:
                print(f"   [OK] Found {len(composite_indexes)} composite index(es)")
                for idx in composite_indexes:
                    cols = idx.get('column_names', [])
                    print(f"      - Index on: {', '.join(cols)}")
            else:
                print("   [NOTE] No composite indexes found (may need to create manually)")
                print("   Recommended: idx_survey_user_category (user_id, question_category)")
                print("   Recommended: idx_survey_user_timestamp (user_id, timestamp)")
            
            print("\n[SUCCESS] Migration complete!")
            print("The survey_responses table is ready to use.")
            print("\nNext steps:")
            print("  1. Run migrate_csv_to_database.py or a data migration script to migrate existing CSV data")
            print("  2. Update SurveyManager to use database backend (if not already done)")
            print("  3. If composite indexes are missing, they can be added manually:")
            print("     CREATE INDEX IF NOT EXISTS idx_survey_user_category ON survey_responses(user_id, question_category);")
            print("     CREATE INDEX IF NOT EXISTS idx_survey_user_timestamp ON survey_responses(user_id, timestamp);")
            
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
