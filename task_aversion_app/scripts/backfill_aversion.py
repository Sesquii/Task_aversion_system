#!/usr/bin/env python3
"""
Backfill missing aversion values in task instances.

This script:
1. Finds all task instances missing aversion data
2. Backfills with 0 (or 1 if using 1-100 scale) as default
3. Uses emotional load as a proxy if available (scaled appropriately)
4. Updates both CSV and database backends
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.instance_manager import InstanceManager


def backfill_aversion(dry_run=True, default_value=0, use_database=None):
    """
    Backfill missing aversion values in task instances.
    
    Args:
        dry_run: If True, only show what would be changed without making changes
        default_value: Default aversion value to use (0 or 1)
        use_database: If True, force database backend. If False, force CSV. If None, auto-detect.
    
    Returns:
        Number of instances updated
    """
    # Set DATABASE_URL if use_database is True
    if use_database is True:
        import os
        if not os.getenv('DATABASE_URL'):
            os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
            print("[Backfill] Set DATABASE_URL for database backend")
    elif use_database is False:
        import os
        if os.getenv('DATABASE_URL'):
            del os.environ['DATABASE_URL']
            print("[Backfill] Unset DATABASE_URL for CSV backend")
    
    im = InstanceManager()
    
    # Reload to get latest data
    if not im.use_db:
        im._reload()
    
    backend_type = "database" if im.use_db else "CSV"
    print(f"[Backfill] Using {backend_type} backend")
    
    updated_count = 0
    changes_summary = []
    
    # Get all instances
    if im.use_db:
        # For database, get all instances (completed and active)
        try:
            with im.db_session() as session:
                db_instances = session.query(im.TaskInstance).all()
                instances = [inst.to_dict() for inst in db_instances]
        except Exception as e:
            print(f"[Backfill] Error loading database instances: {e}")
            instances = []
    else:
        # For CSV, get all instances from dataframe
        im._reload()
        instances = im.df.to_dict(orient='records')
    
    for instance in instances:
        instance_id = instance.get('instance_id')
        if not instance_id:
            continue
        
        try:
            # Get predicted data
            if im.use_db:
                predicted = instance.get('predicted', {})
                if not isinstance(predicted, dict):
                    predicted = {}
            else:
                predicted_str = str(instance.get('predicted', '{}') or '{}').strip()
                try:
                    predicted = json.loads(predicted_str) if predicted_str else {}
                except json.JSONDecodeError:
                    predicted = {}
            
            if not isinstance(predicted, dict):
                predicted = {}
            
            # Check if aversion is missing
            has_aversion = (
                'initial_aversion' in predicted or
                'expected_aversion' in predicted or
                'aversion' in predicted
            )
            
            if not has_aversion:
                # Determine backfill value
                backfill_value = default_value
                
                # Try to infer from emotional load if available
                expected_emotional = predicted.get('expected_emotional_load')
                if expected_emotional is not None:
                    try:
                        emotional_val = float(expected_emotional)
                        # Use emotional load as proxy: scale to 0-100, but cap at reasonable aversion
                        # High emotional load (80+) suggests high aversion (60+)
                        # Low emotional load (20-) suggests low aversion (20-)
                        if emotional_val > 0:
                            # Rough correlation: emotional_load * 0.8, but ensure minimum of default_value
                            inferred_aversion = max(default_value, min(100, emotional_val * 0.8))
                            backfill_value = int(round(inferred_aversion))
                    except (ValueError, TypeError):
                        pass
                
                # Update predicted payload (merge with existing, don't replace)
                predicted['expected_aversion'] = backfill_value
                
                # If this might be a first-time task, also set initial_aversion
                # Check if task has been done before
                task_id = instance.get('task_id')
                if task_id:
                    # Get user_id from instance for proper data isolation
                    user_id = instance.get('user_id')
                    # Convert string user_id to int if needed
                    if user_id is not None:
                        try:
                            user_id = int(user_id) if isinstance(user_id, (str, int)) else None
                        except (ValueError, TypeError):
                            user_id = None
                    # Note: For backfill scripts, we intentionally pass user_id=None if not available
                    # to allow processing across all users when user_id is missing from historical data
                    initial_aversion = im.get_initial_aversion(task_id, user_id=user_id) if hasattr(im, 'get_initial_aversion') else None
                    if initial_aversion is None:
                        # This might be the first time, set initial_aversion too
                        predicted['initial_aversion'] = backfill_value
                
                # Save the update
                if not dry_run:
                    if im.use_db:
                        # Update database - merge with existing predicted data
                        try:
                            with im.db_session() as session:
                                db_instance = session.query(im.TaskInstance).filter(
                                    im.TaskInstance.instance_id == instance_id
                                ).first()
                                if db_instance:
                                    # Merge with existing predicted data
                                    existing_predicted = db_instance.predicted or {}
                                    existing_predicted.update(predicted)
                                    db_instance.predicted = existing_predicted
                                    session.commit()
                                    updated_count += 1
                        except Exception as e:
                            print(f"[Backfill] Error updating {instance_id} in database: {e}")
                    else:
                        # Update CSV - merge with existing predicted data
                        try:
                            idx = im.df.index[im.df['instance_id'] == instance_id]
                            if len(idx) > 0:
                                existing_predicted_str = im.df.at[idx[0], 'predicted'] or '{}'
                                try:
                                    existing_predicted = json.loads(existing_predicted_str) if existing_predicted_str else {}
                                except json.JSONDecodeError:
                                    existing_predicted = {}
                                existing_predicted.update(predicted)
                                im.df.at[idx[0], 'predicted'] = json.dumps(existing_predicted)
                                im._save_csv()
                                updated_count += 1
                        except Exception as e:
                            print(f"[Backfill] Error updating {instance_id} in CSV: {e}")
                
                # Record change
                task_name = instance.get('task_name', 'Unknown')
                changes_summary.append({
                    'instance_id': instance_id,
                    'task_name': task_name,
                    'backfill_value': backfill_value,
                    'emotional_proxy': expected_emotional if expected_emotional else None
                })
        except Exception as e:
            print(f"[Backfill] Error processing instance {instance_id}: {e}")
            continue
    
    # Print summary
    print(f"\n[Backfill Aversion] Summary:")
    print(f"  Instances found: {len(instances)}")
    print(f"  Missing aversion: {len(changes_summary)}")
    
    if changes_summary:
        print(f"\n  Sample changes:")
        for change in changes_summary[:10]:  # Show first 10
            proxy_note = f" (from emotional load: {change['emotional_proxy']})" if change['emotional_proxy'] else ""
            print(f"    - {change['task_name']}: {change['backfill_value']}{proxy_note}")
        if len(changes_summary) > 10:
            print(f"    ... and {len(changes_summary) - 10} more")
    
    if dry_run:
        print(f"\n[DRY RUN] Would update {len(changes_summary)} instances")
        print(f"  Run with dry_run=False to apply changes")
    else:
        print(f"\n[SUCCESS] Updated {updated_count} instances")
    
    return updated_count if not dry_run else len(changes_summary)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill missing aversion values')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--default', type=int, default=0, help='Default aversion value (0 or 1, default: 0)')
    parser.add_argument('--database', action='store_true', help='Use database backend (set DATABASE_URL)')
    parser.add_argument('--csv', action='store_true', help='Use CSV backend (unset DATABASE_URL)')
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    default_value = max(0, min(1, args.default))  # Ensure 0 or 1
    
    # Determine backend
    use_database = None
    if args.database:
        use_database = True
    elif args.csv:
        use_database = False
    
    print(f"[Backfill Aversion] Starting backfill (dry_run={dry_run}, default={default_value})")
    backfill_aversion(dry_run=dry_run, default_value=default_value, use_database=use_database)

