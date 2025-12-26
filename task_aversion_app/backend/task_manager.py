# backend/task_manager.py
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
TASKS_FILE = 'data/tasks.csv'

class TaskManager:
    def __init__(self):
        # Feature flag: Use database if DATABASE_URL is set, otherwise use CSV
        self.use_db = bool(os.getenv('DATABASE_URL'))
        # Strict mode: If DISABLE_CSV_FALLBACK is set, fail instead of falling back to CSV
        self.strict_mode = bool(os.getenv('DISABLE_CSV_FALLBACK', '').lower() in ('1', 'true', 'yes'))
        
        if self.use_db:
            # Database backend
            try:
                from backend.database import get_session, Task, init_db
                self.db_session = get_session
                self.Task = Task
                # Initialize database if tables don't exist
                init_db()
                print("[TaskManager] Using database backend")
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(
                        f"Database initialization failed and CSV fallback is disabled: {e}\n"
                        "Set DISABLE_CSV_FALLBACK=false or unset DATABASE_URL to allow CSV fallback."
                    ) from e
                print(f"[TaskManager] Database initialization failed: {e}, falling back to CSV")
                self.use_db = False
                self._init_csv()
        else:
            # CSV backend (default)
            if self.strict_mode:
                raise RuntimeError(
                    "CSV backend is disabled (DISABLE_CSV_FALLBACK is set) but DATABASE_URL is not set.\n"
                    "Please set DATABASE_URL to use the database backend, or unset DISABLE_CSV_FALLBACK."
                )
            self._init_csv()
            print("[TaskManager] Using CSV backend")
        
        self.initialization_entries = []
    
    def _init_csv(self):
        """Initialize CSV backend."""
        os.makedirs(DATA_DIR, exist_ok=True)
        self.tasks_file = os.path.join(DATA_DIR, 'tasks.csv')
        # task definition fields:
        # task_id, name, description, type, version, created_at, is_recurring, categories (json), default_estimate_minutes, task_type, default_initial_aversion, routine_frequency, routine_days_of_week, routine_time, completion_window_hours, completion_window_days
        if not os.path.exists(self.tasks_file):
            pd.DataFrame(columns=['task_id','name','description','type','version','created_at','is_recurring','categories','default_estimate_minutes','task_type','default_initial_aversion','routine_frequency','routine_days_of_week','routine_time','completion_window_hours','completion_window_days']).to_csv(self.tasks_file, index=False)
        self._reload()
    def _reload(self):
        """Reload data (CSV only)."""
        if not self.use_db:
            self._reload_csv()
    
    def _ensure_csv_initialized(self):
        """Ensure CSV backend is initialized. Called before fallback to CSV methods."""
        if not hasattr(self, 'tasks_file') or not hasattr(self, 'df'):
            self._init_csv()
    
    def _reload_csv(self):
        """CSV-specific reload."""
        self.df = pd.read_csv(self.tasks_file, dtype=str).fillna('')
        # ensure proper dtypes for numeric fields where necessary
        if 'version' not in self.df.columns:
            self.df['version'] = 1
        # ensure task_type column exists with default value
        if 'task_type' not in self.df.columns:
            self.df['task_type'] = 'Work'
        # fill any empty task_type values with default
        self.df['task_type'] = self.df['task_type'].fillna('Work')
        # ensure default_initial_aversion column exists (optional field, can be empty)
        if 'default_initial_aversion' not in self.df.columns:
            self.df['default_initial_aversion'] = ''
        # ensure routine scheduling columns exist
        if 'routine_frequency' not in self.df.columns:
            self.df['routine_frequency'] = 'none'
        if 'routine_days_of_week' not in self.df.columns:
            self.df['routine_days_of_week'] = '[]'
        if 'routine_time' not in self.df.columns:
            self.df['routine_time'] = '00:00'
        if 'completion_window_hours' not in self.df.columns:
            self.df['completion_window_hours'] = ''
        if 'completion_window_days' not in self.df.columns:
            self.df['completion_window_days'] = ''
    
    def _save(self):
        """Save data (CSV only)."""
        if not self.use_db:
            self._save_csv()
    
    def _save_csv(self):
        """CSV-specific save."""
        self.df.to_csv(self.tasks_file, index=False)
        self._reload_csv()
    
    def get_task(self, task_id):
        """Return a task row by id as a dict. Works with both CSV and database."""
        if self.use_db:
            return self._get_task_db(task_id)
        else:
            return self._get_task_csv(task_id)
    
    def _get_task_csv(self, task_id):
        """CSV-specific get_task."""
        self._reload_csv()
        rows = self.df[self.df['task_id'] == task_id]
        return rows.iloc[0].to_dict() if not rows.empty else None
    
    def _get_task_db(self, task_id):
        """Database-specific get_task."""
        try:
            with self.db_session() as session:
                task = session.query(self.Task).filter(self.Task.task_id == task_id).first()
                return task.to_dict() if task else None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_task and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in get_task: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._get_task_csv(task_id)

    def list_tasks(self) -> List[str]:
        """Return list of task names. Works with both CSV and database."""
        if self.use_db:
            return self._list_tasks_db()
        else:
            return self._list_tasks_csv()
    
    def _list_tasks_csv(self) -> List[str]:
        """CSV-specific list_tasks."""
        self._reload_csv()
        return list(self.df['name'].tolist())
    
    def _list_tasks_db(self) -> List[str]:
        """Database-specific list_tasks."""
        try:
            with self.db_session() as session:
                tasks = session.query(self.Task).all()
                return [task.name for task in tasks]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in list_tasks and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in list_tasks: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._list_tasks_csv()

    def save_initialization_entry(self, entry):
        """Save a task initialization entry."""
        self.initialization_entries.append(entry)
        print(f"Saved initialization entry: {entry}")
    def get_all(self):
        """Return all tasks as DataFrame (CSV) or list of dicts (database). Works with both backends."""
        if self.use_db:
            return self._get_all_db()
        else:
            return self._get_all_csv()
    
    def _get_all_csv(self):
        """CSV-specific get_all."""
        self._reload_csv()
        return self.df.copy()
    
    def _get_all_db(self):
        """Database-specific get_all. Returns DataFrame for compatibility."""
        try:
            with self.db_session() as session:
                tasks = session.query(self.Task).all()
                if not tasks:
                    # Return empty DataFrame with expected columns
                    return pd.DataFrame(columns=['task_id','name','description','type','version','created_at','is_recurring','categories','default_estimate_minutes','task_type','default_initial_aversion','routine_frequency','routine_days_of_week','routine_time','completion_window_hours','completion_window_days'])
                # Convert to list of dicts, then to DataFrame
                task_dicts = [task.to_dict() for task in tasks]
                return pd.DataFrame(task_dicts)
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_all and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in get_all: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._get_all_csv()

    def create_task(self, name, description='', ttype='one-time', is_recurring=False, categories='[]', default_estimate_minutes=0, task_type='Work', default_initial_aversion=None, routine_frequency='none', routine_days_of_week=None, routine_time='00:00', completion_window_hours=None, completion_window_days=None):
        """
        Creates a new task definition and returns task_id. Works with both CSV and database.
        
        Args:
            default_initial_aversion: Optional initial aversion value (0-100) to use as default when first initializing this task
            routine_frequency: 'none', 'daily', or 'weekly'
            routine_days_of_week: List of day numbers (0=Monday, 6=Sunday) for weekly frequency
            routine_time: Time in HH:MM format (24-hour), default '00:00'
            completion_window_hours: Hours to complete task after initialization without penalty
            completion_window_days: Days to complete task after initialization without penalty
        """
        if routine_days_of_week is None:
            routine_days_of_week = []
        if self.use_db:
            return self._create_task_db(name, description, ttype, is_recurring, categories, default_estimate_minutes, task_type, default_initial_aversion, routine_frequency, routine_days_of_week, routine_time, completion_window_hours, completion_window_days)
        else:
            return self._create_task_csv(name, description, ttype, is_recurring, categories, default_estimate_minutes, task_type, default_initial_aversion, routine_frequency, routine_days_of_week, routine_time, completion_window_hours, completion_window_days)
    
    def _create_task_csv(self, name, description='', ttype='one-time', is_recurring=False, categories='[]', default_estimate_minutes=0, task_type='Work', default_initial_aversion=None, routine_frequency='none', routine_days_of_week=None, routine_time='00:00', completion_window_hours=None, completion_window_days=None):
        """CSV-specific create_task."""
        self._reload_csv()
        # simple unique id using timestamp + name fragment
        task_id = f"t{int(datetime.now().timestamp())}"
        # Convert default_initial_aversion to string, or empty string if None
        aversion_str = str(int(default_initial_aversion)) if default_initial_aversion is not None else ''
        # Convert routine_days_of_week to JSON string
        if routine_days_of_week is None:
            routine_days_of_week = []
        routine_days_str = json.dumps(routine_days_of_week) if isinstance(routine_days_of_week, list) else (routine_days_of_week or '[]')
        # Convert completion window values to strings or empty
        completion_window_hours_str = str(int(completion_window_hours)) if completion_window_hours is not None else ''
        completion_window_days_str = str(int(completion_window_days)) if completion_window_days is not None else ''
        row = {
            'task_id': task_id,
            'name': name,
            'description': description,
            'type': ttype,
            'version': 1,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'is_recurring': str(bool(is_recurring)),
            'categories': categories,
            'default_estimate_minutes': int(default_estimate_minutes),
            'task_type': task_type,
            'default_initial_aversion': aversion_str,
            'routine_frequency': routine_frequency or 'none',
            'routine_days_of_week': routine_days_str,
            'routine_time': routine_time or '00:00',
            'completion_window_hours': completion_window_hours_str,
            'completion_window_days': completion_window_days_str
        }
        # Ensure all columns exist in dataframe
        for col in ['task_type', 'default_initial_aversion', 'routine_frequency', 'routine_days_of_week', 'routine_time', 'completion_window_hours', 'completion_window_days']:
            if col not in self.df.columns:
                self.df[col] = '' if col != 'routine_frequency' else 'none'
                if col == 'routine_time':
                    self.df[col] = '00:00'
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save_csv()
        return task_id
    
    def _create_task_db(self, name, description='', ttype='one-time', is_recurring=False, categories='[]', default_estimate_minutes=0, task_type='Work', default_initial_aversion=None, routine_frequency='none', routine_days_of_week=None, routine_time='00:00', completion_window_hours=None, completion_window_days=None):
        """Database-specific create_task."""
        try:
            # Parse categories JSON string
            try:
                categories_list = json.loads(categories) if isinstance(categories, str) else (categories or [])
            except (json.JSONDecodeError, TypeError):
                categories_list = []
            
            # Parse routine_days_of_week
            if routine_days_of_week is None:
                routine_days_list = []
            elif isinstance(routine_days_of_week, str):
                try:
                    routine_days_list = json.loads(routine_days_of_week)
                except (json.JSONDecodeError, TypeError):
                    routine_days_list = []
            else:
                routine_days_list = routine_days_of_week
            
            # Convert default_initial_aversion to string, or empty string if None
            aversion_str = str(int(default_initial_aversion)) if default_initial_aversion is not None else ''
            
            # Generate task_id
            task_id = f"t{int(datetime.now().timestamp())}"
            
            with self.db_session() as session:
                task = self.Task(
                    task_id=task_id,
                    name=name,
                    description=description or '',
                    type=ttype,
                    version=1,
                    created_at=datetime.now(),
                    is_recurring=bool(is_recurring),
                    categories=categories_list,
                    default_estimate_minutes=int(default_estimate_minutes),
                    task_type=task_type or 'Work',
                    default_initial_aversion=aversion_str,
                    routine_frequency=routine_frequency or 'none',
                    routine_days_of_week=routine_days_list,
                    routine_time=routine_time or '00:00',
                    completion_window_hours=completion_window_hours,
                    completion_window_days=completion_window_days
                )
                session.add(task)
                session.commit()
                return task_id
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in create_task and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in create_task: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._create_task_csv(name, description, ttype, is_recurring, categories, default_estimate_minutes, task_type, default_initial_aversion, routine_frequency, routine_days_of_week, routine_time, completion_window_hours, completion_window_days)

    def update_task(self, task_id, **kwargs):
        """Update a task. Works with both CSV and database."""
        if self.use_db:
            return self._update_task_db(task_id, **kwargs)
        else:
            return self._update_task_csv(task_id, **kwargs)
    
    def _update_task_csv(self, task_id, **kwargs):
        """CSV-specific update_task."""
        self._reload_csv()
        if task_id not in self.df['task_id'].values:
            return False
        idx = self.df.index[self.df['task_id'] == task_id][0]
        # Ensure task_type column exists
        if 'task_type' not in self.df.columns:
            self.df['task_type'] = 'Work'
        # Ensure default_initial_aversion column exists
        if 'default_initial_aversion' not in self.df.columns:
            self.df['default_initial_aversion'] = ''
        # Ensure routine scheduling columns exist
        for col in ['routine_frequency', 'routine_days_of_week', 'routine_time', 'completion_window_hours', 'completion_window_days']:
            if col not in self.df.columns:
                self.df[col] = '' if col != 'routine_frequency' else 'none'
                if col == 'routine_time':
                    self.df[col] = '00:00'
        for k,v in kwargs.items():
            if k in self.df.columns:
                self.df.at[idx,k] = v
        # bump version
        self.df.at[idx,'version'] = int(self.df.at[idx,'version']) + 1
        self._save_csv()
        return True
    
    def _update_task_db(self, task_id, **kwargs):
        """Database-specific update_task."""
        try:
            with self.db_session() as session:
                task = session.query(self.Task).filter(self.Task.task_id == task_id).first()
                if not task:
                    return False
                
                # Update fields
                for k, v in kwargs.items():
                    if hasattr(task, k):
                        # Handle special cases
                        if k == 'categories' and isinstance(v, str):
                            try:
                                v = json.loads(v)
                            except (json.JSONDecodeError, TypeError):
                                v = []
                        elif k == 'routine_days_of_week' and isinstance(v, str):
                            try:
                                v = json.loads(v)
                            except (json.JSONDecodeError, TypeError):
                                v = []
                        elif k == 'is_recurring' and isinstance(v, str):
                            v = v.lower() == 'true'
                        elif k == 'version' and isinstance(v, str):
                            v = int(v)
                        elif k == 'default_estimate_minutes' and isinstance(v, str):
                            v = int(v)
                        elif k == 'completion_window_hours' and isinstance(v, str):
                            v = int(v) if v.strip() else None
                        elif k == 'completion_window_days' and isinstance(v, str):
                            v = int(v) if v.strip() else None
                        setattr(task, k, v)
                
                # Bump version
                task.version = (task.version or 1) + 1
                task.updated_at = datetime.now()
                
                session.commit()
                return True
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in update_task and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in update_task: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._update_task_csv(task_id, **kwargs)

    def find_by_name(self, name):
        """Find a task by name. Works with both CSV and database."""
        if self.use_db:
            return self._find_by_name_db(name)
        else:
            return self._find_by_name_csv(name)
    
    def _find_by_name_csv(self, name):
        """CSV-specific find_by_name."""
        self._reload_csv()
        rows = self.df[self.df['name'] == name]
        return rows.iloc[0].to_dict() if not rows.empty else None
    
    def _find_by_name_db(self, name):
        """Database-specific find_by_name."""
        try:
            with self.db_session() as session:
                task = session.query(self.Task).filter(self.Task.name == name).first()
                return task.to_dict() if task else None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in find_by_name and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in find_by_name: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._find_by_name_csv(name)

    def ensure_task_exists(self, name):
        t = self.find_by_name(name)
        if t:
            return t['task_id']
        return self.create_task(name)



    def delete_by_id(self, task_id):
        """Remove a task template by id. Works with both CSV and database."""
        print(f"[TaskManager] delete_by_id called with: {task_id}")
        if self.use_db:
            return self._delete_by_id_db(task_id)
        else:
            return self._delete_by_id_csv(task_id)
    
    def _delete_by_id_csv(self, task_id):
        """CSV-specific delete_by_id."""
        self._reload_csv()
        before = len(self.df)
        self.df = self.df[self.df['task_id'] != task_id]
        if len(self.df) == before:
            print("[TaskManager] No matching task to delete.")
            return False
        self._save_csv()
        print("[TaskManager] Task deleted successfully.")
        return True
    
    def _delete_by_id_db(self, task_id):
        """Database-specific delete_by_id."""
        try:
            with self.db_session() as session:
                task = session.query(self.Task).filter(self.Task.task_id == task_id).first()
                if not task:
                    print("[TaskManager] No matching task to delete.")
                    return False
                session.delete(task)
                session.commit()
                print("[TaskManager] Task deleted successfully.")
                return True
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in delete_by_id and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in delete_by_id: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._delete_by_id_csv(task_id)


    def get_recent(self, limit=5):
        """Return tasks sorted by most recently completed instance.

        Falls back to task creation time if no completed instances exist.
        """
        print(f"[TaskManager] get_recent called (limit={limit})")

        # Try to rank tasks by most recent completion
        try:
            from backend.instance_manager import InstanceManager

            im = InstanceManager()
            im._reload()  # ensure fresh data
            inst_df = im.df.copy()

            # Keep only rows with a completion timestamp
            inst_df = inst_df[inst_df["completed_at"].astype(str).str.strip() != ""]
            if not inst_df.empty:
                inst_df["completed_at_ts"] = pd.to_datetime(
                    inst_df["completed_at"], errors="coerce"
                )
                inst_df = inst_df.dropna(subset=["completed_at_ts"])

                # Latest completion per task_id
                inst_df = (
                    inst_df.sort_values("completed_at_ts", ascending=False)
                    .drop_duplicates(subset=["task_id"], keep="first")
                )

                # Join with task metadata for stable names/descriptions.
                # Use an inner merge so we only return tasks that still exist.
                tasks_df = self.get_all()
                merged = inst_df.merge(
                    tasks_df,
                    how="inner",
                    on="task_id",
                    suffixes=("", "_task"),
                )

                if not merged.empty:
                    # Prefer the canonical task name from tasks.csv, fallback to instance name
                    merged["name"] = merged["name"].fillna(merged["task_name"])

                    # Limit and return dicts
                    return (
                        merged.sort_values("completed_at_ts", ascending=False)
                        .head(limit)
                        .to_dict(orient="records")
                    )
        except Exception as e:
            print(f"[TaskManager] get_recent fell back to created_at due to: {e}")

        # Fallback: use creation time if no completions available
        df = self.get_all()
        if df is None or df.empty:
            return []
        df = df.sort_values("created_at", ascending=False)
        return df.head(limit).to_dict(orient="records")
