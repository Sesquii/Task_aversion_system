#!/usr/bin/env python
"""
Migration 009: Create Users Table

This migration creates the users table for OAuth authentication.
This table stores authenticated user accounts (Google OAuth, etc.).

SQLite-specific:
- Uses INTEGER PRIMARY KEY (auto-incrementing) instead of SERIAL
- Foreign keys need to be enabled with PRAGMA foreign_keys = ON
- TEXT type for VARCHAR fields

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine, User
from sqlalchemy import inspect, text

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def migrate():
    """Create users table if it doesn't exist."""
    print("=" * 70)
    print("SQLite Migration 009: Create Users Table")
    print("=" * 70)
    print("\nThis migration creates the users table for OAuth authentication.")
    print("The table stores authenticated user accounts (Google OAuth, etc.).")
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
        print("For PostgreSQL, use the scripts in PostgreSQL_migration/ folder.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Check if tasks table exists (prerequisite)
    if not table_exists('tasks'):
        print("[ERROR] Tasks table does not exist!")
        print("Please run migration 001 (initial schema) first.")
        return False
    
    print("[OK] Tasks table exists (prerequisite check passed)")
    
    # Check if users table already exists
    if table_exists('users'):
        print("[NOTE] Users table already exists.")
        print("If you've already run this migration, this is expected.")
        response = input("Continue anyway (will skip if table exists)? (y/N): ")
        if response.lower() != 'y':
            print("[SKIP] Migration cancelled.")
            return True
    
    try:
        print("\nCreating users table for SQLite...")
        print("This will use INTEGER PRIMARY KEY for auto-incrementing.")
        
        # Enable foreign keys for SQLite (required for foreign key constraints)
        with get_session() as session:
            session.execute(text("PRAGMA foreign_keys = ON"))
            session.commit()
            print("[OK] Foreign keys enabled for this session")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        # SQLAlchemy will automatically use SQLite-compatible types when DATABASE_URL is SQLite
        User.__table__.create(engine, checkfirst=True)
        
        print("[OK] Users table created successfully")
        
        # Verify the table was created
        if table_exists('users'):
            print("[OK] Verification: users table exists")
            
            # Check key columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('users')]
            
            required_columns = [
                'user_id', 'email', 'username', 'google_id', 
                'oauth_provider', 'email_verified', 'is_active',
                'created_at', 'last_login'
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
            
            # Check that user_id is using INTEGER PRIMARY KEY (SQLite-specific)
            print("\nChecking data types...")
            column_info = {col['name']: col for col in inspector.get_columns('users')}
            
            if 'user_id' in column_info:
                col_type = str(column_info['user_id']['type'])
                if 'INTEGER' in col_type.upper() or 'PRIMARY' in col_type.upper():
                    print(f"   [OK] 'user_id' column type: {col_type}")
                else:
                    print(f"   [WARNING] 'user_id' column type: {col_type}")
            
            # Check for unique constraints (SQLite handles these differently)
            print("\nChecking constraints and indexes...")
            try:
                # Check indexes
                indexes = inspector.get_indexes('users')
                index_names = [idx['name'] for idx in indexes]
                
                if indexes:
                    print(f"   [OK] Found {len(indexes)} index(es)")
                    for idx in indexes:
                        if 'email' in idx.get('column_names', []):
                            print("   [OK] Index on 'email' exists")
                        if 'google_id' in idx.get('column_names', []):
                            print("   [OK] Index on 'google_id' exists")
                else:
                    print("   [NOTE] No indexes found (may be created automatically)")
            except Exception as e:
                print(f"   [NOTE] Could not check indexes: {e}")
            
            print("\n[SUCCESS] Migration complete!")
            print("The users table is ready for OAuth authentication.")
            print("\nNext steps:")
            print("  1. Run migration 010 to add user_id foreign keys to existing tables")
            print("  2. Implement OAuth authentication backend (backend/auth.py)")
            print("  3. Update all backend managers to filter by user_id")
            
            return True
        else:
            print("[ERROR] Verification failed: users table was not created")
            return False
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
