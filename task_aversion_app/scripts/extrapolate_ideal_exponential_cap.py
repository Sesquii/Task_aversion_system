"""
Extrapolate ideal exponential cap value for disappointment resilience.

Tests various exponential cap values (2.0 to 3.5) to find optimal correlation.
"""

import os
import sys
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.analytics import Analytics
from backend.database import get_session

def calculate_grit_with_cap(row: pd.Series, task_completion_counts: Dict[str, int], 
                           cap_value: float, analytics: Analytics) -> float:
    """Calculate grit score with specific exponential cap value."""
    try:
        completion_pct = float(row.get('completion_pct', 0) or 0)
        if completion_pct <= 0:
            return 0.0
        
        # Get predicted and actual values
        predicted_dict = eval(row.get('predicted_values', '{}') or '{}')
        actual_dict = eval(row.get('actual_values', '{}') or '{}')
        
        # Time bonus calculation
        time_estimate = float(predicted_dict.get('time_estimate', 0) or 0)
        time_actual = float(actual_dict.get('time_actual', 0) or 0)
        time_bonus = 1.0
        if time_estimate > 0 and time_actual > 0:
            time_ratio = time_actual / time_estimate
            if time_ratio > 1.0:
                excess = time_ratio - 1.0
                if excess <= 1.0:
                    base_time_bonus = 1.0 + (excess * 0.8)
                else:
                    base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)
                base_time_bonus = min(3.0, base_time_bonus)
                
                task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                
                task_name = str(row.get('task_name', ''))
                completion_count = task_completion_counts.get(task_name, 1)
                fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
                time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
            else:
                time_bonus = 1.0
        
        # Passion factor
        relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
        emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
        relief_norm = max(0.0, min(1.0, relief / 100.0))
        emotional_norm = max(0.0, min(1.0, emotional / 100.0))
        passion_delta = relief_norm - emotional_norm
        passion_factor = 1.0 + passion_delta * 0.5
        if completion_pct < 100:
            passion_factor *= 0.9
        passion_factor = max(0.5, min(1.5, passion_factor))
        
        # Persistence and focus factors
        persistence_factor = analytics.calculate_persistence_factor(row=row, task_completion_counts=task_completion_counts)
        persistence_factor_scaled = 0.5 + persistence_factor * 1.0
        focus_factor = analytics.calculate_focus_factor(row)
        focus_factor_scaled = 0.5 + focus_factor * 1.0
        
        # Disappointment factor
        disappointment_factor = 0.0
        if 'disappointment_factor' in row.index:
            try:
                disappointment_factor = float(row.get('disappointment_factor', 0) or 0)
            except (ValueError, TypeError):
                disappointment_factor = 0.0
        else:
            try:
                expected_relief = float(predicted_dict.get('expected_relief', 0) or 0)
                actual_relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
                net_relief = actual_relief - expected_relief
                if net_relief < 0:
                    disappointment_factor = -net_relief
            except (ValueError, TypeError, KeyError):
                disappointment_factor = 0.0
        
        # Disappointment resilience with exponential scaling
        disappointment_resilience = 1.0
        if disappointment_factor > 0:
            if completion_pct >= 100.0:
                # Exponential scaling
                bonus_range = cap_value - 1.0
                k = 144.0  # Consistent exponential parameter
                exponential_factor = 1.0 - math.exp(-disappointment_factor / k)
                scale_factor = bonus_range / (1.0 - math.exp(-100.0 / k))
                disappointment_resilience = 1.0 + (exponential_factor * scale_factor)
                disappointment_resilience = min(cap_value, disappointment_resilience)
            else:
                # Abandonment penalty (linear, same for all)
                disappointment_resilience = 1.0 - (disappointment_factor / 300.0)
                disappointment_resilience = max(0.67, disappointment_resilience)
        
        # Calculate final grit score
        base_score = completion_pct
        grit_score = base_score * (
            persistence_factor_scaled *
            focus_factor_scaled *
            passion_factor *
            time_bonus *
            disappointment_resilience
        )
        
        return float(grit_score)
    
    except (KeyError, TypeError, ValueError, AttributeError):
        return 0.0

