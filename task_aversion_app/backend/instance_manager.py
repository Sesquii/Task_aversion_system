# backend/instance_manager.py
import os
import pandas as pd
from datetime import datetime
from typing import Optional
import json

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
class InstanceManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.file = os.path.join(DATA_DIR, 'task_instances.csv')
        # fields: instance_id, task_id, task_name, task_version, created_at, initialized_at, started_at, completed_at,
        # predicted (json), actual (json), procrastination_score, proactive_score, is_completed, is_deleted
        if not os.path.exists(self.file):
            pd.DataFrame(columns=[
                'instance_id','task_id','task_name','task_version','created_at','initialized_at','started_at',
                'completed_at','cancelled_at','predicted','actual','procrastination_score','proactive_score',
                'is_completed','is_deleted','status'
            ]).to_csv(self.file, index=False)
        self._reload()

    def _reload(self):
        self.df = pd.read_csv(self.file, dtype=str).fillna('')
        defaults = {
            'predicted': '',
            'actual': '',
            'cancelled_at': '',
            'duration_minutes': '',
            'relief_score': '',
            'cognitive_load': '',
            'emotional_load': '',
            'environmental_effect': '',
            'skills_improved': '',
            'behavioral_deviation': '',
            'net_relief': '',
        }
        for col, default in defaults.items():
            if col not in self.df.columns:
                self.df[col] = default
        if 'status' not in self.df.columns:
            if 'is_completed' in self.df.columns:
                self.df['status'] = self.df['is_completed'].apply(
                    lambda v: 'completed' if str(v).lower() == 'true' else 'active'
                )
            else:
                self.df['status'] = 'active'
        else:
            fallback = (
                self.df['is_completed'].apply(lambda v: 'completed' if str(v).lower() == 'true' else 'active')
                if 'is_completed' in self.df.columns else pd.Series(['active'] * len(self.df), index=self.df.index)
            )
            self.df['status'] = self.df['status'].replace('', None)
            self.df['status'] = self.df['status'].fillna(fallback)

    def _save(self):
        self.df.to_csv(self.file, index=False)
        self._reload()

    def create_instance(self, task_id, task_name, task_version=1, predicted: dict = None):
        self._reload()
        instance_id = f"i{int(datetime.now().timestamp())}"
        row = {
            'instance_id': instance_id,
            'task_id': task_id,
            'task_name': task_name,
            'task_version': task_version,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'initialized_at': datetime.now().strftime("%Y-%m-%d %H:%M") if predicted else '',
            'started_at': '',
            'completed_at': '',
            'cancelled_at': '',
            'predicted': json.dumps(predicted or {}),
            'actual': json.dumps({}),
            'procrastination_score': '',
            'proactive_score': '',
            'is_completed': 'False',
            'is_deleted': 'False',
            'status': 'active',
            'duration_minutes': '',
            'relief_score': '',
            'cognitive_load': '',
            'emotional_load': '',
            'environmental_effect': '',
            'skills_improved': '',
            'behavioral_deviation': '',
            'net_relief': '',
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return instance_id

    def list_active_instances(self):
        self._reload()
        status_series = self.df['status'].str.lower()
        df = self.df[
            (self.df['is_completed'] != 'True') &
            (self.df['is_deleted'] != 'True') &
            (~status_series.isin(['completed', 'cancelled']))
        ]
        return df.to_dict(orient='records')

    def get_instance(self, instance_id):
        self._reload()
        rows = self.df[self.df['instance_id'] == instance_id]
        if rows.empty:
            return None
        row = rows.iloc[0].to_dict()
        return row

    def start_instance(self, instance_id):
        self._reload()
        idx = self.df.index[self.df['instance_id']==instance_id][0]
        self.df.at[idx,'started_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()

    def complete_instance(self, instance_id, actual: dict):
        import json, math
        self._reload()
        idx = self.df.index[self.df['instance_id']==instance_id][0]
        # set actual JSON
        self.df.at[idx,'actual'] = json.dumps(actual)
        self.df.at[idx,'completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.df.at[idx,'is_completed'] = 'True'
        self.df.at[idx,'status'] = 'completed'
        self.df.at[idx,'cancelled_at'] = ''
        # compute simple procrastination/proactive metrics
        try:
            created = pd.to_datetime(self.df.at[idx,'created_at'])
            started = pd.to_datetime(self.df.at[idx,'started_at']) if self.df.at[idx,'started_at'] else pd.to_datetime(self.df.at[idx,'initialized_at']) if self.df.at[idx,'initialized_at'] else created
            predicted = json.loads(self.df.at[idx,'predicted'] or "{}")
            estimate = float(predicted.get('time_estimate_minutes') or predicted.get('estimate') or 0) or 1.0
            delay = (started - created).total_seconds() / 60.0
            procrast = delay / max(estimate, 1.0)
            proactive = max(0.0, 1.0 - (delay / max(estimate*2.0,1.0)))
            self.df.at[idx,'procrastination_score'] = round(min(procrast, 10.0), 3)
            self.df.at[idx,'proactive_score'] = round(min(max(proactive*10.0,0.0), 10.0), 3)
        except Exception:
            self.df.at[idx,'procrastination_score'] = ''
            self.df.at[idx,'proactive_score'] = ''
        self._update_attributes_from_payload(idx, actual)
        self._save()

    def cancel_instance(self, instance_id, actual: dict):
        import json
        self._reload()
        matches = self.df.index[self.df['instance_id'] == instance_id]
        if len(matches) == 0:
            raise ValueError(f"Instance {instance_id} not found")
        idx = matches[0]
        self.df.at[idx, 'actual'] = json.dumps(actual or {})
        self.df.at[idx, 'cancelled_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.df.at[idx, 'status'] = 'cancelled'
        self.df.at[idx, 'is_completed'] = 'True'
        self.df.at[idx, 'completed_at'] = ''
        self.df.at[idx, 'procrastination_score'] = ''
        self.df.at[idx, 'proactive_score'] = ''
        self._update_attributes_from_payload(idx, actual or {})
        self._save()

    def add_prediction_to_instance(self, instance_id, predicted: dict):
        import json
        self._reload()
        idx = self.df.index[self.df['instance_id'] == instance_id][0]
        self.df.at[idx,'predicted'] = json.dumps(predicted)
        self.df.at[idx,'initialized_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()

    def ensure_instance_for_task(self, task_id, task_name, predicted: dict = None):
        # create an instance and return id
        return self.create_instance(task_id, task_name, task_version=1, predicted=predicted)



    def delete_instance(self, instance_id):
        print(f"[InstanceManager] delete_instance called with: {instance_id}")
        self._reload()
        before = len(self.df)
        self.df = self.df[self.df['instance_id'] != instance_id]
        if len(self.df) == before:
            print("[InstanceManager] No matching instance to delete.")
            return False
        self._save()
        print("[InstanceManager] Instance deleted.")
        return True

    def _update_attributes_from_payload(self, idx, payload: dict):
        """Persist wellbeing attributes if caller provided them."""
        if not isinstance(payload, dict):
            return
        mappings = [
            'duration_minutes',
            'relief_score',
            'cognitive_load',
            'emotional_load',
            'environmental_effect',
            'skills_improved',
            'behavioral_deviation',
            'net_relief',
        ]
        for key in mappings:
            value = payload.get(key)
            if value is None or value == '':
                continue
            self.df.at[idx, key] = value


    def list_recent_completed(self, limit=20):
        print(f"[InstanceManager] list_recent_completed called (limit={limit})")
        self._reload()
        df = self.df[self.df['completed_at'].astype(str).str.strip() != '']
        if df.empty:
            return []
        df = df.sort_values("completed_at", ascending=False)
        return df.head(limit).to_dict(orient="records")
