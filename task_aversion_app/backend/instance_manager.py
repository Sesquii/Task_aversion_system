# backend/instance_manager.py
import os
import pandas as pd
from datetime import datetime
from typing import Optional
import json
import time

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
class InstanceManager:
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
        
        if self.use_db:
            # Database backend
            try:
                from backend.database import get_session, TaskInstance, init_db
                self.db_session = get_session
                self.TaskInstance = TaskInstance
                # Initialize database if tables don't exist
                init_db()
                print("[InstanceManager] Using database backend")
                # Also initialize CSV for backward compatibility and fallback
                self._init_csv()
                print("[InstanceManager] CSV backend also initialized (for backward compatibility)")
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(
                        f"Database initialization failed and CSV fallback is disabled: {e}\n"
                        "Set DISABLE_CSV_FALLBACK=false or unset DATABASE_URL to allow CSV fallback."
                    ) from e
                print(f"[InstanceManager] Database initialization failed: {e}, falling back to CSV")
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
            print("[InstanceManager] Using CSV backend")
    
    def _init_csv(self):
        """Initialize CSV backend."""
        os.makedirs(DATA_DIR, exist_ok=True)
        self.file = os.path.join(DATA_DIR, 'task_instances.csv')
        # fields: instance_id, task_id, task_name, task_version, created_at, initialized_at, started_at, completed_at,
        # predicted (json), actual (json), procrastination_score, proactive_score, is_completed, is_deleted, delay_minutes
        if not os.path.exists(self.file):
            pd.DataFrame(columns=[
                'instance_id','task_id','task_name','task_version','created_at','initialized_at','started_at',
                'completed_at','cancelled_at','predicted','actual','procrastination_score','proactive_score',
                'is_completed','is_deleted','status','delay_minutes'
            ]).to_csv(self.file, index=False)
        self._reload()

    def _reload(self, max_retries=5, initial_delay=0.1):
        """Reload data (CSV only)."""
        if not self.use_db:
            self._reload_csv(max_retries, initial_delay)
    
    def _reload_csv(self, max_retries=5, initial_delay=0.1):
        """
        Reload CSV file with retry logic to handle file locking issues.
        Common causes: Excel/other programs have file open, OneDrive sync, or concurrent access.
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                self.df = pd.read_csv(self.file, dtype=str).fillna('')
                # Success - break out of retry loop
                break
            except PermissionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                    delay = initial_delay * (2 ** attempt)
                    print(f"[InstanceManager] Permission denied reading {self.file} (attempt {attempt + 1}/{max_retries}). "
                          f"Retrying in {delay:.2f}s... "
                          f"Tip: Close Excel/other programs that may have this file open.")
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    print(f"[InstanceManager] ERROR: Failed to read {self.file} after {max_retries} attempts. "
                          f"File may be locked by another process (Excel, OneDrive sync, etc.). "
                          f"Using empty DataFrame as fallback.")
                    # Fallback to empty DataFrame with expected columns
                    self.df = pd.DataFrame(columns=[
                        'instance_id','task_id','task_name','task_version','created_at','initialized_at','started_at',
                        'completed_at','cancelled_at','predicted','actual','procrastination_score','proactive_score',
                        'is_completed','is_deleted','status','delay_minutes'
                    ])
            except Exception as e:
                # Other errors (file not found, corrupted, etc.)
                last_error = e
                print(f"[InstanceManager] ERROR reading {self.file}: {e}")
                # Fallback to empty DataFrame
                self.df = pd.DataFrame(columns=[
                    'instance_id','task_id','task_name','task_version','created_at','initialized_at','started_at',
                    'completed_at','cancelled_at','predicted','actual','procrastination_score','proactive_score',
                    'is_completed','is_deleted','status','delay_minutes'
                ])
                break
        defaults = {
            'predicted': '',
            'actual': '',
            'cancelled_at': '',
            'duration_minutes': '',
            'delay_minutes': '',
            'relief_score': '',
            'cognitive_load': '',
            'mental_energy_needed': '',
            'task_difficulty': '',
            'emotional_load': '',
            'environmental_effect': '',
            'skills_improved': '',
            'behavioral_score': '',
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

    def _save(self, max_retries=5, initial_delay=0.1):
        """Save data (CSV only)."""
        if not self.use_db:
            self._save_csv(max_retries, initial_delay)
    
    def _save_csv(self, max_retries=5, initial_delay=0.1):
        """
        Save DataFrame to CSV with retry logic to handle file locking issues.
        Common causes: Excel/other programs have file open, OneDrive sync, or concurrent access.
        
        Note: We don't reload after saving since the DataFrame is already in memory.
        Reload only happens when needed (e.g., at initialization or before operations).
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                self.df.to_csv(self.file, index=False)
                # Success - no need to reload since DataFrame is already in memory
                break
            except PermissionError as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                    delay = initial_delay * (2 ** attempt)
                    print(f"[InstanceManager] Permission denied writing to {self.file} (attempt {attempt + 1}/{max_retries}). "
                          f"Retrying in {delay:.2f}s... "
                          f"Tip: Close Excel/other programs that may have this file open.")
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    print(f"[InstanceManager] ERROR: Failed to write to {self.file} after {max_retries} attempts. "
                          f"File may be locked by another process (Excel, OneDrive sync, etc.). "
                          f"Changes were not saved.")
                    raise PermissionError(
                        f"Cannot save to {self.file}. File is locked. "
                        f"Please close any programs (Excel, etc.) that have this file open and try again."
                    ) from e
            except Exception as e:
                # Other errors (disk full, etc.)
                last_error = e
                print(f"[InstanceManager] ERROR writing to {self.file}: {e}")
                raise

    # ============================================================================
    # Helper Methods for CSV/Database Conversion
    # ============================================================================
    
    def _csv_to_db_datetime(self, csv_str):
        """Parse CSV datetime string to datetime object."""
        if not csv_str or csv_str.strip() == '':
            return None
        try:
            return datetime.strptime(csv_str.strip(), "%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return None
    
    def _db_to_csv_datetime(self, dt):
        """Format datetime object to CSV string format."""
        return dt.strftime("%Y-%m-%d %H:%M") if dt else ''
    
    def _parse_json_field(self, json_str):
        """Safe JSON parsing with fallback to empty dict."""
        if not json_str or json_str.strip() == '':
            return {}
        try:
            parsed = json.loads(json_str)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def _csv_to_db_dict(self, row_dict):
        """Convert CSV row dict to database-compatible dict."""
        db_dict = row_dict.copy()
        
        # Convert datetime strings to datetime objects
        for field in ['created_at', 'initialized_at', 'started_at', 'completed_at', 'cancelled_at']:
            if field in db_dict:
                db_dict[field] = self._csv_to_db_datetime(db_dict[field])
        
        # Parse JSON fields
        if 'predicted' in db_dict:
            db_dict['predicted'] = self._parse_json_field(db_dict['predicted'])
        if 'actual' in db_dict:
            db_dict['actual'] = self._parse_json_field(db_dict['actual'])
        
        # Convert numeric fields (empty strings to None)
        for field in ['procrastination_score', 'proactive_score', 'behavioral_score', 'net_relief',
                      'duration_minutes', 'delay_minutes', 'relief_score', 'cognitive_load',
                      'mental_energy_needed', 'task_difficulty', 'emotional_load', 'environmental_effect']:
            if field in db_dict:
                val = db_dict[field]
                if not val or str(val).strip() == '':
                    db_dict[field] = None
                else:
                    try:
                        db_dict[field] = float(val)
                    except (ValueError, TypeError):
                        db_dict[field] = None
        
        # Convert boolean fields
        for field in ['is_completed', 'is_deleted']:
            if field in db_dict:
                db_dict[field] = str(db_dict.get(field, 'False')).lower() == 'true'
        
        # Convert task_version to int
        if 'task_version' in db_dict:
            try:
                db_dict['task_version'] = int(db_dict['task_version']) if db_dict['task_version'] else 1
            except (ValueError, TypeError):
                db_dict['task_version'] = 1
        
        # skills_improved stays as string (or can be converted to list if needed)
        # For now, keep as string to match CSV format
        
        return db_dict
    
    def _csv_to_db_float(self, csv_str):
        """Convert CSV string to float, returning None for empty values."""
        if not csv_str or csv_str.strip() == '':
            return None
        try:
            return float(csv_str)
        except (ValueError, TypeError):
            return None

    def create_instance(self, task_id, task_name, task_version=1, predicted: dict = None):
        """Create a new task instance. Works with both CSV and database."""
        if self.use_db:
            return self._create_instance_db(task_id, task_name, task_version, predicted)
        else:
            return self._create_instance_csv(task_id, task_name, task_version, predicted)
    
    def _create_instance_csv(self, task_id, task_name, task_version=1, predicted: dict = None):
        """CSV-specific create_instance."""
        self._reload()
        instance_id = f"i{int(datetime.now().timestamp())}"
        row = {
            'instance_id': instance_id,
            'task_id': task_id,
            'task_name': task_name,
            'task_version': task_version,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'initialized_at': '',  # Will be set when user saves initialization form
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
            'delay_minutes': '',
            'relief_score': '',
            'cognitive_load': '',
            'mental_energy_needed': '',
            'task_difficulty': '',
            'emotional_load': '',
            'environmental_effect': '',
            'skills_improved': '',
            'behavioral_score': '',
            'net_relief': '',
        }
        self.df = pd.concat([self.df, pd.DataFrame([row])], ignore_index=True)
        self._save()
        return instance_id
    
    def _create_instance_db(self, task_id, task_name, task_version=1, predicted: dict = None):
        """Database-specific create_instance."""
        try:
            instance_id = f"i{int(datetime.now().timestamp())}"
            created_at = datetime.now()
            
            with self.db_session() as session:
                instance = self.TaskInstance(
                    instance_id=instance_id,
                    task_id=task_id,
                    task_name=task_name,
                    task_version=int(task_version) if task_version else 1,
                    created_at=created_at,
                    initialized_at=None,
                    started_at=None,
                    completed_at=None,
                    cancelled_at=None,
                    predicted=predicted or {},
                    actual={},
                    procrastination_score=None,
                    proactive_score=None,
                    behavioral_score=None,
                    net_relief=None,
                    is_completed=False,
                    is_deleted=False,
                    status='active',
                    duration_minutes=None,
                    delay_minutes=None,
                    relief_score=None,
                    cognitive_load=None,
                    mental_energy_needed=None,
                    task_difficulty=None,
                    emotional_load=None,
                    environmental_effect=None,
                    skills_improved=''
                )
                session.add(instance)
                session.commit()
                return instance_id
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in create_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in create_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._create_instance_csv(task_id, task_name, task_version, predicted)

    def pause_instance(self, instance_id: str, reason: Optional[str] = None, completion_percentage: float = 0.0):
        """Pause an active instance and move it back to initialized state. Works with both CSV and database.
        
        Args:
            instance_id: The instance ID to pause
            reason: Optional reason for pausing
            completion_percentage: Completion percentage (0-100) when pausing
        """
        if self.use_db:
            return self._pause_instance_db(instance_id, reason, completion_percentage)
        else:
            return self._pause_instance_csv(instance_id, reason, completion_percentage)
    
    def _pause_instance_csv(self, instance_id: str, reason: Optional[str] = None, completion_percentage: float = 0.0):
        """CSV-specific pause_instance."""
        import json
        self._reload()
        matches = self.df.index[self.df['instance_id'] == instance_id]
        if len(matches) == 0:
            raise ValueError(f"Instance {instance_id} not found")

        idx = matches[0]
        
        # Calculate elapsed time before resetting started_at
        time_spent_before_pause = 0.0
        started_at_str = self.df.at[idx, 'started_at']
        if started_at_str and str(started_at_str).strip():
            try:
                started_at = self._csv_to_db_datetime(started_at_str)
                if started_at:
                    now = datetime.now()
                    elapsed_seconds = (now - started_at).total_seconds()
                    time_spent_before_pause = elapsed_seconds / 60.0  # Convert to minutes
            except Exception as e:
                print(f"[InstanceManager] Error calculating elapsed time on pause: {e}")
        
        # Get existing actual data to preserve time_spent_before_pause if resuming after multiple pauses
        actual_str = self.df.at[idx, 'actual'] or '{}'
        try:
            actual_data = json.loads(actual_str) if actual_str else {}
        except json.JSONDecodeError:
            actual_data = {}
        
        # Accumulate time spent (in case task was paused and resumed multiple times)
        existing_time = actual_data.get('time_spent_before_pause', 0.0)
        if not isinstance(existing_time, (int, float)):
            try:
                existing_time = float(existing_time)
            except (ValueError, TypeError):
                existing_time = 0.0
        total_time_spent = existing_time + time_spent_before_pause
        actual_data['time_spent_before_pause'] = total_time_spent
        
        # Store completion percentage (ensure it's between 0 and 100)
        if not isinstance(completion_percentage, (int, float)):
            try:
                completion_percentage = float(completion_percentage)
            except (ValueError, TypeError):
                completion_percentage = 0.0
        completion_percentage = max(0.0, min(100.0, float(completion_percentage)))
        actual_data['pause_completion_percentage'] = completion_percentage
        
        # Reset timing/status so task returns to initialized state
        self.df.at[idx, 'started_at'] = ''
        self.df.at[idx, 'status'] = 'initialized'
        self.df.at[idx, 'is_completed'] = 'False'
        self.df.at[idx, 'completed_at'] = ''
        self.df.at[idx, 'cancelled_at'] = ''
        self.df.at[idx, 'procrastination_score'] = ''
        self.df.at[idx, 'proactive_score'] = ''

        # Persist pause reason in actual payload
        if reason:
            actual_data['pause_reason'] = reason
        actual_data['paused'] = True
        self.df.at[idx, 'actual'] = json.dumps(actual_data)

        self._save()
    
    def _pause_instance_db(self, instance_id: str, reason: Optional[str] = None, completion_percentage: float = 0.0):
        """Database-specific pause_instance."""
        try:
            import json
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    raise ValueError(f"Instance {instance_id} not found")
                
                # Calculate elapsed time before resetting started_at
                time_spent_before_pause = 0.0
                if instance.started_at:
                    try:
                        now = datetime.now()
                        elapsed_seconds = (now - instance.started_at).total_seconds()
                        time_spent_before_pause = elapsed_seconds / 60.0  # Convert to minutes
                    except Exception as e:
                        print(f"[InstanceManager] Error calculating elapsed time on pause: {e}")
                
                # Get existing actual data to preserve time_spent_before_pause if resuming after multiple pauses
                actual_data = instance.actual or {}
                if not isinstance(actual_data, dict):
                    actual_data = {}
                
                # Accumulate time spent (in case task was paused and resumed multiple times)
                existing_time = actual_data.get('time_spent_before_pause', 0.0)
                if not isinstance(existing_time, (int, float)):
                    try:
                        existing_time = float(existing_time)
                    except (ValueError, TypeError):
                        existing_time = 0.0
                total_time_spent = existing_time + time_spent_before_pause
                actual_data['time_spent_before_pause'] = total_time_spent
                
                # Store completion percentage (ensure it's between 0 and 100)
                if not isinstance(completion_percentage, (int, float)):
                    try:
                        completion_percentage = float(completion_percentage)
                    except (ValueError, TypeError):
                        completion_percentage = 0.0
                completion_percentage = max(0.0, min(100.0, float(completion_percentage)))
                actual_data['pause_completion_percentage'] = completion_percentage
                
                # Reset timing/status so task returns to initialized state
                instance.started_at = None
                instance.status = 'initialized'
                instance.is_completed = False
                instance.completed_at = None
                instance.cancelled_at = None
                instance.procrastination_score = None
                instance.proactive_score = None
                
                # Persist pause reason in actual payload
                if reason:
                    actual_data['pause_reason'] = reason
                actual_data['paused'] = True
                instance.actual = actual_data
                
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in pause_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in pause_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._pause_instance_csv(instance_id, reason, completion_percentage)

    def list_active_instances(self):
        """List active task instances. Works with both CSV and database."""
        if self.use_db:
            return self._list_active_instances_db()
        else:
            return self._list_active_instances_csv()
    
    def get_instances_by_task_id(self, task_id: str, include_completed: bool = False):
        """Get all instances for a specific task_id. Works with both CSV and database."""
        if self.use_db:
            return self._get_instances_by_task_id_db(task_id, include_completed)
        else:
            return self._get_instances_by_task_id_csv(task_id, include_completed)
    
    def _get_instances_by_task_id_csv(self, task_id: str, include_completed: bool = False):
        """CSV-specific get_instances_by_task_id."""
        self._reload()
        df = self.df[self.df['task_id'] == task_id]
        if not include_completed:
            df = df[df['is_completed'] != 'True']
        return df.to_dict(orient='records')
    
    def _get_instances_by_task_id_db(self, task_id: str, include_completed: bool = False):
        """Database-specific get_instances_by_task_id."""
        try:
            with self.db_session() as session:
                query = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id
                )
                if not include_completed:
                    query = query.filter(self.TaskInstance.is_completed == False)
                instances = query.all()
                return [instance.to_dict() for instance in instances]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_instances_by_task_id and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_instances_by_task_id: {e}, falling back to CSV")
            self.use_db = False
            return self._get_instances_by_task_id_csv(task_id, include_completed)
    
    def _list_active_instances_csv(self):
        """CSV-specific list_active_instances."""
        self._reload()
        status_series = self.df['status'].str.lower()
        df = self.df[
            (self.df['is_completed'] != 'True') &
            (self.df['is_deleted'] != 'True') &
            (~status_series.isin(['completed', 'cancelled']))
        ]
        return df.to_dict(orient='records')
    
    def _list_active_instances_db(self):
        """Database-specific list_active_instances."""
        try:
            with self.db_session() as session:
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.is_completed == False,
                    self.TaskInstance.is_deleted == False,
                    ~self.TaskInstance.status.in_(['completed', 'cancelled'])
                ).all()
                return [instance.to_dict() for instance in instances]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in list_active_instances and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in list_active_instances: {e}, falling back to CSV")
            self.use_db = False
            return self._list_active_instances_csv()

    def list_cancelled_instances(self):
        """List all cancelled task instances. Works with both CSV and database."""
        if self.use_db:
            return self._list_cancelled_instances_db()
        else:
            return self._list_cancelled_instances_csv()
    
    def _list_cancelled_instances_csv(self):
        """CSV-specific list_cancelled_instances."""
        self._reload()
        status_series = self.df['status'].str.lower()
        df = self.df[
            (status_series == 'cancelled') & (self.df['is_deleted'] != 'True')
        ]
        # Sort by cancelled_at descending (most recent first)
        if 'cancelled_at' in df.columns:
            df = df.sort_values('cancelled_at', ascending=False, na_position='last')
        return df.to_dict(orient='records')
    
    def _list_cancelled_instances_db(self):
        """Database-specific list_cancelled_instances."""
        try:
            with self.db_session() as session:
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.status == 'cancelled',
                    self.TaskInstance.is_deleted == False
                ).order_by(self.TaskInstance.cancelled_at.desc()).all()
                return [instance.to_dict() for instance in instances]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in list_cancelled_instances and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in list_cancelled_instances: {e}, falling back to CSV")
            self.use_db = False
            return self._list_cancelled_instances_csv()

    def get_instance(self, instance_id):
        """Get a task instance by ID. Works with both CSV and database."""
        if self.use_db:
            return self._get_instance_db(instance_id)
        else:
            return self._get_instance_csv(instance_id)
    
    def _get_instance_csv(self, instance_id):
        """CSV-specific get_instance."""
        self._reload()
        rows = self.df[self.df['instance_id'] == instance_id]
        if rows.empty:
            return None
        row = rows.iloc[0].to_dict()
        return row
    
    def _get_instance_db(self, instance_id):
        """Database-specific get_instance."""
        try:
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                return instance.to_dict() if instance else None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._get_instance_csv(instance_id)

    def start_instance(self, instance_id):
        """Start a task instance. Works with both CSV and database."""
        if self.use_db:
            return self._start_instance_db(instance_id)
        else:
            return self._start_instance_csv(instance_id)
    
    def _start_instance_csv(self, instance_id):
        """CSV-specific start_instance."""
        self._reload()
        idx = self.df.index[self.df['instance_id']==instance_id][0]
        self.df.at[idx,'started_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()
    
    def _start_instance_db(self, instance_id):
        """Database-specific start_instance."""
        try:
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    raise ValueError(f"Instance {instance_id} not found")
                instance.started_at = datetime.now()
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in start_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in start_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._start_instance_csv(instance_id)

    def complete_instance(self, instance_id, actual: dict):
        """Complete a task instance. Works with both CSV and database."""
        if self.use_db:
            return self._complete_instance_db(instance_id, actual)
        else:
            return self._complete_instance_csv(instance_id, actual)
    
    def _complete_instance_csv(self, instance_id, actual: dict):
        """CSV-specific complete_instance."""
        import json, math
        self._reload()
        idx = self.df.index[self.df['instance_id']==instance_id][0]
        # set actual JSON
        self.df.at[idx,'actual'] = json.dumps(actual)
        completed_at = datetime.now()
        self.df.at[idx,'completed_at'] = completed_at.strftime("%Y-%m-%d %H:%M")
        self.df.at[idx,'is_completed'] = 'True'
        self.df.at[idx,'status'] = 'completed'
        self.df.at[idx,'cancelled_at'] = ''
        
        # Calculate duration and delay
        try:
            initialized_at_str = self.df.at[idx,'initialized_at']
            started_at_str = self.df.at[idx,'started_at']
            initialized_at = pd.to_datetime(initialized_at_str) if initialized_at_str else None
            started_at = pd.to_datetime(started_at_str) if started_at_str else None
            
            # Get duration from actual dict, or calculate from start time
            duration_minutes = actual.get('time_actual_minutes')
            if duration_minutes is None or duration_minutes == '':
                # If start button was used, calculate duration from start to completion
                if started_at:
                    current_session_minutes = (completed_at - started_at).total_seconds() / 60.0
                    # Add time spent before pause (if task was paused and resumed)
                    time_spent_before_pause = actual.get('time_spent_before_pause', 0.0)
                    if not isinstance(time_spent_before_pause, (int, float)):
                        try:
                            time_spent_before_pause = float(time_spent_before_pause)
                        except (ValueError, TypeError):
                            time_spent_before_pause = 0.0
                    duration_minutes = current_session_minutes + time_spent_before_pause
                else:
                    # Check if there's time_spent_before_pause even if not currently started
                    time_spent_before_pause = actual.get('time_spent_before_pause', 0.0)
                    if not isinstance(time_spent_before_pause, (int, float)):
                        try:
                            time_spent_before_pause = float(time_spent_before_pause)
                        except (ValueError, TypeError):
                            time_spent_before_pause = 0.0
                    
                    if time_spent_before_pause > 0:
                        duration_minutes = time_spent_before_pause
                    else:
                        # Default to expected duration
                        predicted = json.loads(self.df.at[idx,'predicted'] or "{}")
                        duration_minutes = float(predicted.get('time_estimate_minutes') or predicted.get('estimate') or 0)
            
            # Store duration
            if duration_minutes is not None and duration_minutes != '':
                self.df.at[idx, 'duration_minutes'] = str(duration_minutes)
                # Also update in actual dict if not already set
                if 'time_actual_minutes' not in actual or actual.get('time_actual_minutes') == '':
                    actual['time_actual_minutes'] = duration_minutes
                    self.df.at[idx,'actual'] = json.dumps(actual)
            
            # Calculate delay: time from initialization to start (if started) or to completion minus duration (if not started)
            if initialized_at:
                if started_at:
                    # Delay = start time - initialization time
                    delay_minutes = (started_at - initialized_at).total_seconds() / 60.0
                else:
                    # Delay = completion time - duration - initialization time
                    if duration_minutes:
                        delay_minutes = (completed_at - initialized_at).total_seconds() / 60.0 - float(duration_minutes)
                    else:
                        delay_minutes = (completed_at - initialized_at).total_seconds() / 60.0
                self.df.at[idx, 'delay_minutes'] = str(round(delay_minutes, 2))
        except Exception as e:
            print(f"[InstanceManager] Error calculating duration/delay: {e}")
        
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
    
    def _complete_instance_db(self, instance_id, actual: dict):
        """Database-specific complete_instance."""
        try:
            import json
            import math
            
            completed_at = datetime.now()
            
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    raise ValueError(f"Instance {instance_id} not found")
                
                # Set actual JSON
                instance.actual = actual or {}
                instance.completed_at = completed_at
                instance.is_completed = True
                instance.status = 'completed'
                instance.cancelled_at = None
                
                # Calculate duration and delay
                try:
                    initialized_at = instance.initialized_at
                    started_at = instance.started_at
                    
                    # Get duration from actual dict, or calculate from start time
                    duration_minutes = actual.get('time_actual_minutes') if actual else None
                    if duration_minutes is None or duration_minutes == '':
                        # If start button was used, calculate duration from start to completion
                        if started_at:
                            current_session_minutes = (completed_at - started_at).total_seconds() / 60.0
                            # Add time spent before pause (if task was paused and resumed)
                            time_spent_before_pause = actual.get('time_spent_before_pause', 0.0) if actual else 0.0
                            if not isinstance(time_spent_before_pause, (int, float)):
                                try:
                                    time_spent_before_pause = float(time_spent_before_pause)
                                except (ValueError, TypeError):
                                    time_spent_before_pause = 0.0
                            duration_minutes = current_session_minutes + time_spent_before_pause
                        else:
                            # Check if there's time_spent_before_pause even if not currently started
                            time_spent_before_pause = actual.get('time_spent_before_pause', 0.0) if actual else 0.0
                            if not isinstance(time_spent_before_pause, (int, float)):
                                try:
                                    time_spent_before_pause = float(time_spent_before_pause)
                                except (ValueError, TypeError):
                                    time_spent_before_pause = 0.0
                            
                            if time_spent_before_pause > 0:
                                duration_minutes = time_spent_before_pause
                            else:
                                # Default to expected duration
                                predicted = instance.predicted or {}
                                duration_minutes = float(predicted.get('time_estimate_minutes') or predicted.get('estimate') or 0)
                    
                    # Store duration
                    if duration_minutes is not None and duration_minutes != '':
                        instance.duration_minutes = float(duration_minutes)
                        # Also update in actual dict if not already set
                        if actual and ('time_actual_minutes' not in actual or actual.get('time_actual_minutes') == ''):
                            actual['time_actual_minutes'] = duration_minutes
                            instance.actual = actual
                    
                    # Calculate delay: time from initialization to start (if started) or to completion minus duration (if not started)
                    if initialized_at:
                        if started_at:
                            # Delay = start time - initialization time
                            delay_minutes = (started_at - initialized_at).total_seconds() / 60.0
                        else:
                            # Delay = completion time - duration - initialization time
                            if duration_minutes:
                                delay_minutes = (completed_at - initialized_at).total_seconds() / 60.0 - float(duration_minutes)
                            else:
                                delay_minutes = (completed_at - initialized_at).total_seconds() / 60.0
                        instance.delay_minutes = round(delay_minutes, 2)
                except Exception as e:
                    print(f"[InstanceManager] Error calculating duration/delay: {e}")
                
                # Compute simple procrastination/proactive metrics
                try:
                    created = instance.created_at
                    started = instance.started_at if instance.started_at else (instance.initialized_at if instance.initialized_at else created)
                    predicted = instance.predicted or {}
                    estimate = float(predicted.get('time_estimate_minutes') or predicted.get('estimate') or 0) or 1.0
                    delay = (started - created).total_seconds() / 60.0
                    procrast = delay / max(estimate, 1.0)
                    proactive = max(0.0, 1.0 - (delay / max(estimate*2.0,1.0)))
                    instance.procrastination_score = round(min(procrast, 10.0), 3)
                    instance.proactive_score = round(min(max(proactive*10.0,0.0), 10.0), 3)
                except Exception as e:
                    print(f"[InstanceManager] Error calculating procrastination/proactive scores: {e}")
                    instance.procrastination_score = None
                    instance.proactive_score = None
                
                # Extract attributes from payload
                self._update_attributes_from_payload_db(instance, actual or {})
                
                # Calculate and store emotional factors (serendipity and disappointment)
                self._calculate_and_store_factors_db(instance)
                
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in complete_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in complete_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._complete_instance_csv(instance_id, actual)

    def cancel_instance(self, instance_id, actual: dict):
        """Cancel a task instance. Works with both CSV and database."""
        if self.use_db:
            return self._cancel_instance_db(instance_id, actual)
        else:
            return self._cancel_instance_csv(instance_id, actual)
    
    def _cancel_instance_csv(self, instance_id, actual: dict):
        """CSV-specific cancel_instance."""
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
    
    def _cancel_instance_db(self, instance_id, actual: dict):
        """Database-specific cancel_instance."""
        try:
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    raise ValueError(f"Instance {instance_id} not found")
                
                instance.actual = actual or {}
                instance.cancelled_at = datetime.now()
                instance.status = 'cancelled'
                instance.is_completed = True
                instance.completed_at = None
                instance.procrastination_score = None
                instance.proactive_score = None
                
                # Extract attributes from payload
                self._update_attributes_from_payload_db(instance, actual or {})
                
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in cancel_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in cancel_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._cancel_instance_csv(instance_id, actual)

    def update_cancelled_instance(self, instance_id, cancellation_data: dict):
        """Update cancellation data for an already-cancelled instance. Works with both CSV and database."""
        if self.use_db:
            return self._update_cancelled_instance_db(instance_id, cancellation_data)
        else:
            return self._update_cancelled_instance_csv(instance_id, cancellation_data)
    
    def _update_cancelled_instance_csv(self, instance_id, cancellation_data: dict):
        """CSV-specific update_cancelled_instance."""
        import json
        self._reload()
        matches = self.df.index[self.df['instance_id'] == instance_id]
        if len(matches) == 0:
            raise ValueError(f"Instance {instance_id} not found")
        idx = matches[0]
        
        # Verify it's cancelled
        if self.df.at[idx, 'status'] != 'cancelled':
            raise ValueError(f"Instance {instance_id} is not cancelled")
        
        # Get existing actual data and merge with new cancellation data
        existing_actual_str = self.df.at[idx, 'actual'] or '{}'
        try:
            existing_actual = json.loads(existing_actual_str) if existing_actual_str else {}
        except:
            existing_actual = {}
        
        # Merge cancellation data (preserve cancelled flag)
        updated_actual = {**existing_actual, **cancellation_data}
        updated_actual['cancelled'] = True
        
        self.df.at[idx, 'actual'] = json.dumps(updated_actual)
        self._save()
    
    def _update_cancelled_instance_db(self, instance_id, cancellation_data: dict):
        """Database-specific update_cancelled_instance."""
        try:
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    raise ValueError(f"Instance {instance_id} not found")
                
                if instance.status != 'cancelled':
                    raise ValueError(f"Instance {instance_id} is not cancelled")
                
                # Merge cancellation data with existing actual data
                existing_actual = instance.actual or {}
                updated_actual = {**existing_actual, **cancellation_data}
                updated_actual['cancelled'] = True
                
                instance.actual = updated_actual
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in update_cancelled_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in update_cancelled_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._update_cancelled_instance_csv(instance_id, cancellation_data)

    def add_prediction_to_instance(self, instance_id, predicted: dict):
        """Add prediction data to an instance. Works with both CSV and database."""
        if self.use_db:
            return self._add_prediction_to_instance_db(instance_id, predicted)
        else:
            return self._add_prediction_to_instance_csv(instance_id, predicted)
    
    def _add_prediction_to_instance_csv(self, instance_id, predicted: dict):
        """CSV-specific add_prediction_to_instance."""
        import json
        self._reload()
        idx = self.df.index[self.df['instance_id'] == instance_id][0]
        self.df.at[idx,'predicted'] = json.dumps(predicted)
        # Always set initialized_at when prediction is added (initialization happens)
        if not self.df.at[idx,'initialized_at'] or self.df.at[idx,'initialized_at'] == '':
            self.df.at[idx,'initialized_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Extract predicted values to columns (only if columns are empty)
        self._update_attributes_from_payload(idx, predicted)
        self._save()
    
    def _add_prediction_to_instance_db(self, instance_id, predicted: dict):
        """Database-specific add_prediction_to_instance."""
        try:
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    raise ValueError(f"Instance {instance_id} not found")
                
                # Update predicted JSON
                instance.predicted = predicted or {}
                
                # Always set initialized_at when prediction is added (initialization happens)
                if not instance.initialized_at:
                    instance.initialized_at = datetime.now()
                
                # Extract predicted values to columns (only if columns are empty)
                self._update_attributes_from_payload_db(instance, predicted)
                
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in add_prediction_to_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in add_prediction_to_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._add_prediction_to_instance_csv(instance_id, predicted)

    def ensure_instance_for_task(self, task_id, task_name, predicted: dict = None):
        # create an instance and return id
        return self.create_instance(task_id, task_name, task_version=1, predicted=predicted)



    def delete_instance(self, instance_id):
        """Delete a task instance. Works with both CSV and database."""
        if self.use_db:
            return self._delete_instance_db(instance_id)
        else:
            return self._delete_instance_csv(instance_id)
    
    def _delete_instance_csv(self, instance_id):
        """CSV-specific delete_instance."""
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
    
    def _delete_instance_db(self, instance_id):
        """Database-specific delete_instance."""
        try:
            print(f"[InstanceManager] delete_instance called with: {instance_id}")
            with self.db_session() as session:
                instance = session.query(self.TaskInstance).filter(
                    self.TaskInstance.instance_id == instance_id
                ).first()
                if not instance:
                    print("[InstanceManager] No matching instance to delete.")
                    return False
                
                session.delete(instance)
                session.commit()
                print("[InstanceManager] Instance deleted.")
                return True
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in delete_instance and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in delete_instance: {e}, falling back to CSV")
            self.use_db = False
            return self._delete_instance_csv(instance_id)

    def _update_attributes_from_payload(self, idx, payload: dict):
        """Persist wellbeing attributes if caller provided them (CSV version).
        Maps both direct keys and common aliases from JSON payloads."""
        if not isinstance(payload, dict):
            return
        
        # Mapping from payload keys to CSV column names
        # Handles both direct matches and common aliases
        # IMPORTANT: CSV columns should only contain ACTUAL values (from completion), not expected values
        # Expected values should only be stored in the 'predicted' JSON column
        attribute_mappings = {
            # Direct mappings
            'duration_minutes': ['duration_minutes', 'time_actual_minutes', 'actual_time'],
            # relief_score should ONLY come from actual_relief (from completion), never from expected_relief
            'relief_score': ['relief_score', 'actual_relief'],
            # New cognitive load components (per Cognitive Load Theory)
            # CSV columns should only contain ACTUAL values
            'mental_energy_needed': ['mental_energy_needed', 'actual_mental_energy'],
            'task_difficulty': ['task_difficulty', 'actual_difficulty'],
            # Backward compatibility: map old cognitive_load to both new components
            # (will be handled in analytics.py for data loading)
            'emotional_load': ['emotional_load', 'actual_emotional'],
            'environmental_effect': ['environmental_effect', 'environmental_fit'],
            'skills_improved': ['skills_improved'],
            'behavioral_score': ['behavioral_score'],
            'net_relief': ['net_relief'],
        }
        
        # Also handle physical load if present
        if 'actual_physical' in payload or 'expected_physical_load' in payload:
            # Store in a note or additional field if needed
            pass
        
        # Extract values using mappings
        for csv_column, possible_keys in attribute_mappings.items():
            value = None
            # Try each possible key in order
            for key in possible_keys:
                if key in payload:
                    val = payload[key]
                    # Allow 0 as a valid numeric value - check if it's a number (including 0) or non-empty
                    if val is not None:
                        # For numbers, 0 is valid; for strings, must be non-empty
                        if isinstance(val, (int, float)) or (val != ''):
                            value = val
                            break
            
            # Only update if we found a value and the column is currently empty
            # Explicitly allow 0 as a valid numeric value
            if value is not None:
                # For numbers, 0 is valid; for strings, must be non-empty
                if isinstance(value, (int, float)) or (value != ''):
                    current_value = self.df.at[idx, csv_column]
                    if current_value == '' or pd.isna(current_value):
                        self.df.at[idx, csv_column] = value
    
    def _update_attributes_from_payload_db(self, instance, payload: dict):
        """Persist wellbeing attributes if caller provided them (Database version).
        Maps both direct keys and common aliases from JSON payloads."""
        if not isinstance(payload, dict):
            return
        
        # Mapping from payload keys to database column names
        attribute_mappings = {
            'duration_minutes': ['duration_minutes', 'time_actual_minutes', 'actual_time'],
            'relief_score': ['relief_score', 'actual_relief'],
            'mental_energy_needed': ['mental_energy_needed', 'actual_mental_energy'],
            'task_difficulty': ['task_difficulty', 'actual_difficulty'],
            'emotional_load': ['emotional_load', 'actual_emotional'],
            'environmental_effect': ['environmental_effect', 'environmental_fit'],
            'skills_improved': ['skills_improved'],
            'behavioral_score': ['behavioral_score'],
            'net_relief': ['net_relief'],
        }
        
        # Extract values using mappings
        for db_column, possible_keys in attribute_mappings.items():
            value = None
            # Try each possible key in order
            for key in possible_keys:
                if key in payload:
                    val = payload[key]
                    if val is not None:
                        if isinstance(val, (int, float)) or (val != ''):
                            value = val
                            break
            
            # Only update if we found a value and the column is currently empty/None
            if value is not None:
                if isinstance(value, (int, float)) or (value != ''):
                    current_value = getattr(instance, db_column, None)
                    if current_value is None or (isinstance(current_value, str) and current_value.strip() == ''):
                        # Convert to appropriate type
                        if db_column == 'skills_improved':
                            # Keep as string
                            setattr(instance, db_column, str(value))
                        elif db_column in ['duration_minutes', 'delay_minutes', 'relief_score', 'cognitive_load',
                                          'mental_energy_needed', 'task_difficulty', 'emotional_load',
                                          'environmental_effect', 'behavioral_score', 'net_relief']:
                            # Convert to float
                            try:
                                setattr(instance, db_column, float(value))
                            except (ValueError, TypeError):
                                pass

    def _calculate_and_store_factors_db(self, instance):
        """Calculate and store serendipity_factor and disappointment_factor from expected/actual relief.
        
        Formula:
        - net_relief = actual_relief - expected_relief
        - serendipity_factor = max(0, net_relief)  # Positive net relief (pleasant surprise)
        - disappointment_factor = max(0, -net_relief)  # Negative net relief (disappointment)
        
        Also stores net_relief if not already set.
        """
        try:
            # Get expected and actual relief from JSON
            predicted = instance.predicted or {}
            actual = instance.actual or {}
            
            expected_relief = predicted.get('expected_relief')
            actual_relief = actual.get('actual_relief')
            
            # Normalize relief values (scale 0-10 to 0-100 if needed)
            def normalize_relief(val):
                if val is None:
                    return None
                try:
                    val = float(val)
                    # If value is 0-10, scale to 0-100
                    if 0 <= val <= 10:
                        return val * 10.0
                    return val
                except (ValueError, TypeError):
                    return None
            
            expected_relief = normalize_relief(expected_relief)
            actual_relief = normalize_relief(actual_relief)
            
            # If we have both values, calculate factors
            if expected_relief is not None and actual_relief is not None:
                net_relief = actual_relief - expected_relief
                
                # Store net_relief if not already set
                if instance.net_relief is None:
                    instance.net_relief = net_relief
                
                # Calculate factors
                instance.serendipity_factor = max(0.0, net_relief)  # Positive net relief
                instance.disappointment_factor = max(0.0, -net_relief)  # Negative net relief (as positive value)
            else:
                # If we don't have both values, set factors to None
                instance.serendipity_factor = None
                instance.disappointment_factor = None
        except Exception as e:
            print(f"[InstanceManager] Error calculating factors: {e}")
            # Set to None on error
            instance.serendipity_factor = None
            instance.disappointment_factor = None

    def list_recent_completed(self, limit=20):
        """List recently completed instances. Works with both CSV and database."""
        if self.use_db:
            return self._list_recent_completed_db(limit)
        else:
            return self._list_recent_completed_csv(limit)
    
    def _list_recent_completed_csv(self, limit=20):
        """CSV-specific list_recent_completed."""
        print(f"[InstanceManager] list_recent_completed called (limit={limit})")
        self._reload()
        df = self.df[self.df['completed_at'].astype(str).str.strip() != '']
        if df.empty:
            return []
        df = df.sort_values("completed_at", ascending=False)
        return df.head(limit).to_dict(orient="records")
    
    def _list_recent_completed_db(self, limit=20):
        """Database-specific list_recent_completed."""
        try:
            print(f"[InstanceManager] list_recent_completed called (limit={limit})")
            with self.db_session() as session:
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.completed_at.isnot(None)
                ).order_by(
                    self.TaskInstance.completed_at.desc()
                ).limit(limit).all()
                return [instance.to_dict() for instance in instances]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in list_recent_completed and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in list_recent_completed: {e}, falling back to CSV")
            self.use_db = False
            return self._list_recent_completed_csv(limit)
    
    def backfill_attributes_from_json(self):
        """Backfill empty attribute columns from JSON data in predicted/actual columns.
        This is a migration method to fix existing data. Works with both CSV and database."""
        if self.use_db:
            return self._backfill_attributes_from_json_db()
        else:
            return self._backfill_attributes_from_json_csv()
    
    def _backfill_attributes_from_json_csv(self):
        """CSV-specific backfill_attributes_from_json."""
        import json
        self._reload()
        updated_count = 0
        
        # Helper to check if value is empty
        def is_empty(val):
            if val is None:
                return True
            if isinstance(val, float) and pd.isna(val):
                return True
            if str(val).strip() == '':
                return True
            return False
        
        for idx in self.df.index:
            row_updated = False
            
            # Try to extract from actual JSON first (most accurate)
            actual_str = str(self.df.at[idx, 'actual'] or '{}').strip()
            if actual_str and actual_str != '{}':
                try:
                    actual_dict = json.loads(actual_str)
                    if isinstance(actual_dict, dict) and actual_dict:
                        # Update attributes from actual data only
                        # relief_score should ONLY come from actual_relief, never from expected_relief
                        mappings = {
                            'duration_minutes': ['time_actual_minutes', 'actual_time', 'duration_minutes'],
                            'relief_score': ['actual_relief', 'relief_score'],  # Only actual values
                            'cognitive_load': ['actual_cognitive', 'cognitive_load'],
                            'emotional_load': ['actual_emotional', 'emotional_load'],
                        }
                        for csv_column, possible_keys in mappings.items():
                            current_value = self.df.at[idx, csv_column]
                            if is_empty(current_value):
                                for key in possible_keys:
                                    if key in actual_dict:
                                        val = actual_dict[key]
                                        if not is_empty(val):
                                            self.df.at[idx, csv_column] = str(val)
                                            row_updated = True
                                            break
                except (json.JSONDecodeError, Exception) as e:
                    pass
            
            # If still empty, try predicted JSON
            predicted_str = str(self.df.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    predicted_dict = json.loads(predicted_str)
                    if isinstance(predicted_dict, dict) and predicted_dict:
                        # IMPORTANT: Do NOT write expected values to CSV columns that should contain actual values
                        # expected_relief should stay in predicted JSON only, not in relief_score column
                        # Only backfill if the column is empty AND we don't have actual data
                        mappings = {
                            'duration_minutes': ['time_estimate_minutes', 'estimate', 'duration_minutes'],
                            # DO NOT map expected_relief to relief_score - relief_score is for actual values only
                            # 'relief_score': ['expected_relief', 'relief_score'],  # REMOVED - expected should not overwrite actual
                            'cognitive_load': ['expected_cognitive_load', 'expected_cognitive', 'cognitive_load'],
                            'emotional_load': ['expected_emotional_load', 'expected_emotional', 'emotional_load'],
                        }
                        for csv_column, possible_keys in mappings.items():
                            current_value = self.df.at[idx, csv_column]
                            if is_empty(current_value):
                                for key in possible_keys:
                                    if key in predicted_dict:
                                        val = predicted_dict[key]
                                        if not is_empty(val):
                                            self.df.at[idx, csv_column] = str(val)
                                            row_updated = True
                                            break
                except (json.JSONDecodeError, Exception) as e:
                    pass
            
            if row_updated:
                updated_count += 1
        
        if updated_count > 0:
            self._save()
            print(f"[InstanceManager] Backfilled {updated_count} instances with missing attributes")
        else:
            print(f"[InstanceManager] No instances needed backfilling (all attributes already populated or no JSON data found)")
        
        return updated_count
    
    def _backfill_attributes_from_json_db(self):
        """Database-specific backfill_attributes_from_json."""
        try:
            import json
            updated_count = 0
            
            # Helper to check if value is empty
            def is_empty(val):
                if val is None:
                    return True
                if isinstance(val, str) and val.strip() == '':
                    return True
                return False
            
            with self.db_session() as session:
                # Get all instances
                instances = session.query(self.TaskInstance).all()
                
                for instance in instances:
                    row_updated = False
                    
                    # Try to extract from actual JSON first (most accurate)
                    actual = instance.actual or {}
                    if isinstance(actual, dict) and actual:
                        # Update attributes from actual data only
                        # relief_score should ONLY come from actual_relief, never from expected_relief
                        mappings = {
                            'duration_minutes': ['time_actual_minutes', 'actual_time', 'duration_minutes'],
                            'relief_score': ['actual_relief', 'relief_score'],  # Only actual values
                            'cognitive_load': ['actual_cognitive', 'cognitive_load'],
                            'emotional_load': ['actual_emotional', 'emotional_load'],
                        }
                        for db_column, possible_keys in mappings.items():
                            current_value = getattr(instance, db_column, None)
                            if is_empty(current_value):
                                for key in possible_keys:
                                    if key in actual:
                                        val = actual[key]
                                        if not is_empty(val):
                                            # Convert to appropriate type
                                            try:
                                                if db_column in ['duration_minutes', 'relief_score', 'cognitive_load', 'emotional_load']:
                                                    setattr(instance, db_column, float(val))
                                                else:
                                                    setattr(instance, db_column, val)
                                                row_updated = True
                                                break
                                            except (ValueError, TypeError):
                                                pass
                    
                    # If still empty, try predicted JSON
                    predicted = instance.predicted or {}
                    if isinstance(predicted, dict) and predicted:
                        # IMPORTANT: Do NOT write expected values to database columns that should contain actual values
                        # expected_relief should stay in predicted JSON only, not in relief_score column
                        # Only backfill if the column is empty AND we don't have actual data
                        mappings = {
                            'duration_minutes': ['time_estimate_minutes', 'estimate', 'duration_minutes'],
                            # DO NOT map expected_relief to relief_score - relief_score is for actual values only
                            'cognitive_load': ['expected_cognitive_load', 'expected_cognitive', 'cognitive_load'],
                            'emotional_load': ['expected_emotional_load', 'expected_emotional', 'emotional_load'],
                        }
                        for db_column, possible_keys in mappings.items():
                            current_value = getattr(instance, db_column, None)
                            if is_empty(current_value):
                                for key in possible_keys:
                                    if key in predicted:
                                        val = predicted[key]
                                        if not is_empty(val):
                                            # Convert to appropriate type
                                            try:
                                                if db_column in ['duration_minutes', 'cognitive_load', 'emotional_load']:
                                                    setattr(instance, db_column, float(val))
                                                else:
                                                    setattr(instance, db_column, val)
                                                row_updated = True
                                                break
                                            except (ValueError, TypeError):
                                                pass
                    
                    if row_updated:
                        updated_count += 1
                
                if updated_count > 0:
                    session.commit()
                    print(f"[InstanceManager] Backfilled {updated_count} instances with missing attributes")
                else:
                    print(f"[InstanceManager] No instances needed backfilling (all attributes already populated or no JSON data found)")
                
                return updated_count
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in backfill_attributes_from_json and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in backfill_attributes_from_json: {e}, falling back to CSV")
            self.use_db = False
            return self._backfill_attributes_from_json_csv()

    def get_previous_task_averages(self, task_id: str) -> dict:
        """Get average values from previous initialized instances of the same task.
        Returns a dict with keys: expected_relief, expected_mental_energy, expected_difficulty,
        expected_physical_load, expected_emotional_load, motivation, expected_aversion.
        Values are scaled to 0-100 range."""
        if self.use_db:
            return self._get_previous_task_averages_db(task_id)
        else:
            return self._get_previous_task_averages_csv(task_id)
    
    def _get_previous_task_averages_csv(self, task_id: str) -> dict:
        """CSV-specific get_previous_task_averages."""
        import json
        self._reload()
        
        # Get all initialized instances for this task (completed or not)
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return {}
        
        # Extract values from predicted JSON
        relief_values = []
        mental_energy_values = []
        difficulty_values = []
        cognitive_values = []  # Keep for backward compatibility
        physical_values = []
        emotional_values = []
        motivation_values = []
        aversion_values = []
        
        for idx in initialized.index:
            predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        # Extract values, handling both 0-10 and 0-100 scales
                        for key, value_list in [
                            ('expected_relief', relief_values),
                            ('expected_mental_energy', mental_energy_values),
                            ('expected_difficulty', difficulty_values),
                            ('expected_cognitive_load', cognitive_values),  # Backward compatibility
                            ('expected_physical_load', physical_values),
                            ('expected_emotional_load', emotional_values),
                            ('motivation', motivation_values),
                            ('expected_aversion', aversion_values)
                        ]:
                            val = pred_dict.get(key)
                            if val is not None:
                                try:
                                    num_val = float(val)
                                    # Scale from 0-10 to 0-100 if value is <= 10
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    value_list.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                        
                        # Backward compatibility: if old cognitive_load exists but new fields don't, use it for both
                        if 'expected_mental_energy' not in pred_dict and 'expected_difficulty' not in pred_dict:
                            old_cog = pred_dict.get('expected_cognitive_load')
                            if old_cog is not None:
                                try:
                                    num_val = float(old_cog)
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    # Use old cognitive_load for both new fields
                                    mental_energy_values.append(num_val)
                                    difficulty_values.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        result = {}
        if relief_values:
            result['expected_relief'] = round(sum(relief_values) / len(relief_values))
        if mental_energy_values:
            result['expected_mental_energy'] = round(sum(mental_energy_values) / len(mental_energy_values))
        if difficulty_values:
            result['expected_difficulty'] = round(sum(difficulty_values) / len(difficulty_values))
        if cognitive_values:
            result['expected_cognitive_load'] = round(sum(cognitive_values) / len(cognitive_values))  # Backward compatibility
        if physical_values:
            result['expected_physical_load'] = round(sum(physical_values) / len(physical_values))
        if emotional_values:
            result['expected_emotional_load'] = round(sum(emotional_values) / len(emotional_values))
        if motivation_values:
            result['motivation'] = round(sum(motivation_values) / len(motivation_values))
        if aversion_values:
            result['expected_aversion'] = round(sum(aversion_values) / len(aversion_values))
        
        return result
    
    def _get_previous_task_averages_db(self, task_id: str) -> dict:
        """Database-specific get_previous_task_averages."""
        try:
            import json
            with self.db_session() as session:
                # Get all initialized instances for this task (completed or not)
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id,
                    self.TaskInstance.initialized_at.isnot(None)
                ).all()
                
                if not instances:
                    return {}
                
                # Extract values from predicted JSON
                relief_values = []
                mental_energy_values = []
                difficulty_values = []
                cognitive_values = []  # Keep for backward compatibility
                physical_values = []
                emotional_values = []
                motivation_values = []
                aversion_values = []
                
                for instance in instances:
                    predicted = instance.predicted or {}
                    if isinstance(predicted, dict):
                        # Extract values, handling both 0-10 and 0-100 scales
                        for key, value_list in [
                            ('expected_relief', relief_values),
                            ('expected_mental_energy', mental_energy_values),
                            ('expected_difficulty', difficulty_values),
                            ('expected_cognitive_load', cognitive_values),  # Backward compatibility
                            ('expected_physical_load', physical_values),
                            ('expected_emotional_load', emotional_values),
                            ('motivation', motivation_values),
                            ('expected_aversion', aversion_values)
                        ]:
                            val = predicted.get(key)
                            if val is not None:
                                try:
                                    num_val = float(val)
                                    # Scale from 0-10 to 0-100 if value is <= 10
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    value_list.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                        
                        # Backward compatibility: if old cognitive_load exists but new fields don't, use it for both
                        if 'expected_mental_energy' not in predicted and 'expected_difficulty' not in predicted:
                            old_cog = predicted.get('expected_cognitive_load')
                            if old_cog is not None:
                                try:
                                    num_val = float(old_cog)
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    # Use old cognitive_load for both new fields
                                    mental_energy_values.append(num_val)
                                    difficulty_values.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                
                result = {}
                if relief_values:
                    result['expected_relief'] = round(sum(relief_values) / len(relief_values))
                if mental_energy_values:
                    result['expected_mental_energy'] = round(sum(mental_energy_values) / len(mental_energy_values))
                if difficulty_values:
                    result['expected_difficulty'] = round(sum(difficulty_values) / len(difficulty_values))
                if cognitive_values:
                    result['expected_cognitive_load'] = round(sum(cognitive_values) / len(cognitive_values))  # Backward compatibility
                if physical_values:
                    result['expected_physical_load'] = round(sum(physical_values) / len(physical_values))
                if emotional_values:
                    result['expected_emotional_load'] = round(sum(emotional_values) / len(emotional_values))
                if motivation_values:
                    result['motivation'] = round(sum(motivation_values) / len(motivation_values))
                if aversion_values:
                    result['expected_aversion'] = round(sum(aversion_values) / len(aversion_values))
                
                return result
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_previous_task_averages and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_previous_task_averages: {e}, falling back to CSV")
            self.use_db = False
            return self._get_previous_task_averages_csv(task_id)

    def get_previous_actual_averages(self, task_id: str) -> dict:
        """Get average values from previous completed instances of the same task.
        Returns a dict with keys: actual_relief, actual_cognitive, 
        actual_emotional, actual_physical.
        Values are scaled to 0-100 range."""
        if self.use_db:
            return self._get_previous_actual_averages_db(task_id)
        else:
            return self._get_previous_actual_averages_csv(task_id)
    
    def _get_previous_actual_averages_csv(self, task_id: str) -> dict:
        """CSV-specific get_previous_actual_averages."""
        import json
        self._reload()
        
        # Get all completed instances for this task
        completed = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['completed_at'].astype(str).str.strip() != '')
        ].copy()
        
        if completed.empty:
            return {}
        
        # Extract values from actual JSON
        relief_values = []
        cognitive_values = []
        physical_values = []
        emotional_values = []
        
        for idx in completed.index:
            actual_str = str(completed.at[idx, 'actual'] or '{}').strip()
            if actual_str and actual_str != '{}':
                try:
                    actual_dict = json.loads(actual_str)
                    if isinstance(actual_dict, dict):
                        # Extract values, handling both 0-10 and 0-100 scales
                        for key, value_list in [
                            ('actual_relief', relief_values),
                            ('actual_cognitive', cognitive_values),
                            ('actual_physical', physical_values),
                            ('actual_emotional', emotional_values)
                        ]:
                            val = actual_dict.get(key)
                            if val is not None:
                                try:
                                    num_val = float(val)
                                    # Scale from 0-10 to 0-100 if value is <= 10
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    value_list.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        result = {}
        if relief_values:
            result['actual_relief'] = round(sum(relief_values) / len(relief_values))
        if cognitive_values:
            result['actual_cognitive'] = round(sum(cognitive_values) / len(cognitive_values))
        if physical_values:
            result['actual_physical'] = round(sum(physical_values) / len(physical_values))
        if emotional_values:
            result['actual_emotional'] = round(sum(emotional_values) / len(emotional_values))
        
        return result
    
    def _get_previous_actual_averages_db(self, task_id: str) -> dict:
        """Database-specific get_previous_actual_averages."""
        try:
            with self.db_session() as session:
                # Get all completed instances for this task
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id,
                    self.TaskInstance.completed_at.isnot(None)
                ).all()
                
                if not instances:
                    return {}
                
                # Extract values from actual JSON
                relief_values = []
                cognitive_values = []
                physical_values = []
                emotional_values = []
                
                for instance in instances:
                    actual = instance.actual or {}
                    if isinstance(actual, dict):
                        # Extract values, handling both 0-10 and 0-100 scales
                        for key, value_list in [
                            ('actual_relief', relief_values),
                            ('actual_cognitive', cognitive_values),
                            ('actual_physical', physical_values),
                            ('actual_emotional', emotional_values)
                        ]:
                            val = actual.get(key)
                            if val is not None:
                                try:
                                    num_val = float(val)
                                    # Scale from 0-10 to 0-100 if value is <= 10
                                    if num_val <= 10 and num_val >= 0:
                                        num_val = num_val * 10
                                    value_list.append(num_val)
                                except (ValueError, TypeError):
                                    pass
                
                result = {}
                if relief_values:
                    result['actual_relief'] = round(sum(relief_values) / len(relief_values))
                if cognitive_values:
                    result['actual_cognitive'] = round(sum(cognitive_values) / len(cognitive_values))
                if physical_values:
                    result['actual_physical'] = round(sum(physical_values) / len(physical_values))
                if emotional_values:
                    result['actual_emotional'] = round(sum(emotional_values) / len(emotional_values))
                
                return result
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_previous_actual_averages and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_previous_actual_averages: {e}, falling back to CSV")
            self.use_db = False
            return self._get_previous_actual_averages_csv(task_id)

    def get_initial_aversion(self, task_id: str) -> Optional[float]:
        """Get the initial aversion value for a task (from the first initialized instance).
        Returns None if this is the first time doing the task.
        Values are scaled to 0-100 range."""
        if self.use_db:
            return self._get_initial_aversion_db(task_id)
        else:
            return self._get_initial_aversion_csv(task_id)
    
    def _get_initial_aversion_csv(self, task_id: str) -> Optional[float]:
        """CSV-specific get_initial_aversion."""
        import json
        self._reload()
        
        # Get all initialized instances for this task, sorted by initialized_at
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return None
        
        # Sort by initialized_at to get the first one
        initialized['initialized_at_dt'] = pd.to_datetime(initialized['initialized_at'], errors='coerce')
        initialized = initialized.sort_values('initialized_at_dt')
        
        # Get the first instance's predicted data
        first_idx = initialized.index[0]
        predicted_str = str(initialized.at[first_idx, 'predicted'] or '{}').strip()
        if predicted_str and predicted_str != '{}':
            try:
                pred_dict = json.loads(predicted_str)
                if isinstance(pred_dict, dict):
                    initial_aversion = pred_dict.get('initial_aversion')
                    if initial_aversion is not None:
                        try:
                            num_val = float(initial_aversion)
                            # Scale from 0-10 to 0-100 if value is <= 10
                            if num_val <= 10 and num_val >= 0:
                                num_val = num_val * 10
                            return round(num_val)
                        except (ValueError, TypeError):
                            pass
            except (json.JSONDecodeError, Exception):
                pass
        
        return None
    
    def _get_initial_aversion_db(self, task_id: str) -> Optional[float]:
        """Database-specific get_initial_aversion."""
        try:
            import json
            with self.db_session() as session:
                # Get all initialized instances for this task, sorted by initialized_at
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id,
                    self.TaskInstance.initialized_at.isnot(None)
                ).order_by(self.TaskInstance.initialized_at.asc()).all()
                
                if not instances:
                    return None
                
                # Get the first instance's predicted data
                first_instance = instances[0]
                predicted = first_instance.predicted or {}
                if isinstance(predicted, dict):
                    initial_aversion = predicted.get('initial_aversion')
                    if initial_aversion is not None:
                        try:
                            num_val = float(initial_aversion)
                            # Scale from 0-10 to 0-100 if value is <= 10
                            if num_val <= 10 and num_val >= 0:
                                num_val = num_val * 10
                            return round(num_val)
                        except (ValueError, TypeError):
                            pass
            
            return None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_initial_aversion and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_initial_aversion: {e}, falling back to CSV")
            self.use_db = False
            return self._get_initial_aversion_csv(task_id)

    def has_completed_task(self, task_id: str) -> bool:
        """Check if this task has been completed at least once."""
        if self.use_db:
            return self._has_completed_task_db(task_id)
        else:
            return self._has_completed_task_csv(task_id)
    
    def _has_completed_task_csv(self, task_id: str) -> bool:
        """CSV-specific has_completed_task."""
        self._reload()
        if not task_id:
            return False
        
        # Filter to this task_id first
        task_instances = self.df[self.df['task_id'] == task_id]
        if task_instances.empty:
            return False
        
        # Check if any instance has is_completed == 'True' (case-insensitive)
        is_completed_check = task_instances['is_completed'].astype(str).str.strip().str.lower() == 'true'
        
        # Check if any instance has completed_at set
        completed_at_check = task_instances['completed_at'].astype(str).str.strip() != ''
        
        # Check if any instance has status == 'completed' (case-insensitive)
        status_check = task_instances['status'].astype(str).str.strip().str.lower() == 'completed'
        
        # Return True if any of these conditions are met
        has_completed = (is_completed_check | completed_at_check | status_check).any()
        
        return bool(has_completed)
    
    def _has_completed_task_db(self, task_id: str) -> bool:
        """Database-specific has_completed_task."""
        try:
            if not task_id:
                return False
            
            with self.db_session() as session:
                # Check if any instance has is_completed=True, completed_at set, or status='completed'
                count = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id
                ).filter(
                    (self.TaskInstance.is_completed == True) |
                    (self.TaskInstance.completed_at.isnot(None)) |
                    (self.TaskInstance.status == 'completed')
                ).count()
                
                return count > 0
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in has_completed_task and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in has_completed_task: {e}, falling back to CSV")
            self.use_db = False
            return self._has_completed_task_csv(task_id)

    def get_previous_aversion_average(self, task_id: str) -> Optional[float]:
        """Get average aversion from previous initialized instances of the same task.
        Returns None if no previous instances exist.
        Values are scaled to 0-100 range."""
        if self.use_db:
            return self._get_previous_aversion_average_db(task_id)
        else:
            return self._get_previous_aversion_average_csv(task_id)
    
    def _get_previous_aversion_average_csv(self, task_id: str) -> Optional[float]:
        """CSV-specific get_previous_aversion_average."""
        import json
        self._reload()
        
        # Get all initialized instances for this task (completed or not)
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return None
        
        aversion_values = []
        
        for idx in initialized.index:
            predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        val = pred_dict.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        if aversion_values:
            return round(sum(aversion_values) / len(aversion_values))
        return None
    
    def _get_previous_aversion_average_db(self, task_id: str) -> Optional[float]:
        """Database-specific get_previous_aversion_average."""
        try:
            with self.db_session() as session:
                # Get all initialized instances for this task (completed or not)
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id,
                    self.TaskInstance.initialized_at.isnot(None)
                ).all()
                
                if not instances:
                    return None
                
                aversion_values = []
                
                for instance in instances:
                    predicted = instance.predicted or {}
                    if isinstance(predicted, dict):
                        val = predicted.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                
                if aversion_values:
                    return round(sum(aversion_values) / len(aversion_values))
                return None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_previous_aversion_average and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_previous_aversion_average: {e}, falling back to CSV")
            self.use_db = False
            return self._get_previous_aversion_average_csv(task_id)

    def get_baseline_aversion_robust(self, task_id: str) -> Optional[float]:
        """Get robust baseline aversion using median (less sensitive to outliers).
        Returns None if no previous instances exist.
        Values are scaled to 0-100 range."""
        if self.use_db:
            return self._get_baseline_aversion_robust_db(task_id)
        else:
            return self._get_baseline_aversion_robust_csv(task_id)
    
    def _get_baseline_aversion_robust_csv(self, task_id: str) -> Optional[float]:
        """CSV-specific get_baseline_aversion_robust."""
        import json
        import numpy as np
        try:
            self._reload()
        except Exception as e:
            print(f"[InstanceManager] Error reloading in get_baseline_aversion_robust: {e}")
            # Continue with existing self.df or empty DataFrame
        
        # Get all initialized instances for this task (completed or not)
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return None
        
        aversion_values = []
        
        for idx in initialized.index:
            predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        val = pred_dict.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        if not aversion_values:
            return None
        
        # Use median for robust baseline (less sensitive to outliers)
        baseline = float(np.median(aversion_values))
        return round(baseline)
    
    def _get_baseline_aversion_robust_db(self, task_id: str) -> Optional[float]:
        """Database-specific get_baseline_aversion_robust."""
        try:
            import numpy as np
            with self.db_session() as session:
                # Get all initialized instances for this task (completed or not)
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id,
                    self.TaskInstance.initialized_at.isnot(None)
                ).all()
                
                if not instances:
                    return None
                
                aversion_values = []
                
                for instance in instances:
                    predicted = instance.predicted or {}
                    if isinstance(predicted, dict):
                        val = predicted.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                
                if not aversion_values:
                    return None
                
                # Use median for robust baseline (less sensitive to outliers)
                baseline = float(np.median(aversion_values))
                return round(baseline)
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_baseline_aversion_robust and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_baseline_aversion_robust: {e}, falling back to CSV")
            self.use_db = False
            return self._get_baseline_aversion_robust_csv(task_id)
    
    def get_baseline_aversion_sensitive(self, task_id: str) -> Optional[float]:
        """Get sensitive baseline aversion using trimmed mean (more sensitive to trends).
        Excludes outliers using IQR method, then calculates mean of remaining values.
        Returns None if no previous instances exist.
        Values are scaled to 0-100 range."""
        if self.use_db:
            return self._get_baseline_aversion_sensitive_db(task_id)
        else:
            return self._get_baseline_aversion_sensitive_csv(task_id)
    
    def _get_baseline_aversion_sensitive_csv(self, task_id: str) -> Optional[float]:
        """CSV-specific get_baseline_aversion_sensitive."""
        import json
        import numpy as np
        try:
            self._reload()
        except Exception as e:
            print(f"[InstanceManager] Error reloading in get_baseline_aversion_sensitive: {e}")
            # Continue with existing self.df or empty DataFrame
        
        # Get all initialized instances for this task (completed or not)
        initialized = self.df[
            (self.df['task_id'] == task_id) & 
            (self.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        
        if initialized.empty:
            return None
        
        aversion_values = []
        
        for idx in initialized.index:
            predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        val = pred_dict.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                except (json.JSONDecodeError, Exception):
                    pass
        
        if not aversion_values:
            return None
        
        # If only 1-2 values, just use mean
        if len(aversion_values) <= 2:
            baseline = float(np.mean(aversion_values))
            return round(baseline)
        
        # Use IQR method to exclude outliers
        q1 = np.percentile(aversion_values, 25)
        q3 = np.percentile(aversion_values, 75)
        iqr = q3 - q1
        
        # Filter out outliers (values outside Q1 - 1.5*IQR to Q3 + 1.5*IQR)
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        filtered_values = [v for v in aversion_values if lower_bound <= v <= upper_bound]
        
        # If filtering removed all values, use original values
        if not filtered_values:
            filtered_values = aversion_values
        
        # Calculate trimmed mean
        baseline = float(np.mean(filtered_values))
        return round(baseline)
    
    def _get_baseline_aversion_sensitive_db(self, task_id: str) -> Optional[float]:
        """Database-specific get_baseline_aversion_sensitive."""
        try:
            import numpy as np
            with self.db_session() as session:
                # Get all initialized instances for this task (completed or not)
                instances = session.query(self.TaskInstance).filter(
                    self.TaskInstance.task_id == task_id,
                    self.TaskInstance.initialized_at.isnot(None)
                ).all()
                
                if not instances:
                    return None
                
                aversion_values = []
                
                for instance in instances:
                    predicted = instance.predicted or {}
                    if isinstance(predicted, dict):
                        val = predicted.get('expected_aversion')
                        if val is not None:
                            try:
                                num_val = float(val)
                                # Scale from 0-10 to 0-100 if value is <= 10
                                if num_val <= 10 and num_val >= 0:
                                    num_val = num_val * 10
                                aversion_values.append(num_val)
                            except (ValueError, TypeError):
                                pass
                
                if not aversion_values:
                    return None
                
                # If only 1-2 values, just use mean
                if len(aversion_values) <= 2:
                    baseline = float(np.mean(aversion_values))
                    return round(baseline)
                
                # Use IQR method to exclude outliers
                q1 = np.percentile(aversion_values, 25)
                q3 = np.percentile(aversion_values, 75)
                iqr = q3 - q1
                
                # Filter out outliers (values outside Q1 - 1.5*IQR to Q3 + 1.5*IQR)
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr
                
                filtered_values = [v for v in aversion_values if lower_bound <= v <= upper_bound]
                
                # If filtering removed all values, use original values
                if not filtered_values:
                    filtered_values = aversion_values
                
                # Calculate trimmed mean
                baseline = float(np.mean(filtered_values))
                return round(baseline)
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_baseline_aversion_sensitive and CSV fallback is disabled: {e}") from e
            print(f"[InstanceManager] Database error in get_baseline_aversion_sensitive: {e}, falling back to CSV")
            self.use_db = False
            return self._get_baseline_aversion_sensitive_csv(task_id)

    def scale_values_10_to_100(self):
        """Scale existing values from 0-10 range to 0-100 range.
        This migration updates both JSON payloads and CSV columns.
        Only scales values that are <= 10 (to avoid double-scaling)."""
        import json
        self._reload()
        updated_count = 0
        
        # Fields to scale in predicted JSON
        predicted_fields = [
            'expected_relief', 'expected_cognitive_load', 'expected_physical_load',
            'expected_emotional_load', 'motivation'
        ]
        # Fields to scale in actual JSON
        actual_fields = [
            'actual_relief', 'actual_cognitive', 'actual_emotional', 'actual_physical'
        ]
        # CSV columns to scale
        csv_columns = [
            'relief_score', 'cognitive_load', 'emotional_load'
        ]
        
        for idx in self.df.index:
            row_updated = False
            
            # Scale predicted JSON
            predicted_str = str(self.df.at[idx, 'predicted'] or '{}').strip()
            if predicted_str and predicted_str != '{}':
                try:
                    pred_dict = json.loads(predicted_str)
                    if isinstance(pred_dict, dict):
                        for field in predicted_fields:
                            if field in pred_dict:
                                val = pred_dict[field]
                                try:
                                    num_val = float(val)
                                    # Only scale if value is in 0-10 range
                                    if 0 <= num_val <= 10:
                                        pred_dict[field] = num_val * 10
                                        row_updated = True
                                except (ValueError, TypeError):
                                    pass
                        if row_updated:
                            self.df.at[idx, 'predicted'] = json.dumps(pred_dict)
                except (json.JSONDecodeError, Exception):
                    pass
            
            # Scale actual JSON
            actual_str = str(self.df.at[idx, 'actual'] or '{}').strip()
            if actual_str and actual_str != '{}':
                try:
                    actual_dict = json.loads(actual_str)
                    if isinstance(actual_dict, dict):
                        for field in actual_fields:
                            if field in actual_dict:
                                val = actual_dict[field]
                                try:
                                    num_val = float(val)
                                    # Only scale if value is in 0-10 range
                                    if 0 <= num_val <= 10:
                                        actual_dict[field] = num_val * 10
                                        row_updated = True
                                except (ValueError, TypeError):
                                    pass
                        if row_updated:
                            self.df.at[idx, 'actual'] = json.dumps(actual_dict)
                except (json.JSONDecodeError, Exception):
                    pass
            
            # Scale CSV columns
            for col in csv_columns:
                if col in self.df.columns:
                    val = self.df.at[idx, col]
                    if val and str(val).strip() != '':
                        try:
                            num_val = float(val)
                            # Only scale if value is in 0-10 range
                            if 0 <= num_val <= 10:
                                self.df.at[idx, col] = str(num_val * 10)
                                row_updated = True
                        except (ValueError, TypeError):
                            pass
            
            if row_updated:
                updated_count += 1
        
        if updated_count > 0:
            self._save()
            print(f"[InstanceManager] Scaled {updated_count} instances from 0-10 to 0-100 range")
        else:
            print(f"[InstanceManager] No instances needed scaling (all values already in 0-100 range or empty)")
        
        return updated_count