def main():
    """Extrapolate ideal exponential cap value."""
    print("=" * 80)
    print("Extrapolating Ideal Exponential Cap Value")
    print("=" * 80)
    print()
    
    # Load data (same approach as compare script)
    print("[INFO] Loading task instances...")
    analytics = Analytics()
    # Analysis script: intentionally use user_id=None to load all instances across all users
    df = analytics._load_instances(completed_only=False, user_id=None)
    
    if df.empty:
        print("[ERROR] No instances found")
        return
    
    print(f"[INFO] Loaded {len(df)} instances")
    
    # Extract completion percentage
    def get_completion_pct(row):
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('completion_percent', 100) or 100)
            return 100.0
        except (KeyError, TypeError, ValueError):
            return 100.0
    
    df['completion_pct'] = df.apply(get_completion_pct, axis=1)
    
    # Keep all instances (including 0% completion)
    print(f"[INFO] {len(df)} total instances (including 0% completion)")
    
    # Get task completion counts
    task_completion_counts = {}
    for task_name in df['task_name'].unique():
        task_completion_counts[task_name] = len(df[df['task_name'] == task_name])
    
    # Calculate disappointment factor
    def get_disappointment_factor(row):
        try:
            if 'disappointment_factor' in row.index:
                return float(row.get('disappointment_factor', 0) or 0)
            predicted_dict = eval(row.get('predicted_values', '{}') or '{}')
            actual_dict = eval(row.get('actual_values', '{}') or '{}')
            expected_relief = float(predicted_dict.get('expected_relief', 0) or 0)
            actual_relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            net_relief = actual_relief - expected_relief
            return max(0.0, -net_relief) if net_relief < 0 else 0.0
        except:
            return 0.0
    
    df['disappointment_factor'] = df.apply(get_disappointment_factor, axis=1)
    
    # Test specific cap values (including extreme values to find plateau)
    # Testing very high values to see if correlation continues improving or plateaus
    cap_values = [3.0, 5.0, 10.0, 100.0]
    results = []
    
    print("[INFO] Testing exponential cap values...")
    for cap in cap_values:
        cap = round(cap, 1)
        print(f"  Testing cap: {cap:.1f}x", end='\r')
        
        # Calculate grit scores
        grit_scores = []
        for idx, row in df.iterrows():
            grit = calculate_grit_with_cap(row, task_completion_counts, cap, analytics)
            grit_scores.append(grit)
        
        df[f'grit_cap_{cap:.1f}'] = grit_scores
        
        # Calculate correlations for completed tasks (100%+)
        disappointed_completed = df[(df['disappointment_factor'] > 0) & (df['completion_pct'] >= 100.0)]
        corr_completed = None
        if not disappointed_completed.empty:
            corr_completed = float(disappointed_completed[f'grit_cap_{cap:.1f}'].corr(disappointed_completed['disappointment_factor']))
        
        # Calculate correlations for partial tasks (<100%)
        disappointed_partial = df[(df['disappointment_factor'] > 0) & (df['completion_pct'] < 100.0)]
        corr_partial = None
        if not disappointed_partial.empty:
            corr_partial = float(disappointed_partial[f'grit_cap_{cap:.1f}'].corr(disappointed_partial['disappointment_factor']))
        
        # Overall correlation
        disappointed_all = df[df['disappointment_factor'] > 0]
        corr_overall = None
        if not disappointed_all.empty:
            corr_overall = float(disappointed_all[f'grit_cap_{cap:.1f}'].corr(disappointed_all['disappointment_factor']))
        
        mean_score = df[f'grit_cap_{cap:.1f}'].mean()
        results.append({
            'cap': cap,
            'correlation_completed': corr_completed,
            'correlation_partial': corr_partial,
            'correlation_overall': corr_overall,
            'mean_score': float(mean_score)
        })
    
    print()
    print("[INFO] Analysis complete!")
    print()
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Find where correlation approaches zero
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print("Correlation by Exponential Cap Value:")
    print()
    print(results_df[['cap', 'correlation_completed', 'correlation_partial', 'correlation_overall', 'mean_score']].to_string(index=False))
    print()
    
    # Find best cap values for completed tasks
    if results_df['correlation_completed'].notna().any():
        best_corr_idx = results_df['correlation_completed'].idxmax()
        best_cap = results_df.loc[best_corr_idx, 'cap']
        best_corr = results_df.loc[best_corr_idx, 'correlation_completed']
        
        print(f"Best correlation (completed tasks): {best_corr:.3f} at cap {best_cap:.1f}x")
        print()
    
    # Extrapolate to find ideal cap
    if len(results_df) >= 2 and results_df['correlation_completed'].notna().sum() >= 2:
        # Use linear interpolation/extrapolation
        valid_data = results_df[results_df['correlation_completed'].notna()].copy()
        if len(valid_data) >= 2:
            x = valid_data['cap'].values
            y = valid_data['correlation_completed'].values
            
            # Linear fit
            coeffs = np.polyfit(x, y, 1)
            
            # Find where correlation = 0
            if abs(coeffs[0]) > 1e-6:  # slope is not zero
                zero_cap = -coeffs[1] / coeffs[0]
                print(f"Extrapolated cap for zero correlation: {zero_cap:.2f}x")
                print(f"  (Based on linear fit: y = {coeffs[0]:.4f}x + {coeffs[1]:.4f})")
                print()
                
                # Find where correlation = 0.1 (slightly positive)
                positive_cap = (0.1 - coeffs[1]) / coeffs[0]
                print(f"Extrapolated cap for +0.1 correlation: {positive_cap:.2f}x")
                print()
                
                # Check if 2.3-3.0 range is appropriate
                if 2.3 <= zero_cap <= 3.0:
                    print(f"✓ Zero correlation falls within tested range (2.3-3.0)")
                elif zero_cap < 2.3:
                    print(f"⚠ Zero correlation below tested range - may need lower caps")
                else:
                    print(f"⚠ Zero correlation above tested range - may need higher caps")
                print()
    
    # Create visualization
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'analysis', 'factors', 'disappointment')
    os.makedirs(output_dir, exist_ok=True)
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot 1: Correlation vs Cap (completed tasks)
    ax1 = axes[0]
    valid_data = results_df[results_df['correlation_completed'].notna()]
    if not valid_data.empty:
        ax1.plot(valid_data['cap'], valid_data['correlation_completed'], 'b-o', linewidth=2, markersize=8, label='Completed (100%+)')
    ax1.axhline(y=0, color='r', linestyle='--', linewidth=1, label='Zero correlation')
    ax1.axhline(y=0.1, color='g', linestyle='--', linewidth=1, alpha=0.5, label='+0.1 correlation')
    ax1.set_xlabel('Exponential Cap Value', fontsize=12)
    ax1.set_ylabel('Correlation with Disappointment', fontsize=12)
    ax1.set_title('Correlation vs Exponential Cap Value (Completed Tasks)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Add annotation for best point
    if results_df['correlation_completed'].notna().any():
        best_corr_idx = results_df['correlation_completed'].idxmax()
        best_cap = results_df.loc[best_corr_idx, 'cap']
        best_corr = results_df.loc[best_corr_idx, 'correlation_completed']
        ax1.annotate(f'Best: {best_cap:.1f}x\n({best_corr:.3f})', 
                    xy=(best_cap, best_corr), 
                    xytext=(10, 10), textcoords='offset points',
                    bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                    arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        # Add extrapolation line if we have enough points
        if len(valid_data) >= 2:
            x = valid_data['cap'].values
            y = valid_data['correlation_completed'].values
            coeffs = np.polyfit(x, y, 1)
            x_extrap = np.linspace(2.0, 3.5, 100)
            y_extrap = np.polyval(coeffs, x_extrap)
            ax1.plot(x_extrap, y_extrap, 'r--', alpha=0.5, linewidth=1, label='Linear extrapolation')
            ax1.legend()
    
    # Plot 2: Mean Score vs Cap
    ax2 = axes[1]
    ax2.plot(results_df['cap'], results_df['mean_score'], 'g-o', linewidth=2, markersize=6)
    ax2.set_xlabel('Exponential Cap Value', fontsize=12)
    ax2.set_ylabel('Mean Grit Score', fontsize=12)
    ax2.set_title('Mean Score vs Exponential Cap Value', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'exponential_cap_extrapolation.png'), dpi=150)
    print(f"[SUCCESS] Visualization saved to {output_dir}/exponential_cap_extrapolation.png")
    plt.close()
    
    # Save results to CSV
    results_df.to_csv(os.path.join(output_dir, 'exponential_cap_results.csv'), index=False)
    print(f"[SUCCESS] Results saved to {output_dir}/exponential_cap_results.csv")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Tested cap values: {', '.join([f'{c:.1f}x' for c in cap_values])}")
    if results_df['correlation_completed'].notna().any():
        best_corr_idx = results_df['correlation_completed'].idxmax()
        best_cap = results_df.loc[best_corr_idx, 'cap']
        best_corr = results_df.loc[best_corr_idx, 'correlation_completed']
        print(f"Best correlation (completed): {best_corr:.3f} at cap {best_cap:.1f}x")
        print()
        
        # Show trend
        valid_data = results_df[results_df['correlation_completed'].notna()].copy()
        if len(valid_data) >= 2:
            first_corr = valid_data.iloc[0]['correlation_completed']
            last_corr = valid_data.iloc[-1]['correlation_completed']
            improvement = last_corr - first_corr
            print(f"Correlation trend: {first_corr:.3f} → {last_corr:.3f} ({improvement:+.3f})")
            print()
            
            if improvement > 0:
                print("Trend: Correlation improves with higher cap values")
                if last_corr < 0:
                    print(f"  Still negative at {cap_values[-1]:.1f}x")
                else:
                    print(f"  Reached positive correlation at {cap_values[-1]:.1f}x")
            else:
                print("Trend: Correlation may be plateauing or decreasing")
            print()
    
    print()

if __name__ == '__main__':
    main()
