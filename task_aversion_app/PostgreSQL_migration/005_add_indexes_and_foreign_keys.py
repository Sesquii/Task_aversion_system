#!/usr/bin/env python3
"""
PostgreSQL Migration 005: Add Indexes and Foreign Keys

This migration adds performance indexes and foreign key constraints to improve
query performance and data integrity.

Indexes added to task_instances:
- Composite index on (task_id, status) for filtering by task and status
- Index on created_at for time-based queries
- Index on is_completed for filtering completed instances
- Index on is_deleted for filtering active (non-deleted) instances
- GIN index on JSONB columns (predicted, actual) for efficient JSON queries

Foreign key constraints:
- task_instances.task_id -> tasks.task_id (enforced at database level in PostgreSQL)

PostgreSQL-specific features:
- GIN indexes on JSONB columns for efficient JSON queries
- Proper foreign key constraints (PostgreSQL enforces these)
- CREATE INDEX IF NOT EXISTS (PostgreSQL 9.5+)

Prerequisites:
- Migration 003 (task_instances table) must be completed
- DATABASE_URL environment variable must be set to PostgreSQL connection string
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

def index_exists(index_name, table_name='task_instances'):
    """Check if an index exists."""
    try:
        inspector = inspect(engine)
        indexes = inspector.get_indexes(table_name)
        index_names = [idx['name'] for idx in indexes]
        return index_name in index_names
    except Exception:
        return False

def foreign_key_exists(table_name, constraint_name):
    """Check if a foreign key constraint exists."""
    try:
        inspector = inspect(engine)
        foreign_keys = inspector.get_foreign_keys(table_name)
        fk_names = [fk['name'] for fk in foreign_keys]
        return constraint_name in fk_names
    except Exception:
        return False

def migrate():
    """Add indexes and foreign key constraints."""
    print("=" * 70)
    print("PostgreSQL Migration 005: Add Indexes and Foreign Keys")
    print("=" * 70)
    print("\nThis migration adds:")
    print("  - Performance indexes on task_instances table")
    print("  - GIN indexes on JSONB columns for efficient JSON queries")
    print("  - Foreign key constraint (PostgreSQL enforces these)")
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
    
    # Check prerequisites
    if not table_exists('task_instances'):
        print("[ERROR] Task instances table does not exist!")
        print("Please run migration 003 (create task_instances table) first.")
        return False
    
    if not table_exists('tasks'):
        print("[ERROR] Tasks table does not exist!")
        print("Please run migration 001 (initial schema) first.")
        return False
    
    print("[OK] Task instances table exists (prerequisite check passed)")
    print("[OK] Tasks table exists (prerequisite check passed)")
    
    try:
        with get_session() as session:
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
                {
                    'name': 'idx_task_instances_predicted_gin',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_predicted_gin ON task_instances USING GIN (predicted)',
                    'description': 'GIN index on predicted JSONB column for efficient JSON queries'
                },
                {
                    'name': 'idx_task_instances_actual_gin',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_actual_gin ON task_instances USING GIN (actual)',
                    'description': 'GIN index on actual JSONB column for efficient JSON queries'
                },
            ]
            
            created_count = 0
            skipped_count = 0
            errors = []
            
            print("\nCreating indexes...")
            for idx_def in indexes_to_create:
                idx_name = idx_def['name']
                
                # Check if index already exists (PostgreSQL's IF NOT EXISTS handles this, but we check anyway)
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
            
            # Add foreign key constraint (PostgreSQL-specific - enforces referential integrity)
            print("\n" + "=" * 70)
            print("Foreign Key Constraint")
            print("=" * 70)
            print("\nAdding foreign key constraint: task_instances.task_id -> tasks.task_id")
            print("PostgreSQL will enforce this constraint at the database level.")
            
            fk_name = 'fk_task_instances_task_id'
            
            # Check if foreign key already exists
            inspector = inspect(engine)
            existing_fks = inspector.get_foreign_keys('task_instances')
            fk_exists = any(
                fk['constrained_columns'] == ['task_id'] and 
                fk['referred_table'] == 'tasks' and 
                fk['referred_columns'] == ['task_id']
                for fk in existing_fks
            )
            
            if fk_exists:
                print(f"   [SKIP] Foreign key constraint already exists")
            else:
                try:
                    # Add foreign key constraint
                    fk_sql = """
                    ALTER TABLE task_instances 
                    ADD CONSTRAINT fk_task_instances_task_id 
                    FOREIGN KEY (task_id) 
                    REFERENCES tasks(task_id) 
                    ON DELETE RESTRICT
                    """
                    session.execute(text(fk_sql))
                    session.commit()
                    print(f"   [OK] Added foreign key constraint '{fk_name}'")
                    print("       This ensures referential integrity at the database level.")
                except Exception as e:
                    session.rollback()
                    error_msg = f"Failed to add foreign key constraint: {e}"
                    print(f"   [WARNING] {error_msg}")
                    print("       Foreign key constraint is optional. Continuing...")
                    # Don't fail the migration if FK constraint fails (may have data issues)
            
            # Summary
            print("\n" + "=" * 70)
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
                print("JSONB columns now have GIN indexes for efficient JSON queries.")
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
