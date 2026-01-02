"""Compare grit score formulas v1.2 vs v1.5c with performance analysis.

This script:
1. Calculates grit scores using both v1.2 and v1.5c
2. Compares results and identifies differences
3. Measures performance (timing) for both versions
4. Analyzes which tasks benefit most from v1.5c
5. Provides takeaways and recommendations
"""

import sys
import os
import pandas as pd
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.analytics import Analytics


def load_task_instances() -> pd.DataFrame:
    """Load task instances from database or CSV."""
    # Check if CSV is explicitly requested
    use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
    
    if use_csv:
        # CSV backend (explicitly requested)
        csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'task_instances.csv')
        if os.path.exists(csv_path):
            print(f"[INFO] Loading instances from CSV: {csv_path}")
            return pd.read_csv(csv_path)
        else:
            raise FileNotFoundError(f"Could not find task instances data at {csv_path}")
    else:
        # Database backend (default)
        # Ensure DATABASE_URL is set to default SQLite if not already set
        if not os.getenv('DATABASE_URL'):
            os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
        
        try:
            from backend.database import get_session, TaskInstance
            print("[INFO] Loading instances from database...")
            with get_session() as session:
                # Load all instances from database
                instances = session.query(TaskInstance).all()
                if not instances:
                    print("[WARNING] No instances found in database")
                    return pd.DataFrame()
                
                # Convert to list of dicts
                data = [instance.to_dict() for instance in instances]
                
                # Convert to DataFrame
                df = pd.DataFrame(data).fillna('')
                
                print(f"[INFO] Loaded {len(df)} instances from database")
                return df
        except Exception as e:
            print(f"[WARNING] Could not load from database: {e}")
            print("[INFO] Trying CSV fallback...")
            csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'task_instances.csv')
            if os.path.exists(csv_path):
                return pd.read_csv(csv_path)
            else:
                raise FileNotFoundError(f"Could not load from database and CSV not found at {csv_path}")


def calculate_task_completion_counts(instances: pd.DataFrame) -> Dict[str, int]:
    """Calculate completion counts per task_id."""
    completion_counts = {}
    
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    
    if not completed.empty:
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        counts = completed.groupby('task_id').size()
        completion_counts = counts.to_dict()
    
    return completion_counts


def compare_grit_scores(instances: pd.DataFrame, analytics: Analytics) -> Tuple[pd.DataFrame, Dict]:
    """Compare grit scores using v1.2 and v1.5c with performance timing."""
    results = []
    performance_stats = {
        'v1_2_times': [],
        'v1_5c_times': [],
        'v1_2_total': 0.0,
        'v1_5c_total': 0.0,
        'v1_2_avg': 0.0,
        'v1_5c_avg': 0.0,
        'overhead': 0.0,
        'overhead_pct': 0.0
    }
    
    # Get completion counts
    completion_counts = calculate_task_completion_counts(instances)
    
    # Pre-calculate statistics for v1.5c (shared across all instances)
    print("[INFO] Pre-calculating statistics for v1.5c...")
    stats_start = time.perf_counter()
    stats_cache = analytics._calculate_perseverance_persistence_stats(instances)
    stats_time = time.perf_counter() - stats_start
    print(f"[INFO] Statistics calculation took {stats_time*1000:.2f}ms")
    
    # Filter completed instances
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    
    if completed.empty:
        print("[WARNING] No completed instances found.")
        return pd.DataFrame(), performance_stats
    
    print(f"[INFO] Processing {len(completed)} completed instances...")
    
    for idx, row in completed.iterrows():
        try:
            task_id = row.get('task_id', '')
            task_name = row.get('task_name', '')
            completed_at = row.get('completed_at', '')
            
            # Calculate v1.2 (current implementation)
            v1_2_start = time.perf_counter()
            grit_v1_2 = analytics.calculate_grit_score(row, completion_counts)
            v1_2_time = time.perf_counter() - v1_2_start
            performance_stats['v1_2_times'].append(v1_2_time)
            performance_stats['v1_2_total'] += v1_2_time
            
            # Calculate v1.5c (hybrid with updated bonuses)
            v1_5c_start = time.perf_counter()
            grit_v1_5c = analytics.calculate_grit_score_v1_5c_hybrid(row, completion_counts, stats_cache)
            v1_5c_time = time.perf_counter() - v1_5c_start
            performance_stats['v1_5c_times'].append(v1_5c_time)
            performance_stats['v1_5c_total'] += v1_5c_time
            
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
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            completion_count = completion_counts.get(task_id, 1)
            cognitive_load = float(actual_dict.get('cognitive_load', 0) or 0)
            emotional_load = float(actual_dict.get('emotional_load', 0) or 0)
            combined_load = (cognitive_load + emotional_load) / 2.0
            
            # Calculate difference
            diff = grit_v1_5c - grit_v1_2
            diff_pct = (diff / grit_v1_2 * 100) if grit_v1_2 > 0 else 0.0
            
            # Performance overhead
            overhead = v1_5c_time - v1_2_time
            overhead_pct = (overhead / v1_2_time * 100) if v1_2_time > 0 else 0.0
            
            results.append({
                'task_id': task_id,
                'task_name': task_name,
                'completed_at': completed_at,
                'completion_count': completion_count,
                'completion_pct': completion_pct,
                'combined_load': combined_load,
                'grit_v1_2': grit_v1_2,
                'grit_v1_5c': grit_v1_5c,
                'difference': diff,
                'difference_pct': diff_pct,
                'v1_2_time_ms': v1_2_time * 1000,
                'v1_5c_time_ms': v1_5c_time * 1000,
                'overhead_ms': overhead * 1000,
                'overhead_pct': overhead_pct
            })
            
        except Exception as e:
            print(f"[WARNING] Error processing instance {idx}: {e}")
            continue
    
    # Calculate performance statistics
    if performance_stats['v1_2_times']:
        performance_stats['v1_2_avg'] = np.mean(performance_stats['v1_2_times']) * 1000  # Convert to ms
        performance_stats['v1_5c_avg'] = np.mean(performance_stats['v1_5c_times']) * 1000
        performance_stats['overhead'] = (performance_stats['v1_5c_avg'] - performance_stats['v1_2_avg'])
        performance_stats['overhead_pct'] = (performance_stats['overhead'] / performance_stats['v1_2_avg'] * 100) if performance_stats['v1_2_avg'] > 0 else 0.0
    
    performance_stats['stats_calculation_time_ms'] = stats_time * 1000
    
    return pd.DataFrame(results), performance_stats


