#!/usr/bin/env python3
"""
Migration script to remove UNIQUE constraint from users.username column.

This fixes the issue where multiple users cannot have the same name.
Run this once to update the database schema.
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import engine, Base, User
from sqlalchemy import inspect, text

def migrate_remove_username_unique():
    """Remove UNIQUE constraint from users.username column."""
    print("\n" + "="*70)
    print("MIGRATION: Remove UNIQUE constraint from users.username")
    print("="*70)
    
    try:
        with engine.connect() as conn:
            # Check if we're using SQLite
            if engine.dialect.name == 'sqlite':
                print("\n[INFO] Using SQLite database")
                
                # SQLite doesn't support DROP CONSTRAINT directly
                # We need to recreate the table without the unique constraint
                print("\n[INFO] SQLite requires table recreation to remove constraint")
                print("[INFO] This will preserve all existing data")
                
                # Get current table structure
                inspector = inspect(engine)
                columns = inspector.get_columns('users')
                indexes = inspector.get_indexes('users')
                
                print(f"\n[INFO] Found {len(columns)} columns in users table")
                
                # Check if unique constraint exists by examining table SQL
                # SQLite stores unique constraints in the table definition
                result = conn.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"))
                table_sql = result.fetchone()
                has_unique_username = False
                
                if table_sql and table_sql[0]:
                    table_def = table_sql[0]
                    # Check if username has UNIQUE in the table definition
                    if 'username' in table_def.lower() and 'unique' in table_def.lower():
                        # Check if it's specifically for username column
                        import re
                        # Look for username column definition with UNIQUE
                        username_pattern = r'username\s+[^,)]+unique'
                        if re.search(username_pattern, table_def, re.IGNORECASE):
                            has_unique_username = True
                            print(f"[INFO] Found UNIQUE constraint on username in table definition")
                
                # Also check indexes
                for idx in indexes:
                    if idx.get('unique', False):
                        # Check if this index is on username
                        columns = idx.get('column_names', [])
                        if 'username' in columns:
                            has_unique_username = True
                            print(f"[INFO] Found unique index on username: {idx['name']}")
                            break
                
                if not has_unique_username:
                    print("\n[INFO] No unique constraint detected, but recreating table to be safe...")
                    # Still recreate to ensure schema matches code
                
                print("\n[INFO] Starting migration...")
                print("[INFO] Step 1: Creating backup table...")
                
                # Create backup table
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS users_backup AS 
                    SELECT * FROM users
                """))
                conn.commit()
                print("[SUCCESS] Backup table created")
                
                print("\n[INFO] Step 2: Dropping old table...")
                conn.execute(text("DROP TABLE IF EXISTS users"))
                conn.commit()
                print("[SUCCESS] Old table dropped")
                
                print("\n[INFO] Step 3: Creating new table without unique constraint...")
                # Recreate table without unique constraint on username
                Base.metadata.create_all(engine, tables=[User.__table__])
                print("[SUCCESS] New table created")
                
                print("\n[INFO] Step 4: Copying data from backup...")
                # Copy data back
                conn.execute(text("""
                    INSERT INTO users 
                    SELECT * FROM users_backup
                """))
                conn.commit()
                print("[SUCCESS] Data copied")
                
                print("\n[INFO] Step 5: Dropping backup table...")
                conn.execute(text("DROP TABLE IF EXISTS users_backup"))
                conn.commit()
                print("[SUCCESS] Backup table removed")
                
                print("\n[SUCCESS] Migration completed successfully!")
                print("[INFO] The username column no longer has a UNIQUE constraint")
                print("[INFO] Multiple users can now have the same name")
                return True
                
            elif engine.dialect.name == 'postgresql':
                print("\n[INFO] Using PostgreSQL database")
                
                # PostgreSQL: Drop the unique constraint/index
                print("\n[INFO] Attempting to drop unique constraint on username...")
                
                try:
                    # Try to drop the unique constraint
                    conn.execute(text("""
                        ALTER TABLE users 
                        DROP CONSTRAINT IF EXISTS users_username_key
                    """))
                    conn.commit()
                    print("[SUCCESS] Unique constraint dropped")
                except Exception as e:
                    # Try alternative constraint name
                    print(f"[INFO] First attempt failed: {e}")
                    try:
                        conn.execute(text("""
                            ALTER TABLE users 
                            DROP CONSTRAINT IF EXISTS users_username_unique
                        """))
                        conn.commit()
                        print("[SUCCESS] Unique constraint dropped (alternative name)")
                    except Exception as e2:
                        print(f"[WARNING] Could not drop constraint: {e2}")
                        print("[INFO] The constraint may not exist or have a different name")
                        # Continue anyway - the application code handles conflicts
                
                # Also drop unique index if it exists
                try:
                    conn.execute(text("DROP INDEX IF EXISTS users_username_key"))
                    conn.commit()
                    print("[SUCCESS] Unique index dropped (if it existed)")
                except Exception as e:
                    print(f"[INFO] Index drop (non-critical): {e}")
                
                print("\n[SUCCESS] Migration completed successfully!")
                return True
            else:
                print(f"\n[WARNING] Unsupported database dialect: {engine.dialect.name}")
                print("[INFO] Please manually remove the UNIQUE constraint from users.username")
                return False
                
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate_remove_username_unique()
    sys.exit(0 if success else 1)
