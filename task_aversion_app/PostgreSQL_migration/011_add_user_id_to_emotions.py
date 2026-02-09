#!/usr/bin/env python3
"""
PostgreSQL Migration 011: Add user_id to Emotions Table

This migration adds user_id to the emotions table for data isolation.
Each user has their own emotion vocabulary.

Steps:
1. Add user_id column (nullable initially)
2. Assign existing rows to first user (for migration compatibility)
3. Drop old unique constraint on emotion
4. Add unique constraint on (user_id, emotion)
5. Add index on user_id
6. Optionally set user_id NOT NULL (after data migration)

Prerequisites:
- Migration 009 (users table) must be completed
- Migration 010 (user_id on other tables) must be completed
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


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def get_unique_constraint_name(table_name, column_names):
    """Get the name of a unique constraint covering given columns."""
    try:
        inspector = inspect(engine)
        for constraint in inspector.get_unique_constraints(table_name):
            if set(constraint['column_names']) == set(column_names):
                return constraint.get('name')
    except Exception:
        pass
    return None


def migrate():
    """Add user_id to emotions table for data isolation."""
    print("=" * 70)
    print("PostgreSQL Migration 011: Add user_id to Emotions Table")
    print("=" * 70)
    print("\nThis migration adds user_id to emotions for per-user data isolation.")
    print()

    # Check DATABASE_URL
    database_url = os.getenv('DATABASE_URL', '')
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set!")
        return False

    if not database_url.startswith('postgresql'):
        print("[ERROR] This migration is designed for PostgreSQL only.")
        return False

    # Check prerequisites
    if not table_exists('users'):
        print("[ERROR] Users table does not exist! Run migration 009 first.")
        return False
    if not table_exists('emotions'):
        print("[ERROR] Emotions table does not exist! Run migration 004 first.")
        return False

    print("[OK] Prerequisites check passed")

    try:
        with get_session() as session:
            # Step 1: Add user_id column if not exists
            if column_exists('emotions', 'user_id'):
                print("[NOTE] user_id column already exists in emotions table.")
            else:
                print("\nStep 1: Adding user_id column...")
                session.execute(text(
                    'ALTER TABLE emotions ADD COLUMN user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE'
                ))
                session.commit()
                print("[OK] Added user_id column")

            # Step 2: Assign existing rows with NULL user_id to first user
            print("\nStep 2: Assigning existing emotions to first user...")
            result = session.execute(text(
                "UPDATE emotions SET user_id = (SELECT user_id FROM users ORDER BY user_id LIMIT 1) WHERE user_id IS NULL"
            ))
            session.commit()
            rows_updated = result.rowcount
            if rows_updated > 0:
                print(f"[OK] Assigned {rows_updated} emotion(s) to first user")
            else:
                print("[OK] No rows needed assignment (or table was empty)")

            # Step 3: Drop old unique constraint on emotion (if exists)
            print("\nStep 3: Updating unique constraint...")
            old_constraint = get_unique_constraint_name('emotions', ['emotion'])
            if old_constraint:
                try:
                    session.execute(text(f'ALTER TABLE emotions DROP CONSTRAINT IF EXISTS "{old_constraint}"'))
                    session.commit()
                    print(f"[OK] Dropped old unique constraint on emotion")
                except Exception as e:
                    session.rollback()
                    # Try PostgreSQL default naming
                    session.execute(text('ALTER TABLE emotions DROP CONSTRAINT IF EXISTS emotions_emotion_key'))
                    session.commit()
                    print("[OK] Dropped old unique constraint (emotions_emotion_key)")
            else:
                print("[NOTE] No old unique constraint on emotion found")

            # Step 4: Add unique constraint on (user_id, emotion)
            try:
                session.execute(text(
                    'ALTER TABLE emotions ADD CONSTRAINT uq_emotions_user_emotion UNIQUE (user_id, emotion)'
                ))
                session.commit()
                print("[OK] Added unique constraint on (user_id, emotion)")
            except Exception as e:
                session.rollback()
                if 'already exists' in str(e).lower():
                    print("[NOTE] Unique constraint uq_emotions_user_emotion already exists")
                else:
                    raise

            # Step 5: Add index on user_id
            try:
                session.execute(text('CREATE INDEX IF NOT EXISTS idx_emotions_user_id ON emotions(user_id)'))
                session.commit()
                print("[OK] Added index on user_id")
            except Exception as e:
                session.rollback()
                if 'already exists' in str(e).lower():
                    print("[NOTE] Index idx_emotions_user_id already exists")
                else:
                    raise

        print("\n[SUCCESS] Migration 011 complete!")
        print("Emotions table now supports per-user data isolation.")
        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
