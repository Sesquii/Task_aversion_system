#!/usr/bin/env python3
"""
PostgreSQL Migration 009: Create Users Table

This migration creates the users table for OAuth authentication.
This table stores authenticated user accounts (Google OAuth, etc.).

PostgreSQL-specific conversions:
- Uses SERIAL for auto-incrementing primary key
- Proper indexes on email and google_id for OAuth lookups
- UNIQUE constraints enforced at database level

Prerequisites:
- Migration 001 (initial schema) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine, User
from sqlalchemy import inspect

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
    print("PostgreSQL Migration 009: Create Users Table")
    print("=" * 70)
    print("\nThis migration creates the users table for OAuth authentication.")
    print("The table stores authenticated user accounts (Google OAuth, etc.).")
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
    
    # Check if users table already exists
    if table_exists('users'):
        print("[NOTE] Users table already exists.")
        print("If you've already run this migration, this is expected.")
        response = input("Continue anyway (will skip if table exists)? (y/N): ")
        if response.lower() != 'y':
            print("[SKIP] Migration cancelled.")
            return True
    
    try:
        print("\nCreating users table for PostgreSQL...")
        print("This will use SERIAL for auto-incrementing primary key.")
        print("This table is required for OAuth authentication.")
        
        # Use SQLAlchemy to create the table (this will only create if it doesn't exist)
        # SQLAlchemy will automatically use PostgreSQL-compatible types when DATABASE_URL is PostgreSQL
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
            
            # Check that user_id is using SERIAL (PostgreSQL-specific)
            print("\nChecking data types...")
            column_info = {col['name']: col for col in inspector.get_columns('users')}
            
            if 'user_id' in column_info:
                col_type = str(column_info['user_id']['type'])
                if 'SERIAL' in col_type.upper() or 'INTEGER' in col_type.upper():
                    print(f"   [OK] 'user_id' column type: {col_type}")
                else:
                    print(f"   [WARNING] 'user_id' column type: {col_type}")
            
            # Check for unique constraints on email and google_id
            print("\nChecking constraints and indexes...")
            constraints = inspector.get_unique_constraints('users')
            if constraints:
                print(f"   [OK] Found {len(constraints)} unique constraint(s)")
                for constraint in constraints:
                    if 'email' in constraint['column_names']:
                        print("   [OK] Unique constraint exists on 'email' column")
                    if 'google_id' in constraint['column_names']:
                        print("   [OK] Unique constraint exists on 'google_id' column")
            else:
                print("   [NOTE] No unique constraints found (may be handled at application level)")
            
            # Check indexes
            indexes = inspector.get_indexes('users')
            index_names = [idx['name'] for idx in indexes]
            
            if 'ix_users_email' in index_names or any('email' in idx['column_names'] for idx in indexes):
                print("   [OK] Index on 'email' exists")
            else:
                print("   [NOTE] Index on 'email' not found (may be created automatically)")
            
            if 'ix_users_google_id' in index_names or any('google_id' in idx['column_names'] for idx in indexes):
                print("   [OK] Index on 'google_id' exists")
            else:
                print("   [NOTE] Index on 'google_id' not found (may be created automatically)")
            
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
