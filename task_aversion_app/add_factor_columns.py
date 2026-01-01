#!/usr/bin/env python
"""
Add serendipity_factor and disappointment_factor columns to the task_instances table.
This is a one-time schema migration.
"""
import os
import sys

# Set DATABASE_URL
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///data/task_aversion.db')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import engine, init_db

print("=" * 70)
print("Adding Factor Columns to Database")
print("=" * 70)

# Check if columns already exist
from sqlalchemy import inspect, text

inspector = inspect(engine)
columns = [col['name'] for col in inspector.get_columns('task_instances')]

print(f"\nExisting columns: {', '.join(columns)}")

needs_serendipity = 'serendipity_factor' not in columns
needs_disappointment = 'disappointment_factor' not in columns

if not needs_serendipity and not needs_disappointment:
    print("\n[INFO] Columns already exist. No migration needed.")
    sys.exit(0)

# Add columns using ALTER TABLE
print("\n1. Adding columns to task_instances table...")

with engine.connect() as conn:
    if needs_serendipity:
        print("   Adding serendipity_factor column...")
        conn.execute(text("ALTER TABLE task_instances ADD COLUMN serendipity_factor REAL"))
        conn.commit()
        print("   [OK] serendipity_factor added")
    
    if needs_disappointment:
        print("   Adding disappointment_factor column...")
        conn.execute(text("ALTER TABLE task_instances ADD COLUMN disappointment_factor REAL"))
        conn.commit()
        print("   [OK] disappointment_factor added")

print("\n[SUCCESS] Columns added successfully!")
print("=" * 70)
