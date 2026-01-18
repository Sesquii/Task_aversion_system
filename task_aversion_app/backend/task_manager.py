# backend/task_manager.py
import os
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

from backend.performance_logger import get_perf_logger
from backend.security_utils import (
    validate_task_name, validate_description, validate_note,
    sanitize_for_storage, ValidationError
)

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
TASKS_FILE = 'data/tasks.csv'
perf_logger = get_perf_logger()

class TaskManager:
    # Class-level cache for get_all shared across instances (recommendations create new
    # TaskManager per call; this avoids 8x get_all on dashboard load).
    _get_all_shared: dict = {}
    _get_all_shared_time: dict = {}

    def __init__(self):
        # Default to database (SQLite) unless USE_CSV is explicitly set
        # Check if CSV is explicitly requested
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        
        if use_csv:
            # CSV backend (explicitly requested)
            self.use_db = False
        else:
            # Database backend (default)
            # Ensure DATABASE_URL is set to default SQLite if not already set
            if not os.getenv('DATABASE_URL'):
                # Use the same default as database.py
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
            self.use_db = True
        
        # Strict mode: If DISABLE_CSV_FALLBACK is set, fail instead of falling back to CSV
        self.strict_mode = bool(os.getenv('DISABLE_CSV_FALLBACK', '').lower() in ('1', 'true', 'yes'))
        
        # Cache for frequently accessed data
        self._tasks_list_cache = None
        self._tasks_list_cache_time = None
        self._tasks_all_cache = None
        self._tasks_all_cache_time = None
        self._task_cache = {}  # Per-task cache: {task_id: (task_dict, timestamp)}
        self._cache_ttl_seconds = 300  # 5 minutes
        
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
                print(f"[TaskManager] WARNING: Database initialization failed: {e}, falling back to CSV")
                print(f"[TaskManager] This should not happen in production! Check database connection.")
                import traceback
                traceback.print_exc()
                self.use_db = False
                self._init_csv()
        else:
            # CSV backend (explicitly requested via USE_CSV)
            if self.strict_mode:
                raise RuntimeError(
                    "CSV backend is disabled (DISABLE_CSV_FALLBACK is set) but USE_CSV is set.\n"
                    "Please unset USE_CSV to use the database backend, or unset DISABLE_CSV_FALLBACK."
                )
            self._init_csv()
            print("[TaskManager] Using CSV backend")
        
        self.initialization_entries = []
    
    def _invalidate_task_caches(self):
        """Invalidate all task caches. Call this when tasks are created/updated/deleted."""
        # Clear old-style cache attributes
        self._tasks_list_cache = None
        self._tasks_list_cache_time = None
        self._tasks_all_cache = None
        self._tasks_all_cache_time = None
        self._task_cache.clear()
        TaskManager._get_all_shared.clear()
        TaskManager._get_all_shared_time.clear()

        # Clear dynamic cache keys (used by get_all() and list_tasks() with user_id)
        # These are stored as attributes like: _tasks_all_cache_all:1, _tasks_all_cache_time_all:1, etc.
        # We need to iterate through all attributes and remove cache-related ones
        attrs_to_remove = []
        for attr_name in dir(self):
            # Match patterns like:
            # - _tasks_all_cache_all:1
            # - _tasks_all_cache_time_all:1
            # - _tasks_list_cache_all:1
            # - _tasks_list_cache_time_all:1
            if (attr_name.startswith('_tasks_all_cache_') or 
                attr_name.startswith('_tasks_all_cache_time_') or
                attr_name.startswith('_tasks_list_cache_') or
                attr_name.startswith('_tasks_list_cache_time_')):
                attrs_to_remove.append(attr_name)
        
        for attr_name in attrs_to_remove:
            try:
                delattr(self, attr_name)
            except AttributeError:
                pass  # Attribute doesn't exist, skip
        
        print(f"[TaskManager] Invalidated task caches (cleared {len(attrs_to_remove)} dynamic cache attributes)")
    
    def _init_csv(self):
        """Initialize CSV backend."""
        os.makedirs(DATA_DIR, exist_ok=True)
        self.tasks_file = os.path.join(DATA_DIR, 'tasks.csv')
        # task definition fields:
        # task_id, name, description, type, version, created_at, is_recurring, categories (json), default_estimate_minutes, task_type, default_initial_aversion, routine_frequency, routine_days_of_week, routine_time, completion_window_hours, completion_window_days, notes
        if not os.path.exists(self.tasks_file):
            pd.DataFrame(columns=['task_id','name','description','type','version','created_at','is_recurring','categories','default_estimate_minutes','task_type','default_initial_aversion','routine_frequency','routine_days_of_week','routine_time','completion_window_hours','completion_window_days','notes']).to_csv(self.tasks_file, index=False)
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
        if 'notes' not in self.df.columns:
            self.df['notes'] = ''
    
    def _save(self):
        """Save data (CSV only)."""
        if not self.use_db:
            self._save_csv()
    
    def _save_csv(self):
        """CSV-specific save."""
        self.df.to_csv(self.tasks_file, index=False)
        self._reload_csv()
    
    def get_task(self, task_id, user_id: Optional[int] = None):
        """Return a task row by id as a dict. Works with both CSV and database.
        
        Uses per-task caching to avoid repeated database queries. Cache is TTL-based (5 minutes).
        
        Args:
            task_id: Task ID to retrieve
            user_id: User ID to filter by (required for database, optional for CSV during migration)
        """
        import time
        
        # Check per-task cache first (cache key includes user_id for isolation)
        cache_key = f"{task_id}:{user_id}" if user_id else task_id
        current_time = time.time()
        if cache_key in self._task_cache:
            cached_task, cache_time = self._task_cache[cache_key]
            if (current_time - cache_time) < self._cache_ttl_seconds:
                return cached_task.copy() if isinstance(cached_task, dict) else cached_task
        
        # Cache miss - load from database/CSV
        if self.use_db:
            result = self._get_task_db(task_id, user_id)
        else:
            result = self._get_task_csv(task_id, user_id)
        
        # Store in per-task cache
        if result is not None:
            self._task_cache[cache_key] = (result.copy() if isinstance(result, dict) else result, time.time())
        
        return result

    def get_tasks_bulk(self, task_ids: List[str], user_id: Optional[int] = None) -> Dict[str, dict]:
        """Fetch multiple tasks by id in one query. Returns {task_id: task_dict}."""
        if not task_ids or (self.use_db and user_id is None):
            return {}
        if self.use_db:
            return self._get_tasks_bulk_db(task_ids, user_id)
        return self._get_tasks_bulk_csv(task_ids, user_id)

    def _get_tasks_bulk_db(self, task_ids: List[str], user_id: int) -> Dict[str, dict]:
        try:
            from sqlalchemy import or_
            with self.db_session() as session:
                query = session.query(self.Task).filter(self.Task.task_id.in_(task_ids))
                query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                tasks = query.all()
                return {t.task_id: t.to_dict() for t in tasks}
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_tasks_bulk: {e}") from e
            self.use_db = False
            return self._get_tasks_bulk_csv(task_ids, user_id)

    def _get_tasks_bulk_csv(self, task_ids: List[str], user_id: Optional[int] = None) -> Dict[str, dict]:
        self._reload_csv()
        df = self.df[self.df['task_id'].isin(task_ids)]
        if user_id is not None and 'user_id' in df.columns:
            df = df[df['user_id'].astype(str) == str(user_id)]
        return {r['task_id']: r for r in df.to_dict(orient='records')}

    def _get_task_csv(self, task_id, user_id: Optional[int] = None):
        """CSV-specific get_task."""
        with perf_logger.operation("_get_task_csv", task_id=task_id, user_id=user_id):
            self._reload_csv()
            rows = self.df[self.df['task_id'] == task_id]
            # Filter by user_id for data isolation if provided
            if user_id is not None and 'user_id' in rows.columns:
                # Convert user_id to string for CSV comparison (CSV stores as string)
                user_id_str = str(user_id)
                rows = rows[rows['user_id'] == user_id_str]
            elif user_id is not None and 'user_id' not in rows.columns:
                # CSV doesn't have user_id column - return None for security (data isolation)
                print(f"[TaskManager] WARNING: CSV mode - user_id filtering requested but 'user_id' column not found. Returning None for data isolation.")
                return None
            return rows.iloc[0].to_dict() if not rows.empty else None
    
    def _get_task_db(self, task_id, user_id: Optional[int] = None):
        """Database-specific get_task."""
        try:
            with perf_logger.operation("_get_task_db", task_id=task_id, user_id=user_id):
                with self.db_session() as session:
                    query = session.query(self.Task).filter(self.Task.task_id == task_id)
                    # Filter by user_id if provided (include NULL user_id during migration period)
                    if user_id is not None:
                        # Show both user's tasks AND NULL user_id tasks (anonymous data to be migrated)
                        from sqlalchemy import or_
                        query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                    task = query.first()
                    return task.to_dict() if task else None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_task and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in get_task: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._get_task_csv(task_id, user_id)

    def list_tasks(self, user_id: Optional[int] = None) -> List[str]:
        """Return list of task names. Works with both CSV and database.
        
        Uses caching to avoid repeated database queries. Cache is TTL-based (5 minutes).
        
        Args:
            user_id: User ID to filter by (required for database, optional for CSV during migration)
        """
        import time
        
        # Check cache first (cache key includes user_id for isolation)
        cache_key = f"list:{user_id}" if user_id else "list:all"
        current_time = time.time()
        if (hasattr(self, f'_tasks_list_cache_{cache_key}') and 
            hasattr(self, f'_tasks_list_cache_time_{cache_key}')):
            cache = getattr(self, f'_tasks_list_cache_{cache_key}')
            cache_time = getattr(self, f'_tasks_list_cache_time_{cache_key}')
            if cache is not None and cache_time is not None and (current_time - cache_time) < self._cache_ttl_seconds:
                return cache.copy()
        
        # Cache miss - load from database/CSV
        if self.use_db:
            result = self._list_tasks_db(user_id)
        else:
            result = self._list_tasks_csv()
        
        # Store in cache
        setattr(self, f'_tasks_list_cache_{cache_key}', result.copy() if isinstance(result, list) else result)
        setattr(self, f'_tasks_list_cache_time_{cache_key}', time.time())
        
        return result
    
    def _list_tasks_csv(self) -> List[str]:
        """CSV-specific list_tasks."""
        self._reload_csv()
        return list(self.df['name'].tolist())
    
    def _list_tasks_db(self, user_id: Optional[int] = None) -> List[str]:
        """Database-specific list_tasks."""
        try:
            with self.db_session() as session:
                query = session.query(self.Task)
                # Filter by user_id if provided (include NULL user_id during migration period)
                if user_id is not None:
                    # Show both user's tasks AND NULL user_id tasks (anonymous data to be migrated)
                    from sqlalchemy import or_
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                tasks = query.all()
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
        with perf_logger.operation("save_initialization_entry", instance_id=entry.get('instance_id')):
            self.initialization_entries.append(entry)
            print(f"Saved initialization entry: {entry}")
    def get_all(self, user_id: Optional[int] = None):
        """Return all tasks as DataFrame (CSV) or list of dicts (database). Works with both backends.
        
        Uses caching to avoid repeated database queries. Cache is TTL-based (5 minutes).
        
        Args:
            user_id: User ID to filter by (REQUIRED for database mode, optional for CSV only)
        
        Raises:
            ValueError: If user_id is None in database mode (data isolation requirement)
        """
        import time
        
        # Data isolation: require user_id in database mode
        if self.use_db and user_id is None:
            raise ValueError(
                "user_id is required in database mode for data isolation. "
                "Unauthenticated users should use CSV mode (set USE_CSV=1)."
            )
        
        # Check cache first (cache key includes user_id for isolation)
        cache_key = f"all:{user_id}" if user_id else "all:all"
        current_time = time.time()
        # Class-level shared cache (shared across TaskManager instances, e.g. 8x recommendations on dashboard)
        if (cache_key in getattr(TaskManager, '_get_all_shared', {}) and
            cache_key in getattr(TaskManager, '_get_all_shared_time', {}) and
            (current_time - TaskManager._get_all_shared_time[cache_key]) < self._cache_ttl_seconds):
            return TaskManager._get_all_shared[cache_key].copy()
        if (hasattr(self, f'_tasks_all_cache_{cache_key}') and
            hasattr(self, f'_tasks_all_cache_time_{cache_key}')):
            cache = getattr(self, f'_tasks_all_cache_{cache_key}')
            cache_time = getattr(self, f'_tasks_all_cache_time_{cache_key}')
            if cache is not None and cache_time is not None and (current_time - cache_time) < self._cache_ttl_seconds:
                return cache.copy()

        # Cache miss - load from database/CSV
        if self.use_db:
            result = self._get_all_db(user_id)
        else:
            result = self._get_all_csv(user_id)
        
        # Store in instance and class-level cache
        setattr(self, f'_tasks_all_cache_{cache_key}', result.copy())
        setattr(self, f'_tasks_all_cache_time_{cache_key}', time.time())
        TaskManager._get_all_shared[cache_key] = result.copy()
        TaskManager._get_all_shared_time[cache_key] = time.time()

        return result

    def _get_all_csv(self, user_id: Optional[int] = None):
        """CSV-specific get_all."""
        self._reload_csv()
        df = self.df.copy()
        # Filter by user_id for data isolation if provided
        if user_id is not None and 'user_id' in df.columns:
            # Convert user_id to string for CSV comparison (CSV stores as string)
            user_id_str = str(user_id)
            df = df[df['user_id'] == user_id_str]
        elif user_id is not None and 'user_id' not in df.columns:
            # CSV doesn't have user_id column - return empty DataFrame for security (data isolation)
            print(f"[TaskManager] WARNING: CSV mode - user_id filtering requested but 'user_id' column not found. Returning empty DataFrame for data isolation.")
            return pd.DataFrame(columns=df.columns)
        return df
    
    def _get_all_db(self, user_id: int):
        """Database-specific get_all. Returns DataFrame for compatibility.
        
        Args:
            user_id: User ID (required - data isolation enforced)
        """
        try:
            with self.db_session() as session:
                query = session.query(self.Task)
                # Strict data isolation: only return tasks for this user
                # NULL user_id tasks remain in database for migration but are not accessible
                query = query.filter(self.Task.user_id == user_id)
                tasks = query.all()
                if not tasks:
                    # Return empty DataFrame with expected columns
                    return pd.DataFrame(columns=['task_id','name','description','type','version','created_at','is_recurring','categories','default_estimate_minutes','task_type','default_initial_aversion','routine_frequency','routine_days_of_week','routine_time','completion_window_hours','completion_window_days','notes','user_id'])
                # Convert to list of dicts, then to DataFrame
                task_dicts = [task.to_dict() for task in tasks]
                return pd.DataFrame(task_dicts)
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_all and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in get_all: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._get_all_csv(user_id)

    def create_task(self, name, description='', ttype='one-time', is_recurring=False, categories='[]', default_estimate_minutes=0, task_type='Work', default_initial_aversion=None, routine_frequency='none', routine_days_of_week=None, routine_time='00:00', completion_window_hours=None, completion_window_days=None, user_id: Optional[int] = None):
        """
        Creates a new task definition and returns task_id. Works with both CSV and database.
        
        Args:
            default_initial_aversion: Optional initial aversion value (0-100) to use as default when first initializing this task
            routine_frequency: 'none', 'daily', or 'weekly'
            routine_days_of_week: List of day numbers (0=Monday, 6=Sunday) for weekly frequency
            routine_time: Time in HH:MM format (24-hour), default '00:00'
            completion_window_hours: Hours to complete task after initialization without penalty
            completion_window_days: Days to complete task after initialization without penalty
            user_id: User ID to associate task with (required for database, optional for CSV during migration)
            
        Raises:
            ValidationError: If input validation fails (name too long, etc.)
        """
        # Validate and sanitize inputs
        try:
            name = validate_task_name(name)
            description = validate_description(description)
        except ValidationError as e:
            raise  # Re-raise validation errors for UI to handle
        
        if routine_days_of_week is None:
            routine_days_of_week = []
        # Invalidate caches before creating
        self._invalidate_task_caches()
        if self.use_db:
            return self._create_task_db(name, description, ttype, is_recurring, categories, default_estimate_minutes, task_type, default_initial_aversion, routine_frequency, routine_days_of_week, routine_time, completion_window_hours, completion_window_days, user_id)
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
    
    def _create_task_db(self, name, description='', ttype='one-time', is_recurring=False, categories='[]', default_estimate_minutes=0, task_type='Work', default_initial_aversion=None, routine_frequency='none', routine_days_of_week=None, routine_time='00:00', completion_window_hours=None, completion_window_days=None, user_id: Optional[int] = None):
        """Database-specific create_task."""
        # SECURITY: Require user_id for database operations
        if user_id is None:
            raise ValueError("user_id is required for database operations. User must be authenticated.")
        
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
                    user_id=user_id,
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

    def update_task(self, task_id, user_id: Optional[int] = None, **kwargs):
        """Update a task. Works with both CSV and database.
        
        Args:
            task_id: Task ID to update
            user_id: User ID to filter by (required for database, optional for CSV during migration)
            **kwargs: Fields to update
        """
        # Invalidate caches before updating
        self._invalidate_task_caches()
        if self.use_db:
            return self._update_task_db(task_id, user_id, **kwargs)
        else:
            return self._update_task_csv(task_id, user_id, **kwargs)
    
    def _update_task_csv(self, task_id, user_id: Optional[int] = None, **kwargs):
        """CSV-specific update_task."""
        self._reload_csv()
        matches = self.df.index[self.df['task_id'] == task_id]
        if len(matches) == 0:
            return False
        
        # Filter by user_id for data isolation if provided
        if user_id is not None and 'user_id' in self.df.columns:
            # Convert user_id to string for CSV comparison (CSV stores as string)
            user_id_str = str(user_id)
            matches = matches[self.df.loc[matches, 'user_id'] == user_id_str]
            if len(matches) == 0:
                print(f"[TaskManager] Task {task_id} not found or access denied (user_id mismatch)")
                return False
        elif user_id is not None and 'user_id' not in self.df.columns:
            # CSV doesn't have user_id column - deny access for security (data isolation)
            print(f"[TaskManager] WARNING: CSV mode - user_id verification requested but 'user_id' column not found. Denying access for data isolation.")
            return False
        
        idx = matches[0]
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
    
    def _update_task_db(self, task_id, user_id: Optional[int] = None, **kwargs):
        """Database-specific update_task.
        
        Args:
            task_id: Task ID to update
            user_id: User ID to filter by (required for data isolation)
            **kwargs: Fields to update
        """
        # CRITICAL: Require user_id for data isolation
        if user_id is None:
            print("[TaskManager] WARNING: _update_task_db() called without user_id - returning False for security")
            return False
        
        try:
            with self.db_session() as session:
                from sqlalchemy import or_
                # Filter by task_id and user_id (include NULL user_id during migration period)
                query = session.query(self.Task).filter(
                    self.Task.task_id == task_id
                ).filter(
                    or_(self.Task.user_id == user_id, self.Task.user_id.is_(None))
                )
                task = query.first()
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
            return self._update_task_csv(task_id, user_id, **kwargs)

    def find_by_name(self, name, user_id: Optional[int] = None):
        """Find a task by name. Works with both CSV and database.
        
        Args:
            name: Task name to search for
            user_id: User ID to filter by (required for database, optional for CSV during migration)
        """
        if self.use_db:
            return self._find_by_name_db(name, user_id)
        else:
            return self._find_by_name_csv(name, user_id)
    
    def _find_by_name_csv(self, name, user_id: Optional[int] = None):
        """CSV-specific find_by_name."""
        self._reload_csv()
        rows = self.df[self.df['name'] == name]
        # Filter by user_id for data isolation if provided
        if user_id is not None and 'user_id' in rows.columns:
            # Convert user_id to string for CSV comparison (CSV stores as string)
            user_id_str = str(user_id)
            rows = rows[rows['user_id'] == user_id_str]
        elif user_id is not None and 'user_id' not in rows.columns:
            # CSV doesn't have user_id column - return None for security (data isolation)
            print(f"[TaskManager] WARNING: CSV mode - user_id filtering requested but 'user_id' column not found. Returning None for data isolation.")
            return None
        return rows.iloc[0].to_dict() if not rows.empty else None
    
    def _find_by_name_db(self, name, user_id: Optional[int] = None):
        """Database-specific find_by_name."""
        try:
            with self.db_session() as session:
                query = session.query(self.Task).filter(self.Task.name == name)
                # Filter by user_id if provided (include NULL user_id during migration period)
                if user_id is not None:
                    # Show both user's tasks AND NULL user_id tasks (anonymous data to be migrated)
                    from sqlalchemy import or_
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                task = query.first()
                return task.to_dict() if task else None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in find_by_name and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in find_by_name: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._find_by_name_csv(name, user_id)

    def ensure_task_exists(self, name, user_id: Optional[int] = None):
        """Ensure a task exists, creating it if necessary.
        
        Args:
            name: Task name
            user_id: User ID to filter by (required for database, optional for CSV during migration)
        """
        t = self.find_by_name(name, user_id)
        if t:
            return t['task_id']
        return self.create_task(name, user_id=user_id)
    
    def append_task_notes(self, task_id: str, note: str, user_id: Optional[int] = None):
        """Append a note to a task template (shared across all instances). Works with both CSV and database.
        
        Args:
            task_id: The task ID to append notes to
            note: The note text to append (will be timestamped and separated with '---')
            user_id: User ID to filter by (required for database, optional for CSV during migration)
            
        Raises:
            ValidationError: If note validation fails (too long, etc.)
        """
        # Validate and sanitize note
        try:
            note = validate_note(note)
        except ValidationError as e:
            raise  # Re-raise validation errors for UI to handle
        
        if self.use_db:
            return self._append_task_notes_db(task_id, note, user_id)
        else:
            return self._append_task_notes_csv(task_id, note, user_id)
    
    def _append_task_notes_csv(self, task_id: str, note: str, user_id: Optional[int] = None):
        """CSV-specific append_task_notes."""
        from datetime import datetime
        self._reload_csv()
        matches = self.df.index[self.df['task_id'] == task_id]
        if len(matches) == 0:
            raise ValueError(f"Task {task_id} not found")
        
        # Filter by user_id for data isolation if provided
        if user_id is not None and 'user_id' in self.df.columns:
            # Convert user_id to string for CSV comparison (CSV stores as string)
            user_id_str = str(user_id)
            matches = matches[self.df.loc[matches, 'user_id'] == user_id_str]
            if len(matches) == 0:
                raise ValueError(f"Task {task_id} not found or access denied (user_id mismatch)")
        elif user_id is not None and 'user_id' not in self.df.columns:
            # CSV doesn't have user_id column - deny access for security (data isolation)
            print(f"[TaskManager] WARNING: CSV mode - user_id verification requested but 'user_id' column not found. Denying access for data isolation.")
            raise ValueError(f"Task {task_id} access denied (user_id verification not available in CSV mode)")
        
        idx = matches[0]
        
        # Get existing notes or initialize
        existing_notes = self.df.at[idx, 'notes'] if 'notes' in self.df.columns else ''
        if pd.isna(existing_notes) or existing_notes == '':
            existing_notes = ''
        
        # Append new note with timestamp and separator
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        timestamped_note = f"[{timestamp}]\n{note}"
        
        if existing_notes:
            new_notes = existing_notes + '\n\n---\n\n' + timestamped_note
        else:
            new_notes = timestamped_note
        
        self.df.at[idx, 'notes'] = new_notes
        self._save_csv()
    
    def _append_task_notes_db(self, task_id: str, note: str, user_id: Optional[int] = None):
        """Database-specific append_task_notes."""
        try:
            from datetime import datetime
            with self.db_session() as session:
                query = session.query(self.Task).filter(self.Task.task_id == task_id)
                # Filter by user_id if provided (include NULL user_id during migration period)
                if user_id is not None:
                    # Show both user's tasks AND NULL user_id tasks (anonymous data to be migrated)
                    from sqlalchemy import or_
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                task = query.first()
                if not task:
                    raise ValueError(f"Task {task_id} not found")
                
                # Get existing notes or initialize
                existing_notes = task.notes or ''
                
                # Append new note with timestamp and separator
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                timestamped_note = f"[{timestamp}]\n{note}"
                
                if existing_notes:
                    new_notes = existing_notes + '\n\n---\n\n' + timestamped_note
                else:
                    new_notes = timestamped_note
                
                task.notes = new_notes
                task.updated_at = datetime.now()
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in append_task_notes and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in append_task_notes: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._append_task_notes_csv(task_id, note, user_id)
    
    def get_task_notes(self, task_id: str, user_id: Optional[int] = None) -> str:
        """Get notes for a task template. Works with both CSV and database.
        
        Args:
            task_id: The task ID
            user_id: User ID to filter by (required for database, optional for CSV during migration)
            
        Returns:
            Notes string (empty string if no notes)
        """
        if self.use_db:
            return self._get_task_notes_db(task_id, user_id)
        else:
            return self._get_task_notes_csv(task_id, user_id)
    
    def _get_task_notes_csv(self, task_id: str, user_id: Optional[int] = None) -> str:
        """CSV-specific get_task_notes."""
        self._reload_csv()
        matches = self.df.index[self.df['task_id'] == task_id]
        if len(matches) == 0:
            return ''
        
        # Filter by user_id for data isolation if provided
        if user_id is not None and 'user_id' in self.df.columns:
            # Convert user_id to string for CSV comparison (CSV stores as string)
            user_id_str = str(user_id)
            matches = matches[self.df.loc[matches, 'user_id'] == user_id_str]
            if len(matches) == 0:
                # Task not found or access denied - return empty string for security
                return ''
        elif user_id is not None and 'user_id' not in self.df.columns:
            # CSV doesn't have user_id column - return empty string for security (data isolation)
            print(f"[TaskManager] WARNING: CSV mode - user_id verification requested but 'user_id' column not found. Returning empty string for data isolation.")
            return ''
        
        idx = matches[0]
        notes = self.df.at[idx, 'notes'] if 'notes' in self.df.columns else ''
        return notes if not pd.isna(notes) else ''
    
    def _get_task_notes_db(self, task_id: str, user_id: Optional[int] = None) -> str:
        """Database-specific get_task_notes."""
        try:
            with self.db_session() as session:
                query = session.query(self.Task).filter(self.Task.task_id == task_id)
                # Filter by user_id if provided (include NULL user_id during migration period)
                if user_id is not None:
                    # Show both user's tasks AND NULL user_id tasks (anonymous data to be migrated)
                    from sqlalchemy import or_
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                task = query.first()
                if not task:
                    return ''
                return task.notes or ''
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_task_notes and CSV fallback is disabled: {e}") from e
            print(f"[TaskManager] Database error in get_task_notes: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._get_task_notes_csv(task_id, user_id)

    def get_task_notes_bulk(self, task_ids: List[str], user_id: Optional[int] = None) -> Dict[str, str]:
        """Get notes for multiple tasks in one query. Use to avoid N+1 when filtering by notes.

        Args:
            task_ids: List of task IDs
            user_id: User ID to filter by (required for database, optional for CSV)

        Returns:
            Dict mapping task_id -> notes string (empty string if no notes or not found)
        """
        if not task_ids:
            return {}
        if self.use_db:
            return self._get_task_notes_bulk_db(task_ids, user_id)
        return self._get_task_notes_bulk_csv(task_ids, user_id)

    def _get_task_notes_bulk_csv(self, task_ids: List[str], user_id: Optional[int] = None) -> Dict[str, str]:
        """CSV-specific get_task_notes_bulk."""
        self._reload_csv()
        result: Dict[str, str] = {tid: '' for tid in task_ids}
        for task_id in task_ids:
            mask = self.df['task_id'] == task_id
            if user_id is not None and 'user_id' in self.df.columns:
                mask = mask & (self.df['user_id'].astype(str) == str(user_id))
            elif user_id is not None and 'user_id' not in self.df.columns:
                continue
            rows = self.df.loc[mask]
            if not rows.empty:
                notes = rows.iloc[0].get('notes', '')
                result[task_id] = notes if not pd.isna(notes) else ''
        return result

    def _get_task_notes_bulk_db(self, task_ids: List[str], user_id: Optional[int] = None) -> Dict[str, str]:
        """Database-specific get_task_notes_bulk. One query with IN clause."""
        from sqlalchemy import or_
        result: Dict[str, str] = {tid: '' for tid in task_ids}
        try:
            with self.db_session() as session:
                query = session.query(self.Task.task_id, self.Task.notes).filter(
                    self.Task.task_id.in_(task_ids)
                )
                if user_id is not None:
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                for row in query.all():
                    result[row.task_id] = (row.notes or '') if row.notes else ''
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_task_notes_bulk: {e}") from e
            print(f"[TaskManager] Database error in get_task_notes_bulk: {e}, falling back to CSV")
            self.use_db = False
            self._ensure_csv_initialized()
            return self._get_task_notes_bulk_csv(task_ids, user_id)
        return result

    def delete_by_id(self, task_id, user_id: Optional[int] = None):
        """Remove a task template by id. Works with both CSV and database.
        
        Args:
            task_id: Task ID to delete
            user_id: User ID to filter by (required for database, optional for CSV during migration)
        """
        print(f"[TaskManager] delete_by_id called with: {task_id}")
        # Invalidate caches before deleting
        self._invalidate_task_caches()
        if self.use_db:
            return self._delete_by_id_db(task_id, user_id)
        else:
            return self._delete_by_id_csv(task_id, user_id)
    
    def _delete_by_id_csv(self, task_id, user_id: Optional[int] = None):
        """CSV-specific delete_by_id."""
        self._reload_csv()
        matches = self.df.index[self.df['task_id'] == task_id]
        if len(matches) == 0:
            print("[TaskManager] No matching task to delete.")
            return False
        
        # Filter by user_id for data isolation if provided
        if user_id is not None and 'user_id' in self.df.columns:
            # Convert user_id to string for CSV comparison (CSV stores as string)
            user_id_str = str(user_id)
            matches = matches[self.df.loc[matches, 'user_id'] == user_id_str]
            if len(matches) == 0:
                print(f"[TaskManager] Task {task_id} not found or access denied (user_id mismatch)")
                return False
        elif user_id is not None and 'user_id' not in self.df.columns:
            # CSV doesn't have user_id column - deny access for security (data isolation)
            print(f"[TaskManager] WARNING: CSV mode - user_id verification requested but 'user_id' column not found. Denying access for data isolation.")
            return False
        
        before = len(self.df)
        self.df = self.df[self.df['task_id'] != task_id]
        if len(self.df) == before:
            print("[TaskManager] No matching task to delete.")
            return False
        self._save_csv()
        print("[TaskManager] Task deleted successfully.")
        return True
    
    def _delete_by_id_db(self, task_id, user_id: Optional[int] = None):
        """Database-specific delete_by_id."""
        try:
            with self.db_session() as session:
                query = session.query(self.Task).filter(self.Task.task_id == task_id)
                # Filter by user_id if provided (include NULL user_id during migration period)
                if user_id is not None:
                    # Show both user's tasks AND NULL user_id tasks (anonymous data to be migrated)
                    from sqlalchemy import or_
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                task = query.first()
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
            return self._delete_by_id_csv(task_id, user_id)


    def get_recent(self, limit=5, user_id: Optional[int] = None):
        """Return tasks sorted by most recently completed instance.

        Falls back to task creation time if no completed instances exist.
        
        Args:
            limit: Maximum number of tasks to return
            user_id: Optional user_id for data isolation
        """
        print(f"[TaskManager] get_recent called (limit={limit}, user_id={user_id})")

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
                tasks_df = self.get_all(user_id=user_id)
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
        df = self.get_all(user_id=user_id)
        if df is None or df.empty:
            return []
        df = df.sort_values("created_at", ascending=False)
        return df.head(limit).to_dict(orient="records")
