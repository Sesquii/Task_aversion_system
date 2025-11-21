# backend/analytics.py
from datetime import datetime
import pandas as pd
import os
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

class Analytics:
    def __init__(self):
        self.instances_file = os.path.join(DATA_DIR, 'task_instances.csv')

    def active_summary(self):
        # simple stats for dashboard
        if not os.path.exists(self.instances_file):
            return {}
        df = pd.read_csv(self.instances_file).fillna('')
        active = df[(df['is_completed'] != 'True') & (df['is_deleted'] != 'True')]
        return {
            'active_count': len(active),
            'oldest_active': active['created_at'].min() if not active.empty else None
        }

    def compute_priority_score(self, instance_row: dict):
        # Basic priority heuristic for recommendation:
        # priority = procrastination_score * 1.5 + (predicted_time_minutes / 60) - (proactive_score * 0.5)
        try:
            p = float(instance_row.get('procrastination_score') or 0)
            predicted = instance_row.get('predicted') or '{}'
            import json
            pred = json.loads(predicted)
            tmin = float(pred.get('time_estimate_minutes') or pred.get('estimate') or 0)
            proact = float(instance_row.get('proactive_score') or 0)
            score = p * 1.5 + (tmin / 60.0) - (proact * 0.5)
            return round(score, 3)
        except Exception:
            return 0.0
