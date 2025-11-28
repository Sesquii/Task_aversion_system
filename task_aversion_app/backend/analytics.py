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
            df[column] = df[column].fillna(attr.default)
            if attr.dtype == 'numeric':
                df[column] = pd.to_numeric(df[column], errors='coerce')

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

    # ------------------------------------------------------------------
    # Recommendation helpers
    # ------------------------------------------------------------------
    def default_filters(self) -> Dict[str, Optional[float]]:
        return {
            'max_duration': None,
            'min_relief': None,
            'max_cognitive_load': None,
            'focus_metric': 'relief',
        }

    def available_filters(self) -> List[Dict[str, str]]:
        return [
            {'key': 'max_duration', 'label': 'Max Duration (minutes)'},
            {'key': 'min_relief', 'label': 'Min Relief Score'},
            {'key': 'max_cognitive_load', 'label': 'Max Cognitive Load'},
            {'key': 'focus_metric', 'label': 'Focus Metric'},
        ]

    def recommendations(self, filters: Optional[Dict[str, float]] = None) -> List[Dict[str, str]]:
        filters = {**self.default_filters(), **(filters or {})}
        df = self._load_instances()
        if df.empty:
            return []

        active = df[df['status'].isin(['active', 'in_progress'])]
        if filters.get('max_duration'):
            active = active[active['duration_minutes'] <= float(filters['max_duration'])]
        if filters.get('min_relief'):
            active = active[active['relief_score'] >= float(filters['min_relief'])]
        if filters.get('max_cognitive_load'):
            active = active[active['cognitive_load'] <= float(filters['max_cognitive_load'])]

        if active.empty:
            return []
        # Avoid chained-assignment warnings when we add helper columns later
        active = active.copy()

        focus_metric = filters.get('focus_metric')
        focus_metric = focus_metric if focus_metric in ['relief', 'duration', 'cognitive'] else 'relief'

        ranked = []
        if focus_metric == 'relief':
            row = active.sort_values('relief_score', ascending=False).head(1)
            ranked.append(self._row_to_recommendation(row, "Highest Relief"))
        if focus_metric == 'duration':
            row = active.sort_values('duration_minutes', ascending=True).head(1)
            ranked.append(self._row_to_recommendation(row, "Shortest Task"))
        if focus_metric == 'cognitive':
            row = active.sort_values('cognitive_load', ascending=True).head(1)
            ranked.append(self._row_to_recommendation(row, "Lowest Cognitive Load"))

        # Always include net relief pick for variety
        active.loc[:, 'net_relief_proxy'] = active['relief_score'] - active['cognitive_load']
        row = active.sort_values('net_relief_proxy', ascending=False).head(1)
        ranked.append(self._row_to_recommendation(row, "Highest Net Relief"))
        return [r for r in ranked if r]

    def _row_to_recommendation(self, row_df: pd.DataFrame, label: str) -> Optional[Dict[str, str]]:
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
