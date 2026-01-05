#!/usr/bin/env python3
"""
Compare grit score v1.6 variants (a, b, c) with different disappointment resilience caps.

Variants:
- v1.6a: Original caps (1.5x bonus, 0.67x penalty)
- v1.6b: Reduced positive cap (1.3x bonus, 0.67x penalty)
- v1.6c: Balanced caps (1.2x bonus, 0.8x penalty)
"""

import os
import sys
from datetime import datetime
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from backend.analytics import Analytics

def load_and_prepare_data() -> pd.DataFrame:
    """Load task instances and prepare for grit score calculation."""
    print("[INFO] Loading task instances...")
    
    analytics = Analytics()
    df = analytics._load_instances(completed_only=False)
    
    if df.empty:
        print("[ERROR] No instances found")
        return df
    
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
    
    # Filter to completed instances only (for meaningful comparison)
    completed = df[df['completion_pct'] > 0].copy()
    print(f"[INFO] {len(completed)} instances with completion > 0%")
    
    return completed

def calculate_grit_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate grit scores for all three v1.6 variants."""
    print("[INFO] Calculating grit scores for all variants...")
    
    analytics = Analytics()
    
    # Calculate task completion counts (required for grit score)
    task_completion_counts = {}
    for task_id in df['task_id'].unique():
        task_instances = df[df['task_id'] == task_id]
        task_completion_counts[task_id] = len(task_instances)
    
    # Calculate grit scores for each variant
    grit_scores = {
        'v1_6a': [],
        'v1_6b': [],
        'v1_6c': [],
        'v1_6d': [],
        'v1_6e': [],
        'v1_7a': [],
        'v1_7b': [],
        'v1_7c': []
    }
    
    for idx, row in df.iterrows():
        try:
            grit_v1_6a = analytics.calculate_grit_score_v1_6a(row, task_completion_counts)
            grit_v1_6b = analytics.calculate_grit_score_v1_6b(row, task_completion_counts)
            grit_v1_6c = analytics.calculate_grit_score_v1_6c(row, task_completion_counts)
            grit_v1_6d = analytics.calculate_grit_score_v1_6d(row, task_completion_counts)
            grit_v1_6e = analytics.calculate_grit_score_v1_6e(row, task_completion_counts)
            grit_v1_7a = analytics.calculate_grit_score_v1_7a(row, task_completion_counts)
            grit_v1_7b = analytics.calculate_grit_score_v1_7b(row, task_completion_counts)
            grit_v1_7c = analytics.calculate_grit_score_v1_7c(row, task_completion_counts)
            
            grit_scores['v1_6a'].append(grit_v1_6a)
            grit_scores['v1_6b'].append(grit_v1_6b)
            grit_scores['v1_6c'].append(grit_v1_6c)
            grit_scores['v1_6d'].append(grit_v1_6d)
            grit_scores['v1_6e'].append(grit_v1_6e)
            grit_scores['v1_7a'].append(grit_v1_7a)
            grit_scores['v1_7b'].append(grit_v1_7b)
            grit_scores['v1_7c'].append(grit_v1_7c)
        except Exception as e:
            print(f"[WARNING] Error calculating grit for instance {idx}: {e}")
            grit_scores['v1_6a'].append(0.0)
            grit_scores['v1_6b'].append(0.0)
            grit_scores['v1_6c'].append(0.0)
            grit_scores['v1_6d'].append(0.0)
            grit_scores['v1_6e'].append(0.0)
            grit_scores['v1_7a'].append(0.0)
            grit_scores['v1_7b'].append(0.0)
            grit_scores['v1_7c'].append(0.0)
    
    # Add to dataframe
    df['grit_v1_6a'] = grit_scores['v1_6a']
    df['grit_v1_6b'] = grit_scores['v1_6b']
    df['grit_v1_6c'] = grit_scores['v1_6c']
    df['grit_v1_6d'] = grit_scores['v1_6d']
    df['grit_v1_6e'] = grit_scores['v1_6e']
    df['grit_v1_7a'] = grit_scores['v1_7a']
    df['grit_v1_7b'] = grit_scores['v1_7b']
    df['grit_v1_7c'] = grit_scores['v1_7c']
    
    return df

def get_disappointment_factor(row: pd.Series) -> float:
    """Extract disappointment factor from row."""
    try:
        if 'disappointment_factor' in row.index:
            return float(row.get('disappointment_factor', 0) or 0)
        
        # Calculate from net_relief
        actual_dict = row.get('actual_dict', {})
        predicted_dict = row.get('predicted_dict', {})
        if isinstance(actual_dict, dict) and isinstance(predicted_dict, dict):
            expected_relief = float(predicted_dict.get('expected_relief', 0) or 0)
            actual_relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            net_relief = actual_relief - expected_relief
            if net_relief < 0:
                return -net_relief
        return 0.0
    except (KeyError, TypeError, ValueError):
        return 0.0

def analyze_variants(df: pd.DataFrame) -> Dict:
    """Analyze differences between variants."""
    print("[INFO] Analyzing variant differences...")
    
    results = {
        'summary': {},
        'by_completion_status': {},
        'by_disappointment_level': {},
        'correlations': {}
    }
    
    # Add disappointment factor
    df['disappointment_factor'] = df.apply(get_disappointment_factor, axis=1)
    
    # Summary statistics
    results['summary'] = {
        'v1_6a_mean': float(df['grit_v1_6a'].mean()),
        'v1_6a_std': float(df['grit_v1_6a'].std()),
        'v1_6b_mean': float(df['grit_v1_6b'].mean()),
        'v1_6b_std': float(df['grit_v1_6b'].std()),
        'v1_6c_mean': float(df['grit_v1_6c'].mean()),
        'v1_6c_std': float(df['grit_v1_6c'].std()),
        'v1_6d_mean': float(df['grit_v1_6d'].mean()),
        'v1_6d_std': float(df['grit_v1_6d'].std()),
        'v1_6e_mean': float(df['grit_v1_6e'].mean()),
        'v1_6e_std': float(df['grit_v1_6e'].std()),
        'v1_7a_mean': float(df['grit_v1_7a'].mean()),
        'v1_7a_std': float(df['grit_v1_7a'].std()),
        'v1_7b_mean': float(df['grit_v1_7b'].mean()),
        'v1_7b_std': float(df['grit_v1_7b'].std()),
        'v1_7c_mean': float(df['grit_v1_7c'].mean()),
        'v1_7c_std': float(df['grit_v1_7c'].std()),
        'v1_6a_vs_6b_diff': float(df['grit_v1_6a'].mean() - df['grit_v1_6b'].mean()),
        'v1_6a_vs_6c_diff': float(df['grit_v1_6a'].mean() - df['grit_v1_6c'].mean()),
        'v1_6a_vs_6d_diff': float(df['grit_v1_6a'].mean() - df['grit_v1_6d'].mean()),
        'v1_6a_vs_6e_diff': float(df['grit_v1_6a'].mean() - df['grit_v1_6e'].mean()),
        'v1_6e_vs_7a_diff': float(df['grit_v1_6e'].mean() - df['grit_v1_7a'].mean()),
        'v1_6e_vs_7b_diff': float(df['grit_v1_6e'].mean() - df['grit_v1_7b'].mean()),
        'v1_6e_vs_7c_diff': float(df['grit_v1_6e'].mean() - df['grit_v1_7c'].mean()),
        'v1_7a_vs_7b_diff': float(df['grit_v1_7a'].mean() - df['grit_v1_7b'].mean()),
        'v1_7a_vs_7c_diff': float(df['grit_v1_7a'].mean() - df['grit_v1_7c'].mean()),
        'v1_7b_vs_7c_diff': float(df['grit_v1_7b'].mean() - df['grit_v1_7c'].mean()),
    }
    
    # Analysis by completion status
    completed = df[df['completion_pct'] >= 100.0]
    partial = df[df['completion_pct'] < 100.0]
    
    if not completed.empty:
        results['by_completion_status']['completed'] = {
            'count': len(completed),
            'v1_6a_mean': float(completed['grit_v1_6a'].mean()),
            'v1_6b_mean': float(completed['grit_v1_6b'].mean()),
            'v1_6c_mean': float(completed['grit_v1_6c'].mean()),
            'v1_6d_mean': float(completed['grit_v1_6d'].mean()),
            'v1_6e_mean': float(completed['grit_v1_6e'].mean()),
            'v1_7a_mean': float(completed['grit_v1_7a'].mean()),
            'v1_7b_mean': float(completed['grit_v1_7b'].mean()),
            'v1_7c_mean': float(completed['grit_v1_7c'].mean()),
        }
    
    if not partial.empty:
        results['by_completion_status']['partial'] = {
            'count': len(partial),
            'v1_6a_mean': float(partial['grit_v1_6a'].mean()),
            'v1_6b_mean': float(partial['grit_v1_6b'].mean()),
            'v1_6c_mean': float(partial['grit_v1_6c'].mean()),
            'v1_6d_mean': float(partial['grit_v1_6d'].mean()),
            'v1_6e_mean': float(partial['grit_v1_6e'].mean()),
            'v1_7a_mean': float(partial['grit_v1_7a'].mean()),
            'v1_7b_mean': float(partial['grit_v1_7b'].mean()),
            'v1_7c_mean': float(partial['grit_v1_7c'].mean()),
        }
    
    # Analysis by disappointment level
    high_disappointment = df[df['disappointment_factor'] > 30]
    if not high_disappointment.empty:
        results['by_disappointment_level']['high'] = {
            'count': len(high_disappointment),
            'v1_6a_mean': float(high_disappointment['grit_v1_6a'].mean()),
            'v1_6b_mean': float(high_disappointment['grit_v1_6b'].mean()),
            'v1_6c_mean': float(high_disappointment['grit_v1_6c'].mean()),
            'v1_6d_mean': float(high_disappointment['grit_v1_6d'].mean()),
            'v1_6e_mean': float(high_disappointment['grit_v1_6e'].mean()),
            'v1_7a_mean': float(high_disappointment['grit_v1_7a'].mean()),
            'v1_7b_mean': float(high_disappointment['grit_v1_7b'].mean()),
            'v1_7c_mean': float(high_disappointment['grit_v1_7c'].mean()),
        }
    
    # Correlations with disappointment (overall and conditional)
    disappointed = df[df['disappointment_factor'] > 0]
    if not disappointed.empty:
        results['correlations'] = {
            'overall': {
                'v1_6a': float(disappointed['grit_v1_6a'].corr(disappointed['disappointment_factor'])),
                'v1_6b': float(disappointed['grit_v1_6b'].corr(disappointed['disappointment_factor'])),
                'v1_6c': float(disappointed['grit_v1_6c'].corr(disappointed['disappointment_factor'])),
                'v1_6d': float(disappointed['grit_v1_6d'].corr(disappointed['disappointment_factor'])),
                'v1_6e': float(disappointed['grit_v1_6e'].corr(disappointed['disappointment_factor'])),
                'v1_7a': float(disappointed['grit_v1_7a'].corr(disappointed['disappointment_factor'])),
                'v1_7b': float(disappointed['grit_v1_7b'].corr(disappointed['disappointment_factor'])),
                'v1_7c': float(disappointed['grit_v1_7c'].corr(disappointed['disappointment_factor'])),
            }
        }
        
        # Conditional correlations: by completion status
        disappointed_completed = disappointed[disappointed['completion_pct'] >= 100.0]
        disappointed_partial = disappointed[disappointed['completion_pct'] < 100.0]
        
        if not disappointed_completed.empty:
            results['correlations']['completed'] = {
                'v1_6a': float(disappointed_completed['grit_v1_6a'].corr(disappointed_completed['disappointment_factor'])),
                'v1_6b': float(disappointed_completed['grit_v1_6b'].corr(disappointed_completed['disappointment_factor'])),
                'v1_6c': float(disappointed_completed['grit_v1_6c'].corr(disappointed_completed['disappointment_factor'])),
                'v1_6d': float(disappointed_completed['grit_v1_6d'].corr(disappointed_completed['disappointment_factor'])),
                'v1_6e': float(disappointed_completed['grit_v1_6e'].corr(disappointed_completed['disappointment_factor'])),
                'v1_7a': float(disappointed_completed['grit_v1_7a'].corr(disappointed_completed['disappointment_factor'])),
                'v1_7b': float(disappointed_completed['grit_v1_7b'].corr(disappointed_completed['disappointment_factor'])),
                'v1_7c': float(disappointed_completed['grit_v1_7c'].corr(disappointed_completed['disappointment_factor'])),
            }
        
        if not disappointed_partial.empty:
            results['correlations']['partial'] = {
                'v1_6a': float(disappointed_partial['grit_v1_6a'].corr(disappointed_partial['disappointment_factor'])),
                'v1_6b': float(disappointed_partial['grit_v1_6b'].corr(disappointed_partial['disappointment_factor'])),
                'v1_6c': float(disappointed_partial['grit_v1_6c'].corr(disappointed_partial['disappointment_factor'])),
                'v1_6d': float(disappointed_partial['grit_v1_6d'].corr(disappointed_partial['disappointment_factor'])),
                'v1_6e': float(disappointed_partial['grit_v1_6e'].corr(disappointed_partial['disappointment_factor'])),
                'v1_7a': float(disappointed_partial['grit_v1_7a'].corr(disappointed_partial['disappointment_factor'])),
                'v1_7b': float(disappointed_partial['grit_v1_7b'].corr(disappointed_partial['disappointment_factor'])),
                'v1_7c': float(disappointed_partial['grit_v1_7c'].corr(disappointed_partial['disappointment_factor'])),
            }
    
    return results

def create_visualizations(df: pd.DataFrame, output_dir: str, results: Dict = None):
    """Create comparison visualizations."""
    print("[INFO] Creating visualizations...")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Add disappointment factor
    df['disappointment_factor'] = df.apply(get_disappointment_factor, axis=1)
    
    # Calculate correlations if not provided
    if results is None:
        disappointed = df[df['disappointment_factor'] > 0]
        results = {'correlations': {}}
        if not disappointed.empty:
            results['correlations']['overall'] = {
                'v1_6a': float(disappointed['grit_v1_6a'].corr(disappointed['disappointment_factor'])),
                'v1_6b': float(disappointed['grit_v1_6b'].corr(disappointed['disappointment_factor'])),
                'v1_6c': float(disappointed['grit_v1_6c'].corr(disappointed['disappointment_factor'])),
                'v1_6d': float(disappointed['grit_v1_6d'].corr(disappointed['disappointment_factor'])),
                'v1_6e': float(disappointed['grit_v1_6e'].corr(disappointed['disappointment_factor'])),
            }
            disappointed_completed = disappointed[disappointed['completion_pct'] >= 100.0]
            disappointed_partial = disappointed[disappointed['completion_pct'] < 100.0]
            if not disappointed_completed.empty:
                results['correlations']['completed'] = {
                    'v1_6a': float(disappointed_completed['grit_v1_6a'].corr(disappointed_completed['disappointment_factor'])),
                    'v1_6b': float(disappointed_completed['grit_v1_6b'].corr(disappointed_completed['disappointment_factor'])),
                    'v1_6c': float(disappointed_completed['grit_v1_6c'].corr(disappointed_completed['disappointment_factor'])),
                    'v1_6d': float(disappointed_completed['grit_v1_6d'].corr(disappointed_completed['disappointment_factor'])),
                    'v1_6e': float(disappointed_completed['grit_v1_6e'].corr(disappointed_completed['disappointment_factor'])),
                }
            if not disappointed_partial.empty:
                results['correlations']['partial'] = {
                    'v1_6a': float(disappointed_partial['grit_v1_6a'].corr(disappointed_partial['disappointment_factor'])),
                    'v1_6b': float(disappointed_partial['grit_v1_6b'].corr(disappointed_partial['disappointment_factor'])),
                    'v1_6c': float(disappointed_partial['grit_v1_6c'].corr(disappointed_partial['disappointment_factor'])),
                    'v1_6d': float(disappointed_partial['grit_v1_6d'].corr(disappointed_partial['disappointment_factor'])),
                    'v1_6e': float(disappointed_partial['grit_v1_6e'].corr(disappointed_partial['disappointment_factor'])),
                }
    
    # 1. Scatter plot: Disappointment vs Grit (focus on v1.6e and v1.7 variants)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, variant in enumerate(['v1_6e', 'v1_7a', 'v1_7b', 'v1_7c']):
        ax = axes[idx]
        disappointed = df[df['disappointment_factor'] > 0]
        
        if not disappointed.empty:
            # Color by completion status
            completed = disappointed[disappointed['completion_pct'] >= 100.0]
            partial = disappointed[disappointed['completion_pct'] < 100.0]
            
            if not completed.empty:
                ax.scatter(completed['disappointment_factor'], completed[f'grit_{variant}'], 
                          alpha=0.6, label='Completed (100%+)', color='green', s=30)
            if not partial.empty:
                ax.scatter(partial['disappointment_factor'], partial[f'grit_{variant}'], 
                          alpha=0.6, label='Partial (<100%)', color='red', s=30)
        
        ax.set_xlabel('Disappointment Factor')
        ax.set_ylabel('Grit Score')
        ax.set_title(f'Grit Score vs Disappointment ({variant.upper()})')
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'disappointment_vs_grit_v1_7_comparison.png'), dpi=150)
    plt.close()
    
    # 2. Box plot: Grit score distribution by variant (v1.6e and v1.7)
    fig, ax = plt.subplots(figsize=(10, 6))
    data_to_plot = [df['grit_v1_6e'], df['grit_v1_7a'], df['grit_v1_7b'], df['grit_v1_7c']]
    bp = ax.boxplot(data_to_plot, labels=['v1.6e', 'v1.7a', 'v1.7b', 'v1.7c'], patch_artist=True)
    
    colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    ax.set_ylabel('Grit Score')
    ax.set_title('Grit Score Distribution: v1.6e vs v1.7 Variants')
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'grit_distribution_v1_7_comparison.png'), dpi=150)
    plt.close()
    
    # 3. Difference plot: v1.6e vs v1.7 variants
    fig, ax = plt.subplots(figsize=(12, 6))
    
    df['diff_6e_7a'] = df['grit_v1_6e'] - df['grit_v1_7a']
    df['diff_6e_7b'] = df['grit_v1_6e'] - df['grit_v1_7b']
    df['diff_6e_7c'] = df['grit_v1_6e'] - df['grit_v1_7c']
    df['diff_7a_7b'] = df['grit_v1_7a'] - df['grit_v1_7b']
    df['diff_7a_7c'] = df['grit_v1_7a'] - df['grit_v1_7c']
    df['diff_7b_7c'] = df['grit_v1_7b'] - df['grit_v1_7c']
    
    ax.scatter(df.index, df['diff_6e_7a'], alpha=0.5, label='v1.6e - v1.7a', s=20)
    ax.scatter(df.index, df['diff_6e_7b'], alpha=0.5, label='v1.6e - v1.7b', s=20)
    ax.scatter(df.index, df['diff_6e_7c'], alpha=0.5, label='v1.6e - v1.7c', s=20)
    
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax.set_xlabel('Instance Index')
    ax.set_ylabel('Grit Score Difference')
    ax.set_title('Grit Score Differences: v1.6e vs v1.7 Variants')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'grit_differences_v1_7.png'), dpi=150)
    plt.close()
    
    # 4. Correlation comparison chart
    fig, ax = plt.subplots(figsize=(12, 6))
    
    if results and 'correlations' in results and 'completed' in results['correlations'] and 'partial' in results['correlations']:
        comp_corr = results['correlations']['completed']
        part_corr = results['correlations']['partial']
        
        variants = ['v1.6e', 'v1.7a', 'v1.7b', 'v1.7c']
        comp_values = [comp_corr['v1_6e'], comp_corr['v1_7a'], comp_corr['v1_7b'], comp_corr['v1_7c']]
        part_values = [part_corr['v1_6e'], part_corr['v1_7a'], part_corr['v1_7b'], part_corr['v1_7c']]
        
        x = np.arange(len(variants))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, comp_values, width, label='Completed (100%+)', color='green', alpha=0.7)
        bars2 = ax.bar(x + width/2, part_values, width, label='Partial (<100%)', color='red', alpha=0.7)
        
        ax.axhline(y=0, color='black', linestyle='--', linewidth=1)
        ax.set_xlabel('Variant')
        ax.set_ylabel('Correlation with Disappointment')
        ax.set_title('Correlation Comparison: v1.6e vs v1.7 Variants')
        ax.set_xticks(x)
        ax.set_xticklabels(variants)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}',
                       ha='center', va='bottom' if height > 0 else 'top', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'correlation_comparison.png'), dpi=150)
    plt.close()
    
    # 5. Conditional correlation: By completion status (all variants)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    
    completed = df[df['completion_pct'] >= 100.0]
    partial = df[df['completion_pct'] < 100.0]
    
    for idx, (subset, title) in enumerate([(completed, 'Completed (100%+)'), (partial, 'Partial (<100%)')]):
        ax = axes[idx]
        disappointed = subset[subset['disappointment_factor'] > 0]
        
        if not disappointed.empty:
            colors_map = {'v1_6e': 'blue', 'v1_7a': 'green', 'v1_7b': 'orange', 'v1_7c': 'red'}
            for variant in ['v1_6e', 'v1_7a', 'v1_7b', 'v1_7c']:
                ax.scatter(disappointed['disappointment_factor'], disappointed[f'grit_{variant}'], 
                          alpha=0.5, label=variant.upper(), s=25, color=colors_map.get(variant, 'gray'))
        
        ax.set_xlabel('Disappointment Factor')
        ax.set_ylabel('Grit Score')
        ax.set_title(f'{title}: Disappointment vs Grit (v1.6e vs v1.7)')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'conditional_correlations.png'), dpi=150)
    plt.close()
    
    print(f"[SUCCESS] Visualizations saved to {output_dir}")

def generate_report(results: Dict, df: pd.DataFrame, output_file: str):
    """Generate markdown report of analysis."""
    report_lines = [
        "# Grit Score v1.6 & v1.7 Variants Comparison",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Variant Definitions",
        "",
        "### v1.6 Variants (Previous Analysis)",
        "",
        "- **v1.6a**: Linear scaling, original caps (1.5x bonus, 0.67x penalty)",
        "- **v1.6b**: Linear scaling, reduced positive cap (1.3x bonus, 0.67x penalty)",
        "- **v1.6c**: Linear scaling, balanced caps (1.2x bonus, 0.8x penalty)",
        "- **v1.6d**: Exponential scaling up to 1.5x bonus, 0.67x penalty",
        "- **v1.6e**: Exponential scaling up to 2.0x bonus, 0.67x penalty ← **Best v1.6 variant**",
        "",
        "### v1.7 Variants (New)",
        "",
        "- **v1.7a**: v1.6e + 1.1x base score multiplier",
        "  - Adds 10% multiplier to base score (completion_pct) before applying other factors",
        "  - Exponential scaling up to 2.0x bonus, 0.67x penalty",
        "",
        "- **v1.7b**: Exponential scaling up to 2.1x bonus, 0.67x penalty",
        "  - Higher cap than v1.6e (2.1x vs 2.0x) for stronger bonuses",
        "  - Exponential scaling with 110% max bonus",
        "",
        "- **v1.7c**: v1.7a + v1.7b combined",
        "  - 1.1x base score multiplier",
        "  - Exponential scaling up to 2.1x bonus",
        "  - Applies both enhancements",
        "",
        "## Summary Statistics",
        "",
        f"- **Total instances analyzed**: {len(df)}",
        "",
        "### Overall Means (Focus: v1.6e vs v1.7)",
        f"- v1.6e mean: {results['summary']['v1_6e_mean']:.2f} (std: {results['summary']['v1_6e_std']:.2f}) - baseline",
        f"- v1.7a mean: {results['summary']['v1_7a_mean']:.2f} (std: {results['summary']['v1_7a_std']:.2f}) - +1.1x base",
        f"- v1.7b mean: {results['summary']['v1_7b_mean']:.2f} (std: {results['summary']['v1_7b_std']:.2f}) - 2.1x cap",
        f"- v1.7c mean: {results['summary']['v1_7c_mean']:.2f} (std: {results['summary']['v1_7c_std']:.2f}) - both",
        "",
        "### Differences (v1.6e baseline)",
        f"- v1.6e - v1.7a: {results['summary']['v1_6e_vs_7a_diff']:.2f}",
        f"- v1.6e - v1.7b: {results['summary']['v1_6e_vs_7b_diff']:.2f}",
        f"- v1.6e - v1.7c: {results['summary']['v1_6e_vs_7c_diff']:.2f}",
        f"- v1.7a - v1.7b: {results['summary']['v1_7a_vs_7b_diff']:.2f}",
        f"- v1.7a - v1.7c: {results['summary']['v1_7a_vs_7c_diff']:.2f}",
        f"- v1.7b - v1.7c: {results['summary']['v1_7b_vs_7c_diff']:.2f}",
        "",
    ]
    
    # By completion status
    if 'completed' in results['by_completion_status']:
        comp = results['by_completion_status']['completed']
        report_lines.extend([
            "## Analysis by Completion Status",
            "",
            f"### Completed Tasks (100%+): {comp['count']} instances",
            f"- v1.6e mean: {comp['v1_6e_mean']:.2f} (baseline)",
            f"- v1.7a mean: {comp['v1_7a_mean']:.2f} (+1.1x base)",
            f"- v1.7b mean: {comp['v1_7b_mean']:.2f} (2.1x cap)",
            f"- v1.7c mean: {comp['v1_7c_mean']:.2f} (both)",
            "",
        ])
    
    if 'partial' in results['by_completion_status']:
        part = results['by_completion_status']['partial']
        report_lines.extend([
            f"### Partial Tasks (<100%): {part['count']} instances",
            f"- v1.6e mean: {part['v1_6e_mean']:.2f}",
            f"- v1.7a mean: {part['v1_7a_mean']:.2f}",
            f"- v1.7b mean: {part['v1_7b_mean']:.2f}",
            f"- v1.7c mean: {part['v1_7c_mean']:.2f}",
            "",
        ])
    
    # Correlations
    if results['correlations']:
        report_lines.extend([
            "## Correlation with Disappointment Factor",
            "",
            "### Overall Correlation (all instances with disappointment > 0)",
            "",
        ])
        
        if 'overall' in results['correlations']:
            overall = results['correlations']['overall']
            report_lines.extend([
                "| Variant | Correlation | Features |",
                "|---------|-------------|----------|",
                f"| v1.6e | {overall['v1_6e']:.3f} | Baseline (exp 2.0x) |",
                f"| v1.7a | {overall['v1_7a']:.3f} | +1.1x base multiplier |",
                f"| v1.7b | {overall['v1_7b']:.3f} | Exp 2.1x cap |",
                f"| v1.7c | {overall['v1_7c']:.3f} | Both enhancements |",
                "",
            ])
        
        if 'completed' in results['correlations']:
            completed_corr = results['correlations']['completed']
            report_lines.extend([
                "### Conditional: Completed Tasks (100%+)",
                "",
                "**Expected**: Positive correlation (disappointment increases grit)",
                "",
                "| Variant | Correlation | Features |",
                "|---------|-------------|----------|",
                f"| v1.6e | {completed_corr['v1_6e']:.3f} | Baseline (exp 2.0x) |",
                f"| v1.7a | {completed_corr['v1_7a']:.3f} | +1.1x base multiplier |",
                f"| v1.7b | {completed_corr['v1_7b']:.3f} | Exp 2.1x cap |",
                f"| v1.7c | {completed_corr['v1_7c']:.3f} | Both enhancements |",
                "",
                "**Key Finding**: Look for variants with positive or least negative correlation.",
                "",
            ])
        
        if 'partial' in results['correlations']:
            partial_corr = results['correlations']['partial']
            report_lines.extend([
                "### Conditional: Partial Tasks (<100%)",
                "",
                "**Expected**: Negative correlation (disappointment decreases grit)",
                "",
                f"- v1.6a: {partial_corr['v1_6a']:.3f}",
                f"- v1.6b: {partial_corr['v1_6b']:.3f}",
                f"- v1.6c: {partial_corr['v1_6c']:.3f}",
                f"- v1.6d: {partial_corr['v1_6d']:.3f}",
                f"- v1.6e: {partial_corr['v1_6e']:.3f}",
                "",
            ])
        
        report_lines.extend([
            "**Interpretation**:",
            "- For completed tasks: Positive correlation = disappointment resilience working correctly",
            "- For partial tasks: Negative correlation = abandonment penalty working correctly",
            "- Overall correlation may be negative if partial tasks dominate",
            "",
        ])
    
    # Preliminary recommendations
    report_lines.extend([
        "## Preliminary Analysis",
        "",
        "### Key Observations",
        "",
    ])
    
    # Add observations based on data
    if results['summary']['v1_6a_vs_6b_diff'] > 5:
        report_lines.append(f"- v1.6a produces significantly higher scores than v1.6b (mean difference: {results['summary']['v1_6a_vs_6b_diff']:.2f})")
    elif results['summary']['v1_6a_vs_6b_diff'] < -5:
        report_lines.append(f"- v1.6b produces significantly higher scores than v1.6a (mean difference: {abs(results['summary']['v1_6a_vs_6b_diff']):.2f})")
    else:
        report_lines.append(f"- v1.6a and v1.6b produce similar scores (mean difference: {abs(results['summary']['v1_6a_vs_6b_diff']):.2f})")
    
    if results['correlations']:
        if 'completed' in results['correlations']:
            comp_corr = results['correlations']['completed']
            # Find variant with most positive correlation for completed tasks
            best_completed = max([
                ('v1.6e', comp_corr['v1_6e']),
                ('v1.7a', comp_corr['v1_7a']),
                ('v1.7b', comp_corr['v1_7b']),
                ('v1.7c', comp_corr['v1_7c'])
            ], key=lambda x: x[1])
            report_lines.append(f"- For completed tasks, {best_completed[0]} shows most positive correlation: {best_completed[1]:.3f}")
            if best_completed[1] > 0:
                report_lines.append(f"  **SUCCESS**: {best_completed[0]} achieves positive correlation (as expected)!")
            else:
                improvement = ((comp_corr['v1_6e'] - best_completed[1]) / abs(comp_corr['v1_6e'])) * 100 if comp_corr['v1_6e'] != 0 else 0
                report_lines.append(f"  **Improvement**: {improvement:.1f}% better than v1.6e baseline")
        
        if 'partial' in results['correlations']:
            part_corr = results['correlations']['partial']
            # All variants should be identical for partial tasks
            report_lines.append(f"- For partial tasks, all variants show correlation: {part_corr['v1_6e']:.3f}")
    
    report_lines.extend([
        "",
        "### Next Steps",
        "",
        "If the analysis is ambiguous, consider:",
        "1. Creating an experimental module to test all three variants in production",
        "2. A/B testing with user feedback",
        "3. Monitoring which variant produces more meaningful grit scores over time",
        "",
    ])
    
    # Write report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"[SUCCESS] Report generated: {output_file}")

def main():
    """Main comparison function."""
    print("=" * 80)
    print("Grit Score v1.6 Variants Comparison")
    print("=" * 80)
    print()
    
    # Load data
    df = load_and_prepare_data()
    if df.empty:
        return
    
    # Calculate grit scores
    df = calculate_grit_scores(df)
    
    # Analyze
    results = analyze_variants(df)
    
    # Create visualizations
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'analysis', 'factors', 'disappointment')
    create_visualizations(df, output_dir, results)
    
    # Generate report
    report_file = os.path.join(output_dir, 'grit_v1_6_variants_comparison.md')
    generate_report(results, df, report_file)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"v1.6e mean: {results['summary']['v1_6e_mean']:.2f} (baseline)")
    print(f"v1.7a mean: {results['summary']['v1_7a_mean']:.2f} (+1.1x base)")
    print(f"v1.7b mean: {results['summary']['v1_7b_mean']:.2f} (2.1x cap)")
    print(f"v1.7c mean: {results['summary']['v1_7c_mean']:.2f} (both)")
    print(f"\nDifference (6e - 7a): {results['summary']['v1_6e_vs_7a_diff']:.2f}")
    print(f"Difference (6e - 7b): {results['summary']['v1_6e_vs_7b_diff']:.2f}")
    print(f"Difference (6e - 7c): {results['summary']['v1_6e_vs_7c_diff']:.2f}")
    
    if results['correlations']:
        print(f"\nCorrelation with disappointment:")
        if 'overall' in results['correlations']:
            overall = results['correlations']['overall']
            print(f"  Overall - v1.6a: {overall['v1_6a']:.3f}, v1.6b: {overall['v1_6b']:.3f}, v1.6c: {overall['v1_6c']:.3f}")
        if 'completed' in results['correlations']:
            comp = results['correlations']['completed']
            print(f"  Completed (100%+) - v1.6e: {comp['v1_6e']:.3f} (baseline)")
            print(f"    v1.7a: {comp['v1_7a']:.3f} (+1.1x), v1.7b: {comp['v1_7b']:.3f} (2.1x), v1.7c: {comp['v1_7c']:.3f} (both)")
        if 'partial' in results['correlations']:
            part = results['correlations']['partial']
            print(f"  Partial (<100%) - All variants: {part['v1_6e']:.3f}")
    
    print(f"\n[INFO] Full report: {report_file}")
    print(f"[INFO] Visualizations: {output_dir}")

if __name__ == '__main__':
    main()
