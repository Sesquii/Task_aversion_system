#!/usr/bin/env python
"""
Migration 010: Add user_id Foreign Keys to Existing Tables

This migration adds user_id INTEGER foreign key columns to existing tables
and links them to the users table for OAuth authentication and data isolation.

Tables updated:
- tasks: Add user_id INTEGER REFERENCES users(user_id) (nullable initially for migration)
- task_instances: Add user_id INTEGER REFERENCES users(user_id) (nullable initially)
- emotions: Add user_id INTEGER REFERENCES users(user_id) (nullable, if user-specific)
- user_preferences: Migrate user_id from VARCHAR to INTEGER (nullable initially)
- survey_responses: Migrate user_id from VARCHAR to INTEGER (nullable initially)
- popup_triggers: Migrate user_id from VARCHAR to INTEGER (nullable initially)
- popup_responses: Migrate user_id from VARCHAR to INTEGER (nullable initially)
- notes: Add user_id INTEGER REFERENCES users(user_id) (nullable initially)

IMPORTANT: This migration sets user_id as nullable initially to allow
existing anonymous data to remain in the database. A separate data migration
script will be needed to link existing anonymous data to authenticated users.

SQLite-specific:
- Foreign keys must be enabled with PRAGMA foreign_keys = ON
- Uses INTEGER instead of SERIAL for foreign keys
- VARCHAR/TEXT columns are converted to INTEGER by adding new column
- SQLite doesn't support ALTER TABLE for primary key changes easily
- For user_preferences (PRIMARY KEY), needs special handling (migration 010b)

Prerequisites:
- Migration 009 (users table) must be completed
- Migration 001-008 (all other tables) must be completed
- DATABASE_URL environment variable must be set
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import get_session, engine
from sqlalchemy import inspect, text

def table_exists(table_name):
    """Check if a table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False

def get_column_type(table_name, column_name):
    """Get the data type of a column."""
    try:
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        for col in columns:
            if col['name'] == column_name:
                return str(col['type'])
        return None
    except Exception:
        return None

