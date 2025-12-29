#!/usr/bin/env python3
"""
Fix incorrectly scaled actual values in completed task instances.

This script finds completed instances where actual values are approximately 10x
the predicted/initialization values (indicating they were incorrectly scaled)
and divides them by 10 to fix the data.

Run this to retroactively fix data corrupted by the 0-10 to 0-100 scaling bug.
"""
import sys
import os
import json

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.instance_manager import InstanceManager

def fix_scaled_values(im, tolerance=0.15):
    """
    Fix actual values that are incorrectly 10x the predicted values.
    
    Args:
        im: InstanceManager instance
        tolerance: Allowed ratio range (0.85-1.15 means within 15% of exactly 10x)
    
    Returns:
        tuple: (total_checked, total_fixed, details)
    """
    total_checked = 0
    total_fixed = 0
    details = []
    
    # Field mappings: (actual_key, predicted_key, display_name)
    fields_to_check = [
        ('actual_relief', 'expected_relief', 'Relief'),
        ('actual_mental_energy', 'expected_mental_energy', 'Mental Energy'),
        ('actual_difficulty', 'expected_difficulty', 'Difficulty'),
        ('actual_emotional', 'expected_emotional_load', 'Emotional'),
        ('actual_physical', 'expected_physical_load', 'Physical'),
    ]
    
    # Get all instances
    if im.use_db:
        # Database backend
        with im.db_session() as session:
            instances = session.query(im.TaskInstance).filter(
                im.TaskInstance.is_completed == True
            ).all()
            
            for instance in instances:
                total_checked += 1
                instance_id = instance.instance_id
                fixed_any = False
                instance_fixes = []
                
                # Parse JSON fields
                actual_data = instance.actual or {}
                predicted_data = instance.predicted or {}
                
                if isinstance(actual_data, str):
                    try:
                        actual_data = json.loads(actual_data) if actual_data else {}
                    except json.JSONDecodeError:
                        actual_data = {}
                
                if isinstance(predicted_data, str):
                    try:
                        predicted_data = json.loads(predicted_data) if predicted_data else {}
                    except json.JSONDecodeError:
                        predicted_data = {}
                
                # Check each field
                updated_actual = actual_data.copy()
                for actual_key, predicted_key, display_name in fields_to_check:
                    actual_val = actual_data.get(actual_key)
                    predicted_val = predicted_data.get(predicted_key)
                    
                    # Skip if either value is missing
                    if actual_val is None or predicted_val is None:
                        continue
                    
                    try:
                        actual_float = float(actual_val)
                        predicted_float = float(predicted_val)
                        
                        # Skip if predicted is 0 (can't calculate ratio)
                        if predicted_float == 0:
                            continue
                        
                        # Skip if actual is already reasonable (not suspiciously high)
                        # Only fix values > 100 (which would indicate incorrect scaling from 0-100 to 0-1000)
                        if actual_float <= 100:
                            continue
                        
                        # Calculate ratio
                        ratio = actual_float / predicted_float if predicted_float > 0 else 0
                        
                        # Check if ratio is approximately 10 (indicating incorrect scaling)
                        # Allow tolerance around 10 (e.g., 8.5 to 11.5 with default tolerance of 0.15)
                        if 10.0 * (1 - tolerance) <= ratio <= 10.0 * (1 + tolerance):
                            # Fix by dividing by 10
                            corrected_val = actual_float / 10.0
                            updated_actual[actual_key] = int(round(corrected_val))
                            fixed_any = True
                            instance_fixes.append(
                                f"{display_name}: {int(actual_float)} -> {int(round(corrected_val))} (predicted: {int(predicted_float)})"
                            )
                    except (ValueError, TypeError):
                        continue
                
                # Update instance if any fixes were made
                if fixed_any:
                    instance.actual = updated_actual
                    session.commit()
                    total_fixed += 1
                    details.append({
                        'instance_id': instance_id,
                        'task_name': instance.task_name if hasattr(instance, 'task_name') else 'Unknown',
                        'fixes': instance_fixes
                    })
    else:
        # CSV backend
        im._reload()
        completed = im.df[im.df['is_completed'].astype(str).str.lower() == 'true'].copy()
        
        for idx in completed.index:
            total_checked += 1
            instance_id = completed.at[idx, 'instance_id']
            fixed_any = False
            instance_fixes = []
            
            # Parse JSON fields
            actual_str = str(completed.at[idx, 'actual'] or '{}')
            predicted_str = str(completed.at[idx, 'predicted'] or '{}')
            
            try:
                actual_data = json.loads(actual_str) if actual_str else {}
            except json.JSONDecodeError:
                actual_data = {}
            
            try:
                predicted_data = json.loads(predicted_str) if predicted_str else {}
            except json.JSONDecodeError:
                predicted_data = {}
            
            # Check each field
            updated_actual = actual_data.copy()
            for actual_key, predicted_key, display_name in fields_to_check:
                actual_val = actual_data.get(actual_key)
                predicted_val = predicted_data.get(predicted_key)
                
                # Skip if either value is missing
                if actual_val is None or predicted_val is None:
                    continue
                
                try:
                    actual_float = float(actual_val)
                    predicted_float = float(predicted_val)
                    
                    # Skip if predicted is 0 (can't calculate ratio)
                    if predicted_float == 0:
                        continue
                    
                    # Skip if actual is already reasonable (not suspiciously high)
                    # Only fix values > 100 (which would indicate incorrect scaling from 0-100 to 0-1000)
                    if actual_float <= 100:
                        continue
                    
                    # Calculate ratio
                    ratio = actual_float / predicted_float if predicted_float > 0 else 0
                    
                    # Check if ratio is approximately 10 (indicating incorrect scaling)
                    if 10.0 * (1 - tolerance) <= ratio <= 10.0 * (1 + tolerance):
                        # Fix by dividing by 10
                        corrected_val = actual_float / 10.0
                        updated_actual[actual_key] = int(round(corrected_val))
                        fixed_any = True
                        instance_fixes.append(
                            f"{display_name}: {int(actual_float)} -> {int(round(corrected_val))} (predicted: {int(predicted_float)})"
                        )
                except (ValueError, TypeError):
                    continue
            
            # Update instance if any fixes were made
            if fixed_any:
                im.df.at[idx, 'actual'] = json.dumps(updated_actual)
                total_fixed += 1
                task_name = completed.at[idx, 'task_name'] if 'task_name' in completed.columns else 'Unknown'
                details.append({
                    'instance_id': instance_id,
                    'task_name': task_name,
                    'fixes': instance_fixes
                })
        
        # Save CSV once after all updates (more efficient)
        if total_fixed > 0:
            im._save()
    
    return total_checked, total_fixed, details

