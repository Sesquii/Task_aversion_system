#!/usr/bin/env python3
"""
PostgreSQL Migration 018: Add hour12 to user_preferences

Adds column for 12/24-hour clock preference (from browser Intl).
Run after 016 (timezone columns exist).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from backend.database import engine


def column_exists(table: str, column: str) -> bool:
    try:
        inspector = inspect(engine)
        cols = [c["name"] for c in inspector.get_columns(table)]
        return column in cols
    except Exception:
        return False


def migrate():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[SKIP] DATABASE_URL not set or not PostgreSQL")
        return True

    with engine.connect() as conn:
        if not column_exists("user_preferences", "hour12"):
            conn.execute(text("ALTER TABLE user_preferences ADD COLUMN hour12 BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("[OK] Added user_preferences.hour12")
        else:
            print("[OK] user_preferences.hour12 already exists")
    return True


if __name__ == "__main__":
    migrate()
