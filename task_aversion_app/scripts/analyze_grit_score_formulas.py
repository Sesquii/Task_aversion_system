"""Analyze and compare grit score formulas v1.2 vs v1.3.

This script:
1. Loads real task instance data
2. Calculates grit scores using both v1.2 and v1.3 formulas
3. Compares results and identifies differences
4. Generates analysis with notes and insights
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


def calculate_grit_scores(instances: pd.DataFrame, analytics: Analytics) -> pd.DataFrame:
    """Calculate grit scores using both v1.2 and v1.3 formulas."""
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
            # Calculate v1.2 (current implementation)
            grit_v1_2 = analytics.calculate_grit_score(row, completion_counts)
            
            # Calculate v1.3 (new implementation)
            grit_v1_3 = analytics.calculate_grit_score_v1_3(row, completion_counts)
            
            # Get task info
            task_id = row.get('task_id', '')
            task_name = row.get('task_name', '')
            completed_at = row.get('completed_at', '')
            
            # Parse actual_dict for additional info
            actual_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            completion_count = completion_counts.get(task_id, 1)
            
            # Calculate difference
            diff = grit_v1_3 - grit_v1_2
            diff_pct = (diff / grit_v1_2 * 100) if grit_v1_2 > 0 else 0.0
            
            results.append({
                'task_id': task_id,
                'task_name': task_name,
                'completed_at': completed_at,
                'completion_count': completion_count,
                'completion_pct': completion_pct,
                'grit_v1_2': grit_v1_2,
                'grit_v1_3': grit_v1_3,
                'difference': diff,
                'difference_pct': diff_pct
            })
            
        except Exception as e:
            print(f"[WARNING] Error processing instance {idx}: {e}")
            continue
    
    return pd.DataFrame(results)


def generate_analysis_report(results_df: pd.DataFrame) -> str:
    """Generate analysis report comparing v1.2 and v1.3."""
    if results_df.empty:
        return "No data to analyze."
    
    report = []
    report.append("=" * 80)
    report.append("GRIT SCORE FORMULA COMPARISON: v1.2 vs v1.3")
    report.append("=" * 80)
    report.append("")
    report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Instances Analyzed: {len(results_df)}")
    report.append("")
    
    # Summary Statistics
    report.append("-" * 80)
    report.append("SUMMARY STATISTICS")
    report.append("-" * 80)
    report.append("")
    
    report.append(f"Grit Score v1.2:")
    report.append(f"  Mean:   {results_df['grit_v1_2'].mean():.2f}")
    report.append(f"  Median: {results_df['grit_v1_2'].median():.2f}")
    report.append(f"  Min:    {results_df['grit_v1_2'].min():.2f}")
    report.append(f"  Max:    {results_df['grit_v1_2'].max():.2f}")
    report.append(f"  Std:    {results_df['grit_v1_2'].std():.2f}")
    report.append("")
    
    report.append(f"Grit Score v1.3:")
    report.append(f"  Mean:   {results_df['grit_v1_3'].mean():.2f}")
    report.append(f"  Median: {results_df['grit_v1_3'].median():.2f}")
    report.append(f"  Min:    {results_df['grit_v1_3'].min():.2f}")
    report.append(f"  Max:    {results_df['grit_v1_3'].max():.2f}")
    report.append(f"  Std:    {results_df['grit_v1_3'].std():.2f}")
    report.append("")
    
    report.append(f"Difference (v1.3 - v1.2):")
    report.append(f"  Mean:   {results_df['difference'].mean():.2f}")
    report.append(f"  Median: {results_df['difference'].median():.2f}")
    report.append(f"  Min:    {results_df['difference'].min():.2f}")
    report.append(f"  Max:    {results_df['difference'].max():.2f}")
    report.append(f"  Std:    {results_df['difference'].std():.2f}")
    report.append("")
    
    # Difference Analysis
    report.append("-" * 80)
    report.append("DIFFERENCE ANALYSIS")
    report.append("-" * 80)
    report.append("")
    
    increased = results_df[results_df['difference'] > 0]
    decreased = results_df[results_df['difference'] < 0]
    unchanged = results_df[results_df['difference'] == 0]
    
    report.append(f"Instances with increased score (v1.3 > v1.2): {len(increased)} ({len(increased)/len(results_df)*100:.1f}%)")
    report.append(f"Instances with decreased score (v1.3 < v1.2): {len(decreased)} ({len(decreased)/len(results_df)*100:.1f}%)")
    report.append(f"Instances with unchanged score (v1.3 = v1.2): {len(unchanged)} ({len(unchanged)/len(results_df)*100:.1f}%)")
    report.append("")
    
    if len(increased) > 0:
        report.append(f"Largest increases:")
        top_increases = increased.nlargest(5, 'difference')
        for idx, row in top_increases.iterrows():
            report.append(f"  {row['task_name']} (count={row['completion_count']}): "
                         f"v1.2={row['grit_v1_2']:.2f} → v1.3={row['grit_v1_3']:.2f} "
                         f"(+{row['difference']:.2f}, +{row['difference_pct']:.1f}%)")
        report.append("")
    
    if len(decreased) > 0:
        report.append(f"Largest decreases:")
        top_decreases = decreased.nsmallest(5, 'difference')
        for idx, row in top_decreases.iterrows():
            report.append(f"  {row['task_name']} (count={row['completion_count']}): "
                         f"v1.2={row['grit_v1_2']:.2f} → v1.3={row['grit_v1_3']:.2f} "
                         f"({row['difference']:.2f}, {row['difference_pct']:.1f}%)")
        report.append("")
    
    # Completion Count Analysis
    report.append("-" * 80)
    report.append("COMPLETION COUNT ANALYSIS")
    report.append("-" * 80)
    report.append("")
    
    # Group by completion count ranges
    results_df['count_range'] = pd.cut(
        results_df['completion_count'],
        bins=[0, 1, 5, 10, 25, 50, 100, float('inf')],
        labels=['1', '2-5', '6-10', '11-25', '26-50', '51-100', '100+']
    )
    
    for count_range in results_df['count_range'].cat.categories:
        subset = results_df[results_df['count_range'] == count_range]
        if len(subset) > 0:
            avg_diff = subset['difference'].mean()
            avg_diff_pct = subset['difference_pct'].mean()
            report.append(f"Completion count {count_range}:")
            report.append(f"  Instances: {len(subset)}")
            report.append(f"  Avg difference: {avg_diff:.2f} ({avg_diff_pct:+.1f}%)")
            report.append("")
    
    # Correlation Analysis
    report.append("-" * 80)
    report.append("CORRELATION ANALYSIS")
    report.append("-" * 80)
    report.append("")
    
    corr_completion_count = results_df['difference'].corr(results_df['completion_count'])
    corr_completion_pct = results_df['difference'].corr(results_df['completion_pct'])
    
    report.append(f"Correlation between difference and completion_count: {corr_completion_count:.3f}")
    report.append(f"Correlation between difference and completion_pct: {corr_completion_pct:.3f}")
    report.append("")
    
    # Key Insights
    report.append("-" * 80)
    report.append("KEY INSIGHTS")
    report.append("-" * 80)
    report.append("")
    
    # Check if persistence_factor integration is working as expected
    high_count = results_df[results_df['completion_count'] >= 10]
    if len(high_count) > 0:
        avg_diff_high = high_count['difference'].mean()
        if avg_diff_high < 0:
            report.append("1. HIGH COMPLETION COUNT TASKS (10+):")
            report.append(f"   Average difference: {avg_diff_high:.2f}")
            report.append("   [INSIGHT] v1.3 shows lower scores for high completion count tasks.")
            report.append("   This is expected - persistence_factor makes consistency harder to max out.")
            report.append("")
    
    low_count = results_df[results_df['completion_count'] <= 3]
    if len(low_count) > 0:
        avg_diff_low = low_count['difference'].mean()
        report.append("2. LOW COMPLETION COUNT TASKS (1-3):")
        report.append(f"   Average difference: {avg_diff_low:.2f}")
        if abs(avg_diff_low) < 1.0:
            report.append("   [INSIGHT] Minimal impact on new tasks (expected).")
        report.append("")
    
    # Overall assessment
    mean_abs_diff = results_df['difference'].abs().mean()
    report.append("3. OVERALL ASSESSMENT:")
    report.append(f"   Mean absolute difference: {mean_abs_diff:.2f}")
    if mean_abs_diff < 5.0:
        report.append("   [INSIGHT] Formulas are relatively similar (low mean absolute difference).")
    elif mean_abs_diff < 15.0:
        report.append("   [INSIGHT] Moderate differences between formulas.")
    else:
        report.append("   [INSIGHT] Significant differences between formulas.")
    report.append("")
    
    # Recommendations
    report.append("-" * 80)
    report.append("RECOMMENDATIONS")
    report.append("-" * 80)
    report.append("")
    
    if corr_completion_count < -0.3:
        report.append("1. Strong negative correlation with completion_count suggests persistence_factor")
        report.append("   integration is working as intended (making consistency harder to max out).")
    elif corr_completion_count > 0.3:
        report.append("1. Positive correlation with completion_count - review persistence_factor scaling.")
    else:
        report.append("1. Weak correlation with completion_count - persistence_factor may need adjustment.")
    report.append("")
    
    if mean_abs_diff < 5.0:
        report.append("2. Formulas are similar - consider if v1.3 improvements justify the change.")
    else:
        report.append("2. Formulas show meaningful differences - validate which better captures grit.")
    report.append("")
    
    report.append("3. Review specific task examples to ensure changes align with grit definition:")
    report.append("   - Perseverance: continuing despite obstacles")
    report.append("   - Persistence: repeated completion over time")
    report.append("   - Both should be rewarded appropriately")
    report.append("")
    
    return "\n".join(report)


def save_detailed_results(results_df: pd.DataFrame, output_path: str):
    """Save detailed results to CSV."""
    results_df.to_csv(output_path, index=False)
    print(f"[INFO] Detailed results saved to: {output_path}")


def main():
    """Main analysis function."""
    print("=" * 80)
    print("GRIT SCORE FORMULA ANALYSIS: v1.2 vs v1.3")
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
        
        # Calculate grit scores
        print("[INFO] Calculating grit scores (v1.2 and v1.3)...")
        results_df = calculate_grit_scores(instances, analytics)
        
        if results_df.empty:
            print("[ERROR] No results generated. Check data availability.")
            return
        
        print(f"[INFO] Calculated scores for {len(results_df)} instances")
        
        # Generate report
        print("[INFO] Generating analysis report...")
        report = generate_analysis_report(results_df)
        
        # Print report
        print("\n" + report)
        
        # Save results
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(output_dir, exist_ok=True)
        
        report_path = os.path.join(output_dir, 'grit_score_comparison_report.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n[INFO] Report saved to: {report_path}")
        
        csv_path = os.path.join(output_dir, 'grit_score_comparison_results.csv')
        save_detailed_results(results_df, csv_path)
        
        print("\n[SUCCESS] Analysis complete!")
        
    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

