#!/usr/bin/env python3
"""
PostgreSQL Migration 004: Create Emotions Table

This migration creates the emotions table to store the list of available emotions.
This table is migrated from emotions.csv.

PostgreSQL-specific conversions:
- INTEGER PRIMARY KEY with autoincrement → SERIAL PRIMARY KEY (PostgreSQL native)
- Unique constraint enforced at database level
- Index created automatically on primary key

Run this migration after adding the Emotion model to backend/database.py.

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine
from sqlalchemy import inspect, text

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def migrate():
    """Create emotions table if it doesn't exist."""
    print("=" * 70)
    print("PostgreSQL Migration 004: Create Emotions Table")
    print("=" * 70)
    print("\nThis migration creates the emotions table for PostgreSQL.")
    print("The table stores the list of available emotions for user selection.")
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
    
    # Check if emotions table already exists (idempotent: skip if already done)
    if table_exists('emotions'):
        print("[NOTE] Emotions table already exists. Skipping (idempotent).")
        return True
    
    try:
        print("\nCreating emotions table for PostgreSQL...")
        print("This will use SERIAL for auto-incrementing primary key.")
        print("NOTE: Uses raw SQL to create base schema. Migration 011 adds user_id for data isolation.")
        
        # Use raw SQL so migration is independent of Emotion model (which may reference users table)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS emotions (
                    emotion_id SERIAL PRIMARY KEY,
                    emotion VARCHAR NOT NULL UNIQUE
                )
            """))
            conn.commit()
        
        print("[OK] Emotions table created successfully")
        
        # Verify the table was created
        if table_exists('emotions'):
            print("[OK] Verification: emotions table exists")
            
            # Check key columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('emotions')]
            
            required_columns = ['emotion_id', 'emotion']
            
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
            
            # Check that emotion_id is using SERIAL (PostgreSQL-specific)
            print("\nChecking data types...")
            column_info = {col['name']: col for col in inspector.get_columns('emotions')}
            
            if 'emotion_id' in column_info:
                col_type = str(column_info['emotion_id']['type'])
                if 'SERIAL' in col_type.upper() or 'INTEGER' in col_type.upper():
                    print(f"   [OK] 'emotion_id' column type: {col_type}")
                else:
                    print(f"   [WARNING] 'emotion_id' column type: {col_type}")
            
            # Check for unique constraint on emotion column
            print("\nChecking constraints...")
            constraints = inspector.get_unique_constraints('emotions')
            if constraints:
                print(f"   [OK] Found {len(constraints)} unique constraint(s)")
                for constraint in constraints:
                    if 'emotion' in constraint['column_names']:
                        print("   [OK] Unique constraint exists on 'emotion' column")
            else:
                print("   [NOTE] No unique constraints found (may be handled at application level)")
            
            print("\n[SUCCESS] Migration complete!")
            print("The emotions table is ready to use.")
            print("\nNext steps:")
            print("  1. Run migrate_csv_to_database.py to migrate existing CSV data")
            print("  2. Update EmotionManager to use database backend")
            
            return True
        else:
            print("[ERROR] Verification failed: emotions table was not created")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
