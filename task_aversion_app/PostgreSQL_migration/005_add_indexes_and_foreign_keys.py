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
            # Check all JSON columns in task_instances and tasks tables - convert to JSONB if needed
            # GIN indexes only work on JSONB, and JSONB provides better performance even without indexes
            print("\nChecking JSON column types (converting to JSONB for optimal performance)...")
            inspector = inspect(engine)
            
            # Check task_instances table
            task_instances_columns = inspector.get_columns('task_instances')
            task_instances_types = {col['name']: str(col['type']) for col in task_instances_columns}
            
            # Check tasks table (if it exists)
            tasks_types = {}
            if 'tasks' in inspector.get_table_names():
                tasks_columns = inspector.get_columns('tasks')
                tasks_types = {col['name']: str(col['type']) for col in tasks_columns}
            
            # List of columns to check and convert (table_name: [column_names])
            columns_to_check = {
                'task_instances': ['predicted', 'actual'],
                'tasks': ['categories', 'routine_days_of_week']
            }
            
            all_column_types = {}  # Will store (table, column): type mapping
            needs_conversion = False
            
            for table_name, column_names in columns_to_check.items():
                if table_name == 'task_instances':
                    current_types = task_instances_types
                elif table_name == 'tasks':
                    current_types = tasks_types
                else:
                    continue
                
                for col_name in column_names:
                    if col_name in current_types:
                        col_type = current_types[col_name]
                        all_column_types[(table_name, col_name)] = col_type
                        if 'JSONB' not in col_type.upper():
                            print(f"   [WARNING] {table_name}.{col_name} is {col_type}, not JSONB")
                            print("   JSONB provides better performance - will convert...")
                            needs_conversion = True
                        else:
                            print(f"   [OK] {table_name}.{col_name} is already JSONB")
            
            # Convert JSON to JSONB if needed (for PostgreSQL)
            # This improves performance and enables GIN indexes
            if needs_conversion:
                print("\nConverting JSON columns to JSONB (better performance, enables GIN indexes)...")
                conversion_errors = []
                
                for (table_name, col_name), col_type in all_column_types.items():
                    if 'JSONB' not in col_type.upper():
                        try:
                            print(f"   Converting {table_name}.{col_name} to JSONB...")
                            session.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} TYPE JSONB USING {col_name}::JSONB"))
                            session.commit()
                            print(f"   [OK] {table_name}.{col_name} converted to JSONB")
                            # Update type after conversion
                            all_column_types[(table_name, col_name)] = 'JSONB'
                        except Exception as e:
                            session.rollback()
                            error_msg = f"Failed to convert {table_name}.{col_name}: {e}"
                            print(f"   [ERROR] {error_msg}")
                            conversion_errors.append(error_msg)
                
                if conversion_errors:
                    print(f"\n   [WARNING] {len(conversion_errors)} conversion(s) failed:")
                    for error in conversion_errors:
                        print(f"     - {error}")
                    print("   GIN indexes for these columns will be skipped, but other indexes will still be created")
                else:
                    print("\n[OK] All JSON → JSONB conversions complete. GIN indexes can now be created.")
            
            # Define indexes to create (standard indexes)
            indexes_to_create = [
                {
                    'name': 'idx_task_instances_task_status',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_task_status ON task_instances(task_id, status)',
                    'description': 'Composite index on task_id and status for filtering',
                    'table': 'task_instances'
                },
                {
                    'name': 'idx_task_instances_created_at',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_created_at ON task_instances(created_at)',
                    'description': 'Index on created_at for time-based queries',
                    'table': 'task_instances'
                },
                {
                    'name': 'idx_task_instances_is_completed',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_is_completed ON task_instances(is_completed)',
                    'description': 'Index on is_completed for filtering completed instances',
                    'table': 'task_instances'
                },
                {
                    'name': 'idx_task_instances_is_deleted',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_is_deleted ON task_instances(is_deleted)',
                    'description': 'Index on is_deleted for filtering active instances',
                    'table': 'task_instances'
                },
                {
                    'name': 'idx_task_instances_predicted_gin',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_predicted_gin ON task_instances USING GIN (predicted)',
                    'description': 'GIN index on predicted JSONB column for efficient JSON queries',
                    'requires_jsonb': True,
                    'table': 'task_instances',
                    'column': 'predicted'
                },
                {
                    'name': 'idx_task_instances_actual_gin',
                    'sql': 'CREATE INDEX IF NOT EXISTS idx_task_instances_actual_gin ON task_instances USING GIN (actual)',
                    'description': 'GIN index on actual JSONB column for efficient JSON queries',
                    'requires_jsonb': True,
                    'table': 'task_instances',
                    'column': 'actual'
                },
            ]
            
            # Optional: Add GIN indexes for tasks table JSON columns (if tasks table exists and columns are JSONB)
            # Re-inspect columns after conversion to get latest types
            if 'tasks' in inspector.get_table_names():
                print("\nChecking tasks table JSON columns for optional GIN indexes...")
                
                # Re-inspect to get latest column types (after any conversions)
                try:
                    tasks_columns_updated = inspector.get_columns('tasks')
                    tasks_types_updated = {col['name']: str(col['type']) for col in tasks_columns_updated}
                    
                    # Update all_column_types with latest types
                    for col_name in ['categories', 'routine_days_of_week']:
                        if col_name in tasks_types_updated:
                            all_column_types[('tasks', col_name)] = tasks_types_updated[col_name]
                except Exception as e:
                    print(f"   [WARNING] Could not re-inspect tasks table: {e}")
                
                tasks_gin_indexes = [
                    {
                        'name': 'idx_tasks_categories_gin',
                        'sql': 'CREATE INDEX IF NOT EXISTS idx_tasks_categories_gin ON tasks USING GIN (categories)',
                        'description': 'GIN index on categories JSONB column for efficient category filtering (optional)',
                        'requires_jsonb': True,
                        'table': 'tasks',
                        'column': 'categories',
                        'optional': True  # Mark as optional - don't fail if can't create
                    },
                    {
                        'name': 'idx_tasks_routine_days_gin',
                        'sql': 'CREATE INDEX IF NOT EXISTS idx_tasks_routine_days_gin ON tasks USING GIN (routine_days_of_week)',
                        'description': 'GIN index on routine_days_of_week JSONB column for efficient routine scheduling (optional)',
                        'requires_jsonb': True,
                        'table': 'tasks',
                        'column': 'routine_days_of_week',
                        'optional': True  # Mark as optional - don't fail if can't create
                    },
                ]
                
                # Check if tasks JSON columns are JSONB before adding indexes
                for idx_def in tasks_gin_indexes:
                    col_name = idx_def['column']
                    if ('tasks', col_name) in all_column_types:
                        col_type = all_column_types[('tasks', col_name)]
                        if 'JSONB' in col_type.upper():
                            indexes_to_create.append(idx_def)
                            print(f"   [INFO] Will create optional GIN index on tasks.{col_name} for future-proofing")
                        else:
                            print(f"   [SKIP] Skipping optional GIN index on tasks.{col_name} (not JSONB - type: {col_type})")
                    else:
                        print(f"   [SKIP] Skipping optional GIN index on tasks.{col_name} (column not found - may not exist yet)")
            
            created_count = 0
            skipped_count = 0
            errors = []
            
            print("\nCreating indexes...")
            for idx_def in indexes_to_create:
                idx_name = idx_def['name']
                idx_table = idx_def.get('table', 'task_instances')

                # Check if index already exists (PostgreSQL's IF NOT EXISTS handles this, but we check anyway)
                if index_exists(idx_name, idx_table):
                    print(f"   [SKIP] Index '{idx_name}' already exists")
                    skipped_count += 1
                else:
                    # For GIN indexes, verify columns are JSONB (not JSON)
                    if idx_def.get('requires_jsonb', False):
                        table_name = idx_def.get('table', 'task_instances')
                        column_name = idx_def.get('column')
                        
                        # Fallback: Determine from index name if column not specified
                        if not column_name:
                            if 'predicted' in idx_name:
                                column_name = 'predicted'
                            elif 'actual' in idx_name:
                                column_name = 'actual'
                            elif 'categories' in idx_name:
                                column_name = 'categories'
                                table_name = 'tasks'
                            elif 'routine_days' in idx_name:
                                column_name = 'routine_days_of_week'
                                table_name = 'tasks'
                        
                        if table_name and column_name and (table_name, column_name) in all_column_types:
                            col_type = all_column_types[(table_name, column_name)]
                            if 'JSONB' not in col_type.upper():
                                error_msg = f"Cannot create GIN index '{idx_name}': {table_name}.{column_name} is not JSONB (it's {col_type})"
                                print(f"   [ERROR] {error_msg}")
                                print(f"   [INFO] The conversion step above should have fixed this, but it may have failed")
                                errors.append(error_msg)
                                continue
                    
                    try:
                        session.execute(text(idx_def['sql']))
                        session.commit()
                        print(f"   [OK] Created index '{idx_name}' ({idx_def['description']})")
                        created_count += 1
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to create index '{idx_name}': {e}"
                        
                        # If this is an optional index, warn but don't add to errors
                        if idx_def.get('optional', False):
                            print(f"   [WARNING] Optional index '{idx_name}' could not be created: {e}")
                            print(f"   [INFO] This is optional and won't block the migration. Index can be created later if needed.")
                            skipped_count += 1  # Count as skipped, not error
                        else:
                            print(f"   [ERROR] {error_msg}")
                            
                            # Helpful error message for GIN index failures
                            if idx_def.get('requires_jsonb', False) and 'gin' in error_msg.lower():
                                print(f"   [INFO] GIN indexes require JSONB columns. Make sure columns are JSONB type.")
                                print(f"   [INFO] If columns are JSON (not JSONB), they should have been converted above.")
                            
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
            
            # Verification (only check required indexes - optional indexes are allowed to be missing)
            print("\n" + "=" * 70)
            print("Verification")
            print("=" * 70)
            required_exist = True
            optional_count = 0
            optional_exist_count = 0
            
            for idx_def in indexes_to_create:
                is_optional = idx_def.get('optional', False)
                idx_table = idx_def.get('table', 'task_instances')
                exists = index_exists(idx_def['name'], idx_table)
                
                if is_optional:
                    # Optional indexes - just track for info, don't fail on these
                    optional_count += 1
                    if exists:
                        optional_exist_count += 1
                        status = "[OK]"
                        print(f"   {status} {idx_def['name']} (optional): exists")
                    else:
                        status = "[OPTIONAL]"
                        print(f"   {status} {idx_def['name']} (optional): not created (can be added later)")
                else:
                    # Required indexes - these must exist
                    status = "[OK]" if exists else "[MISSING]"
                    print(f"   {status} {idx_def['name']}: {'exists' if exists else 'MISSING'}")
                    if not exists:
                        required_exist = False
            
            # Summary
            if optional_count > 0:
                print(f"\n   Optional indexes: {optional_exist_count}/{optional_count} created")
                print("   (Optional indexes are nice-to-have but not required)")
            
            if required_exist:
                print("\n[OK] All required indexes verified successfully!")
                if optional_count > 0 and optional_exist_count < optional_count:
                    print(f"[INFO] {optional_count - optional_exist_count} optional index(es) were not created but this is acceptable.")
            else:
                print("\n[ERROR] Some required indexes are missing. Migration failed.")
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
