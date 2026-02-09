#!/usr/bin/env python
"""
Migration 011: Add user_id to Emotions Table (SQLite)

This migration adds user_id to the emotions table for data isolation.
SQLite requires recreating the table to change unique constraints.

Prerequisites:
- Migration 009 (users table) must be completed
- Migration 010 must be completed
"""
import os
import sys

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
    """Check if a column exists."""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def migrate():
    """Add user_id to emotions table for data isolation."""
    print("=" * 70)
    print("SQLite Migration 011: Add user_id to Emotions Table")
    print("=" * 70)

    if not table_exists('users') or not table_exists('emotions'):
        print("[ERROR] Prerequisites not met. Run migrations 004 and 009 first.")
        return False

    if column_exists('emotions', 'user_id'):
        print("[NOTE] user_id already exists in emotions. Skipping.")
        return True

    try:
        with get_session() as session:
            # SQLite: recreate table to add user_id and change unique constraint
            session.execute(text("PRAGMA foreign_keys = ON"))

            # Drop emotions_new if it exists from a previous failed run (idempotent)
            if table_exists('emotions_new'):
                print("[NOTE] Dropping leftover emotions_new from previous run...")
                session.execute(text("DROP TABLE emotions_new"))
                session.commit()

            # Create new table with user_id and unique(user_id, emotion)
            session.execute(text("""
                CREATE TABLE emotions_new (
                    emotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(user_id),
                    emotion VARCHAR NOT NULL,
                    UNIQUE(user_id, emotion)
                )
            """))
            session.commit()

            # Get first user_id for existing rows
            result = session.execute(text("SELECT user_id FROM users ORDER BY user_id LIMIT 1"))
            row = result.fetchone()
            default_user_id = row[0] if row else None

            # Copy data (use named params for SQLAlchemy 2.0 compatibility)
            if default_user_id is not None:
                session.execute(
                    text(
                        "INSERT INTO emotions_new (emotion_id, user_id, emotion) "
                        "SELECT emotion_id, :uid, emotion FROM emotions"
                    ),
                    {"uid": default_user_id},
                )
            else:
                # No users yet - insert with NULL (or skip)
                session.execute(text(
                    "INSERT INTO emotions_new (emotion_id, user_id, emotion) "
                    "SELECT emotion_id, NULL, emotion FROM emotions"
                ))
            session.commit()

            # Drop old, rename new
            session.execute(text("DROP TABLE emotions"))
            session.execute(text("ALTER TABLE emotions_new RENAME TO emotions"))

            # Add index
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_emotions_user_id ON emotions(user_id)"))
            session.commit()

        print("[OK] Migration 011 complete. Emotions now have user_id for data isolation.")
        return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
