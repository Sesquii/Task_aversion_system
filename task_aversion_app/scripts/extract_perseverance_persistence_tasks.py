"""Extract tasks with high perseverance only, high persistence only, and both.

This script:
1. Calculates perseverance_factor and persistence_factor separately for each task
2. Identifies tasks with high perseverance only, high persistence only, and both
3. Shows their values and characteristics
4. Provides data for synergy multiplier design
"""

import sys
import os
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.analytics import Analytics
from backend.instance_manager import InstanceManager


def load_task_instances() -> pd.DataFrame:
    """Load task instances from database or CSV.
    
    Note: Analysis script - uses user_id=None to analyze data across all users.
    """
    try:
        analytics = Analytics()
        # Analysis script: intentionally use user_id=None to analyze across all users
        instances = analytics._load_instances(user_id=None)
        return instances
    except Exception as e:
        print(f"[WARNING] Could not load from database: {e}")
        print("[INFO] Trying CSV fallback...")
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'task_instances.csv')
        if os.path.exists(csv_path):
            return pd.read_csv(csv_path)
        else:
            raise FileNotFoundError(f"Could not find task instances data at {csv_path}")


def calculate_persistence_factor(completion_count: int) -> float:
    """Calculate persistence factor (completion count multiplier)."""
    # Raw growth: power curve to approximate anchors
    raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
    # Familiarity decay after 100+ completions
    if completion_count > 100:
        decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
    else:
        decay = 1.0
    return max(1.0, min(5.0, raw_multiplier * decay))


def calculate_task_completion_counts(instances: pd.DataFrame) -> Dict[str, int]:
    """Calculate completion counts per task_id."""
    completion_counts = {}
    
    # Filter completed instances
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    
    if not completed.empty:
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # Count completions per task_id
        counts = completed.groupby('task_id').size()
        completion_counts = counts.to_dict()
    
    return completion_counts


def extract_perseverance_persistence_data(instances: pd.DataFrame, analytics: Analytics) -> pd.DataFrame:
    """Extract perseverance and persistence factors for each task instance."""
    results = []
    
    # Get completion counts
    completion_counts = calculate_task_completion_counts(instances)
    
    # Filter completed instances
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    
    if completed.empty:
        print("[WARNING] No completed instances found.")
        return pd.DataFrame()
    
    print(f"[INFO] Processing {len(completed)} completed instances...")
    
    for idx, row in completed.iterrows():
        try:
            task_id = row.get('task_id', '')
            task_name = row.get('task_name', '')
            completed_at = row.get('completed_at', '')
            
            # Get completion count
            completion_count = completion_counts.get(task_id, 1)
            
            # Calculate persistence_factor (completion count multiplier)
            persistence_factor = calculate_persistence_factor(completion_count)
            
            # Calculate perseverance_factor (obstacle overcoming)
            # We need to calculate this using the v1.3 method
            # First calculate persistence_factor for the perseverance calculation
            perseverance_factor = analytics.calculate_perseverance_factor_v1_3(
                row=row,
                task_completion_counts=completion_counts,
                persistence_factor=persistence_factor
            )
            
            # Parse actual_dict for additional info
            actual_dict = {}
            predicted_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
            if 'predicted_dict' in row and row.get('predicted_dict'):
                try:
                    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
                except (json.JSONDecodeError, TypeError):
                    predicted_dict = {}
            
            # Get task characteristics
            cognitive_load = row.get('cognitive_load', 0)
            emotional_load = row.get('emotional_load', 0)
            initial_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion') or 0
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            
            results.append({
                'task_id': task_id,
                'task_name': task_name,
                'completed_at': completed_at,
                'completion_count': completion_count,
                'completion_pct': completion_pct,
                'perseverance_factor': perseverance_factor,
                'persistence_factor': persistence_factor,
                'cognitive_load': cognitive_load,
                'emotional_load': emotional_load,
                'initial_aversion': initial_aversion,
                'combined_load': (float(cognitive_load or 0) + float(emotional_load or 0)) / 2.0
            })
            
        except Exception as e:
            print(f"[WARNING] Error processing instance {idx}: {e}")
            continue
    
    return pd.DataFrame(results)