def generate_comparison_report(results_df: pd.DataFrame, performance_stats: Dict) -> str:
    """Generate comprehensive comparison report."""
    if results_df.empty:
        return "No data to analyze."
    
    report = []
    report.append("=" * 80)
    report.append("GRIT SCORE COMPARISON: v1.2 vs v1.5c")
    report.append("=" * 80)
    report.append("")
    report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Instances Analyzed: {len(results_df)}")
    report.append("")
    
    # Performance Analysis
    report.append("-" * 80)
    report.append("PERFORMANCE ANALYSIS")
    report.append("-" * 80)
    report.append("")
    report.append(f"Statistics Calculation (one-time): {performance_stats['stats_calculation_time_ms']:.2f}ms")
    report.append("")
    report.append(f"v1.2 Performance:")
    report.append(f"  Average time per instance: {performance_stats['v1_2_avg']:.2f}ms")
    report.append(f"  Total time: {performance_stats['v1_2_total']*1000:.2f}ms")
    report.append("")
    report.append(f"v1.5c Performance:")
    report.append(f"  Average time per instance: {performance_stats['v1_5c_avg']:.2f}ms")
    report.append(f"  Total time: {performance_stats['v1_5c_total']*1000:.2f}ms")
    report.append("")
    report.append(f"Performance Overhead:")
    report.append(f"  Additional time per instance: {performance_stats['overhead']:.2f}ms")
    report.append(f"  Overhead percentage: {performance_stats['overhead_pct']:.1f}%")
    report.append("")
    
    # Score Comparison
    report.append("-" * 80)
    report.append("SCORE COMPARISON")
    report.append("-" * 80)
    report.append("")
    report.append(f"Grit Score v1.2:")
    report.append(f"  Mean:   {results_df['grit_v1_2'].mean():.2f}")
    report.append(f"  Median: {results_df['grit_v1_2'].median():.2f}")
    report.append(f"  Min:    {results_df['grit_v1_2'].min():.2f}")
    report.append(f"  Max:    {results_df['grit_v1_2'].max():.2f}")
    report.append(f"  Std:    {results_df['grit_v1_2'].std():.2f}")
    report.append("")
    report.append(f"Grit Score v1.5c:")
    report.append(f"  Mean:   {results_df['grit_v1_5c'].mean():.2f}")
    report.append(f"  Median: {results_df['grit_v1_5c'].median():.2f}")
    report.append(f"  Min:    {results_df['grit_v1_5c'].min():.2f}")
    report.append(f"  Max:    {results_df['grit_v1_5c'].max():.2f}")
    report.append(f"  Std:    {results_df['grit_v1_5c'].std():.2f}")
    report.append("")
    report.append(f"Difference (v1.5c - v1.2):")
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
    
    report.append(f"Instances with increased score (v1.5c > v1.2): {len(increased)} ({len(increased)/len(results_df)*100:.1f}%)")
    report.append(f"Instances with decreased score (v1.5c < v1.2): {len(decreased)} ({len(decreased)/len(results_df)*100:.1f}%)")
    report.append(f"Instances with unchanged score (v1.5c = v1.2): {len(unchanged)} ({len(unchanged)/len(results_df)*100:.1f}%)")
    report.append("")
    
    if len(increased) > 0:
        report.append(f"Largest increases (Top 10):")
        top_increases = increased.nlargest(10, 'difference')
        for idx, row in top_increases.iterrows():
            report.append(f"  {row['task_name']} (count={row['completion_count']:.0f}, load={row['combined_load']:.1f}): "
                         f"v1.2={row['grit_v1_2']:.2f} → v1.5c={row['grit_v1_5c']:.2f} "
                         f"(+{row['difference']:.2f}, +{row['difference_pct']:.1f}%)")
        report.append("")
    
    if len(decreased) > 0:
        report.append(f"Largest decreases (Top 10):")
        top_decreases = decreased.nsmallest(10, 'difference')
        for idx, row in top_decreases.iterrows():
            report.append(f"  {row['task_name']} (count={row['completion_count']:.0f}, load={row['combined_load']:.1f}): "
                         f"v1.2={row['grit_v1_2']:.2f} → v1.5c={row['grit_v1_5c']:.2f} "
                         f"({row['difference']:.2f}, {row['difference_pct']:.1f}%)")
        report.append("")
    
    # Category Analysis
    report.append("-" * 80)
    report.append("CATEGORY ANALYSIS")
    report.append("-" * 80)
    report.append("")
    
    # High completion count
    high_count = results_df[results_df['completion_count'] >= 25]
    if len(high_count) > 0:
        avg_diff_high = high_count['difference'].mean()
        avg_diff_pct_high = high_count['difference_pct'].mean()
        report.append(f"High Completion Count (25+):")
        report.append(f"  Count: {len(high_count)}")
        report.append(f"  Avg difference: {avg_diff_high:.2f} ({avg_diff_pct_high:+.1f}%)")
        report.append("")
    
    # High load
    high_load = results_df[results_df['combined_load'] >= 50]
    if len(high_load) > 0:
        avg_diff_load = high_load['difference'].mean()
        avg_diff_pct_load = high_load['difference_pct'].mean()
        report.append(f"High Load (50+):")
        report.append(f"  Count: {len(high_load)}")
        report.append(f"  Avg difference: {avg_diff_load:.2f} ({avg_diff_pct_load:+.1f}%)")
        report.append("")
    
    # Both high
    both_high = results_df[(results_df['completion_count'] >= 25) & (results_df['combined_load'] >= 50)]
    if len(both_high) > 0:
        avg_diff_both = both_high['difference'].mean()
        avg_diff_pct_both = both_high['difference_pct'].mean()
        report.append(f"Both High (25+ count AND 50+ load):")
        report.append(f"  Count: {len(both_high)}")
        report.append(f"  Avg difference: {avg_diff_both:.2f} ({avg_diff_pct_both:+.1f}%)")
        report.append("")
    
    # Key Takeaways
    report.append("-" * 80)
    report.append("KEY TAKEAWAYS")
    report.append("-" * 80)
    report.append("")
    
    # Performance assessment
    if performance_stats['overhead_pct'] < 50:
        report.append("1. PERFORMANCE: ✅ ACCEPTABLE")
        report.append(f"   Overhead: {performance_stats['overhead_pct']:.1f}% ({performance_stats['overhead']:.2f}ms per instance)")
        report.append("   v1.5c adds minimal overhead while providing enhanced scoring.")
    elif performance_stats['overhead_pct'] < 100:
        report.append("1. PERFORMANCE: ⚠️ MODERATE OVERHEAD")
        report.append(f"   Overhead: {performance_stats['overhead_pct']:.1f}% ({performance_stats['overhead']:.2f}ms per instance)")
        report.append("   Consider caching statistics for better performance.")
    else:
        report.append("1. PERFORMANCE: ❌ HIGH OVERHEAD")
        report.append(f"   Overhead: {performance_stats['overhead_pct']:.1f}% ({performance_stats['overhead']:.2f}ms per instance)")
        report.append("   Performance impact may be significant. Consider optimization.")
    report.append("")
    
    # Score differences
    mean_abs_diff = results_df['difference'].abs().mean()
    if mean_abs_diff < 2.0:
        report.append("2. SCORE DIFFERENCES: ✅ MINIMAL")
        report.append(f"   Mean absolute difference: {mean_abs_diff:.2f}")
        report.append("   v1.5c produces similar scores to v1.2 for most tasks.")
    elif mean_abs_diff < 5.0:
        report.append("2. SCORE DIFFERENCES: ⚠️ MODERATE")
        report.append(f"   Mean absolute difference: {mean_abs_diff:.2f}")
        report.append("   v1.5c shows meaningful differences for some tasks.")
    else:
        report.append("2. SCORE DIFFERENCES: ✅ SIGNIFICANT")
        report.append(f"   Mean absolute difference: {mean_abs_diff:.2f}")
        report.append("   v1.5c produces notably different scores, better capturing grit.")
    report.append("")
    
    # Who benefits
    if len(increased) > len(decreased):
        report.append("3. WHO BENEFITS: ✅ MORE TASKS GET HIGHER SCORES")
        report.append(f"   {len(increased)} tasks increased vs {len(decreased)} decreased")
        report.append("   v1.5c rewards more tasks with higher scores (synergy bonuses).")
    elif len(increased) < len(decreased):
        report.append("3. WHO BENEFITS: ⚠️ MORE TASKS GET LOWER SCORES")
        report.append(f"   {len(increased)} tasks increased vs {len(decreased)} decreased")
        report.append("   v1.5c is more selective (only rewards 'both high' tasks).")
    else:
        report.append("3. WHO BENEFITS: ⚖️ BALANCED")
        report.append(f"   Similar number of increases and decreases")
        report.append("   v1.5c redistributes scores rather than uniformly increasing.")
    report.append("")
    
    # Recommendation
    report.append("-" * 80)
    report.append("RECOMMENDATION")
    report.append("-" * 80)
    report.append("")
    
    # Calculate recommendation score
    perf_score = 1.0 if performance_stats['overhead_pct'] < 50 else (0.5 if performance_stats['overhead_pct'] < 100 else 0.0)
    diff_score = 1.0 if mean_abs_diff > 2.0 else (0.5 if mean_abs_diff > 0.5 else 0.0)
    benefit_score = 1.0 if len(increased) > len(decreased) * 1.2 else 0.5
    
    total_score = perf_score + diff_score + benefit_score
    
    if total_score >= 2.5:
        report.append("✅ RECOMMENDED: Adopt v1.5c")
        report.append("")
        report.append("Reasons:")
        report.append("  - Performance overhead is acceptable")
        report.append("  - Score differences are meaningful")
        report.append("  - More tasks benefit from enhanced scoring")
        report.append("  - Better captures grit (perseverance + persistence synergy)")
    elif total_score >= 1.5:
        report.append("⚠️ CONDITIONAL: Consider v1.5c with optimizations")
        report.append("")
        report.append("Reasons:")
        report.append("  - Some performance concerns")
        report.append("  - Score differences may be worth it")
        report.append("  - Consider caching statistics for better performance")
    else:
        report.append("❌ NOT RECOMMENDED: Stick with v1.2")
        report.append("")
        report.append("Reasons:")
        report.append("  - Performance overhead too high")
        report.append("  - Score differences too small")
        report.append("  - Limited benefit over v1.2")
    report.append("")
    
    return "\n".join(report)


