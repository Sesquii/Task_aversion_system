# backend/analytics.py
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .task_schema import TASK_ATTRIBUTES, attribute_defaults

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


class Analytics:
    """Central analytics + lightweight recommendation helper."""

    def __init__(self):
        self.instances_file = os.path.join(DATA_DIR, 'task_instances.csv')
        self.tasks_file = os.path.join(DATA_DIR, 'tasks.csv')

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------
    def _load_instances(self) -> pd.DataFrame:
        if not os.path.exists(self.instances_file):
            return pd.DataFrame()

        df = pd.read_csv(self.instances_file).fillna('')
        attr_defaults = attribute_defaults()

        def _ensure_column(col: str, default):
            if col not in df.columns:
                df[col] = default

        for attr, default in attr_defaults.items():
            _ensure_column(attr, default)
        _ensure_column('status', 'active')

        def _safe_json(cell: str) -> Dict:
            if isinstance(cell, dict):
                return cell
            cell = cell or '{}'
            try:
                return json.loads(cell)
            except Exception:
                return {}

        df['predicted_dict'] = df['predicted'].apply(_safe_json) if 'predicted' in df.columns else {}
        df['actual_dict'] = df['actual'].apply(_safe_json) if 'actual' in df.columns else {}

        # Fill attribute columns from JSON payloads if CSV column empty
        for attr in TASK_ATTRIBUTES:
            column = attr.key
            df[column] = df[column].replace('', pd.NA)
            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get(column)))
            df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get(column)))
            # Special handling for relief_score: check for actual_relief in JSON if relief_score is missing
            if column == 'relief_score':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_relief')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_relief')))
            # Similar for cognitive_load
            if column == 'cognitive_load':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_cognitive')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_cognitive_load') or r.get('expected_cognitive')))
            # Similar for emotional_load
            if column == 'emotional_load':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_emotional')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_emotional_load') or r.get('expected_emotional')))
            # Similar for duration_minutes
            if column == 'duration_minutes':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('time_actual_minutes')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('time_estimate_minutes')))
            df[column] = df[column].fillna(attr.default)
            if attr.dtype == 'numeric':
                df[column] = pd.to_numeric(df[column], errors='coerce')
                # Replace NaN with default after numeric conversion
                df[column] = df[column].fillna(attr.default)

        df['status'] = df['status'].replace('', 'active').str.lower()
        return df

    # ------------------------------------------------------------------
    # Dashboard summaries
    # ------------------------------------------------------------------
    def active_summary(self) -> Dict[str, Optional[str]]:
        df = self._load_instances()
        if df.empty:
            return {'active_count': 0, 'oldest_active': None}
        active = df[
            (df['status'].isin(['active', 'in_progress'])) &
            (df['is_deleted'] != 'True')
        ]
        return {
            'active_count': int(len(active)),
            'oldest_active': active['created_at'].min() if not active.empty else None,
        }

    def get_dashboard_metrics(self) -> Dict[str, Dict[str, Optional[float]]]:
        df = self._load_instances()
        if df.empty:
            return {
                'counts': {'active': 0, 'completed_7d': 0},
                'quality': {'avg_relief': 0.0, 'avg_cognitive_load': 0.0},
                'time': {'median_duration': 0.0, 'avg_delay': 0.0},
            }
        active = df[df['status'].isin(['active', 'in_progress'])]
        completed = df[df['completed_at'].astype(str).str.len() > 0]
        completed_7d = completed[
            pd.to_datetime(completed['completed_at']) >= datetime.now() - pd.Timedelta(days=7)
        ]

        def _median(series):
            clean = series.dropna()
            return round(float(clean.median()), 2) if not clean.empty else 0.0

        def _avg(series):
            clean = series.dropna()
            return round(float(clean.mean()), 2) if not clean.empty else 0.0

        df['delay_minutes'] = (
            pd.to_datetime(df['started_at'].replace('', pd.NA))
            - pd.to_datetime(df['created_at'].replace('', pd.NA))
        ).dt.total_seconds() / 60

        metrics = {
            'counts': {
                'active': int(len(active)),
                'completed_7d': int(len(completed_7d)),
            },
            'quality': {
                'avg_relief': _avg(df['relief_score']),
                'avg_cognitive_load': _avg(df['cognitive_load']),
            },
            'time': {
                'median_duration': _median(df['duration_minutes']),
                'avg_delay': _avg(df['delay_minutes']),
            },
        }
        return metrics

    def get_relief_summary(self) -> Dict[str, any]:
        """Calculate relief points, productivity time, and relief statistics."""
        df = self._load_instances()
        
        if df.empty:
            return {
                'productivity_time_minutes': 0.0,
                'default_relief_points': 0.0,
                'net_relief_points': 0.0,
                'positive_relief_count': 0,
                'positive_relief_total': 0.0,
                'positive_relief_avg': 0.0,
                'negative_relief_count': 0,
                'negative_relief_total': 0.0,
                'negative_relief_avg': 0.0,
            }
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'productivity_time_minutes': 0.0,
                'default_relief_points': 0.0,
                'net_relief_points': 0.0,
                'positive_relief_count': 0,
                'positive_relief_total': 0.0,
                'positive_relief_avg': 0.0,
                'negative_relief_count': 0,
                'negative_relief_total': 0.0,
                'negative_relief_avg': 0.0,
            }
        
        # Extract expected relief from predicted_dict
        # predicted_dict is a Series, so we need to access it properly
        def _get_expected_relief(row):
            try:
                pred_dict = row['predicted_dict']
                if isinstance(pred_dict, dict):
                    return pred_dict.get('expected_relief', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
        completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
        
        # Get actual relief from relief_score column (already populated from actual_dict)
        completed['actual_relief'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        
        # Filter to rows where we have both expected and actual relief
        has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
        relief_data = completed[has_both].copy()
        
        # Calculate default relief points (actual - expected, can be negative)
        relief_data['default_relief_points'] = relief_data['actual_relief'] - relief_data['expected_relief']
        
        # Calculate net relief points (calibrated):
        # - 0 for negative net relief (when actual < expected)
        # - actual - expected for positive (when actual >= expected)
        # - For negative cases, store the negative value separately
        relief_data['net_relief_points'] = relief_data.apply(
            lambda row: max(0.0, row['default_relief_points']), axis=1
        )
        relief_data['negative_relief_points'] = relief_data.apply(
            lambda row: min(0.0, row['default_relief_points']), axis=1
        )
        
        # Calculate productivity time (sum of actual time from actual_dict)
        def _get_actual_time(row):
            try:
                actual_dict = row['actual_dict']
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed['time_actual'] = completed.apply(_get_actual_time, axis=1)
        completed['time_actual'] = pd.to_numeric(completed['time_actual'], errors='coerce')
        productivity_time = completed['time_actual'].fillna(0).sum()
        
        # Calculate default relief points totals
        default_total = relief_data['default_relief_points'].sum()
        net_total = relief_data['net_relief_points'].sum()
        
        # Separate positive and negative relief
        positive_relief = relief_data[relief_data['default_relief_points'] > 0]
        negative_relief = relief_data[relief_data['default_relief_points'] < 0]
        
        positive_count = len(positive_relief)
        positive_total = positive_relief['default_relief_points'].sum() if positive_count > 0 else 0.0
        positive_avg = positive_total / positive_count if positive_count > 0 else 0.0
        
        negative_count = len(negative_relief)
        negative_total = abs(negative_relief['default_relief_points'].sum()) if negative_count > 0 else 0.0
        negative_avg = abs(negative_relief['default_relief_points'].mean()) if negative_count > 0 else 0.0
        
        # Get efficiency summary
        efficiency_summary = self.get_efficiency_summary()
        
        return {
            'productivity_time_minutes': round(float(productivity_time), 1),
            'default_relief_points': round(float(default_total), 2),
            'net_relief_points': round(float(net_total), 2),
            'positive_relief_count': int(positive_count),
            'positive_relief_total': round(float(positive_total), 2),
            'positive_relief_avg': round(float(positive_avg), 2),
            'negative_relief_count': int(negative_count),
            'negative_relief_total': round(float(negative_total), 2),
            'negative_relief_avg': round(float(negative_avg), 2),
            'avg_efficiency': efficiency_summary.get('avg_efficiency', 0.0),
            'high_efficiency_count': efficiency_summary.get('high_efficiency_count', 0),
            'low_efficiency_count': efficiency_summary.get('low_efficiency_count', 0),
        }

    def calculate_efficiency_score(self, row: pd.Series) -> float:
        """Calculate productivity efficiency score for a task instance.
        
        Formula considers:
        - Time efficiency: completion % relative to time spent vs expected
        - Relief bonus: higher relief increases efficiency
        - Motivation factor: low motivation + high relief + good time ratio = bonus
        
        Returns efficiency score (0-100+ scale, higher is better).
        """
        try:
            # Extract data
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = actual_dict.get('completion_percent', 0)
            time_actual = actual_dict.get('time_actual_minutes', 0)
            relief_score = pd.to_numeric(row.get('relief_score', 0), errors='coerce') or 0
            
            time_estimate = predicted_dict.get('time_estimate_minutes', 0)
            motivation = predicted_dict.get('motivation', None)
            
            # Convert to numeric
            completion_pct = float(completion_pct) if completion_pct else 0.0
            time_actual = float(time_actual) if time_actual else 0.0
            time_estimate = float(time_estimate) if time_estimate else 0.0
            relief_score = float(relief_score) if relief_score else 0.0
            motivation = float(motivation) if motivation is not None else None
            
            # Base efficiency: completion percentage
            base_efficiency = completion_pct
            
            # Time efficiency factor
            # If we have both actual and expected time, calculate time ratio
            if time_estimate > 0 and time_actual > 0:
                # Expected time for this completion %: (completion_pct / 100) * time_estimate
                expected_time_for_completion = (completion_pct / 100.0) * time_estimate
                
                if expected_time_for_completion > 0:
                    # Time efficiency: did we complete faster or slower than expected?
                    # Ratio > 1 means we were faster, < 1 means slower
                    time_ratio = expected_time_for_completion / max(time_actual, 0.1)
                    
                    # Time efficiency bonus/penalty: scales with completion %
                    # If 100% done in less time = big bonus
                    # If 25% done in <25% of time = good bonus
                    time_efficiency_factor = time_ratio * (completion_pct / 100.0)
                else:
                    time_efficiency_factor = 1.0
                
                # For 100% completed tasks that took longer: factor in relief to mitigate penalty
                if completion_pct >= 100 and time_actual > time_estimate:
                    # Over time penalty is reduced by relief
                    over_time_penalty = (time_actual / time_estimate) - 1.0
                    # Relief mitigates: high relief (8+) can offset up to 50% of over-time penalty
                    relief_mitigation = min(relief_score / 10.0, 0.5)
                    # Adjust time efficiency factor to account for over-time, mitigated by relief
                    time_efficiency_factor = max(0.5, 1.0 - (over_time_penalty * (1.0 - relief_mitigation)))
            else:
                # No time data, neutral factor
                time_efficiency_factor = 1.0
            
            # Relief bonus: scales with relief score (0-10 -> 0-20 bonus points)
            relief_bonus = relief_score * 2.0
            
            # Motivation factor: if low motivation but high relief and good time ratio
            motivation_bonus = 0.0
            if motivation is not None and motivation < 5 and relief_score >= 6:
                # Low motivation (0-4) + high relief (6+) = bonus
                # Bonus increases if time efficiency is also good
                motivation_bonus = (5 - motivation) * (relief_score / 10.0) * time_efficiency_factor
            
            # Calculate final efficiency score
            efficiency = (base_efficiency * time_efficiency_factor) + relief_bonus + motivation_bonus
            
            return round(float(efficiency), 2)
        except Exception as e:
            # Return 0 if calculation fails
            return 0.0

    def get_efficiency_summary(self) -> Dict[str, any]:
        """Calculate efficiency statistics for completed tasks."""
        df = self._load_instances()
        
        if df.empty:
            return {
                'avg_efficiency': 0.0,
                'high_efficiency_count': 0,
                'low_efficiency_count': 0,
                'efficiency_by_completion': {},
            }
        
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'avg_efficiency': 0.0,
                'high_efficiency_count': 0,
                'low_efficiency_count': 0,
                'efficiency_by_completion': {},
            }
        
        # Calculate efficiency for each completed task
        completed['efficiency_score'] = completed.apply(self.calculate_efficiency_score, axis=1)
        
        # Filter out zero efficiency (likely missing data)
        valid_efficiency = completed[completed['efficiency_score'] > 0]
        
        if valid_efficiency.empty:
            return {
                'avg_efficiency': 0.0,
                'high_efficiency_count': 0,
                'low_efficiency_count': 0,
                'efficiency_by_completion': {},
            }
        
        avg_efficiency = valid_efficiency['efficiency_score'].mean()
        high_efficiency = valid_efficiency[valid_efficiency['efficiency_score'] >= 80]
        low_efficiency = valid_efficiency[valid_efficiency['efficiency_score'] < 50]
        
        # Group by completion percentage ranges
        def _get_completion_range(row):
            actual_dict = row.get('actual_dict', {})
            completion = actual_dict.get('completion_percent', 0)
            try:
                completion = float(completion)
                if completion >= 100:
                    return '100%'
                elif completion >= 75:
                    return '75-99%'
                elif completion >= 50:
                    return '50-74%'
                elif completion >= 25:
                    return '25-49%'
                else:
                    return '0-24%'
            except:
                return 'unknown'
        
        completed['completion_range'] = completed.apply(_get_completion_range, axis=1)
        efficiency_by_completion = completed.groupby('completion_range')['efficiency_score'].mean().to_dict()
        
        return {
            'avg_efficiency': round(float(avg_efficiency), 2),
            'high_efficiency_count': int(len(high_efficiency)),
            'low_efficiency_count': int(len(low_efficiency)),
            'efficiency_by_completion': {k: round(float(v), 2) for k, v in efficiency_by_completion.items()},
        }

    def get_task_relief_history(self, task_id: Optional[str] = None) -> Dict[str, float]:
        """Get relief history for a specific task or all tasks.
        
        Returns average relief points (actual - expected) per task.
        Negative values indicate tasks that consistently underdeliver on expected relief.
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {}
        
        # Extract expected and actual relief
        def _get_expected_relief(row):
            try:
                pred_dict = row['predicted_dict']
                if isinstance(pred_dict, dict):
                    return pred_dict.get('expected_relief', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
        completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
        completed['actual_relief'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        
        # Filter to rows with both expected and actual
        has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
        relief_data = completed[has_both].copy()
        
        if relief_data.empty:
            return {}
        
        # Calculate relief points per row
        relief_data['relief_points'] = relief_data['actual_relief'] - relief_data['expected_relief']
        
        # Filter by task_id if provided
        if task_id:
            relief_data = relief_data[relief_data['task_id'] == task_id]
        
        if relief_data.empty:
            return {}
        
        # Group by task_id and calculate average relief points
        task_relief = relief_data.groupby('task_id')['relief_points'].agg(['mean', 'count']).to_dict('index')
        
        # Convert to simpler format: {task_id: avg_relief_points}
        result = {}
        for tid, stats in task_relief.items():
            result[tid] = round(float(stats['mean']), 2)
        
        return result

    def get_task_efficiency_history(self) -> Dict[str, float]:
        """Get average efficiency score per task based on completed instances.
        
        Returns {task_id: avg_efficiency_score}
        Useful for recommending tasks that have historically been efficient.
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {}
        
        # Calculate efficiency for each completed task
        completed['efficiency_score'] = completed.apply(self.calculate_efficiency_score, axis=1)
        
        # Filter to valid efficiency scores
        valid = completed[completed['efficiency_score'] > 0]
        
        if valid.empty:
            return {}
        
        # Group by task_id and calculate average efficiency
        task_efficiency = valid.groupby('task_id')['efficiency_score'].agg(['mean', 'count']).to_dict('index')
        
        # Convert to simpler format: {task_id: avg_efficiency}
        result = {}
        for tid, stats in task_efficiency.items():
            result[tid] = round(float(stats['mean']), 2)
        
        return result

    # ------------------------------------------------------------------
    # Recommendation helpers
    # ------------------------------------------------------------------
    def default_filters(self) -> Dict[str, Optional[float]]:
        return {
            'max_duration': None,
        }

    def available_filters(self) -> List[Dict[str, str]]:
        return [
            {'key': 'max_duration', 'label': 'Max Duration (minutes)'},
        ]

    def recommendations(self, filters: Optional[Dict[str, float]] = None) -> List[Dict[str, str]]:
        """Generate recommendations based on all task templates, using historical data from completed instances."""
        from .task_manager import TaskManager
        
        filters = {**self.default_filters(), **(filters or {})}
        print(f"[Analytics] recommendations called with filters: {filters}")
        
        # Load all task templates
        task_manager = TaskManager()
        all_tasks_df = task_manager.get_all()
        if all_tasks_df.empty:
            return []
        
        # Load historical instance data to inform recommendations
        instances_df = self._load_instances()
        
        # Get historical averages per task from completed instances
        completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy() if not instances_df.empty else pd.DataFrame()
        
        # Calculate historical averages per task_id
        task_stats = {}
        if not completed.empty:
            # Group by task_id and calculate averages
            for task_id in completed['task_id'].unique():
                task_completed = completed[completed['task_id'] == task_id]
                if not task_completed.empty:
                    task_stats[task_id] = {
                        'avg_relief': task_completed['relief_score'].mean() if task_completed['relief_score'].notna().any() else None,
                        'avg_cognitive_load': task_completed['cognitive_load'].mean() if task_completed['cognitive_load'].notna().any() else None,
                        'avg_emotional_load': task_completed['emotional_load'].mean() if task_completed['emotional_load'].notna().any() else None,
                        'avg_duration': task_completed['duration_minutes'].mean() if task_completed['duration_minutes'].notna().any() else None,
                        'count': len(task_completed),
                    }
        
        # Get task efficiency history
        task_efficiency = self.get_task_efficiency_history()
        
        # Build recommendation candidates from all task templates
        candidates = []
        max_duration_filter = None
        if filters.get('max_duration'):
            try:
                max_duration_filter = float(filters['max_duration'])
            except (ValueError, TypeError):
                max_duration_filter = None
        
        for _, task_row in all_tasks_df.iterrows():
            task_id = task_row['task_id']
            task_name = task_row['name']
            default_estimate = task_row.get('default_estimate_minutes', 0)
            
            try:
                default_estimate = float(default_estimate) if default_estimate else 0
            except (ValueError, TypeError):
                default_estimate = 0
            
            # Get historical stats for this task
            stats = task_stats.get(task_id, {})
            avg_relief = stats.get('avg_relief') if stats.get('avg_relief') is not None else None
            avg_cognitive = stats.get('avg_cognitive_load') if stats.get('avg_cognitive_load') is not None else None
            avg_emotional = stats.get('avg_emotional_load') if stats.get('avg_emotional_load') is not None else None
            avg_duration = stats.get('avg_duration') if stats.get('avg_duration') is not None else default_estimate
            historical_efficiency = task_efficiency.get(task_id, 0)
            
            # Use historical data if available, otherwise use defaults
            relief_score = avg_relief if avg_relief is not None else 5.0  # Default neutral
            cognitive_load = avg_cognitive if avg_cognitive is not None else 5.0  # Default neutral
            emotional_load = avg_emotional if avg_emotional is not None else 5.0  # Default neutral
            duration_minutes = avg_duration if avg_duration else default_estimate
            
            # Apply max_duration filter after calculating duration_minutes
            # Use the duration_minutes (which includes historical average if available)
            if max_duration_filter is not None:
                # Filter out tasks that exceed the max duration
                # Note: tasks with 0 duration (unknown) will pass the filter
                if duration_minutes > max_duration_filter:
                    continue
            
            candidates.append({
                'task_id': task_id,
                'task_name': task_name,
                'relief_score': relief_score,
                'cognitive_load': cognitive_load,
                'emotional_load': emotional_load,
                'duration_minutes': duration_minutes,
                'historical_efficiency': historical_efficiency,
                'default_estimate': default_estimate,
            })
        
        if not candidates:
            return []
        
        candidates_df = pd.DataFrame(candidates)
        
        ranked = []
        
        # Always include highest relief pick
        row = candidates_df.sort_values('relief_score', ascending=False).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Highest Relief"))
        
        # Always include shortest task pick
        row = candidates_df.sort_values('duration_minutes', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Shortest Task"))
        
        # Always include lowest cognitive load pick
        row = candidates_df.sort_values('cognitive_load', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Cognitive Load"))
        
        # Always include lowest emotional load pick
        row = candidates_df.sort_values('emotional_load', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Emotional Load"))
        
        # Always include lowest net load pick (cognitive + emotional)
        candidates_df['net_load'] = candidates_df['cognitive_load'] + candidates_df['emotional_load']
        row = candidates_df.sort_values('net_load', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Net Load"))
        
        # Always include net relief pick for variety
        candidates_df['net_relief_proxy'] = candidates_df['relief_score'] - candidates_df['cognitive_load']
        row = candidates_df.sort_values('net_relief_proxy', ascending=False).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Highest Net Relief"))
        
        # Always include efficiency-based pick if we have efficiency data
        high_eff = candidates_df[candidates_df['historical_efficiency'] > 0]
        if not high_eff.empty:
            row = high_eff.sort_values('historical_efficiency', ascending=False).head(1)
            if not row.empty:
                ranked.append(self._task_to_recommendation(row.iloc[0], "High Efficiency Candidate"))
        
        return [r for r in ranked if r]

    def _row_to_recommendation(self, row_df: pd.DataFrame, label: str) -> Optional[Dict[str, str]]:
        """Legacy method for instance-based recommendations."""
        if row_df is None or row_df.empty:
            return None
        row = row_df.iloc[0]
        reason = f"{label}: relief {row.get('relief_score', '—')} / cognitive {row.get('cognitive_load', '—')}."
        return {
            'title': label,
            'instance_id': row.get('instance_id'),
            'task_id': row.get('task_id'),
            'task_name': row.get('task_name'),
            'reason': reason,
            'duration': row.get('duration_minutes'),
            'relief': row.get('relief_score'),
            'cognitive_load': row.get('cognitive_load'),
        }
    
    def _task_to_recommendation(self, task_row: pd.Series, label: str) -> Dict[str, str]:
        """Convert a task template row to a recommendation dict."""
        relief = task_row.get('relief_score', 0)
        cognitive = task_row.get('cognitive_load', 0)
        emotional = task_row.get('emotional_load', 0)
        duration = task_row.get('duration_minutes', task_row.get('default_estimate', 0))
        
        # Format relief and cognitive to 1 decimal place
        try:
            relief_val = float(relief) if relief is not None else 0
            relief_str = f"{relief_val:.1f}" if relief_val > 0 else "—"
        except (ValueError, TypeError):
            relief_str = "—"
        
        try:
            cognitive_val = float(cognitive) if cognitive is not None else 0
            cognitive_str = f"{cognitive_val:.1f}" if cognitive_val > 0 else "—"
        except (ValueError, TypeError):
            cognitive_str = "—"
        
        try:
            emotional_val = float(emotional) if emotional is not None else 0
            emotional_str = f"{emotional_val:.1f}" if emotional_val > 0 else "—"
        except (ValueError, TypeError):
            emotional_str = "—"
        
        try:
            duration_val = float(duration) if duration is not None else 0
            duration_str = f"{duration_val:.0f}" if duration_val > 0 else "—"
        except (ValueError, TypeError):
            duration_str = "—"
        
        # Build reason string - include emotional load if relevant
        if emotional_str != "—" and emotional_val > 0:
            reason = f"{label}: relief {relief_str} / cognitive {cognitive_str} / emotional {emotional_str}."
        else:
            reason = f"{label}: relief {relief_str} / cognitive {cognitive_str}."
        
        return {
            'title': label,
            'task_id': task_row.get('task_id'),
            'task_name': task_row.get('task_name'),
            'reason': reason,
            'duration': duration_str,
            'relief': relief_str,
            'cognitive_load': cognitive_str,
        }

    # ------------------------------------------------------------------
    # Analytics datasets for charts
    # ------------------------------------------------------------------
    def trend_series(self) -> pd.DataFrame:
        df = self._load_instances()
        if df.empty:
            return pd.DataFrame(columns=['completed_at', 'relief_score', 'duration_minutes'])
        completed = df[df['completed_at'].astype(str).str.len() > 0]
        if completed.empty:
            return pd.DataFrame(columns=['completed_at', 'relief_score', 'duration_minutes'])
        completed['completed_at'] = pd.to_datetime(completed['completed_at'])
        completed = completed.sort_values('completed_at')
        return completed[['completed_at', 'relief_score', 'duration_minutes', 'cognitive_load']]

    def attribute_distribution(self) -> pd.DataFrame:
        df = self._load_instances()
        if df.empty:
            return pd.DataFrame(columns=['attribute', 'value'])
        melted_frames = []
        for attr in TASK_ATTRIBUTES:
            if attr.dtype != 'numeric':
                continue
            sub = df[[attr.key]].rename(columns={attr.key: 'value'}).dropna()
            sub['attribute'] = attr.label
            melted_frames.append(sub)
        if not melted_frames:
            return pd.DataFrame(columns=['attribute', 'value'])
        return pd.concat(melted_frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Priority heuristics (used for legacy views)
    # ------------------------------------------------------------------
    def compute_priority_score(self, instance_row: dict):
        try:
            p = float(instance_row.get('procrastination_score') or 0)
            predicted = instance_row.get('predicted') or '{}'
            pred = json.loads(predicted)
            tmin = float(pred.get('time_estimate_minutes') or pred.get('estimate') or 0)
            proact = float(instance_row.get('proactive_score') or 0)
            score = p * 1.5 + (tmin / 60.0) - (proact * 0.5)
            return round(score, 3)
        except Exception:
            return 0.0


# Library references for documentation / UI hints
SUGGESTED_ANALYTICS_LIBRARIES = [
    "Plotly Express (interactive, declarative)",
    "Altair / Vega-Lite (grammar of graphics, good for small datasets)",
    "Pandas Profiling (automatic data summaries)",
]

SUGGESTED_ML_LIBRARIES = [
    "scikit-learn (baselines, pipelines)",
    "PyTorch (deep recommenders, embeddings)",
    "LightFM (hybrid recommendation systems)",
]