def classify_tasks(results_df: pd.DataFrame) -> pd.DataFrame:
    """Classify tasks into categories based on perseverance and persistence."""
    if results_df.empty:
        return pd.DataFrame()
    
    # Calculate thresholds (using percentiles)
    perseverance_median = results_df['perseverance_factor'].median()
    perseverance_75th = results_df['perseverance_factor'].quantile(0.75)
    persistence_median = results_df['persistence_factor'].median()
    persistence_75th = results_df['persistence_factor'].quantile(0.75)
    
    # Define "high" as 75th percentile or above
    high_perseverance_threshold = perseverance_75th
    high_persistence_threshold = persistence_75th
    
    # Classify tasks
    def classify_row(row):
        high_perseverance = row['perseverance_factor'] >= high_perseverance_threshold
        high_persistence = row['persistence_factor'] >= high_persistence_threshold
        
        if high_perseverance and high_persistence:
            return 'both_high'
        elif high_perseverance and not high_persistence:
            return 'high_perseverance_only'
        elif not high_perseverance and high_persistence:
            return 'high_persistence_only'
        else:
            return 'neither_high'
    
    results_df['category'] = results_df.apply(classify_row, axis=1)
    results_df['high_perseverance'] = results_df['perseverance_factor'] >= high_perseverance_threshold
    results_df['high_persistence'] = results_df['persistence_factor'] >= high_persistence_threshold
    
    return results_df, {
        'perseverance_median': perseverance_median,
        'perseverance_75th': perseverance_75th,
        'persistence_median': persistence_median,
        'persistence_75th': persistence_75th
    }