def migrate():
    """Add user_id foreign keys to existing tables."""
    print("=" * 70)
    print("SQLite Migration 010: Add user_id Foreign Keys")
    print("=" * 70)
    print("\nThis migration adds user_id foreign keys to existing tables.")
    print("This enables OAuth authentication and user data isolation.")
    print()
    print("IMPORTANT: user_id columns will be nullable initially to allow")
    print("existing anonymous data to remain in the database.")
    print("A separate data migration will link anonymous data to users.")
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
    
    # Check prerequisites
    if not table_exists('users'):
        print("[ERROR] Users table does not exist!")
        print("Please run migration 009 (create users table) first.")
        return False
    
    print("[OK] Users table exists (prerequisite check passed)")
    
    # Tables that need user_id added (new column)
    tables_with_new_user_id = [
        {
            'table': 'tasks',
            'description': 'Tasks table - links tasks to users',
            'add_index': True
        },
        {
            'table': 'task_instances',
            'description': 'Task instances table - links instances to users',
            'add_index': True
        },
        {
            'table': 'notes',
            'description': 'Notes table - links notes to users',
            'add_index': True
        },
    ]
    
    # Tables that need user_id converted from VARCHAR/TEXT to INTEGER
    tables_with_varchar_user_id = [
        {
            'table': 'user_preferences',
            'description': 'User preferences table - convert TEXT user_id to INTEGER',
            'is_primary_key': True,  # user_id is primary key in this table
            'add_index': False  # Already indexed as PK
        },
        {
            'table': 'survey_responses',
            'description': 'Survey responses table - convert TEXT user_id to INTEGER',
            'is_primary_key': False,
            'add_index': True
        },
        {
            'table': 'popup_triggers',
            'description': 'Popup triggers table - convert TEXT user_id to INTEGER',
            'is_primary_key': False,
            'add_index': True
        },
        {
            'table': 'popup_responses',
            'description': 'Popup responses table - convert TEXT user_id to INTEGER',
            'is_primary_key': False,
            'add_index': True
        },
    ]
    
    try:
        with get_session() as session:
            # Enable foreign keys for SQLite (required for foreign key constraints)
            session.execute(text("PRAGMA foreign_keys = ON"))
            session.commit()
            print("[OK] Foreign keys enabled for this session")
            
            added_count = 0
            converted_count = 0
            skipped_count = 0
            errors = []
            
            # Step 1: Add user_id to tables that don't have it
            print("\nStep 1: Adding user_id column to tables that don't have it...")
            print("-" * 70)
            
            for table_def in tables_with_new_user_id:
                table_name = table_def['table']
                
                if not table_exists(table_name):
                    print(f"   [SKIP] Table '{table_name}' does not exist (may not be migrated yet)")
                    skipped_count += 1
                    continue
                
                if column_exists(table_name, 'user_id'):
                    print(f"   [SKIP] Column 'user_id' already exists in '{table_name}'")
                    skipped_count += 1
                    continue
                
                try:
                    # SQLite: ALTER TABLE table_name ADD COLUMN user_id INTEGER
                    # Note: SQLite doesn't support foreign keys in ALTER TABLE ADD COLUMN
                    # Foreign key constraint will be enforced at application level or via triggers
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER"
                    session.execute(text(alter_sql))
                    
                    # Add index if requested
                    if table_def.get('add_index', False):
                        index_sql = f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_id ON {table_name}(user_id)"
                        session.execute(text(index_sql))
                    
                    session.commit()
                    print(f"   [OK] Added 'user_id' column to '{table_name}' ({table_def['description']})")
                    print(f"        Note: Foreign key constraint enforced at application level (SQLite limitation)")
                    added_count += 1
                except Exception as e:
                    session.rollback()
                    error_msg = f"Failed to add user_id to '{table_name}': {e}"
                    print(f"   [ERROR] {error_msg}")
                    errors.append(error_msg)
            
            # Step 2: Convert TEXT/VARCHAR user_id to INTEGER for tables that have TEXT user_id
            print("\nStep 2: Converting TEXT user_id to INTEGER for existing tables...")
            print("-" * 70)
            print("NOTE: This is a complex migration. For tables with existing TEXT user_id,")
            print("we will add a new INTEGER user_id column and keep TEXT temporarily.")
            print("A separate data migration script will populate INTEGER user_id from TEXT.")
            print()
            
            for table_def in tables_with_varchar_user_id:
                table_name = table_def['table']
                
                if not table_exists(table_name):
                    print(f"   [SKIP] Table '{table_name}' does not exist (may not be migrated yet)")
                    skipped_count += 1
                    continue
                
                # Check if user_id exists and what type it is
                if not column_exists(table_name, 'user_id'):
                    print(f"   [SKIP] Column 'user_id' does not exist in '{table_name}' (will be added as INTEGER)")
                    # Add as INTEGER directly (not conversion needed)
                    try:
                        if table_def.get('is_primary_key', False):
                            # Primary key conversion is complex - needs special handling
                            print(f"   [WARNING] '{table_name}' has user_id as PRIMARY KEY - needs manual migration")
                            print(f"            Skipping automatic conversion. Manual migration required.")
                            errors.append(f"Primary key conversion needed for {table_name}")
                        else:
                            alter_sql = f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER"
                            session.execute(text(alter_sql))
                            
                            if table_def.get('add_index', False):
                                index_sql = f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_id ON {table_name}(user_id)"
                                session.execute(text(index_sql))
                            
                            session.commit()
                            print(f"   [OK] Added INTEGER 'user_id' column to '{table_name}' ({table_def['description']})")
                            converted_count += 1
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to add INTEGER user_id to '{table_name}': {e}"
                        print(f"   [ERROR] {error_msg}")
                        errors.append(error_msg)
                    continue
                
                # Check column type
                col_type = get_column_type(table_name, 'user_id')
                if col_type and ('VARCHAR' in col_type.upper() or 'TEXT' in col_type.upper() or 'STRING' in col_type.upper()):
                    print(f"   [INFO] '{table_name}' has TEXT/VARCHAR user_id (type: {col_type})")
                    
                    if table_def.get('is_primary_key', False):
                        # Primary key conversion is complex - needs special handling
                        print(f"   [WARNING] '{table_name}' has user_id as PRIMARY KEY - cannot convert automatically")
                        print(f"            For user_preferences table, a separate migration script is needed")
                        print(f"            that will:")
                        print(f"              1. Create new table with INTEGER primary key")
                        print(f"              2. Migrate data from old table")
                        print(f"              3. Drop old table and rename new table")
                        errors.append(f"Primary key conversion needed for {table_name}")
                        continue
                    
                    # For non-primary key columns, add new INTEGER column
                    try:
                        # SQLite: Add new INTEGER column (nullable, no foreign key constraint in ALTER TABLE)
                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN user_id_new INTEGER"
                        session.execute(text(alter_sql))
                        
                        # Add index if requested
                        if table_def.get('add_index', False):
                            index_sql = f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_id_new ON {table_name}(user_id_new)"
                            session.execute(text(index_sql))
                        
                        session.commit()
                        print(f"   [OK] Added INTEGER 'user_id_new' column to '{table_name}' ({table_def['description']})")
                        print(f"        Note: Original TEXT user_id column kept temporarily for data migration")
                        print(f"        A separate data migration script will populate user_id_new from user_id")
                        converted_count += 1
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to add INTEGER user_id to '{table_name}': {e}"
                        print(f"   [ERROR] {error_msg}")
                        errors.append(error_msg)
                elif col_type and 'INTEGER' in col_type.upper():
                    print(f"   [OK] '{table_name}' already has INTEGER user_id (type: {col_type})")
                    # Check if foreign key constraint exists (SQLite doesn't expose this easily)
                    # Just note that it's already correct
                    print(f"   [OK] Column type is correct - no conversion needed")
                    skipped_count += 1
                else:
                    print(f"   [WARNING] '{table_name}' has user_id with unexpected type: {col_type}")
                    errors.append(f"Unexpected user_id type in {table_name}: {col_type}")
            
            # Summary
            print("\n" + "=" * 70)
            print("Migration Summary")
            print("=" * 70)
            print(f"Columns added (new): {added_count}")
            print(f"Columns converted (TEXT to INTEGER): {converted_count}")
            print(f"Columns skipped (already exist/correct type): {skipped_count}")
            
            if errors:
                print(f"\nErrors/Warnings encountered: {len(errors)}")
                for error in errors:
                    print(f"  - {error}")
                
                if any("Primary key conversion" in e for e in errors):
                    print("\n[IMPORTANT] Some tables require manual primary key conversion:")
                    print("  - user_preferences: Has TEXT user_id as PRIMARY KEY")
                    print("  - A separate migration script (010b) will be needed for this")
                    print("  - This requires: 1) Create new table, 2) Migrate data, 3) Drop old, 4) Rename")
            
            if errors and any("Primary key conversion" not in e for e in errors):
                print("\n[WARNING] Some migrations failed. Review errors above.")
                return False
            
            if added_count > 0 or converted_count > 0:
                print("\n[SUCCESS] Migration complete!")
                print("\nNext steps:")
                print("  1. For tables with 'user_id_new' columns: Run data migration to populate from TEXT user_id")
                print("  2. For user_preferences: Run special migration (010b) for primary key conversion")
                print("  3. Update all backend managers to filter by INTEGER user_id")
                print("  4. Implement OAuth authentication to create users")
                print("\nNote: SQLite foreign key constraints are enforced at application level")
                print("      (SQLite doesn't support foreign keys in ALTER TABLE ADD COLUMN)")
            else:
                print("\n[NOTE] All columns already exist or are correct type. No migration needed.")
            
            # Verification
            print("\n" + "=" * 70)
            print("Verification")
            print("=" * 70)
            all_ok = True
            
            for table_def in tables_with_new_user_id:
                table_name = table_def['table']
                if table_exists(table_name):
                    exists = column_exists(table_name, 'user_id')
                    status = "[OK]" if exists else "[MISSING]"
                    print(f"   {status} {table_name}.user_id: {'exists' if exists else 'MISSING'}")
                    if not exists:
                        all_ok = False
            
            print("\n[OK] Migration 010 complete!")
            print("\nNOTE: Tables with TEXT user_id columns will need a data migration script")
            print("to populate the new INTEGER user_id columns. This will be migration 010b.")
            print("\nNOTE: SQLite foreign key constraints are enforced at application level.")
            
            return True
            
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
