#!/usr/bin/env python
"""
Migration script to calculate and store serendipity_factor and disappointment_factor
for existing task instances in the database.

This script:
1. Loads all completed task instances
2. Calculates factors from expected_relief and actual_relief
3. Stores the calculated values in the database

Run this after adding the new columns to the database schema.
"""
import os
import sys
from datetime import datetime

# Set DATABASE_URL
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///data/task_aversion.db')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_session, TaskInstance

print("=" * 70)
print("Factor Migration: Calculate and Store Serendipity/Disappointment Factors")
print("=" * 70)

# Initialize database (creates tables if they don't exist)
print("\n1. Initializing database...")
init_db()
print("   [OK] Database initialized")

# Load all completed instances
print("\n2. Loading completed task instances...")
with get_session() as session:
    instances = session.query(TaskInstance).filter(
        TaskInstance.is_completed == True,
        TaskInstance.completed_at.isnot(None)
    ).all()
    print(f"   Found {len(instances)} completed instance(s)")

if len(instances) == 0:
    print("\n   [INFO] No completed instances found. Nothing to migrate.")
    sys.exit(0)

# Helper function to normalize relief values
def normalize_relief(val):
    """Normalize relief value: scale 0-10 to 0-100 if needed."""
    if val is None:
        return None
    try:
        val = float(val)
        # Note: All inputs now use 0-100 scale natively.
        # Old data may have 0-10 scale values, but we use them as-is (no scaling).
        return val
    except (ValueError, TypeError):
        return None

# Calculate and store factors
print("\n3. Calculating and storing factors...")
updated = 0
skipped = 0
errors = 0

with get_session() as session:
    for instance in instances:
        try:
            # Get expected and actual relief from JSON
            predicted = instance.predicted or {}
            actual = instance.actual or {}
            
            expected_relief = predicted.get('expected_relief')
            actual_relief = actual.get('actual_relief')
            
            # Normalize relief values
            expected_relief = normalize_relief(expected_relief)
            actual_relief = normalize_relief(actual_relief)
            
            # If we have both values, calculate factors
            if expected_relief is not None and actual_relief is not None:
                net_relief = actual_relief - expected_relief
                
                # Store net_relief if not already set
                if instance.net_relief is None:
                    instance.net_relief = net_relief
                
                # Only update factors if they're missing (idempotent - safe to run multiple times)
                needs_update = (
                    instance.serendipity_factor is None or 
                    instance.disappointment_factor is None
                )
                
                if needs_update:
                    # Calculate factors
                    instance.serendipity_factor = max(0.0, net_relief)  # Positive net relief
                    instance.disappointment_factor = max(0.0, -net_relief)  # Negative net relief (as positive value)
                    
                    updated += 1
                    if updated % 10 == 0:
                        print(f"   Processed {updated} instance(s)...")
                else:
                    # Factors already exist, skip
                    skipped += 1
            else:
                # Skip if we don't have both values
                skipped += 1
                if instance.serendipity_factor is None:
                    instance.serendipity_factor = None
                if instance.disappointment_factor is None:
                    instance.disappointment_factor = None
                
        except Exception as e:
            errors += 1
            print(f"   [ERROR] Instance {instance.instance_id}: {e}")
            instance.serendipity_factor = None
            instance.disappointment_factor = None
    
    # Commit all changes
    print("\n4. Committing changes to database...")
    session.commit()
    print("   [OK] Changes committed")

# Summary
print("\n" + "=" * 70)
print("Migration Summary")
print("=" * 70)
print(f"Total instances processed: {len(instances)}")
print(f"Successfully updated: {updated}")
print(f"Skipped (already have factors or missing data): {skipped}")
print(f"Errors: {errors}")
print("=" * 70)

if errors > 0:
    print("\n[WARNING] Some instances had errors. Check the output above for details.")
    sys.exit(1)
else:
    print("\n[SUCCESS] Migration completed successfully!")
    sys.exit(0)
