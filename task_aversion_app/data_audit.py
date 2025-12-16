#!/usr/bin/env python3
"""
Comprehensive Data Audit Script for Task Aversion System
Analyzes data quality, gaps, formula coherence, and psychological validity
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# Add parent directory to path to import backend modules
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir) if os.path.basename(script_dir) == 'task_aversion_app' else script_dir
sys.path.insert(0, project_root)

try:
    from task_aversion_app.backend.analytics import Analytics
except ImportError:
    # Fallback if import fails
    Analytics = None

DATA_DIR = os.path.join(script_dir, 'data')


class DataAuditor:
    """Comprehensive data audit and validation."""
    
    # Dev/test task name patterns to exclude
    DEV_TASK_PATTERNS = [
        'test', 'dev', 'example', 'fix', 'completion test',
        'devtest', 'f'  # Single letter 'f' is a test task
    ]
    
    def __init__(self):
        self.data_dir = DATA_DIR
        self.issues = []
        self.warnings = []
        self.recommendations = []
        self.dev_task_names = set()
        self.dev_task_ids = set()
        
    def load_data(self) -> Dict[str, pd.DataFrame]:
        """Load all CSV data files."""
        data = {}
        
        files = {
            'tasks': 'tasks.csv',
            'instances': 'task_instances.csv',
            'emotions': 'emotions.csv',
            'logs': 'logs.csv',
            'survey': 'survey_responses.csv',
            'preferences': 'user_preferences.csv'
        }
        
        for key, filename in files.items():
            filepath = os.path.join(self.data_dir, filename)
            if os.path.exists(filepath):
                try:
                    data[key] = pd.read_csv(filepath, dtype=str, low_memory=False)
                    print(f"[OK] Loaded {filename}: {len(data[key])} rows")
                except Exception as e:
                    self.issues.append(f"Failed to load {filename}: {e}")
                    print(f"[ERROR] Failed to load {filename}: {e}")
            else:
                self.warnings.append(f"File not found: {filename}")
                print(f"[WARN] File not found: {filename}")
        
        return data
    
    def identify_dev_tasks(self, instances: pd.DataFrame, tasks: pd.DataFrame = None) -> Tuple[set, set]:
        """Identify dev/test tasks by name patterns.
        
        Returns:
            Tuple of (dev_task_names, dev_task_ids) sets
        """
        dev_names = set()
        dev_ids = set()
        
        if instances.empty:
            return dev_names, dev_ids
        
        # Check task names in instances
        if 'task_name' in instances.columns:
            for task_name in instances['task_name'].dropna().unique():
                task_name_lower = str(task_name).lower().strip()
                # Check if task name matches any dev pattern
                for pattern in self.DEV_TASK_PATTERNS:
                    if pattern.lower() in task_name_lower:
                        dev_names.add(task_name)
                        # Get all task_ids for this task name
                        matching_instances = instances[instances['task_name'] == task_name]
                        if 'task_id' in matching_instances.columns:
                            dev_ids.update(matching_instances['task_id'].dropna().unique())
                        break
                
                # Also check for single letter names (like 'f')
                if len(task_name_lower) == 1 and task_name_lower in ['f', 't', 'e']:
                    dev_names.add(task_name)
                    matching_instances = instances[instances['task_name'] == task_name]
                    if 'task_id' in matching_instances.columns:
                        dev_ids.update(matching_instances['task_id'].dropna().unique())
        
        # Also check tasks dataframe if provided
        if tasks is not None and not tasks.empty:
            if 'name' in tasks.columns:
                for task_name in tasks['name'].dropna().unique():
                    task_name_lower = str(task_name).lower().strip()
                    for pattern in self.DEV_TASK_PATTERNS:
                        if pattern.lower() in task_name_lower:
                            dev_names.add(task_name)
                            if 'task_id' in tasks.columns:
                                matching_tasks = tasks[tasks['name'] == task_name]
                                dev_ids.update(matching_tasks['task_id'].dropna().unique())
                            break
        
        self.dev_task_names = dev_names
        self.dev_task_ids = dev_ids
        return dev_names, dev_ids
    
    def filter_dev_tasks(self, instances: pd.DataFrame) -> pd.DataFrame:
        """Filter out dev/test tasks from instances dataframe."""
        if instances.empty:
            return instances
        
        # Identify dev tasks if not already done
        if not self.dev_task_names and not self.dev_task_ids:
            self.identify_dev_tasks(instances)
        
        # Filter by task_name
        if 'task_name' in instances.columns:
            filtered = instances[~instances['task_name'].isin(self.dev_task_names)]
        else:
            filtered = instances.copy()
        
        # Also filter by task_id
        if 'task_id' in filtered.columns:
            filtered = filtered[~filtered['task_id'].isin(self.dev_task_ids)]
        
        return filtered
    
    def parse_json_columns(self, df: pd.DataFrame, json_cols: List[str]) -> pd.DataFrame:
        """Safely parse JSON columns."""
        df = df.copy()
        for col in json_cols:
            if col in df.columns:
                def _safe_json(x):
                    if pd.isna(x) or x == '':
                        return {}
                    try:
                        if isinstance(x, str):
                            return json.loads(x)
                        return x if isinstance(x, dict) else {}
                    except:
                        return {}
                df[f'{col}_parsed'] = df[col].apply(_safe_json)
        return df
    
    def audit_data_volume(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """Audit data volume and basic statistics."""
        report = {
            'total_tasks': len(data.get('tasks', pd.DataFrame())),
            'total_instances': len(data.get('instances', pd.DataFrame())),
            'total_emotions': len(data.get('emotions', pd.DataFrame())),
            'total_logs': len(data.get('logs', pd.DataFrame())),
            'total_surveys': len(data.get('survey', pd.DataFrame())),
        }
        
        instances = data.get('instances', pd.DataFrame())
        if not instances.empty:
            # Check completion rate
            if 'is_completed' in instances.columns:
                completed = instances['is_completed'].str.lower() == 'true'
                report['completed_instances'] = completed.sum()
                report['completion_rate'] = (completed.sum() / len(instances) * 100) if len(instances) > 0 else 0
            else:
                report['completed_instances'] = 0
                report['completion_rate'] = 0
            
            # Check for cancelled
            if 'status' in instances.columns:
                cancelled = instances['status'].str.lower() == 'cancelled'
                report['cancelled_instances'] = cancelled.sum()
            else:
                report['cancelled_instances'] = 0
        
        return report
    
    def audit_temporal_gaps(self, instances: pd.DataFrame) -> Dict:
        """Detect temporal gaps in data, especially around merge period."""
        if instances.empty or 'created_at' not in instances.columns:
            return {'gaps': [], 'merge_gap_detected': False}
        
        # Parse dates
        instances = instances.copy()
        instances['created_at_parsed'] = pd.to_datetime(instances['created_at'], errors='coerce')
        instances = instances.sort_values('created_at_parsed').dropna(subset=['created_at_parsed'])
        
        if len(instances) < 2:
            return {'gaps': [], 'merge_gap_detected': False}
        
        # Calculate gaps
        instances['gap_days'] = instances['created_at_parsed'].diff().dt.total_seconds() / 86400
        
        # Find significant gaps (>7 days)
        large_gaps = instances[instances['gap_days'] > 7].copy()
        
        gaps = []
        for idx, row in large_gaps.iterrows():
            gap_info = {
                'gap_days': round(row['gap_days'], 1),
                'gap_start': instances.loc[instances.index < idx, 'created_at_parsed'].max(),
                'gap_end': row['created_at_parsed'],
                'instances_before': len(instances[instances.index < idx]),
                'instances_after': len(instances[instances.index > idx])
            }
            gaps.append(gap_info)
        
        # Detect potential merge gap (largest gap)
        merge_gap_detected = len(gaps) > 0
        largest_gap = max(gaps, key=lambda x: x['gap_days']) if gaps else None
        
        return {
            'gaps': gaps,
            'merge_gap_detected': merge_gap_detected,
            'largest_gap': largest_gap,
            'total_instances': len(instances),
            'date_range_days': (instances['created_at_parsed'].max() - instances['created_at_parsed'].min()).days
        }
    
    def audit_formula_coherence(self, instances: pd.DataFrame, exclude_dev: bool = True) -> Dict:
        """Validate formula calculations and coherence.
        
        Args:
            instances: Task instances dataframe
            exclude_dev: If True, exclude dev/test tasks from analysis
        """
        if instances.empty:
            return {}
        
        # Filter out dev tasks if requested
        if exclude_dev:
            instances = self.filter_dev_tasks(instances.copy())
            if instances.empty:
                return {'error': 'No instances remaining after filtering dev tasks'}
        
        # Parse JSON columns
        instances = self.parse_json_columns(instances, ['predicted', 'actual'])
        
        # Extract calculated values
        completed = instances[instances['is_completed'].str.lower() == 'true'].copy() if 'is_completed' in instances.columns else instances.copy()
        
        if len(completed) == 0:
            return {'error': 'No completed instances to analyze'}
        
        # Extract metrics from JSON
        metrics_data = {}
        for metric in ['relief', 'cognitive', 'emotional', 'physical', 'aversion', 'stress_level', 'net_wellbeing']:
            pred_col = f'predicted_parsed'
            actual_col = f'actual_parsed'
            
            # Get from actual_dict
            actual_values = []
            predicted_values = []
            
            for idx, row in completed.iterrows():
                actual_dict = row.get(actual_col, {}) if isinstance(row.get(actual_col), dict) else {}
                predicted_dict = row.get(pred_col, {}) if isinstance(row.get(pred_col), dict) else {}
                
                # Try different key names
                if metric == 'relief':
                    actual_values.append(actual_dict.get('actual_relief') or actual_dict.get('relief') or np.nan)
                    predicted_values.append(predicted_dict.get('expected_relief') or predicted_dict.get('relief') or np.nan)
                elif metric == 'cognitive':
                    actual_values.append(actual_dict.get('actual_cognitive') or actual_dict.get('cognitive_load') or np.nan)
                    predicted_values.append(predicted_dict.get('expected_cognitive_load') or predicted_dict.get('cognitive') or np.nan)
                elif metric == 'emotional':
                    actual_values.append(actual_dict.get('actual_emotional') or actual_dict.get('emotional_load') or np.nan)
                    predicted_values.append(predicted_dict.get('expected_emotional_load') or predicted_dict.get('emotional') or np.nan)
                elif metric == 'aversion':
                    actual_values.append(actual_dict.get('actual_aversion') or np.nan)
                    predicted_values.append(predicted_dict.get('expected_aversion') or predicted_dict.get('aversion') or np.nan)
            
            actual_series = pd.Series(actual_values)
            predicted_series = pd.Series(predicted_values)
            
            metrics_data[metric] = {
                'actual': {
                    'mean': actual_series.mean(),
                    'std': actual_series.std(),
                    'min': actual_series.min(),
                    'max': actual_series.max(),
                    'count': actual_series.notna().sum(),
                    'outliers_high': ((actual_series > 100) | (actual_series < 0)).sum() if not actual_series.empty else 0
                },
                'predicted': {
                    'mean': predicted_series.mean(),
                    'std': predicted_series.std(),
                    'min': predicted_series.min(),
                    'max': predicted_series.max(),
                    'count': predicted_series.notna().sum(),
                    'outliers_high': ((predicted_series > 100) | (predicted_series < 0)).sum() if not predicted_series.empty else 0
                }
            }
        
        # Check for calculated columns
        calculated_metrics = {}
        for col in ['relief_score', 'cognitive_load', 'emotional_load', 'stress_level', 'net_wellbeing']:
            if col in completed.columns:
                values = pd.to_numeric(completed[col], errors='coerce').dropna()
                if len(values) > 0:
                    calculated_metrics[col] = {
                        'mean': values.mean(),
                        'std': values.std(),
                        'min': values.min(),
                        'max': values.max(),
                        'count': len(values),
                        'outliers': ((values > 100) | (values < -100)).sum() if col == 'net_wellbeing' else ((values > 100) | (values < 0)).sum()
                    }
        
        return {
            'metrics': metrics_data,
            'calculated_metrics': calculated_metrics,
            'total_completed': len(completed)
        }
    
    def audit_prediction_accuracy(self, instances: pd.DataFrame, exclude_dev: bool = True) -> Dict:
        """Analyze prediction vs actual relief accuracy.
        
        Args:
            instances: Task instances dataframe
            exclude_dev: If True, exclude dev/test tasks from analysis
        """
        if instances.empty:
            return {}
        
        # Filter out dev tasks if requested
        if exclude_dev:
            instances = self.filter_dev_tasks(instances.copy())
            if instances.empty:
                return {'error': 'No instances remaining after filtering dev tasks'}
        
        # Parse JSON columns
        instances = self.parse_json_columns(instances, ['predicted', 'actual'])
        
        # Get completed instances only
        completed = instances[instances['is_completed'].str.lower() == 'true'].copy() if 'is_completed' in instances.columns else instances.copy()
        
        if len(completed) == 0:
            return {'error': 'No completed instances to analyze'}
        
        # Extract predicted and actual relief
        predicted_relief = []
        actual_relief = []
        
        for idx, row in completed.iterrows():
            predicted_dict = row.get('predicted_parsed', {}) if isinstance(row.get('predicted_parsed'), dict) else {}
            actual_dict = row.get('actual_parsed', {}) if isinstance(row.get('actual_parsed'), dict) else {}
            
            # Get predicted relief (expected_relief)
            pred = predicted_dict.get('expected_relief') or predicted_dict.get('relief')
            if pred is not None:
                # Scale if needed (0-10 -> 0-100)
                if 0 <= pred <= 10:
                    pred = pred * 10
                predicted_relief.append(pred)
            
            # Get actual relief
            actual = actual_dict.get('actual_relief') or actual_dict.get('relief')
            if actual is not None:
                # Scale if needed (0-10 -> 0-100)
                if 0 <= actual <= 10:
                    actual = actual * 10
                actual_relief.append(actual)
        
        predicted_series = pd.Series(predicted_relief)
        actual_series = pd.Series(actual_relief)
        
        # Only analyze where we have both
        if len(predicted_series) == 0 or len(actual_series) == 0:
            return {'error': 'Insufficient data for prediction accuracy analysis'}
        
        # Find matching pairs (by index in completed dataframe)
        matching_indices = []
        for idx in completed.index:
            pred_dict = completed.loc[idx, 'predicted_parsed'] if isinstance(completed.loc[idx, 'predicted_parsed'], dict) else {}
            actual_dict = completed.loc[idx, 'actual_parsed'] if isinstance(completed.loc[idx, 'actual_parsed'], dict) else {}
            
            pred = pred_dict.get('expected_relief') or pred_dict.get('relief')
            actual = actual_dict.get('actual_relief') or actual_dict.get('relief')
            
            if pred is not None and actual is not None:
                # Scale if needed
                if 0 <= pred <= 10:
                    pred = pred * 10
                if 0 <= actual <= 10:
                    actual = actual * 10
                matching_indices.append({'predicted': pred, 'actual': actual})
        
        if len(matching_indices) == 0:
            return {'error': 'No matching predicted/actual pairs found'}
        
        pred_values = [m['predicted'] for m in matching_indices]
        actual_values = [m['actual'] for m in matching_indices]
        
        pred_series = pd.Series(pred_values)
        actual_series = pd.Series(actual_values)
        
        # Calculate differences
        differences = actual_series - pred_series
        
        return {
            'predicted': {
                'mean': pred_series.mean(),
                'std': pred_series.std(),
                'min': pred_series.min(),
                'max': pred_series.max(),
                'count': len(pred_series)
            },
            'actual': {
                'mean': actual_series.mean(),
                'std': actual_series.std(),
                'min': actual_series.min(),
                'max': actual_series.max(),
                'count': len(actual_series)
            },
            'difference': {
                'mean': differences.mean(),
                'std': differences.std(),
                'min': differences.min(),
                'max': differences.max(),
                'spread': abs(differences.mean())  # Absolute mean difference
            },
            'correlation': np.corrcoef(pred_series, actual_series)[0, 1] if len(pred_series) > 1 else None,
            'total_pairs': len(matching_indices)
        }
    
    def audit_psychological_validity(self, instances: pd.DataFrame) -> Dict:
        """Check if calculated scores align with psychological literature norms."""
        if instances.empty:
            return {}
        
        # Parse JSON and extract values
        instances = self.parse_json_columns(instances, ['predicted', 'actual'])
        completed = instances[instances['is_completed'].str.lower() == 'true'].copy() if 'is_completed' in instances.columns else instances.copy()
        
        if len(completed) == 0:
            return {'error': 'No completed instances'}
        
        # Extract relief, stress, and aversion values
        relief_values = []
        stress_values = []
        aversion_values = []
        
        for idx, row in completed.iterrows():
            actual_dict = row.get('actual_parsed', {})
            predicted_dict = row.get('predicted_parsed', {})
            
            # Relief (0-10 scale, should be normalized to 0-100)
            relief = actual_dict.get('actual_relief')
            if relief is not None:
                # Check if needs scaling (0-10 -> 0-100)
                if 0 <= relief <= 10:
                    relief = relief * 10
                relief_values.append(relief)
            
            # Stress components
            cognitive = actual_dict.get('actual_cognitive', 0)
            emotional = actual_dict.get('actual_emotional', 0)
            if 0 <= cognitive <= 10:
                cognitive = cognitive * 10
            if 0 <= emotional <= 10:
                emotional = emotional * 10
            stress = (cognitive + emotional) / 2
            stress_values.append(stress)
            
            # Aversion
            aversion = predicted_dict.get('expected_aversion') or predicted_dict.get('aversion')
            if aversion is not None:
                if 0 <= aversion <= 10:
                    aversion = aversion * 10
                aversion_values.append(aversion)
        
        relief_series = pd.Series(relief_values)
        stress_series = pd.Series(stress_values)
        aversion_series = pd.Series(aversion_values)
        
        # Psychological validity checks
        validity_issues = []
        
        # Relief should typically be positive (0-100)
        if len(relief_series) > 0:
            if relief_series.mean() < 20:
                validity_issues.append(f"Low average relief ({relief_series.mean():.1f}), may indicate measurement issues")
            if relief_series.max() > 100:
                validity_issues.append(f"Relief values exceed 100 (max: {relief_series.max():.1f})")
        
        # Stress should be moderate (typically 30-70 for challenging tasks)
        if len(stress_series) > 0:
            if stress_series.mean() > 80:
                validity_issues.append(f"Very high average stress ({stress_series.mean():.1f}), may indicate burnout")
            if stress_series.mean() < 10:
                validity_issues.append(f"Very low average stress ({stress_series.mean():.1f}), may indicate measurement issues")
        
        # Aversion should correlate with stress
        if len(aversion_series) > 0 and len(stress_series) > 0:
            min_len = min(len(aversion_series), len(stress_series))
            if min_len > 5:
                correlation = np.corrcoef(aversion_series[:min_len], stress_series[:min_len])[0, 1]
                if correlation < 0.3:
                    validity_issues.append(f"Low aversion-stress correlation ({correlation:.2f}), expected positive correlation")
        
        return {
            'relief_stats': {
                'mean': relief_series.mean() if len(relief_series) > 0 else None,
                'std': relief_series.std() if len(relief_series) > 0 else None,
                'range': (relief_series.min(), relief_series.max()) if len(relief_series) > 0 else None
            },
            'stress_stats': {
                'mean': stress_series.mean() if len(stress_series) > 0 else None,
                'std': stress_series.std() if len(stress_series) > 0 else None,
                'range': (stress_series.min(), stress_series.max()) if len(stress_series) > 0 else None
            },
            'aversion_stats': {
                'mean': aversion_series.mean() if len(aversion_series) > 0 else None,
                'std': aversion_series.std() if len(aversion_series) > 0 else None,
                'range': (aversion_series.min(), aversion_series.max()) if len(aversion_series) > 0 else None
            },
            'validity_issues': validity_issues
        }
    
    def audit_data_quality(self, data: Dict[str, pd.DataFrame]) -> Dict:
        """Check for data quality issues."""
        issues = []
        warnings = []
        
        instances = data.get('instances', pd.DataFrame())
        if not instances.empty:
            # Check for missing task_ids
            missing_task_ids = instances['task_id'].isna().sum() if 'task_id' in instances.columns else 0
            if missing_task_ids > 0:
                issues.append(f"{missing_task_ids} instances missing task_id")
            
            # Check for empty predicted/actual
            if 'predicted' in instances.columns:
                empty_predicted = (instances['predicted'].isna() | (instances['predicted'] == '')).sum()
                if empty_predicted > 0:
                    warnings.append(f"{empty_predicted} instances with empty predicted data")
            
            if 'actual' in instances.columns:
                completed = instances[instances['is_completed'].str.lower() == 'true'] if 'is_completed' in instances.columns else instances
                empty_actual = (completed['actual'].isna() | (completed['actual'] == '')).sum()
                if empty_actual > 0:
                    warnings.append(f"{empty_actual} completed instances with empty actual data")
            
            # Check for duplicate instance_ids
            if 'instance_id' in instances.columns:
                duplicates = instances['instance_id'].duplicated().sum()
                if duplicates > 0:
                    issues.append(f"{duplicates} duplicate instance_ids found")
        
        tasks = data.get('tasks', pd.DataFrame())
        if not tasks.empty:
            if 'task_id' in tasks.columns:
                duplicates = tasks['task_id'].duplicated().sum()
                if duplicates > 0:
                    issues.append(f"{duplicates} duplicate task_ids found")
        
        return {
            'issues': issues,
            'warnings': warnings
        }
    
    def generate_recommendations(self, audit_results: Dict) -> List[str]:
        """Generate actionable recommendations based on audit results."""
        recommendations = []
        
        # Temporal gaps
        if audit_results.get('temporal', {}).get('merge_gap_detected'):
            largest_gap = audit_results['temporal'].get('largest_gap')
            if largest_gap:
                gap_days = largest_gap['gap_days']
                recommendations.append(
                    f"DATA GAP DETECTED: {gap_days:.0f} day gap from {largest_gap['gap_start']} to {largest_gap['gap_end']}. "
                    f"Consider: (1) Imputing missing data if patterns are clear, (2) Focusing analysis on post-gap data, "
                    f"or (3) Marking gap period for exclusion in trend analysis."
                )
        
        # Formula issues
        formula_results = audit_results.get('formulas', {})
        if 'calculated_metrics' in formula_results:
            for metric, stats in formula_results['calculated_metrics'].items():
                if stats.get('outliers', 0) > 0:
                    recommendations.append(
                        f"OUTLIERS: {stats['outliers']} {metric} values outside expected range. "
                        f"Review calculation logic and data entry."
                    )
        
        # Psychological validity
        psych_results = audit_results.get('psychological', {})
        if psych_results.get('validity_issues'):
            for issue in psych_results['validity_issues']:
                recommendations.append(f"VALIDITY: {issue}")
        
        # Data quality
        quality_results = audit_results.get('quality', {})
        if quality_results.get('issues'):
            for issue in quality_results['issues']:
                recommendations.append(f"DATA QUALITY: {issue}")
        
        return recommendations
    
    def run_full_audit(self) -> Dict:
        """Run complete audit and generate report."""
        print("\n" + "="*80)
        print("TASK AVERSION SYSTEM - COMPREHENSIVE DATA AUDIT")
        print("="*80 + "\n")
        
        print("Loading data files...")
        data = self.load_data()
        
        if 'instances' not in data or data['instances'].empty:
            return {'error': 'No instance data found'}
        
        print("\n" + "-"*80)
        print("1. DATA VOLUME ANALYSIS")
        print("-"*80)
        volume_results = self.audit_data_volume(data)
        print(f"   Tasks: {volume_results['total_tasks']}")
        print(f"   Instances: {volume_results['total_instances']}")
        print(f"   Completed: {volume_results.get('completed_instances', 0)} ({volume_results.get('completion_rate', 0):.1f}%)")
        print(f"   Cancelled: {volume_results.get('cancelled_instances', 0)}")
        
        print("\n" + "-"*80)
        print("2. TEMPORAL GAP ANALYSIS")
        print("-"*80)
        temporal_results = self.audit_temporal_gaps(data['instances'])
        if temporal_results.get('gaps'):
            print(f"   Found {len(temporal_results['gaps'])} significant gaps (>7 days):")
            for gap in temporal_results['gaps']:
                print(f"     • {gap['gap_days']:.0f} days ending {gap['gap_end']}")
                print(f"       ({gap['instances_before']} instances before, {gap['instances_after']} after)")
        else:
            print("   [OK] No significant temporal gaps detected")
        
        # Identify dev tasks
        print("\n" + "-"*80)
        print("0. DEV TASK IDENTIFICATION")
        print("-"*80)
        dev_names, dev_ids = self.identify_dev_tasks(data['instances'], data.get('tasks'))
        print(f"   Found {len(dev_names)} dev/test task names: {list(dev_names)}")
        print(f"   Found {len(dev_ids)} dev/test task IDs")
        
        # Count dev instances
        if dev_names or dev_ids:
            dev_instances = data['instances'].copy()
            if 'task_name' in dev_instances.columns:
                dev_instances = dev_instances[dev_instances['task_name'].isin(dev_names)]
            if 'task_id' in dev_instances.columns and dev_ids:
                dev_instances = dev_instances[dev_instances['task_id'].isin(dev_ids)]
            print(f"   Total dev instances: {len(dev_instances)}")
        
        print("\n" + "-"*80)
        print("3. FORMULA COHERENCE ANALYSIS (Excluding Dev Tasks)")
        print("-"*80)
        formula_results = self.audit_formula_coherence(data['instances'], exclude_dev=True)
        if 'error' not in formula_results:
            print(f"   Analyzed {formula_results.get('total_completed', 0)} completed instances (dev tasks excluded)")
            if 'calculated_metrics' in formula_results:
                for metric, stats in formula_results['calculated_metrics'].items():
                    print(f"   {metric}:")
                    print(f"     Mean: {stats['mean']:.2f}, Std: {stats['std']:.2f}")
                    print(f"     Range: [{stats['min']:.2f}, {stats['max']:.2f}]")
                    if stats.get('outliers', 0) > 0:
                        print(f"     [WARN] {stats['outliers']} outliers detected")
        
        print("\n" + "-"*80)
        print("3b. PREDICTION ACCURACY ANALYSIS (Excluding Dev Tasks)")
        print("-"*80)
        pred_accuracy = self.audit_prediction_accuracy(data['instances'], exclude_dev=True)
        if 'error' not in pred_accuracy:
            print(f"   Analyzed {pred_accuracy.get('total_pairs', 0)} predicted/actual pairs")
            print(f"   Predicted Relief:")
            print(f"     Mean: {pred_accuracy['predicted']['mean']:.2f}, Range: [{pred_accuracy['predicted']['min']:.2f}, {pred_accuracy['predicted']['max']:.2f}]")
            print(f"   Actual Relief:")
            print(f"     Mean: {pred_accuracy['actual']['mean']:.2f}, Range: [{pred_accuracy['actual']['min']:.2f}, {pred_accuracy['actual']['max']:.2f}]")
            print(f"   Difference (Actual - Predicted):")
            print(f"     Mean: {pred_accuracy['difference']['mean']:.2f}, Spread: {pred_accuracy['difference']['spread']:.2f}")
            if pred_accuracy.get('correlation') is not None:
                print(f"   Correlation: {pred_accuracy['correlation']:.3f}")
        else:
            print(f"   [WARN] {pred_accuracy.get('error', 'Unknown error')}")
        
        # Also run with dev tasks for comparison
        print("\n" + "-"*80)
        print("3c. PREDICTION ACCURACY COMPARISON (With Dev Tasks)")
        print("-"*80)
        pred_accuracy_with_dev = self.audit_prediction_accuracy(data['instances'], exclude_dev=False)
        if 'error' not in pred_accuracy_with_dev:
            print(f"   Analyzed {pred_accuracy_with_dev.get('total_pairs', 0)} predicted/actual pairs (including dev)")
            print(f"   Predicted Relief Mean: {pred_accuracy_with_dev['predicted']['mean']:.2f}")
            print(f"   Actual Relief Mean: {pred_accuracy_with_dev['actual']['mean']:.2f}")
            print(f"   Difference Mean: {pred_accuracy_with_dev['difference']['mean']:.2f}")
            print(f"   Spread Change: {pred_accuracy_with_dev['difference']['spread'] - pred_accuracy['difference']['spread']:.2f} points")
        
        print("\n" + "-"*80)
        print("4. PSYCHOLOGICAL VALIDITY CHECK (Excluding Dev Tasks)")
        print("-"*80)
        # Filter dev tasks for psychological validity check too
        instances_filtered = self.filter_dev_tasks(data['instances'].copy())
        psych_results = self.audit_psychological_validity(instances_filtered)
        if 'error' not in psych_results:
            if psych_results.get('relief_stats', {}).get('mean') is not None:
                print(f"   Relief: mean={psych_results['relief_stats']['mean']:.1f}, "
                      f"range=[{psych_results['relief_stats']['range'][0]:.1f}, {psych_results['relief_stats']['range'][1]:.1f}]")
            if psych_results.get('stress_stats', {}).get('mean') is not None:
                print(f"   Stress: mean={psych_results['stress_stats']['mean']:.1f}, "
                      f"range=[{psych_results['stress_stats']['range'][0]:.1f}, {psych_results['stress_stats']['range'][1]:.1f}]")
            if psych_results.get('validity_issues'):
                print("   [WARN] Validity Issues:")
                for issue in psych_results['validity_issues']:
                    print(f"     - {issue}")
            else:
                print("   [OK] Values appear within expected psychological ranges")
        
        print("\n" + "-"*80)
        print("5. DATA QUALITY CHECK")
        print("-"*80)
        quality_results = self.audit_data_quality(data)
        if quality_results.get('issues'):
            print("   Issues:")
            for issue in quality_results['issues']:
                print(f"     [ERROR] {issue}")
        if quality_results.get('warnings'):
            print("   Warnings:")
            for warning in quality_results['warnings']:
                print(f"     [WARN] {warning}")
        if not quality_results.get('issues') and not quality_results.get('warnings'):
            print("   [OK] No major data quality issues detected")
        
        # Compile results
        audit_results = {
            'volume': volume_results,
            'temporal': temporal_results,
            'formulas': formula_results,
            'prediction_accuracy': pred_accuracy,
            'prediction_accuracy_with_dev': pred_accuracy_with_dev if 'error' not in pred_accuracy_with_dev else {},
            'dev_tasks': {
                'names': list(dev_names),
                'ids': list(dev_ids),
                'count': len(dev_names)
            },
            'psychological': psych_results,
            'quality': quality_results
        }
        
        # Generate recommendations
        recommendations = self.generate_recommendations(audit_results)
        audit_results['recommendations'] = recommendations
        
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")
        else:
            print("[OK] No critical issues requiring immediate action")
        
        print("\n" + "="*80 + "\n")
        
        return audit_results


def main():
    """Run the audit."""
    auditor = DataAuditor()
    results = auditor.run_full_audit()
    
    # Save results to JSON
    output_file = os.path.join(DATA_DIR, 'audit_results.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[OK] Audit results saved to: {output_file}")
    
    return results


if __name__ == '__main__':
    main()

