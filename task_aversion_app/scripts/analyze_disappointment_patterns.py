#!/usr/bin/env python3
"""
Analyze disappointment patterns in task completion data.

Focus: Find instances with disappointment > 0 and completion >= 100%
to understand when disappointment occurs despite full task completion.
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
from backend.database import get_session, TaskInstance
from backend.analytics import Analytics

def load_instances_with_disappointment() -> pd.DataFrame:
    """Load all task instances and calculate disappointment metrics."""
    print("[INFO] Loading task instances from database...")
    
    analytics = Analytics()
    
    # Load all instances
    df = analytics._load_instances(completed_only=False)
    
    if df.empty:
        print("[WARNING] No instances found in database")
        return df
    
    print(f"[INFO] Loaded {len(df)} total instances")
    
    # Extract completion percentage from actual_dict
    def get_completion_pct(row):
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('completion_percent', 100) or 100)
            return 100.0
        except (KeyError, TypeError, ValueError):
            return 100.0
    
    df['completion_pct'] = df.apply(get_completion_pct, axis=1)
    
    # Extract time data
    def get_time_actual(row):
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('time_actual_minutes', 0) or 0)
            return 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0
    
    def get_time_estimate(row):
        try:
            predicted_dict = row.get('predicted_dict', {})
            if isinstance(predicted_dict, dict):
                return float(predicted_dict.get('time_estimate_minutes', 0) or 
                            predicted_dict.get('estimate', 0) or 0)
            return 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0
    
    df['time_actual'] = df.apply(get_time_actual, axis=1)
    df['time_estimate'] = df.apply(get_time_estimate, axis=1)
    df['time_ratio'] = df.apply(
        lambda row: row['time_actual'] / row['time_estimate'] if row['time_estimate'] > 0 else 0.0,
        axis=1
    )
    
    # Extract relief data
    def get_expected_relief(row):
        try:
            predicted_dict = row.get('predicted_dict', {})
            if isinstance(predicted_dict, dict):
                return float(predicted_dict.get('expected_relief', 0) or 0)
            return 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0
    
    def get_actual_relief(row):
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('actual_relief', 
                                            actual_dict.get('relief_score', 0)) or 0)
            return 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0
    
    df['expected_relief'] = df.apply(get_expected_relief, axis=1)
    df['actual_relief'] = df.apply(get_actual_relief, axis=1)
    df['net_relief'] = df['actual_relief'] - df['expected_relief']
    
    # Get disappointment factor (use stored if available, otherwise calculate)
    if 'disappointment_factor' in df.columns:
        df['disappointment_factor'] = pd.to_numeric(df['disappointment_factor'], errors='coerce').fillna(0.0)
    else:
        df['disappointment_factor'] = 0.0
    
    # Calculate if missing
    missing_disappointment = df['disappointment_factor'].isna() | (df['disappointment_factor'] == 0)
    if missing_disappointment.any():
        df.loc[missing_disappointment, 'disappointment_factor'] = df.loc[missing_disappointment, 'net_relief'].apply(
            lambda x: max(0.0, -float(x)) if pd.notna(x) and x < 0 else 0.0
        )
    
    df['disappointment_factor'] = df['disappointment_factor'].fillna(0.0)
    
    print(f"[INFO] Found {len(df[df['disappointment_factor'] > 0])} instances with disappointment > 0")
    
    return df

def analyze_disappointment_patterns(df: pd.DataFrame) -> Dict:
    """Analyze disappointment patterns by completion status."""
    results = {
        'summary': {},
        'high_completion_with_disappointment': [],
        'low_completion_with_disappointment': [],
        'statistics': {}
    }
    
    # Filter instances with disappointment
    disappointed = df[df['disappointment_factor'] > 0].copy()
    
    if disappointed.empty:
        print("[WARNING] No instances with disappointment found")
        return results
    
    # Summary statistics
    results['summary'] = {
        'total_with_disappointment': len(disappointed),
        'completed_with_disappointment': len(disappointed[disappointed['completion_pct'] >= 100]),
        'partial_with_disappointment': len(disappointed[disappointed['completion_pct'] < 100]),
        'avg_disappointment_completed': float(disappointed[disappointed['completion_pct'] >= 100]['disappointment_factor'].mean()) if len(disappointed[disappointed['completion_pct'] >= 100]) > 0 else 0.0,
        'avg_disappointment_partial': float(disappointed[disappointed['completion_pct'] < 100]['disappointment_factor'].mean()) if len(disappointed[disappointed['completion_pct'] < 100]) > 0 else 0.0,
    }
    
    # Focus: Instances with disappointment AND completion >= 100%
    high_completion = disappointed[disappointed['completion_pct'] >= 100].copy()
    
    print(f"\n[ANALYSIS] Found {len(high_completion)} instances with disappointment AND completion >= 100%")
    
    # Detailed analysis of high completion + disappointment
    for idx, row in high_completion.iterrows():
        instance_data = {
            'instance_id': row.get('instance_id', 'unknown'),
            'task_name': row.get('task_name', 'unknown'),
            'task_id': row.get('task_id', 'unknown'),
            'completion_pct': float(row['completion_pct']),
            'disappointment_factor': float(row['disappointment_factor']),
            'expected_relief': float(row['expected_relief']),
            'actual_relief': float(row['actual_relief']),
            'net_relief': float(row['net_relief']),
            'time_estimate': float(row['time_estimate']),
            'time_actual': float(row['time_actual']),
            'time_ratio': float(row['time_ratio']) if row['time_estimate'] > 0 else 0.0,
            'date': str(row.get('completed_at', row.get('created_at', 'unknown')))
        }
        results['high_completion_with_disappointment'].append(instance_data)
    
    # Also analyze low completion + disappointment for comparison
    low_completion = disappointed[disappointed['completion_pct'] < 100].copy()
    
    for idx, row in low_completion.head(20).iterrows():  # Limit to first 20 for brevity
        instance_data = {
            'instance_id': row.get('instance_id', 'unknown'),
            'task_name': row.get('task_name', 'unknown'),
            'completion_pct': float(row['completion_pct']),
            'disappointment_factor': float(row['disappointment_factor']),
            'expected_relief': float(row['expected_relief']),
            'actual_relief': float(row['actual_relief']),
            'time_estimate': float(row['time_estimate']),
            'time_actual': float(row['time_actual']),
            'time_ratio': float(row['time_ratio']) if row['time_estimate'] > 0 else 0.0,
        }
        results['low_completion_with_disappointment'].append(instance_data)
    
    # Statistics
    if not high_completion.empty:
        results['statistics']['high_completion'] = {
            'count': len(high_completion),
            'avg_disappointment': float(high_completion['disappointment_factor'].mean()),
            'max_disappointment': float(high_completion['disappointment_factor'].max()),
            'min_disappointment': float(high_completion['disappointment_factor'].min()),
            'avg_time_ratio': float(high_completion['time_ratio'].mean()) if high_completion['time_ratio'].notna().any() else 0.0,
            'avg_expected_relief': float(high_completion['expected_relief'].mean()),
            'avg_actual_relief': float(high_completion['actual_relief'].mean()),
            'avg_net_relief': float(high_completion['net_relief'].mean()),
        }
    
    if not low_completion.empty:
        results['statistics']['low_completion'] = {
            'count': len(low_completion),
            'avg_disappointment': float(low_completion['disappointment_factor'].mean()),
            'avg_time_ratio': float(low_completion['time_ratio'].mean()) if low_completion['time_ratio'].notna().any() else 0.0,
            'avg_expected_relief': float(low_completion['expected_relief'].mean()),
            'avg_actual_relief': float(low_completion['actual_relief'].mean()),
        }
    
    return results

def generate_report(results: Dict, output_file: str):
    """Generate a markdown report of the analysis."""
    report_lines = [
        "# Disappointment Pattern Analysis Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Total instances with disappointment**: {results['summary']['total_with_disappointment']}",
        f"- **Completed tasks (100%+) with disappointment**: {results['summary']['completed_with_disappointment']}",
        f"- **Partial tasks (<100%) with disappointment**: {results['summary']['partial_with_disappointment']}",
        "",
        f"- **Average disappointment (completed)**: {results['summary']['avg_disappointment_completed']:.2f}",
        f"- **Average disappointment (partial)**: {results['summary']['avg_disappointment_partial']:.2f}",
        "",
        "## Key Finding",
        "",
        "This analysis focuses on instances where disappointment occurred **despite** full task completion (100%+).",
        "These represent cases of 'persistent disappointment' - completing tasks even when outcomes don't meet expectations.",
        "",
    ]
    
    # Statistics section
    if 'high_completion' in results['statistics']:
        stats = results['statistics']['high_completion']
        report_lines.extend([
            "## Statistics: High Completion (100%+) with Disappointment",
            "",
            f"- **Count**: {stats['count']} instances",
            f"- **Average disappointment**: {stats['avg_disappointment']:.2f}",
            f"- **Max disappointment**: {stats['max_disappointment']:.2f}",
            f"- **Min disappointment**: {stats['min_disappointment']:.2f}",
            f"- **Average time ratio** (actual/estimate): {stats['avg_time_ratio']:.2f}x",
            f"- **Average expected relief**: {stats['avg_expected_relief']:.2f}",
            f"- **Average actual relief**: {stats['avg_actual_relief']:.2f}",
            f"- **Average net relief**: {stats['avg_net_relief']:.2f}",
            "",
        ])
    
    # Detailed instances
    if results['high_completion_with_disappointment']:
        report_lines.extend([
            "## Detailed Instances: Completion >= 100% with Disappointment",
            "",
            "These instances represent 'persistent disappointment' - completing tasks despite unmet expectations.",
            "",
            "| Task Name | Completion % | Disappointment | Expected Relief | Actual Relief | Time Ratio | Date |",
            "|-----------|--------------|----------------|----------------|---------------|------------|------|",
        ])
        
        # Sort by disappointment (highest first)
        sorted_instances = sorted(
            results['high_completion_with_disappointment'],
            key=lambda x: x['disappointment_factor'],
            reverse=True
        )
        
        for inst in sorted_instances:
            report_lines.append(
                f"| {inst['task_name']} | {inst['completion_pct']:.0f}% | "
                f"{inst['disappointment_factor']:.2f} | {inst['expected_relief']:.1f} | "
                f"{inst['actual_relief']:.1f} | {inst['time_ratio']:.2f}x | {inst['date']} |"
            )
        
        report_lines.extend(["", "### Analysis of High Completion + Disappointment", ""])
        
        # Analyze patterns
        time_ratios = [inst['time_ratio'] for inst in sorted_instances if inst['time_ratio'] > 0]
        if time_ratios:
            avg_time_ratio = sum(time_ratios) / len(time_ratios)
            report_lines.append(f"- **Average time ratio**: {avg_time_ratio:.2f}x (spent {avg_time_ratio:.1f}x longer than estimated)")
        
        high_time_ratio = [inst for inst in sorted_instances if inst['time_ratio'] > 1.5]
        if high_time_ratio:
            report_lines.append(f"- **Instances with time ratio > 1.5x**: {len(high_time_ratio)} (spent significantly longer than estimated)")
        
        report_lines.extend([
            "",
            "### Interpretation",
            "",
            "These instances show that disappointment can occur even when tasks are fully completed.",
            "Possible reasons:",
            "- Task took longer than expected (time ratio > 1.0)",
            "- Actual relief was lower than expected relief",
            "- Both factors combined",
            "",
            "**Key Insight**: When disappointment occurs with 100%+ completion, it indicates:",
            "1. **Grit/Resilience**: Persisting through disappointment to complete the task",
            "2. **Expectation Mismatch**: Expected relief was higher than actual relief",
            "3. **Time Investment**: May have spent more time than anticipated",
            "",
        ])
    
    # Comparison with partial completion
    if results['low_completion_with_disappointment']:
        report_lines.extend([
            "## Comparison: Partial Completion (<100%) with Disappointment",
            "",
            "For comparison, here are some instances where disappointment occurred with partial completion:",
            "",
            "| Task Name | Completion % | Disappointment | Time Ratio |",
            "|-----------|--------------|----------------|------------|",
        ])
        
        for inst in results['low_completion_with_disappointment'][:10]:  # First 10
            report_lines.append(
                f"| {inst['task_name']} | {inst['completion_pct']:.0f}% | "
                f"{inst['disappointment_factor']:.2f} | {inst['time_ratio']:.2f}x |"
            )
        
        report_lines.extend([
            "",
            "**Key Difference**:",
            "- **High completion + disappointment**: Indicates grit (persisting despite disappointment)",
            "- **Low completion + disappointment**: Indicates lack of grit (giving up due to disappointment)",
            "",
        ])
    
    # Write report
    report_content = "\n".join(report_lines)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"\n[SUCCESS] Report generated: {output_file}")

def main():
    """Main analysis function."""
    print("=" * 80)
    print("Disappointment Pattern Analysis")
    print("=" * 80)
    print()
    
    # Load data
    df = load_instances_with_disappointment()
    
    if df.empty:
        print("[ERROR] No data to analyze")
        return
    
    # Analyze patterns
    print("\n[INFO] Analyzing disappointment patterns...")
    results = analyze_disappointment_patterns(df)
    
    # Generate report
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'analysis', 'factors', 'disappointment')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'disappointment_patterns_analysis.md')
    
    generate_report(results, output_file)
    
    # Print summary to console
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total instances with disappointment: {results['summary']['total_with_disappointment']}")
    print(f"Completed (100%+) with disappointment: {results['summary']['completed_with_disappointment']}")
    print(f"Partial (<100%) with disappointment: {results['summary']['partial_with_disappointment']}")
    
    if results['high_completion_with_disappointment']:
        print(f"\n[KEY FINDING] Found {len(results['high_completion_with_disappointment'])} instances")
        print("with disappointment AND completion >= 100%")
        print("\nThese represent 'persistent disappointment' - completing tasks despite unmet expectations.")
        print("This indicates grit/resilience.")
    
    print(f"\n[INFO] Full report saved to: {output_file}")

if __name__ == '__main__':
    main()