def generate_analysis_report(results_df: pd.DataFrame, thresholds: Dict) -> str:
    """Generate analysis report."""
    if results_df.empty:
        return "No data to analyze."
    
    report = []
    report.append("=" * 80)
    report.append("PERSEVERANCE vs PERSISTENCE TASK ANALYSIS")
    report.append("=" * 80)
    report.append("")
    report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Instances Analyzed: {len(results_df)}")
    report.append("")
    
    # Thresholds
    report.append("-" * 80)
    report.append("THRESHOLDS")
    report.append("-" * 80)
    report.append("")
    report.append(f"High Perseverance Threshold (75th percentile): {thresholds['perseverance_75th']:.3f}")
    report.append(f"High Persistence Threshold (75th percentile): {thresholds['persistence_75th']:.3f}")
    report.append(f"Perseverance Median: {thresholds['perseverance_median']:.3f}")
    report.append(f"Persistence Median: {thresholds['persistence_median']:.3f}")
    report.append("")
    
    # Category counts
    report.append("-" * 80)
    report.append("CATEGORY BREAKDOWN")
    report.append("-" * 80)
    report.append("")
    
    category_counts = results_df['category'].value_counts()
    for category, count in category_counts.items():
        pct = count / len(results_df) * 100
        report.append(f"{category.replace('_', ' ').title()}: {count} ({pct:.1f}%)")
    report.append("")
    
    # High Perseverance Only
    report.append("-" * 80)
    report.append("HIGH PERSEVERANCE ONLY (High Obstacle Overcoming, Low Completion Count)")
    report.append("-" * 80)
    report.append("")
    
    high_perseverance_only = results_df[results_df['category'] == 'high_perseverance_only']
    if len(high_perseverance_only) > 0:
        report.append(f"Count: {len(high_perseverance_only)}")
        report.append("")
        report.append("Statistics:")
        report.append(f"  Perseverance Factor: Mean={high_perseverance_only['perseverance_factor'].mean():.3f}, "
                     f"Median={high_perseverance_only['perseverance_factor'].median():.3f}, "
                     f"Range=[{high_perseverance_only['perseverance_factor'].min():.3f}, {high_perseverance_only['perseverance_factor'].max():.3f}]")
        report.append(f"  Persistence Factor: Mean={high_perseverance_only['persistence_factor'].mean():.3f}, "
                     f"Median={high_perseverance_only['persistence_factor'].median():.3f}, "
                     f"Range=[{high_perseverance_only['persistence_factor'].min():.3f}, {high_perseverance_only['persistence_factor'].max():.3f}]")
        report.append(f"  Completion Count: Mean={high_perseverance_only['completion_count'].mean():.1f}, "
                     f"Median={high_perseverance_only['completion_count'].median():.1f}, "
                     f"Range=[{high_perseverance_only['completion_count'].min():.0f}, {high_perseverance_only['completion_count'].max():.0f}]")
        report.append(f"  Combined Load: Mean={high_perseverance_only['combined_load'].mean():.1f}, "
                     f"Median={high_perseverance_only['combined_load'].median():.1f}")
        report.append(f"  Initial Aversion: Mean={high_perseverance_only['initial_aversion'].mean():.1f}, "
                     f"Median={high_perseverance_only['initial_aversion'].median():.1f}")
        report.append("")
        report.append("Top 10 Tasks (by perseverance_factor):")
        top_perseverance = high_perseverance_only.nlargest(10, 'perseverance_factor')
        for idx, row in top_perseverance.iterrows():
            report.append(f"  {row['task_name']}: perseverance={row['perseverance_factor']:.3f}, "
                         f"persistence={row['persistence_factor']:.3f}, count={row['completion_count']:.0f}, "
                         f"load={row['combined_load']:.1f}, aversion={row['initial_aversion']:.1f}")
    else:
        report.append("No tasks found in this category.")
    report.append("")
    
    # High Persistence Only
    report.append("-" * 80)
    report.append("HIGH PERSISTENCE ONLY (High Completion Count, Low Obstacle Overcoming)")
    report.append("-" * 80)
    report.append("")
    
    high_persistence_only = results_df[results_df['category'] == 'high_persistence_only']
    if len(high_persistence_only) > 0:
        report.append(f"Count: {len(high_persistence_only)}")
        report.append("")
        report.append("Statistics:")
        report.append(f"  Perseverance Factor: Mean={high_persistence_only['perseverance_factor'].mean():.3f}, "
                     f"Median={high_persistence_only['perseverance_factor'].median():.3f}, "
                     f"Range=[{high_persistence_only['perseverance_factor'].min():.3f}, {high_persistence_only['perseverance_factor'].max():.3f}]")
        report.append(f"  Persistence Factor: Mean={high_persistence_only['persistence_factor'].mean():.3f}, "
                     f"Median={high_persistence_only['persistence_factor'].median():.3f}, "
                     f"Range=[{high_persistence_only['persistence_factor'].min():.3f}, {high_persistence_only['persistence_factor'].max():.3f}]")
        report.append(f"  Completion Count: Mean={high_persistence_only['completion_count'].mean():.1f}, "
                     f"Median={high_persistence_only['completion_count'].median():.1f}, "
                     f"Range=[{high_persistence_only['completion_count'].min():.0f}, {high_persistence_only['completion_count'].max():.0f}]")
        report.append(f"  Combined Load: Mean={high_persistence_only['combined_load'].mean():.1f}, "
                     f"Median={high_persistence_only['combined_load'].median():.1f}")
        report.append(f"  Initial Aversion: Mean={high_persistence_only['initial_aversion'].mean():.1f}, "
                     f"Median={high_persistence_only['initial_aversion'].median():.1f}")
        report.append("")
        report.append("Top 10 Tasks (by persistence_factor):")
        top_persistence = high_persistence_only.nlargest(10, 'persistence_factor')
        for idx, row in top_persistence.iterrows():
            report.append(f"  {row['task_name']}: perseverance={row['perseverance_factor']:.3f}, "
                         f"persistence={row['persistence_factor']:.3f}, count={row['completion_count']:.0f}, "
                         f"load={row['combined_load']:.1f}, aversion={row['initial_aversion']:.1f}")
    else:
        report.append("No tasks found in this category.")
    report.append("")
    
    # Both High
    report.append("-" * 80)
    report.append("BOTH HIGH (High Obstacle Overcoming AND High Completion Count)")
    report.append("-" * 80)
    report.append("")
    
    both_high = results_df[results_df['category'] == 'both_high']
    if len(both_high) > 0:
        report.append(f"Count: {len(both_high)}")
        report.append("")
        report.append("Statistics:")
        report.append(f"  Perseverance Factor: Mean={both_high['perseverance_factor'].mean():.3f}, "
                     f"Median={both_high['perseverance_factor'].median():.3f}, "
                     f"Range=[{both_high['perseverance_factor'].min():.3f}, {both_high['perseverance_factor'].max():.3f}]")
        report.append(f"  Persistence Factor: Mean={both_high['persistence_factor'].mean():.3f}, "
                     f"Median={both_high['persistence_factor'].median():.3f}, "
                     f"Range=[{both_high['persistence_factor'].min():.3f}, {both_high['persistence_factor'].max():.3f}]")
        report.append(f"  Completion Count: Mean={both_high['completion_count'].mean():.1f}, "
                     f"Median={both_high['completion_count'].median():.1f}, "
                     f"Range=[{both_high['completion_count'].min():.0f}, {both_high['completion_count'].max():.0f}]")
        report.append(f"  Combined Load: Mean={both_high['combined_load'].mean():.1f}, "
                     f"Median={both_high['combined_load'].median():.1f}")
        report.append(f"  Initial Aversion: Mean={both_high['initial_aversion'].mean():.1f}, "
                     f"Median={both_high['initial_aversion'].median():.1f}")
        report.append("")
        report.append("Top 10 Tasks (by combined score):")
        both_high['combined_score'] = both_high['perseverance_factor'] * both_high['persistence_factor']
        top_both = both_high.nlargest(10, 'combined_score')
        for idx, row in top_both.iterrows():
            report.append(f"  {row['task_name']}: perseverance={row['perseverance_factor']:.3f}, "
                         f"persistence={row['persistence_factor']:.3f}, count={row['completion_count']:.0f}, "
                         f"load={row['combined_load']:.1f}, aversion={row['initial_aversion']:.1f}, "
                         f"combined={row['combined_score']:.3f}")
    else:
        report.append("No tasks found in this category.")
    report.append("")
    
    # Synergy Analysis
    report.append("-" * 80)
    report.append("SYNERGY ANALYSIS")
    report.append("-" * 80)
    report.append("")
    
    report.append("Current Formula (v1.3):")
    report.append("  grit_score = base_score * (perseverance_factor_scaled * focus_factor * passion_factor * time_bonus)")
    report.append("  Note: persistence_factor is only used in consistency component of perseverance_factor")
    report.append("")
    
    report.append("Synergy Opportunity:")
    report.append("  Tasks with BOTH high perseverance AND high persistence should get a bonus multiplier")
    report.append("  This rewards the combination of:")
    report.append("    - Perseverance: Continuing despite obstacles (high load, high aversion)")
    report.append("    - Persistence: Repeated completion over time (high completion count)")
    report.append("")
    
    if len(both_high) > 0:
        avg_perseverance = both_high['perseverance_factor'].mean()
        avg_persistence = both_high['persistence_factor'].mean()
        report.append(f"Average values for 'both high' tasks:")
        report.append(f"  Perseverance: {avg_perseverance:.3f}")
        report.append(f"  Persistence: {avg_persistence:.3f}")
        report.append(f"  Product: {avg_perseverance * avg_persistence:.3f}")
        report.append("")
        report.append("Suggested Synergy Multiplier:")
        report.append("  synergy_multiplier = 1.0 + (perseverance_bonus * persistence_bonus * synergy_strength)")
        report.append("  where:")
        report.append("    perseverance_bonus = max(0, (perseverance_factor - threshold) / (1.0 - threshold))")
        report.append("    persistence_bonus = max(0, (persistence_factor - threshold) / (5.0 - threshold))")
        report.append("    synergy_strength = 0.1 to 0.2 (10-20% bonus when both are high)")
        report.append("")
        report.append("Example:")
        report.append(f"  If perseverance={avg_perseverance:.3f} (threshold={thresholds['perseverance_75th']:.3f}):")
        pers_bonus = max(0, (avg_perseverance - thresholds['perseverance_75th']) / (1.0 - thresholds['perseverance_75th']))
        report.append(f"    perseverance_bonus = {pers_bonus:.3f}")
        report.append(f"  If persistence={avg_persistence:.3f} (threshold={thresholds['persistence_75th']:.3f}):")
        persis_bonus = max(0, (avg_persistence - thresholds['persistence_75th']) / (5.0 - thresholds['persistence_75th']))
        report.append(f"    persistence_bonus = {persis_bonus:.3f}")
        report.append(f"  With synergy_strength=0.15:")
        synergy = 1.0 + (pers_bonus * persis_bonus * 0.15)
        report.append(f"    synergy_multiplier = {synergy:.3f} ({((synergy-1.0)*100):.1f}% bonus)")
    report.append("")
    
    return "\n".join(report)


