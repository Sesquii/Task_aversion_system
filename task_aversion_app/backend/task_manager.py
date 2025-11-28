# backend/task_manager.py
import os
import pandas as pd
from datetime import datetime
from typing import List

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
TASKS_FILE = 'data/tasks.csv'
class TaskManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.tasks_file = os.path.join(DATA_DIR, 'tasks.csv')
        # task definition fields:
        # task_id, name, description, type, version, created_at, is_recurring, categories (json), default_estimate_minutes
        if not os.path.exists(self.tasks_file):
            pd.DataFrame(columns=['task_id','name','description','type','version','created_at','is_recurring','categories','default_estimate_minutes']).to_csv(self.tasks_file, index=False)
        self._reload()
        self.initialization_entries = []
    def _reload(self):
        self.df = pd.read_csv(self.tasks_file, dtype=str).fillna('')
        # ensure proper dtypes for numeric fields where necessary
        if 'version' not in self.df.columns:
            self.df['version'] = 1
    def get_task(self, task_id):
        """Return a task row by id as a dict."""
        self._reload()
        rows = self.df[self.df['task_id'] == task_id]
        return rows.iloc[0].to_dict() if not rows.empty else None
    def _save(self):
        self.df.to_csv(self.tasks_file, index=False)
        self._reload()

    def list_tasks(self) -> List[str]:
        self._reload()
        return list(self.df['name'].tolist())

    def save_initialization_entry(self, entry):
        """Save a task initialization entry."""
        self.initialization_entries.append(entry)
        print(f"Saved initialization entry: {entry}")
    def get_all(self):
        self._reload()
        return self.df.copy()

    def create_task(self, name, description='', ttype='one-time', is_recurring=False, categories='[]', default_estimate_minutes=0):
        """
        Creates a new task definition and returns task_id
        """
        self._reload()
        # simple unique id using timestamp + name fragment
        task_id = f"t{int(datetime.now().timestamp())}"
        row = {
            'task_id': task_id,
            'name': name,
            'description': description,
            'type': ttype,
            'version': 1,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'is_recurring': str(bool(is_recurring)),
            'categories': categories,
            'default_estimate_minutes': int(default_estimate_minutes)
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return task_id

    def update_task(self, task_id, **kwargs):
        self._reload()
        if task_id not in self.df['task_id'].values:
            return False
        idx = self.df.index[self.df['task_id'] == task_id][0]
        for k,v in kwargs.items():
            if k in self.df.columns:
                self.df.at[idx,k] = v
        # bump version
        self.df.at[idx,'version'] = int(self.df.at[idx,'version']) + 1
        self._save()
        return True

    def find_by_name(self, name):
        self._reload()
        rows = self.df[self.df['name'] == name]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def ensure_task_exists(self, name):
        t = self.find_by_name(name)
        if t:
            return t['task_id']
        return self.create_task(name)



    def delete_by_id(self, task_id):
        """Remove a task template by id."""
        print(f"[TaskManager] delete_by_id called with: {task_id}")
        self._reload()
        before = len(self.df)
        self.df = self.df[self.df['task_id'] != task_id]
        if len(self.df) == before:
            print("[TaskManager] No matching task to delete.")
            return False
        self._save()
        print("[TaskManager] Task deleted successfully.")
        return True


    def get_recent(self, limit=5):
        print(f"[TaskManager] get_recent called (limit={limit})")

        df = self.get_all()
        if df is None or df.empty:
            return []

        df = df.sort_values("created_at", ascending=False)
        return df.head(limit).to_dict(orient="records")
