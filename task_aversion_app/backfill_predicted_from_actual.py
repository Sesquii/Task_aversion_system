#!/usr/bin/env python3
"""
Backfill missing predicted values with actual values.

This script updates the 'predicted' JSON in task instances to use actual values
when predicted values are missing. For example:
- If expected_relief is missing but actual_relief exists, use actual_relief as expected_relief
- If expected_cognitive_load is missing but actual_cognitive exists, use actual_cognitive as expected_cognitive_load
- And similar for other fields.

This helps improve future predictions by using historical actual data.
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent))

from backend.instance_manager import InstanceManager

# Mapping from actual JSON keys to predicted JSON keys
ACTUAL_TO_PREDICTED_MAPPING = {
    'actual_relief': 'expected_relief',
    'actual_cognitive': 'expected_cognitive_load',
    'actual_emotional': 'expected_emotional_load',
    'actual_physical': 'expected_physical_load',
    'time_actual_minutes': 'time_estimate_minutes',
    # Also handle direct matches
    'relief_score': 'expected_relief',
    'cognitive_load': 'expected_cognitive_load',
    'emotional_load': 'expected_emotional_load',
    'physical_load': 'expected_physical_load',
    'duration_minutes': 'time_estimate_minutes',
}

# Also map motivation and other fields that might be in actual
ADDITIONAL_MAPPINGS = {
    'motivation': 'motivation',  # Keep same name
    'physical_context': 'physical_context',
    'description': 'description',
    'emotions': 'emotions',
}


def is_empty(val):
    """Check if a value is considered empty."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    if isinstance(val, str) and val.strip() == '':
        return True
    return False


def backfill_predicted_from_actual(dry_run=True):
    """
    Backfill missing predicted values with actual values.
    
    Args:
        dry_run: If True, only show what would be changed without making changes.
    
    Returns:
        Number of instances updated.
    """
    im = InstanceManager()
    im._reload()
    
    updated_count = 0
    changes_summary = []
    
    for idx in im.df.index:
        instance_id = im.df.at[idx, 'instance_id']
        predicted_str = str(im.df.at[idx, 'predicted'] or '{}').strip()
        actual_str = str(im.df.at[idx, 'actual'] or '{}').strip()
        
        # Skip if no actual data
        if not actual_str or actual_str == '{}':
            continue
        
        try:
            predicted_dict = json.loads(predicted_str) if predicted_str else {}
            actual_dict = json.loads(actual_str) if actual_str else {}
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse JSON for instance {instance_id}: {e}")
            continue
        
        if not isinstance(predicted_dict, dict):
            predicted_dict = {}
        if not isinstance(actual_dict, dict):
            actual_dict = {}
        
        instance_changes = []
        predicted_updated = False
        
        # Map actual values to predicted keys
        for actual_key, predicted_key in ACTUAL_TO_PREDICTED_MAPPING.items():
            # Check if predicted value is missing or empty
            predicted_value = predicted_dict.get(predicted_key)
            if is_empty(predicted_value):
                # Check if actual value exists
                actual_value = actual_dict.get(actual_key)
                if not is_empty(actual_value):
                    # Use actual value for predicted
                    predicted_dict[predicted_key] = actual_value
                    instance_changes.append(f"{predicted_key}: {actual_value} (from {actual_key})")
                    predicted_updated = True
        
        # Also handle additional mappings (same key name)
        for key in ADDITIONAL_MAPPINGS:
            predicted_key = ADDITIONAL_MAPPINGS[key]
            predicted_value = predicted_dict.get(predicted_key)
            if is_empty(predicted_value):
                actual_value = actual_dict.get(key)
                if not is_empty(actual_value):
                    predicted_dict[predicted_key] = actual_value
                    instance_changes.append(f"{predicted_key}: {actual_value} (from {key})")
                    predicted_updated = True
        
        if predicted_updated:
            if not dry_run:
                # Update the predicted JSON
                im.df.at[idx, 'predicted'] = json.dumps(predicted_dict)
            
            changes_summary.append({
                'instance_id': instance_id,
                'task_name': im.df.at[idx, 'task_name'],
                'changes': instance_changes,
            })
            updated_count += 1
    
    if not dry_run:
        im._save()
        print(f"\n✓ Saved changes to {im.file}")
    
    return updated_count, changes_summary


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Backfill missing predicted values with actual values from completed tasks.'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually make the changes (default is dry-run)',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed changes for each instance',
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    print("=" * 60)
    print("Backfill Predicted Values from Actual Values")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'EXECUTE (changes will be saved)'}")
    print()
    
    updated_count, changes_summary = backfill_predicted_from_actual(dry_run=dry_run)
    
    print(f"\nFound {updated_count} instance(s) that would be updated.")
    
    if changes_summary and args.verbose:
        print("\nDetailed changes:")
        print("-" * 60)
        for item in changes_summary:
            print(f"\nInstance: {item['instance_id']}")
            print(f"Task: {item['task_name']}")
            print("Changes:")
            for change in item['changes']:
                print(f"  - {change}")
    
    if dry_run and updated_count > 0:
        print("\n" + "=" * 60)
        print("This was a DRY RUN. No changes were made.")
        print("Run with --execute to apply these changes.")
        print("=" * 60)
    elif not dry_run and updated_count > 0:
        print("\n" + "=" * 60)
        print(f"✓ Successfully updated {updated_count} instance(s).")
        print("=" * 60)
    elif updated_count == 0:
        print("\nNo instances need updating.")
    
    return 0 if updated_count >= 0 else 1


if __name__ == '__main__':
    sys.exit(main())