def main():
    """Main analysis function."""
    print("=" * 80)
    print("PERSEVERANCE vs PERSISTENCE TASK EXTRACTION")
    print("=" * 80)
    print("")
    
    try:
        # Load data
        print("[INFO] Loading task instances...")
        instances = load_task_instances()
        print(f"[INFO] Loaded {len(instances)} instances")
        
        # Initialize analytics
        print("[INFO] Initializing analytics...")
        analytics = Analytics()
        
        # Extract data
        print("[INFO] Extracting perseverance and persistence factors...")
        results_df = extract_perseverance_persistence_data(instances, analytics)
        
        if results_df.empty:
            print("[ERROR] No results generated. Check data availability.")
            return 1
        
        print(f"[INFO] Extracted data for {len(results_df)} instances")
        
        # Classify tasks
        print("[INFO] Classifying tasks...")
        results_df, thresholds = classify_tasks(results_df)
        
        # Generate report
        print("[INFO] Generating analysis report...")
        report = generate_analysis_report(results_df, thresholds)
        
        # Print report
        print("\n" + report)
        
        # Save results
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(output_dir, exist_ok=True)
        
        report_path = os.path.join(output_dir, 'perseverance_persistence_analysis.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n[INFO] Report saved to: {report_path}")
        
        csv_path = os.path.join(output_dir, 'perseverance_persistence_data.csv')
        results_df.to_csv(csv_path, index=False)
        print(f"[INFO] Detailed data saved to: {csv_path}")
        
        # Save categorized data
        for category in ['high_perseverance_only', 'high_persistence_only', 'both_high']:
            category_df = results_df[results_df['category'] == category]
            if len(category_df) > 0:
                category_path = os.path.join(output_dir, f'{category}_tasks.csv')
                category_df.to_csv(category_path, index=False)
                print(f"[INFO] {category.replace('_', ' ').title()} tasks saved to: {category_path}")
        
        print("\n[SUCCESS] Analysis complete!")
        
    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