if __name__ == "__main__":
    print("=" * 60)
    print("Fix Incorrectly Scaled Actual Values")
    print("=" * 60)
    print()
    print("This script will find completed instances where actual values")
    print("are approximately 10x the predicted values (indicating incorrect scaling)")
    print("and divide them by 10 to fix the data.")
    print()
    print("WARNING: This will modify your data directly.")
    print()
    
    # Check for --yes flag or Y environment variable
    auto_yes = '--yes' in sys.argv or os.getenv('AUTO_YES', '').lower() in ('1', 'true', 'yes')
    
    if not auto_yes:
        try:
            response = input("Continue? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("Cancelled.")
                sys.exit(0)
        except EOFError:
            print("No input available. Use --yes flag or set AUTO_YES=1 to run non-interactively.")
            sys.exit(1)
    
    print()
    print("Loading instances...")
    im = InstanceManager()
    
    backend_type = "CSV" if not im.use_db else "Database"
    print(f"Using {backend_type} backend")
    print()
    
    print("Checking completed instances for incorrectly scaled values...")
    total_checked, total_fixed, details = fix_scaled_values(im)
    
    print()
    print("=" * 60)
    print("Results")
    print("=" * 60)
    print(f"Total completed instances checked: {total_checked}")
    print(f"Instances fixed: {total_fixed}")
    print()
    
    if details:
        print("Fixed instances:")
        for detail in details:
            print(f"  - {detail['instance_id']} ({detail['task_name']})")
            for fix in detail['fixes']:
                print(f"      {fix}")
    else:
        print("No instances needed fixing.")
    
    print()
    print("=" * 60)
    if total_fixed > 0:
        print(f"[SUCCESS] Fixed {total_fixed} instance(s)")
    else:
        print("[INFO] No fixes needed")
    print("=" * 60)
