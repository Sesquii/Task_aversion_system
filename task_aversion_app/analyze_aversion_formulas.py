"""
Diagnostic script to analyze why aversion analytics formulas produce identical results.
"""
import pandas as pd
import os
import json
from backend.analytics import Analytics
from backend.instance_manager import InstanceManager

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def analyze_formula_differences():
    """Analyze the data and formulas to understand why all variants are identical."""
    
    analytics = Analytics()
    im = InstanceManager()
    
    # Load task instances
    instances_file = os.path.join(DATA_DIR, 'task_instances.csv')
    if not os.path.exists(instances_file):
        print("ERROR: task_instances.csv not found")
        return
    
    df = pd.read_csv(instances_file)
    print(f"Total instances: {len(df)}")
    
    # Filter to completed tasks
    completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
    print(f"Completed instances: {len(completed)}")
    
    if completed.empty:
        print("No completed tasks found")
        return
    
    # Extract expected relief from predicted_dict (matching analytics.py approach)
    def _safe_json(cell):
        if isinstance(cell, dict):
            return cell
        cell = cell or '{}'
        try:
            return json.loads(cell)
        except Exception:
            return {}
    
    completed['predicted_dict'] = completed['predicted'].apply(_safe_json) if 'predicted' in completed.columns else pd.Series([{}] * len(completed))
    completed['actual_dict'] = completed['actual'].apply(_safe_json) if 'actual' in completed.columns else pd.Series([{}] * len(completed))
    
    def _get_expected_relief(row):
        try:
            pred_dict = row['predicted_dict']
            if isinstance(pred_dict, dict):
                return pred_dict.get('expected_relief', None)
        except (KeyError, TypeError):
            pass
        return None
    
    def _get_actual_relief(row):
        try:
            return float(row['relief_score']) if pd.notna(row['relief_score']) else None
        except (ValueError, TypeError):
            return None
    
    def _get_expected_aversion(row):
        try:
            pred_dict = row['predicted_dict']
            if isinstance(pred_dict, dict):
                return pred_dict.get('expected_aversion', None)
        except (KeyError, TypeError):
            pass
        return None
    
    # Also try getting actual relief from actual_dict
    def _get_actual_relief_from_dict(row):
        try:
            actual_dict = row['actual_dict']
            if isinstance(actual_dict, dict):
                return actual_dict.get('actual_relief', None)
        except (KeyError, TypeError):
            pass
        return None
    
    completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
    completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
    
    # Try both relief_score column and actual_dict
    completed['actual_relief'] = completed.apply(_get_actual_relief, axis=1)
    completed['actual_relief'] = pd.to_numeric(completed['actual_relief'], errors='coerce')
    # Fill missing from actual_dict
    actual_from_dict = completed.apply(_get_actual_relief_from_dict, axis=1)
    actual_from_dict = pd.to_numeric(actual_from_dict, errors='coerce')
    completed['actual_relief'] = completed['actual_relief'].fillna(actual_from_dict)
    
    completed['expected_aversion'] = completed.apply(_get_expected_aversion, axis=1)
    completed['expected_aversion'] = pd.to_numeric(completed['expected_aversion'], errors='coerce')
    
    # Filter to rows with both expected and actual relief
    has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
    relief_data = completed[has_both].copy()
    print(f"\nInstances with both expected and actual relief: {len(relief_data)}")
    
    if relief_data.empty:
        print("No instances with both expected and actual relief")
        return
    
    # Analyze expected vs actual relief differences
    relief_data['relief_diff'] = relief_data['actual_relief'] - relief_data['expected_relief']
    relief_data['relief_diff_abs'] = relief_data['relief_diff'].abs()
    
    print("\n=== RELIEF DATA ANALYSIS ===")
    print(f"Expected relief stats:")
    print(f"  Mean: {relief_data['expected_relief'].mean():.2f}")
    print(f"  Std: {relief_data['expected_relief'].std():.2f}")
    print(f"  Min: {relief_data['expected_relief'].min():.2f}")
    print(f"  Max: {relief_data['expected_relief'].max():.2f}")
    
    print(f"\nActual relief stats:")
    print(f"  Mean: {relief_data['actual_relief'].mean():.2f}")
    print(f"  Std: {relief_data['actual_relief'].std():.2f}")
    print(f"  Min: {relief_data['actual_relief'].min():.2f}")
    print(f"  Max: {relief_data['actual_relief'].max():.2f}")
    
    print(f"\nRelief difference (actual - expected) stats:")
    print(f"  Mean: {relief_data['relief_diff'].mean():.2f}")
    print(f"  Std: {relief_data['relief_diff'].std():.2f}")
    print(f"  Min: {relief_data['relief_diff'].min():.2f}")
    print(f"  Max: {relief_data['relief_diff'].max():.2f}")
    print(f"  Mean absolute diff: {relief_data['relief_diff_abs'].mean():.2f}")
    
    # Count how many have identical expected and actual
    identical_count = (relief_data['relief_diff_abs'] < 0.01).sum()
    print(f"\nInstances with identical expected/actual relief (diff < 0.01): {identical_count} / {len(relief_data)} ({100*identical_count/len(relief_data):.1f}%)")
    
    # Get baseline aversions
    def _get_baseline_robust(row):
        task_id = row.get('task_id')
        if task_id:
            try:
                return im.get_baseline_aversion_robust(task_id)
            except:
                return None
        return None
    
    def _get_baseline_sensitive(row):
        task_id = row.get('task_id')
        if task_id:
            try:
                return im.get_baseline_aversion_sensitive(task_id)
            except:
                return None
        return None
    
    relief_data['baseline_aversion_robust'] = relief_data.apply(_get_baseline_robust, axis=1)
    relief_data['baseline_aversion_sensitive'] = relief_data.apply(_get_baseline_sensitive, axis=1)
    
    # Check for spontaneous aversion spikes
    print("\n=== AVERSION SPIKE ANALYSIS ===")
    spontaneous_count_robust = 0
    spontaneous_count_sensitive = 0
    total_spike_robust = 0.0
    total_spike_sensitive = 0.0
    
    for idx, row in relief_data.iterrows():
        baseline_robust = row.get('baseline_aversion_robust')
        baseline_sensitive = row.get('baseline_aversion_sensitive')
        current = row.get('expected_aversion')
        
        if baseline_robust is not None and current is not None:
            is_spontaneous, spike_amount = Analytics.detect_spontaneous_aversion(baseline_robust, current)
            if is_spontaneous:
                spontaneous_count_robust += 1
                total_spike_robust += spike_amount
        
        if baseline_sensitive is not None and current is not None:
            is_spontaneous, spike_amount = Analytics.detect_spontaneous_aversion(baseline_sensitive, current)
            if is_spontaneous:
                spontaneous_count_sensitive += 1
                total_spike_sensitive += spike_amount
    
    print(f"Spontaneous spikes (robust): {spontaneous_count_robust} / {len(relief_data)}")
    print(f"Spontaneous spikes (sensitive): {spontaneous_count_sensitive} / {len(relief_data)}")
    if spontaneous_count_robust > 0:
        print(f"  Avg spike amount (robust): {total_spike_robust / spontaneous_count_robust:.2f}")
    if spontaneous_count_sensitive > 0:
        print(f"  Avg spike amount (sensitive): {total_spike_sensitive / spontaneous_count_sensitive:.2f}")
    
    # Calculate obstacles scores for a sample of rows
    print("\n=== FORMULA VARIANT ANALYSIS ===")
    print("Calculating scores for first 5 rows with spontaneous spikes...")
    
    sample_rows = []
    for idx, row in relief_data.iterrows():
        baseline_robust = row.get('baseline_aversion_robust')
        current = row.get('expected_aversion')
        expected_relief = row.get('expected_relief')
        actual_relief = row.get('actual_relief')
        
        if baseline_robust is not None and current is not None:
            is_spontaneous, spike_amount = Analytics.detect_spontaneous_aversion(baseline_robust, current)
            if is_spontaneous:
                expected_relief_float = float(expected_relief) if expected_relief is not None and not pd.isna(expected_relief) else None
                actual_relief_float = float(actual_relief) if actual_relief is not None and not pd.isna(actual_relief) else None
                
                scores = Analytics.calculate_obstacles_scores(
                    baseline_robust, current, expected_relief_float, actual_relief_float
                )
                
                sample_rows.append({
                    'task_id': row.get('task_id'),
                    'baseline': baseline_robust,
                    'current': current,
                    'spike': spike_amount,
                    'expected_relief': expected_relief_float,
                    'actual_relief': actual_relief_float,
                    'relief_diff': actual_relief_float - expected_relief_float if (expected_relief_float is not None and actual_relief_float is not None) else None,
                    **scores
                })
                
                if len(sample_rows) >= 5:
                    break
    
    if sample_rows:
        print("\nSample calculations:")
        for i, row_data in enumerate(sample_rows, 1):
            print(f"\n  Row {i}:")
            print(f"    Task ID: {row_data['task_id']}")
            print(f"    Baseline: {row_data['baseline']:.1f}, Current: {row_data['current']:.1f}, Spike: {row_data['spike']:.1f}")
            print(f"    Expected relief: {row_data['expected_relief']:.1f}, Actual relief: {row_data['actual_relief']:.1f}")
            print(f"    Relief diff: {row_data['relief_diff']:.1f}" if row_data['relief_diff'] is not None else "    Relief diff: N/A")
            print(f"    Scores:")
            for variant in ['expected_only', 'actual_only', 'minimum', 'average', 'net_penalty', 'net_bonus', 'net_weighted']:
                print(f"      {variant}: {row_data[variant]:.2f}")
    else:
        print("No rows with spontaneous spikes found")
    
    # Calculate totals for all variants
    print("\n=== TOTAL SCORES BY VARIANT ===")
    score_variants = ['expected_only', 'actual_only', 'minimum', 'average', 'net_penalty', 'net_bonus', 'net_weighted']
    
    totals_robust = {variant: 0.0 for variant in score_variants}
    totals_sensitive = {variant: 0.0 for variant in score_variants}
    
    for idx, row in relief_data.iterrows():
        baseline_robust = row.get('baseline_aversion_robust')
        baseline_sensitive = row.get('baseline_aversion_sensitive')
        current = row.get('expected_aversion')
        expected_relief = row.get('expected_relief')
        actual_relief = row.get('actual_relief')
        
        expected_relief_float = float(expected_relief) if expected_relief is not None and not pd.isna(expected_relief) else None
        actual_relief_float = float(actual_relief) if actual_relief is not None and not pd.isna(actual_relief) else None
        
        if baseline_robust is not None and current is not None:
            scores_robust = Analytics.calculate_obstacles_scores(
                baseline_robust, current, expected_relief_float, actual_relief_float
            )
            for variant in score_variants:
                totals_robust[variant] += scores_robust.get(variant, 0.0)
        
        if baseline_sensitive is not None and current is not None:
            scores_sensitive = Analytics.calculate_obstacles_scores(
                baseline_sensitive, current, expected_relief_float, actual_relief_float
            )
            for variant in score_variants:
                totals_sensitive[variant] += scores_sensitive.get(variant, 0.0)
    
    print("\nRobust baseline totals:")
    for variant in score_variants:
        print(f"  {variant}: {totals_robust[variant]:.2f}")
    
    print("\nSensitive baseline totals:")
    for variant in score_variants:
        print(f"  {variant}: {totals_sensitive[variant]:.2f}")
    
    # Check if all variants are identical
    robust_values = list(totals_robust.values())
    sensitive_values = list(totals_sensitive.values())
    
    robust_all_same = all(abs(v - robust_values[0]) < 0.01 for v in robust_values)
    sensitive_all_same = all(abs(v - sensitive_values[0]) < 0.01 for v in sensitive_values)
    
    print(f"\n=== SUMMARY ===")
    print(f"All robust variants identical: {robust_all_same}")
    print(f"All sensitive variants identical: {sensitive_all_same}")
    
    if robust_all_same or sensitive_all_same:
        print("\nPOSSIBLE CAUSES:")
        if identical_count == len(relief_data):
            print("  - All tasks have identical expected and actual relief (net_relief = 0)")
            print("    This makes net_penalty, net_bonus, net_weighted identical to expected_only")
        if spontaneous_count_robust == 0 and spontaneous_count_sensitive == 0:
            print("  - No spontaneous aversion spikes detected")
            print("    All formulas return 0.0 when there's no spike")
        if len(relief_data) == 0:
            print("  - No data with both expected and actual relief")

if __name__ == '__main__':
    analyze_formula_differences()