def main():
    """Main comparison function."""
    print("=" * 80)
    print("GRIT SCORE COMPARISON: v1.2 vs v1.5c")
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
        
        # Compare scores
        print("[INFO] Comparing grit scores (v1.2 vs v1.5c)...")
        print("[INFO] This may take a moment...")
        results_df, performance_stats = compare_grit_scores(instances, analytics)
        
        if results_df.empty:
            print("[ERROR] No results generated. Check data availability.")
            return 1
        
        print(f"[INFO] Compared {len(results_df)} instances")
        
        # Generate report
        print("[INFO] Generating comparison report...")
        report = generate_comparison_report(results_df, performance_stats)
        
        # Print report
        print("\n" + report)
        
        # Save results
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(output_dir, exist_ok=True)
        
        report_path = os.path.join(output_dir, 'grit_score_v1_2_vs_v1_5c_comparison.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n[INFO] Report saved to: {report_path}")
        
        csv_path = os.path.join(output_dir, 'grit_score_v1_2_vs_v1_5c_results.csv')
        results_df.to_csv(csv_path, index=False)
        print(f"[INFO] Detailed results saved to: {csv_path}")
        
        print("\n[SUCCESS] Comparison complete!")
        
    except Exception as e:
        print(f"\n[ERROR] Comparison failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

