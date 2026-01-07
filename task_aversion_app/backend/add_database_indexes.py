#!/usr/bin/env python3
"""
Script to add database indexes to existing databases.

This script adds indexes that were added to the models but may not exist
in databases created before the indexes were added.

Run this once after updating the database models with new indexes.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, Base, Task, TaskInstance
from sqlalchemy import Index, text


def add_indexes():
    """Add indexes to existing database if they don't exist."""
    print("[Add Indexes] Starting index creation...")
    
    try:
        with engine.connect() as conn:
            # Check if indexes already exist and create if needed
            # SQLite syntax for creating indexes
            indexes_to_create = [
                # TaskInstance indexes
                ("idx_taskinstance_status_completed", 
                 "CREATE INDEX IF NOT EXISTS idx_taskinstance_status_completed ON task_instances (status, is_completed, is_deleted)"),
                ("idx_taskinstance_task_completed",
                 "CREATE INDEX IF NOT EXISTS idx_taskinstance_task_completed ON task_instances (task_id, is_completed)"),
                # Note: completed_at index is already created via Column definition
                # Note: task_id, created_at, is_completed, is_deleted, status indexes are already created via Column definitions
                
                # Task indexes
                # Note: created_at and task_type indexes are already created via Column definitions
            ]
            
            for index_name, create_sql in indexes_to_create:
                try:
                    conn.execute(text(create_sql))
                    conn.commit()
                    print(f"[Add Indexes] Created index: {index_name}")
                except Exception as e:
                    print(f"[Add Indexes] Warning: Could not create index {index_name}: {e}")
                    # Continue with other indexes
        
        print("[Add Indexes] Index creation complete!")
        print("[Add Indexes] Note: Some indexes may already exist (created via Column definitions)")
        print("[Add Indexes] This is safe - SQLite will skip creating duplicates")
        
    except Exception as e:
        print(f"[Add Indexes] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    success = add_indexes()
    sys.exit(0 if success else 1)
