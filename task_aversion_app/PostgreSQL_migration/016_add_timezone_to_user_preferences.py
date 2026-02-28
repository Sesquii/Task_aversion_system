#!/usr/bin/env python3
"""
PostgreSQL Migration 016: Add timezone and detected_tz to user_preferences

Adds columns for per-user timezone setting and browser-detected timezone.
Run after 007 (user_preferences table exists).
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
        if not column_exists("user_preferences", "timezone"):
            conn.execute(text("ALTER TABLE user_preferences ADD COLUMN timezone VARCHAR(64)"))
            conn.commit()
            print("[OK] Added user_preferences.timezone")
        else:
            print("[OK] user_preferences.timezone already exists")
        if not column_exists("user_preferences", "detected_tz"):
            conn.execute(text("ALTER TABLE user_preferences ADD COLUMN detected_tz VARCHAR(64)"))
            conn.commit()
            print("[OK] Added user_preferences.detected_tz")
        else:
            print("[OK] user_preferences.detected_tz already exists")
    return True


if __name__ == "__main__":
    migrate()
