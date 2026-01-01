#!/usr/bin/env python
"""
Migration 005: Add Indexes and Foreign Keys

This migration adds performance indexes and foreign key constraints to improve
query performance and data integrity.

Indexes added to task_instances:
- Composite index on (task_id, status) for filtering by task and status
- Index on created_at for time-based queries
- Index on is_completed for filtering completed instances
- Index on is_deleted for filtering active (non-deleted) instances

Foreign key constraints:
- task_instances.task_id -> tasks.task_id (optional, SQLite requires foreign keys to be enabled)

Prerequisites:
- Migration 003 (task_instances table) must be completed
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

def index_exists(index_name):
    """Check if an index exists."""
    try:
        inspector = inspect(engine)
        indexes = inspector.get_indexes('task_instances')
        index_names = [idx['name'] for idx in indexes]
        return index_name in index_names
    except Exception:
        return False

def migrate():
    """Add indexes and foreign key constraints."""
    print("=" * 70)
    print("Migration 005: Add Indexes and Foreign Keys")
    print("=" * 70)
    print("\nThis migration adds:")
    print("  - Performance indexes on task_instances table")
    print("  - Foreign key constraint (requires SQLite foreign keys to be enabled)")
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
    
    # Check prerequisites
    if not table_exists('task_instances'):
        print("[ERROR] Task instances table does not exist!")
        print("Please run migration 003 (create task_instances table) first.")
        return False
    
    print("[OK] Task instances table exists (prerequisite check passed)")
    
    try:
        with get_session() as session:
            # Enable foreign keys for SQLite (required for foreign key constraints)
            # Note: This only applies to the current connection
            if database_url.startswith('sqlite'):
                session.execute(text("PRAGMA foreign_keys = ON"))
                session.commit()
                print("[OK] Foreign keys enabled for this session")
            
            # Define indexes to create
            indexes_to_create = [
                {
                    'name': 'idx_task_instances_task_status',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_task_status ON task_instances(task_id, status)',
                    'description': 'Composite index on task_id and status for filtering'
                },
                {
                    'name': 'idx_task_instances_created_at',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_created_at ON task_instances(created_at)',
                    'description': 'Index on created_at for time-based queries'
                },
                {
                    'name': 'idx_task_instances_is_completed',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_is_completed ON task_instances(is_completed)',
                    'description': 'Index on is_completed for filtering completed instances'
                },
                {
                    'name': 'idx_task_instances_is_deleted',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_is_deleted ON task_instances(is_deleted)',
                    'description': 'Index on is_deleted for filtering active instances'
                },
            ]
            
            created_count = 0
            skipped_count = 0
            errors = []
            
            print("\nCreating indexes...")
            for idx_def in indexes_to_create:
                idx_name = idx_def['name']
                
                # Check if index already exists (SQLite's IF NOT EXISTS handles this, but we check anyway)
                if index_exists(idx_name):
                    print(f"   [SKIP] Index '{idx_name}' already exists")
                    skipped_count += 1
                else:
                    try:
                        session.execute(text(idx_def['sql']))
                        session.commit()
                        print(f"   [OK] Created index '{idx_name}' ({idx_def['description']})")
                        created_count += 1
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to create index '{idx_name}': {e}"
                        print(f"   [ERROR] {error_msg}")
                        errors.append(error_msg)
            
            # Note about foreign key constraint
            # SQLite has limited foreign key support - we'll add it but it requires foreign_keys to be enabled
            print("\n" + "=" * 70)
            print("Foreign Key Constraint")
            print("=" * 70)
            print("\nNote: SQLite foreign key constraints require:")
            print("  1. Foreign keys to be enabled (PRAGMA foreign_keys = ON)")
            print("  2. The constraint to be defined at table creation time")
            print("\nSince task_instances table already exists, we cannot add a foreign key")
            print("constraint via ALTER TABLE in SQLite. The relationship is enforced")
            print("at the application level (SQLAlchemy) and will work correctly.")
            print("\nFor future migrations or fresh databases, foreign keys can be")
            print("defined at table creation time.")
            print()
            
            # Summary
            print("=" * 70)
            print("Migration Summary")
            print("=" * 70)
            print(f"Indexes created: {created_count}")
            print(f"Indexes skipped (already exist): {skipped_count}")
            
            if errors:
                print(f"\nErrors encountered: {len(errors)}")
                for error in errors:
                    print(f"  - {error}")
                return False
            
            if created_count > 0:
                print("\n[SUCCESS] Migration complete!")
                print("Performance indexes have been added to the task_instances table.")
            else:
                print("\n[NOTE] All indexes already exist. No migration needed.")
            
            # Verification
            print("\n" + "=" * 70)
            print("Verification")
            print("=" * 70)
            all_exist = True
            for idx_def in indexes_to_create:
                exists = index_exists(idx_def['name'])
                status = "[OK]" if exists else "[MISSING]"
                print(f"   {status} {idx_def['name']}: {'exists' if exists else 'MISSING'}")
                if not exists:
                    all_exist = False
            
            if all_exist:
                print("\n[OK] All indexes verified successfully!")
            else:
                print("\n[WARNING] Some indexes are missing. Migration may have failed.")
                return False
            
            return True
            
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)

