# backend/analytics.py
from __future__ import annotations

import json
import math
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from scipy import stats

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

        # Extract physical_load from JSON if not in CSV columns
        if 'physical_load' not in df.columns:
            df['physical_load'] = pd.NA
        df['physical_load'] = df['physical_load'].replace('', pd.NA)
        df['physical_load'] = df['physical_load'].fillna(df['actual_dict'].apply(lambda r: r.get('actual_physical')))
        df['physical_load'] = df['physical_load'].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_physical_load')))
        df['physical_load'] = pd.to_numeric(df['physical_load'], errors='coerce')
        df['physical_load'] = df['physical_load'].fillna(0.0)  # Default to 0 if missing

        # Calculate stress_level: average of all loads (0-100 scale to match relief)
        df['relief_score_numeric'] = pd.to_numeric(df['relief_score'], errors='coerce').fillna(0.0)
        df['cognitive_load_numeric'] = pd.to_numeric(df['cognitive_load'], errors='coerce').fillna(0.0)
        df['emotional_load_numeric'] = pd.to_numeric(df['emotional_load'], errors='coerce').fillna(0.0)
        df['physical_load_numeric'] = pd.to_numeric(df['physical_load'], errors='coerce').fillna(0.0)
        
        df['stress_level'] = (
            (df['cognitive_load_numeric'] + 
             df['emotional_load_numeric'] + 
             df['physical_load_numeric']) / 3.0
        )
        
        # Calculate net_wellbeing: relief minus stress (can be positive or negative)
        # Range: -100 to +100, where 0 = neutral (relief = stress)
        df['net_wellbeing'] = df['relief_score_numeric'] - df['stress_level']
        
        # Calculate net_wellbeing_normalized: normalized to 0-100 scale with 50 as neutral
        # Range: 0-100, where 50 = neutral (relief = stress), >50 = beneficial, <50 = costly
        df['net_wellbeing_normalized'] = 50.0 + (df['net_wellbeing'] / 2.0)
        
        # Calculate stress_efficiency: relief per unit of stress (ratio). If stress_level
        # is zero or missing, leave the metric empty to avoid infinities. Ensure numeric dtype.
        stress_safe = pd.to_numeric(df['stress_level'], errors='coerce')
        stress_safe = stress_safe.mask(stress_safe <= 0, np.nan)  # keep float dtype
        relief_safe = pd.to_numeric(df['relief_score_numeric'], errors='coerce')
        df['stress_efficiency'] = (relief_safe / stress_safe).round(4)

        # Keep raw ratio and provide a 0-100 normalized version (min-max across observed rows)
        df['stress_efficiency_raw'] = df['stress_efficiency']
        se_valid = df['stress_efficiency'].dropna()
        if not se_valid.empty:
            se_min = se_valid.min()
            se_max = se_valid.max()
            if pd.notna(se_min) and pd.notna(se_max):
                if se_max > se_min:
                    df['stress_efficiency'] = ((df['stress_efficiency'] - se_min) / (se_max - se_min)) * 100.0
                else:
                    # All values identical; treat them as 100 for visibility
                    df['stress_efficiency'] = 100.0
            df['stress_efficiency'] = df['stress_efficiency'].round(2)
        
        # Auto-calculate behavioral_score: how well you adhered to planned behaviour
        # 0 = maximum procrastination, 50 = neutral (perfect adherence), 100 = maximum overachievement
        # Range: 0-100 (50 = neutral)
        def _calculate_behavioral_score(row):
            try:
                # Get completion percentage
                actual_dict = row.get('actual_dict', {})
                predicted_dict = row.get('predicted_dict', {})
                
                completion_pct = actual_dict.get('completion_percent', 100)
                completion_pct = float(completion_pct) if completion_pct else 100.0
                
                # Get time data
                time_actual = actual_dict.get('time_actual_minutes', 0)
                time_estimate = predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0)
                time_actual = float(time_actual) if time_actual else 0.0
                time_estimate = float(time_estimate) if time_estimate else 0.0
                
                # Get procrastination score (0-10 scale)
                procrast_score = pd.to_numeric(row.get('procrastination_score', 0), errors='coerce') or 0.0
                
                # Calculate components (each contributes to -10 to +10 range internally)
                # 1. Completion component: -5 to +5 based on completion percentage
                #    100% = 0, <100% = negative, >100% = positive (if possible)
                completion_component = ((completion_pct - 100.0) / 100.0) * 5.0
                completion_component = max(-5.0, min(5.0, completion_component))
                
                # 2. Time efficiency component: -5 to +5 based on actual vs expected time
                #    Faster than expected = positive, slower = negative
                time_component = 0.0
                if time_estimate > 0 and time_actual > 0:
                    time_ratio = time_estimate / max(time_actual, 0.1)  # >1 if faster, <1 if slower
                    # Convert to -5 to +5 scale
                    # If took exactly expected time: 0
                    # If took 2x expected: -2.5
                    # If took 0.5x expected: +2.5
                    time_component = ((time_ratio - 1.0) * 5.0)
                    time_component = max(-5.0, min(5.0, time_component))
                
                # 3. Procrastination component: -5 to 0 based on delay
                #    No delay = 0, high delay = -5
                procrast_component = -(procrast_score / 10.0) * 5.0
                procrast_component = max(-5.0, min(0.0, procrast_component))
                
                # Combine components (weighted average) - still in -10 to +10 range
                # Completion and time efficiency are equally important
                # Procrastination adds negative bias
                behavioral_deviation = (completion_component * 0.4) + (time_component * 0.4) + (procrast_component * 0.2)
                
                # Clamp to -10 to +10 range
                behavioral_deviation = max(-10.0, min(10.0, behavioral_deviation))
                
                # Convert to 0-100 scale where 50 = neutral (0 deviation)
                # Formula: 50 + (deviation * 5)
                # -10 → 0, 0 → 50, +10 → 100
                behavioral_score = 50.0 + (behavioral_deviation * 5.0)
                
                # Clamp to 0-100 range
                behavioral_score = max(0.0, min(100.0, behavioral_score))
                
                return round(behavioral_score, 2)
            except Exception as e:
                # Return 50 (neutral) if calculation fails
                return 50.0
        
        df['behavioral_score'] = df.apply(_calculate_behavioral_score, axis=1)
        # Normalize behavioral_score relative to observed best/worst so the most
        # proactive instance maps to 100 and the worst procrastination maps to 0.
        # Keep the raw value for inspection if needed.
        df['behavioral_score_raw'] = df['behavioral_score']
        min_bs = df['behavioral_score'].min()
        max_bs = df['behavioral_score'].max()
        if pd.notna(min_bs) and pd.notna(max_bs) and max_bs > min_bs:
            df['behavioral_score'] = ((df['behavioral_score'] - min_bs) / (max_bs - min_bs)) * 100.0
        # If all values are identical, leave the original (already 0-100) scale.
        df['behavioral_score'] = df['behavioral_score'].round(2)

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
                'quality': {'avg_relief': 0.0, 'avg_cognitive_load': 0.0, 'avg_stress_level': 0.0, 'avg_net_wellbeing': 0.0, 'avg_net_wellbeing_normalized': 50.0, 'avg_stress_efficiency': None},
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

        # Calculate completion rate
        total_created = len(df[df['created_at'].astype(str).str.len() > 0])
        total_completed = len(completed)
        completion_rate = (total_completed / total_created * 100.0) if total_created > 0 else 0.0
        
        # Calculate time estimation accuracy
        completed_with_time = completed.copy()
        completed_with_time['time_actual_num'] = pd.to_numeric(
            completed_with_time['duration_minutes'], errors='coerce'
        )
        completed_with_time['time_estimate_num'] = completed_with_time['predicted_dict'].apply(
            lambda d: float(d.get('time_estimate_minutes') or d.get('estimate') or 0) if isinstance(d, dict) else 0
        )
        # Filter to rows with both actual and estimate > 0
        valid_time_comparisons = completed_with_time[
            (completed_with_time['time_actual_num'] > 0) & 
            (completed_with_time['time_estimate_num'] > 0)
        ]
        time_accuracy = 0.0
        if not valid_time_comparisons.empty:
            # Calculate ratio: actual / estimate (1.0 = perfect, >1 = took longer, <1 = took less)
            time_accuracy = _avg(valid_time_comparisons['time_actual_num'] / valid_time_comparisons['time_estimate_num'])
        
        metrics = {
            'counts': {
                'active': int(len(active)),
                'completed_7d': int(len(completed_7d)),
                'total_created': int(total_created),
                'total_completed': int(total_completed),
                'completion_rate': round(completion_rate, 1),
            },
            'quality': {
                'avg_relief': _avg(df['relief_score']),
                'avg_cognitive_load': _avg(df['cognitive_load']),
                'avg_stress_level': _avg(df['stress_level']),
                'avg_net_wellbeing': _avg(df['net_wellbeing']),
                'avg_net_wellbeing_normalized': _avg(df['net_wellbeing_normalized']),
                'avg_stress_efficiency': _avg(df['stress_efficiency']),
            },
            'time': {
                'median_duration': _median(df['duration_minutes']),
                'avg_delay': _avg(df['delay_minutes']),
                'estimation_accuracy': round(time_accuracy, 2),
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
                'total_relief_duration_score': 0.0,
                'avg_relief_duration_score': 0.0,
                'total_relief_score': 0.0,
                'weekly_relief_score': 0.0,
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
                'total_relief_duration_score': 0.0,
                'avg_relief_duration_score': 0.0,
                'total_relief_score': 0.0,
                'weekly_relief_score': 0.0,
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
        
        # Calculate productivity time (sum of actual time from actual_dict) - LAST 7 DAYS ONLY
        from datetime import timedelta
        seven_days_ago = datetime.now() - timedelta(days=7)
        
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
        
        # Filter to last 7 days
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed_last_7d = completed[completed['completed_at_dt'] >= seven_days_ago]
        productivity_time = completed_last_7d['time_actual'].fillna(0).sum()
        
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
        
        # Calculate relief × duration metrics
        # Use actual relief_score and duration_minutes from completed tasks
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        completed['duration_minutes_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce')
        
        # Calculate relief_duration_score per task instance (relief_score × duration_minutes)
        completed['relief_duration_score'] = (
            completed['relief_score_numeric'] * completed['duration_minutes_numeric']
        )
        
        # Filter to rows with valid relief_duration_score (both relief and duration must be present)
        valid_relief_duration = completed[
            completed['relief_duration_score'].notna() & 
            (completed['relief_duration_score'] != 0)
        ]
        
        # Calculate totals and averages
        total_relief_duration_score = valid_relief_duration['relief_duration_score'].sum() if not valid_relief_duration.empty else 0.0
        avg_relief_duration_score = valid_relief_duration['relief_duration_score'].mean() if not valid_relief_duration.empty else 0.0
        
        # Total relief score is the same as total_relief_duration_score (sum of relief × duration)
        total_relief_score = total_relief_duration_score
        
        # Calculate weekly relief score (sum of relief × duration for last 7 days)
        completed_last_7d['relief_score_numeric'] = pd.to_numeric(completed_last_7d['relief_score'], errors='coerce')
        completed_last_7d['duration_minutes_numeric'] = pd.to_numeric(completed_last_7d['duration_minutes'], errors='coerce')
        completed_last_7d['relief_duration_score'] = (
            completed_last_7d['relief_score_numeric'] * completed_last_7d['duration_minutes_numeric']
        )
        weekly_relief_score = completed_last_7d['relief_duration_score'].fillna(0).sum()
        
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
            'total_relief_duration_score': round(float(total_relief_duration_score), 2),
            'avg_relief_duration_score': round(float(avg_relief_duration_score), 2),
            'total_relief_score': round(float(total_relief_score), 2),
            'weekly_relief_score': round(float(weekly_relief_score), 2),
        }

    def get_weekly_hours_history(self) -> Dict[str, any]:
        """Get historical daily productivity hours data for trend analysis (last 90 days).
        
        Returns:
            Dict with 'dates' (list of date strings), 'hours' (list of hours per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'hours': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Get actual time from completed tasks
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
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows with time and date
        valid = completed[completed['time_actual'].notna() & completed['completed_at_dt'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'hours': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last 90 days
        from datetime import timedelta
        ninety_days_ago = datetime.now() - timedelta(days=90)
        valid = valid[valid['completed_at_dt'] >= ninety_days_ago].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'hours': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by day - only include days with data
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_data = valid.groupby('date')['time_actual'].sum().reset_index()
        daily_data['hours'] = daily_data['time_actual'] / 60.0
        daily_data = daily_data.sort_values('date')
        
        # Filter to last 90 days (but keep only days with data)
        daily_data = daily_data[daily_data['date'] >= ninety_days_ago.date()].copy()
        
        # Format dates as strings
        daily_data['date_str'] = daily_data['date'].astype(str)
        
        # Get current value (last 7 days total) - this stays as weekly total for the main card
        seven_days_ago = datetime.now() - timedelta(days=7)
        current_week_data = valid[valid['completed_at_dt'] >= seven_days_ago]
        current_value = current_week_data['time_actual'].sum() / 60.0 if not current_week_data.empty else 0.0
        
        # Calculate weekly average (average of daily hours over last 7 days with data)
        # This is the average daily value, used for chart comparison
        last_7_days = daily_data.tail(7) if len(daily_data) >= 7 else daily_data
        weekly_average = last_7_days['hours'].mean() if not last_7_days.empty else 0.0
        
        # Calculate 3-month average (average of daily hours over all days with data)
        three_month_average = daily_data['hours'].mean() if not daily_data.empty else 0.0
        
        # Check if we have at least 2 weeks of data
        days_with_data = len(daily_data)
        has_sufficient_data = days_with_data >= 14
        
        return {
            'dates': daily_data['date_str'].tolist(),
            'hours': daily_data['hours'].tolist(),
            'current_value': round(float(current_value), 2),
            'weekly_average': round(float(weekly_average), 2),
            'three_month_average': round(float(three_month_average), 2),
            'has_sufficient_data': has_sufficient_data,
            'days_with_data': days_with_data,
        }

    def get_weekly_relief_history(self) -> Dict[str, any]:
        """Get historical daily relief points data for trend analysis (last 90 days).
        
        Returns:
            Dict with 'dates' (list of date strings), 'relief_points' (list of relief points per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'relief_points': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Calculate relief × duration score for each task
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        completed['duration_minutes_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce')
        completed['relief_duration_score'] = (
            completed['relief_score_numeric'] * completed['duration_minutes_numeric']
        )
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows with relief score and date
        valid = completed[
            completed['relief_duration_score'].notna() & 
            (completed['relief_duration_score'] != 0) &
            completed['completed_at_dt'].notna()
        ].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'relief_points': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last 90 days
        from datetime import timedelta
        ninety_days_ago = datetime.now() - timedelta(days=90)
        valid = valid[valid['completed_at_dt'] >= ninety_days_ago].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'relief_points': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by day - only include days with data
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_data = valid.groupby('date')['relief_duration_score'].sum().reset_index()
        daily_data['relief_points'] = daily_data['relief_duration_score']
        daily_data = daily_data.sort_values('date')
        
        # Filter to last 90 days (but keep only days with data)
        daily_data = daily_data[daily_data['date'] >= ninety_days_ago.date()].copy()
        
        # Format dates as strings
        daily_data['date_str'] = daily_data['date'].astype(str)
        
        # Get current value (last 7 days total) - this stays as weekly total for the main card
        seven_days_ago = datetime.now() - timedelta(days=7)
        current_week_data = valid[valid['completed_at_dt'] >= seven_days_ago]
        current_value = current_week_data['relief_duration_score'].sum() if not current_week_data.empty else 0.0
        
        # Calculate weekly average (average of daily relief points over last 7 days with data)
        # This is the average daily value, used for chart comparison
        last_7_days = daily_data.tail(7) if len(daily_data) >= 7 else daily_data
        weekly_average = last_7_days['relief_points'].mean() if not last_7_days.empty else 0.0
        
        # Calculate 3-month average (average of daily relief points over all days with data)
        three_month_average = daily_data['relief_points'].mean() if not daily_data.empty else 0.0
        
        # Check if we have at least 2 weeks of data
        days_with_data = len(daily_data)
        has_sufficient_data = days_with_data >= 14
        
        return {
            'dates': daily_data['date_str'].tolist(),
            'relief_points': daily_data['relief_points'].tolist(),
            'current_value': round(float(current_value), 2),
            'weekly_average': round(float(weekly_average), 2),
            'three_month_average': round(float(three_month_average), 2),
            'has_sufficient_data': has_sufficient_data,
            'days_with_data': days_with_data,
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

    def get_task_performance_ranking(self, metric: str = 'relief', top_n: int = 5) -> List[Dict[str, any]]:
        """Get top/bottom performing tasks by various metrics.
        
        Args:
            metric: 'relief', 'stress_efficiency', 'behavioral_score', 'stress_level'
            top_n: Number of top tasks to return
        
        Returns:
            List of dicts with task_id, task_name, metric_value, and count
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return []
        
        # Map metric names to columns
        metric_map = {
            'relief': 'relief_score',
            'stress_efficiency': 'stress_efficiency',
            'behavioral_score': 'behavioral_score',
            'stress_level': 'stress_level',
        }
        
        if metric not in metric_map:
            metric = 'relief'
        
        column = metric_map[metric]
        
        # Group by task_id and calculate averages
        task_stats = completed.groupby('task_id').agg({
            column: ['mean', 'count'],
            'task_name': 'first'
        }).reset_index()
        
        task_stats.columns = ['task_id', 'metric_value', 'count', 'task_name']
        
        # Filter out tasks with no valid data
        task_stats = task_stats[task_stats['metric_value'].notna()]
        
        if task_stats.empty:
            return []
        
        # Sort appropriately (higher is better for relief, stress_efficiency, behavioral_score; lower is better for stress_level)
        ascending = (metric == 'stress_level')
        task_stats = task_stats.sort_values('metric_value', ascending=ascending)
        
        # Get top N
        top_tasks = task_stats.head(top_n)
        
        result = []
        for _, row in top_tasks.iterrows():
            result.append({
                'task_id': row['task_id'],
                'task_name': row['task_name'],
                'metric_value': round(float(row['metric_value']), 2),
                'count': int(row['count']),
                'metric': metric,
            })
        
        return result

    def get_stress_efficiency_leaderboard(self, top_n: int = 10) -> List[Dict[str, any]]:
        """Get tasks with highest stress efficiency (relief per unit of stress).
        
        Args:
            top_n: Number of top tasks to return
        
        Returns:
            List of dicts with task_id, task_name, stress_efficiency, avg_relief, avg_stress, and count
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return []
        
        # Filter to tasks with valid stress efficiency
        valid = completed[completed['stress_efficiency'].notna() & (completed['stress_efficiency'] > 0)].copy()
        
        if valid.empty:
            return []
        
        # Group by task_id and calculate averages
        task_stats = valid.groupby('task_id').agg({
            'stress_efficiency': 'mean',
            'relief_score': 'mean',
            'stress_level': 'mean',
            'task_name': 'first'
        }).reset_index()
        
        task_stats.columns = ['task_id', 'avg_stress_efficiency', 'avg_relief', 'avg_stress', 'task_name']
        
        # Add count
        task_counts = valid.groupby('task_id').size().reset_index(name='count')
        task_stats = task_stats.merge(task_counts, on='task_id')
        
        # Sort by stress efficiency (descending)
        task_stats = task_stats.sort_values('avg_stress_efficiency', ascending=False)
        
        # Get top N
        top_tasks = task_stats.head(top_n)
        
        result = []
        for _, row in top_tasks.iterrows():
            result.append({
                'task_id': row['task_id'],
                'task_name': row['task_name'],
                'stress_efficiency': round(float(row['avg_stress_efficiency']), 2),
                'avg_relief': round(float(row['avg_relief']), 2),
                'avg_stress': round(float(row['avg_stress']), 2),
                'count': int(row['count']),
            })
        
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
        
        # Always include net relief picks for variety
        candidates_df['net_relief_proxy'] = candidates_df['relief_score'] - candidates_df['cognitive_load']
        # Highest Net Relief
        row = candidates_df.sort_values('net_relief_proxy', ascending=False).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Highest Net Relief"))
        # Lowest Net Relief (for comparison)
        row = candidates_df.sort_values('net_relief_proxy', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Net Relief"))
        
        # Always include efficiency-based pick if we have efficiency data
        high_eff = candidates_df[candidates_df['historical_efficiency'] > 0]
        if not high_eff.empty:
            row = high_eff.sort_values('historical_efficiency', ascending=False).head(1)
            if not row.empty:
                ranked.append(self._task_to_recommendation(row.iloc[0], "High Efficiency Candidate"))
        
        return [r for r in ranked if r]

    def recommendations_by_category(self, metrics: Union[str, List[str]], filters: Optional[Dict[str, float]] = None, limit: int = 3) -> List[Dict[str, str]]:
        """Generate recommendations ranked by a set of metrics.

        metrics can be a single metric name or a list. Each metric contributes to
        the score; high-is-good metrics add their value, and low-is-good metrics
        add (100 - value) to prioritize lower numbers.
        """
        from .task_manager import TaskManager
        
        filters = {**self.default_filters(), **(filters or {})}
        print(f"[Analytics] recommendations_by_category called with metrics: {metrics}, limit: {limit}, filters: {filters}")
        
        # Normalize metrics input
        if metrics is None:
            metrics = []
        if isinstance(metrics, str):
            metrics = [metrics]
        metrics = [m for m in metrics if m] or ["relief_score"]
        
        # Which metrics are better when low
        low_is_good = {
            "cognitive_load",
            "emotional_load",
            "net_load",
            "duration_minutes",
            "stress_level",
            "physical_load",
        }
        
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
                        'avg_stress_level': task_completed['stress_level'].mean() if 'stress_level' in task_completed and task_completed['stress_level'].notna().any() else None,
                        'avg_behavioral_score': task_completed['behavioral_score'].mean() if 'behavioral_score' in task_completed and task_completed['behavioral_score'].notna().any() else None,
                        'avg_net_wellbeing': task_completed['net_wellbeing_normalized'].mean() if 'net_wellbeing_normalized' in task_completed and task_completed['net_wellbeing_normalized'].notna().any() else None,
                        'avg_physical_load': task_completed['physical_load'].mean() if 'physical_load' in task_completed and task_completed['physical_load'].notna().any() else None,
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
            avg_stress = stats.get('avg_stress_level') if stats.get('avg_stress_level') is not None else None
            avg_behavioral = stats.get('avg_behavioral_score') if stats.get('avg_behavioral_score') is not None else None
            avg_net_wellbeing = stats.get('avg_net_wellbeing') if stats.get('avg_net_wellbeing') is not None else None
            avg_physical = stats.get('avg_physical_load') if stats.get('avg_physical_load') is not None else None
            
            # Use historical data if available, otherwise use defaults
            relief_score = avg_relief if avg_relief is not None else 5.0  # Default neutral
            cognitive_load = avg_cognitive if avg_cognitive is not None else 5.0  # Default neutral
            emotional_load = avg_emotional if avg_emotional is not None else 5.0  # Default neutral
            stress_level = avg_stress if avg_stress is not None else 50.0  # Neutral midpoint
            behavioral_score = avg_behavioral if avg_behavioral is not None else 50.0  # Neutral adherence
            net_wellbeing = avg_net_wellbeing if avg_net_wellbeing is not None else 50.0  # Neutral wellbeing (normalized)
            physical_load = avg_physical if avg_physical is not None else 0.0  # Default minimal physical load
            duration_minutes = avg_duration if avg_duration else default_estimate
            
            # Apply max_duration filter
            if max_duration_filter is not None:
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
                'stress_level': stress_level,
                'behavioral_score': behavioral_score,
                'net_wellbeing_normalized': net_wellbeing,
                'physical_load': physical_load,
            })
        
        if not candidates:
            return []
        
        candidates_df = pd.DataFrame(candidates)
        
        # Calculate derived metrics
        candidates_df['net_load'] = candidates_df['cognitive_load'] + candidates_df['emotional_load']
        candidates_df['net_relief_proxy'] = candidates_df['relief_score'] - candidates_df['cognitive_load']
        
        # Scoring helper: high-good adds value; low-good adds (100 - value)
        def metric_score(metric_name: str, value: float) -> float:
            try:
                v = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                v = 0.0
            if metric_name in low_is_good:
                return max(0.0, 100.0 - v)
            return v
        
        # Compute score per task
        scores = []
        for _, row in candidates_df.iterrows():
            score_total = 0.0
            for metric in metrics:
                score_total += metric_score(metric, row.get(metric))
            scores.append(score_total)
        candidates_df['score'] = scores
        
        # Sort by score descending and take top N
        top_n = candidates_df.sort_values('score', ascending=False).head(limit)
        
        ranked = []
        for _, row in top_n.iterrows():
            # Collect only the metrics the user selected
            metric_values = {}
            for metric in metrics:
                try:
                    metric_values[metric] = float(row.get(metric)) if row.get(metric) is not None else None
                except (ValueError, TypeError):
                    metric_values[metric] = None
            
            ranked.append({
                'title': "Recommendation",
                'task_id': row.get('task_id'),
                'task_name': row.get('task_name'),
                'score': round(float(row.get('score', 0.0)), 1),
                'metric_values': metric_values,
                'duration': row.get('duration_minutes'),
                'relief': row.get('relief_score'),
                'cognitive_load': row.get('cognitive_load'),
                'emotional_load': row.get('emotional_load'),
            })
        
        return ranked

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
            'emotional_load': emotional_str,
        }

    # ------------------------------------------------------------------
    # Analytics datasets for charts
    # ------------------------------------------------------------------
    def trend_series(self) -> pd.DataFrame:
        df = self._load_instances()
        if df.empty:
            return pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])
        completed = df[df['completed_at'].astype(str).str.len() > 0]
        if completed.empty:
            return pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])

        # Ensure datetime and numeric relief
        completed = completed.copy()
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()]
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce').fillna(0.0)

        if completed.empty:
            return pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])

        # Aggregate relief per day, then compute cumulative total over time
        daily = (
            completed
            .groupby(completed['completed_at_dt'].dt.date)['relief_score_numeric']
            .sum()
            .reset_index()
            .rename(columns={'completed_at_dt': 'completed_at', 'relief_score_numeric': 'daily_relief_score'})
        )

        daily = daily.sort_values('completed_at')
        daily['completed_at'] = pd.to_datetime(daily['completed_at'])
        daily['cumulative_relief_score'] = daily['daily_relief_score'].cumsum()

        return daily[['completed_at', 'daily_relief_score', 'cumulative_relief_score']]

    def attribute_distribution(self) -> pd.DataFrame:
        df = self._load_instances()
        if df.empty:
            return pd.DataFrame(columns=['attribute', 'value'])
        melted_frames = []
        
        # Attributes to exclude from distribution chart (not actively tracked)
        excluded_attributes = {'environmental_effect'}  # Not collected in UI
        
        for attr in TASK_ATTRIBUTES:
            if attr.dtype != 'numeric':
                continue
            if attr.key in excluded_attributes:
                continue  # Skip excluded attributes
            sub = df[[attr.key]].rename(columns={attr.key: 'value'}).dropna()
            sub['attribute'] = attr.label
            melted_frames.append(sub)
        
        # Include physical load, which is derived from predicted/actual payloads
        if 'physical_load' in df.columns:
            physical_sub = (
                df[['physical_load']]
                .rename(columns={'physical_load': 'value'})
                .dropna()
            )
            physical_sub = physical_sub[physical_sub['value'] > 0]  # omit zeros/missing
            if not physical_sub.empty:
                physical_sub['attribute'] = 'Physical Load'
                melted_frames.append(physical_sub)
        
        # Add calculated metrics: stress_level, net_wellbeing, net_wellbeing_normalized, and stress_efficiency
        if 'stress_level' in df.columns:
            stress_sub = df[['stress_level']].rename(columns={'stress_level': 'value'}).dropna()
            stress_sub['attribute'] = 'Stress Level'
            melted_frames.append(stress_sub)
        
        if 'net_wellbeing' in df.columns:
            wellbeing_sub = df[['net_wellbeing']].rename(columns={'net_wellbeing': 'value'}).dropna()
            wellbeing_sub['attribute'] = 'Net Wellbeing'
            melted_frames.append(wellbeing_sub)
        
        if 'net_wellbeing_normalized' in df.columns:
            wellbeing_norm_sub = df[['net_wellbeing_normalized']].rename(columns={'net_wellbeing_normalized': 'value'}).dropna()
            wellbeing_norm_sub['attribute'] = 'Net Wellbeing (Normalized)'
            melted_frames.append(wellbeing_norm_sub)
        
        if 'stress_efficiency' in df.columns:
            efficiency_sub = df[['stress_efficiency']].rename(columns={'stress_efficiency': 'value'}).dropna()
            efficiency_sub['attribute'] = 'Stress Efficiency'
            melted_frames.append(efficiency_sub)
        
        if not melted_frames:
            return pd.DataFrame(columns=['attribute', 'value'])
        return pd.concat(melted_frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Trends and correlation helpers
    # ------------------------------------------------------------------
    def get_attribute_trends(self, attribute_key: str, aggregation: str = 'mean', days: int = 90) -> Dict[str, any]:
        """Return daily aggregated values for a single attribute."""
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty or attribute_key not in completed.columns:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()]
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            completed = completed[completed['completed_at_dt'] >= cutoff]
        if completed.empty:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        # Convert to numeric where possible
        completed['value_numeric'] = pd.to_numeric(completed[attribute_key], errors='coerce')
        # Group by date
        completed['date'] = completed['completed_at_dt'].dt.date

        agg_map = {
            'mean': 'mean',
            'sum': 'sum',
            'median': 'median',
            'min': 'min',
            'max': 'max',
            'count': 'count',
            'std': 'std',
            'var': 'var',
        }
        agg = agg_map.get(str(aggregation).lower(), 'mean')

        if agg == 'count':
            daily = completed.groupby('date')['value_numeric'].count().reset_index(name='value')
        else:
            daily = completed.groupby('date')['value_numeric'].agg(agg).reset_index(name='value')

        if daily.empty:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        daily = daily.sort_values('date')
        return {
            'dates': daily['date'].astype(str).tolist(),
            'values': daily['value'].fillna(0).astype(float).tolist(),
            'aggregation': agg,
        }

    def get_multi_attribute_trends(
        self,
        attribute_keys: List[str],
        aggregation: str = 'mean',
        days: int = 90,
        normalize: bool = False,
    ) -> Dict[str, Dict[str, any]]:
        """Return trends for multiple attributes; optionally normalize each series (min-max)."""
        trends = {}
        attribute_keys = attribute_keys or []
        for key in attribute_keys:
            data = self.get_attribute_trends(key, aggregation, days)
            values = data.get('values') or []
            if normalize and values:
                v_min = min(values)
                v_max = max(values)
                if v_max != v_min:
                    normalized = [(v - v_min) / (v_max - v_min) for v in values]
                else:
                    normalized = [0.0 for _ in values]
                data['values'] = normalized
                data['original_min'] = v_min
                data['original_max'] = v_max
            trends[key] = data
        return trends

    def calculate_correlation(self, attribute_x: str, attribute_y: str, method: str = 'pearson') -> Dict[str, any]:
        """Calculate correlation between two attributes with metadata for tooltips."""
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty or attribute_x not in completed.columns or attribute_y not in completed.columns:
            return {'correlation': None, 'p_value': None, 'r_squared': None, 'n': 0}

        completed['x_val'] = pd.to_numeric(completed[attribute_x], errors='coerce')
        completed['y_val'] = pd.to_numeric(completed[attribute_y], errors='coerce')
        clean = completed[['x_val', 'y_val']].dropna()
        if clean.empty or len(clean) < 2:
            return {'correlation': None, 'p_value': None, 'r_squared': None, 'n': len(clean)}

        method = (method or 'pearson').lower()
        meta = {
            'pearson': {
                'name': 'Pearson Correlation',
                'description': 'Measures linear relationship strength between two variables. Range -1..1.',
                'statistician': 'Karl Pearson',
                'search_term': 'Pearson correlation coefficient',
            },
            'spearman': {
                'name': 'Spearman Rank Correlation',
                'description': 'Non-parametric measure of monotonic relationship using ranked data. Range -1..1.',
                'statistician': 'Charles Spearman',
                'search_term': 'Spearman rank correlation',
            },
        }

        correlation = None
        p_value = None
        try:
            if method == 'spearman':
                correlation, p_value = stats.spearmanr(clean['x_val'], clean['y_val'])
            else:
                correlation, p_value = stats.pearsonr(clean['x_val'], clean['y_val'])
        except Exception:
            correlation, p_value = None, None

        r_squared = correlation ** 2 if correlation is not None else None
        return {
            'correlation': correlation,
            'p_value': p_value,
            'r_squared': r_squared,
            'n': len(clean),
            'method': method,
            'meta': meta.get(method, {}),
        }

    def find_threshold_relationships(self, dependent_var: str, independent_var: str, bins: int = 10) -> Dict[str, any]:
        """Bin independent variable and summarize dependent averages to surface threshold ranges."""
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty or dependent_var not in completed.columns or independent_var not in completed.columns:
            return {'bins': [], 'best_max': None, 'best_min': None}

        completed['x_val'] = pd.to_numeric(completed[independent_var], errors='coerce')
        completed['y_val'] = pd.to_numeric(completed[dependent_var], errors='coerce')
        clean = completed[['x_val', 'y_val']].dropna()
        if clean.empty or len(clean) < 2:
            return {'bins': [], 'best_max': None, 'best_min': None}

        unique_x = clean['x_val'].nunique()
        bin_count = max(1, min(bins, unique_x))

        try:
            clean['bin'] = pd.cut(clean['x_val'], bins=bin_count, duplicates='drop')
        except Exception:
            return {'bins': [], 'best_max': None, 'best_min': None}

        grouped = clean.groupby('bin')['y_val'].agg(['mean', 'count']).reset_index()
        if grouped.empty:
            return {'bins': [], 'best_max': None, 'best_min': None}

        bins_list = []
        for _, row in grouped.iterrows():
            interval = row['bin']
            bins_list.append({
                'range': str(interval),
                'dependent_avg': round(float(row['mean']), 4) if pd.notna(row['mean']) else None,
                'count': int(row['count']),
            })

        best_max = grouped.loc[grouped['mean'].idxmax()] if grouped['mean'].notna().any() else None
        best_min = grouped.loc[grouped['mean'].idxmin()] if grouped['mean'].notna().any() else None

        def _format_best(row):
            if row is None or pd.isna(row['mean']):
                return None
            return {
                'range': str(row['bin']),
                'dependent_avg': round(float(row['mean']), 4),
                'count': int(row['count']),
            }

        return {
            'bins': bins_list,
            'best_max': _format_best(best_max),
            'best_min': _format_best(best_min),
        }

    def get_scatter_data(self, attribute_x: str, attribute_y: str) -> Dict[str, any]:
        """Return paired scatter values for two attributes."""
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty or attribute_x not in completed.columns or attribute_y not in completed.columns:
            return {'x': [], 'y': [], 'n': 0}

        completed['x_val'] = pd.to_numeric(completed[attribute_x], errors='coerce')
        completed['y_val'] = pd.to_numeric(completed[attribute_y], errors='coerce')
        clean = completed[['x_val', 'y_val']].dropna()
        return {
            'x': clean['x_val'].astype(float).tolist(),
            'y': clean['y_val'].astype(float).tolist(),
            'n': len(clean),
        }

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
