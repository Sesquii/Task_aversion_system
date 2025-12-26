#!/usr/bin/env python3
"""
Sync aversion values from CSV to database.

This script:
1. Reads aversion values from CSV task_instances.csv
2. Updates corresponding instances in the database
3. Useful after running backfill_aversion.py on CSV when using database backend
"""

import os
import sys
import json
from pathlib import Path

# Set DATABASE_URL to use database backend
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.instance_manager import InstanceManager
import pandas as pd


def sync_aversion_csv_to_db(dry_run=True):
    """
    Sync aversion values from CSV to database.
    
    Args:
        dry_run: If True, only show what would be changed without making changes
    
    Returns:
        Number of instances updated
    """
    # Load CSV data
    csv_file = os.path.join('data', 'task_instances.csv')
    if not os.path.exists(csv_file):
        print(f"[Sync] CSV file not found: {csv_file}")
        return 0
    
    csv_df = pd.read_csv(csv_file, dtype=str).fillna('')
    print(f"[Sync] Loaded {len(csv_df)} instances from CSV")
    
    # Initialize database backend
    im = InstanceManager()
    if not im.use_db:
        print("[Sync] ERROR: InstanceManager is not using database backend!")
        print("[Sync] Make sure DATABASE_URL is set")
        return 0
    
    updated_count = 0
    changes_summary = []
    
    # Process each CSV row
    for idx, row in csv_df.iterrows():
        instance_id = row.get('instance_id', '').strip()
        if not instance_id:
            continue
        
        try:
            # Get predicted JSON from CSV
            predicted_str = str(row.get('predicted', '{}') or '{}').strip()
            try:
                predicted_csv = json.loads(predicted_str) if predicted_str else {}
            except json.JSONDecodeError:
                predicted_csv = {}
            
            if not isinstance(predicted_csv, dict):
                predicted_csv = {}
            
            # Check if CSV has aversion data
            csv_aversion = (predicted_csv.get('initial_aversion') or 
                          predicted_csv.get('expected_aversion') or 
                          predicted_csv.get('aversion'))
            
            if csv_aversion is None:
                continue  # No aversion in CSV, skip
            
            # Get database instance
            try:
                with im.db_session() as session:
                    db_instance = session.query(im.TaskInstance).filter(
                        im.TaskInstance.instance_id == instance_id
                    ).first()
                    
                    if not db_instance:
                        continue  # Instance not in database yet
                    
                    # Get database predicted data
                    db_predicted = db_instance.predicted or {}
                    if not isinstance(db_predicted, dict):
                        db_predicted = {}
                    
                    # Check if database already has aversion
                    db_aversion = (db_predicted.get('initial_aversion') or 
                                 db_predicted.get('expected_aversion') or 
                                 db_predicted.get('aversion'))
                    
                    # Update if CSV has aversion and database doesn't, or if they differ
                    if db_aversion is None or db_aversion != csv_aversion:
                        # Merge CSV predicted data into database
                        db_predicted['expected_aversion'] = csv_aversion
                        
                        # Also set initial_aversion if CSV has it
                        if 'initial_aversion' in predicted_csv:
                            db_predicted['initial_aversion'] = predicted_csv['initial_aversion']
                        
                        if not dry_run:
                            db_instance.predicted = db_predicted
                            session.commit()
                            updated_count += 1
                        
                        task_name = row.get('task_name', 'Unknown')
                        changes_summary.append({
                            'instance_id': instance_id,
                            'task_name': task_name,
                            'csv_aversion': csv_aversion,
                            'db_aversion': db_aversion
                        })
            except Exception as e:
                print(f"[Sync] Error processing {instance_id}: {e}")
                continue
        except Exception as e:
            print(f"[Sync] Error processing row {idx}: {e}")
            continue
    
    # Print summary
    print(f"\n[Sync Aversion] Summary:")
    print(f"  CSV instances: {len(csv_df)}")
    print(f"  Instances to update: {len(changes_summary)}")
    
    if changes_summary:
        print(f"\n  Sample changes:")
        for change in changes_summary[:10]:  # Show first 10
            db_note = f" (was: {change['db_aversion']})" if change['db_aversion'] is not None else " (was: missing)"
            print(f"    - {change['task_name']}: {change['csv_aversion']}{db_note}")
        if len(changes_summary) > 10:
            print(f"    ... and {len(changes_summary) - 10} more")
    
    if dry_run:
        print(f"\n[DRY RUN] Would update {len(changes_summary)} instances in database")
        print(f"  Run with dry_run=False to apply changes")
    else:
        print(f"\n[SUCCESS] Updated {updated_count} instances in database")
    
    return updated_count if not dry_run else len(changes_summary)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Sync aversion values from CSV to database')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    print(f"[Sync Aversion] Starting sync (dry_run={dry_run})")
    sync_aversion_csv_to_db(dry_run=dry_run)

