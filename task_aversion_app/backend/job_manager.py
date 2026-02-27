# backend/job_manager.py
"""
JobManager: CRUD and assignment for jobs (grouping layer between task_type and tasks).
Supports both database and CSV backends (dual backend pattern).
"""
import os
import random
from datetime import datetime
from typing import List, Optional

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
JOBS_FILE = os.path.join(DATA_DIR, 'jobs.csv')
JOB_TASK_MAPPING_FILE = os.path.join(DATA_DIR, 'job_task_mapping.csv')


class JobManager:
    """Manage jobs and job-task assignments. Dual backend: database (default) or CSV."""

    def __init__(self, use_csv: Optional[bool] = None) -> None:
        _explicit_csv = use_csv is True
        if use_csv is None:
            use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')

        if use_csv:
            self.use_db = False
        else:
            if not os.getenv('DATABASE_URL'):
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
            self.use_db = True

        self.strict_mode = bool(
            os.getenv('DISABLE_CSV_FALLBACK', '').lower() in ('1', 'true', 'yes')
        )

        if self.use_db:
            try:
                from backend.database import get_session, Job, JobTaskMapping, Task, init_db
                self.db_session = get_session
                self.Job = Job
                self.JobTaskMapping = JobTaskMapping
                self.Task = Task
                init_db()
                if not getattr(JobManager, '_printed_backend', False):
                    print("[JobManager] Using database backend")
                    JobManager._printed_backend = True
            except Exception as e:
                if self.strict_mode:
                    raise RuntimeError(
                        f"Database initialization failed and CSV fallback is disabled: {e}"
                    ) from e
                print(f"[JobManager] WARNING: Database failed: {e}, falling back to CSV")
                self.use_db = False
                self._init_csv()
        else:
            if not _explicit_csv and self.strict_mode:
                raise RuntimeError(
                    "CSV backend requested but DISABLE_CSV_FALLBACK is set."
                )
            self._init_csv()
            if not _explicit_csv:
                print("[JobManager] Using CSV backend")

    def _init_csv(self) -> None:
        """Initialize CSV backend files."""
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(JOBS_FILE):
            pd.DataFrame(columns=[
                'job_id', 'name', 'task_type', 'description', 'created_at', 'updated_at'
            ]).to_csv(JOBS_FILE, index=False)
        if not os.path.exists(JOB_TASK_MAPPING_FILE):
            pd.DataFrame(columns=['job_id', 'task_id', 'created_at']).to_csv(
                JOB_TASK_MAPPING_FILE, index=False
            )
        self._reload_csv()

    def _reload_csv(self) -> None:
        """Reload CSV data into memory."""
        if not self.use_db:
            self._jobs_df = pd.read_csv(JOBS_FILE, dtype=str).fillna('')
            self._mapping_df = pd.read_csv(JOB_TASK_MAPPING_FILE, dtype=str).fillna('')

    def _save_csv(self) -> None:
        """Persist CSV data."""
        if not self.use_db:
            self._jobs_df.to_csv(JOBS_FILE, index=False)
            self._mapping_df.to_csv(JOB_TASK_MAPPING_FILE, index=False)
            self._reload_csv()

    def create_job(
        self,
        name: str,
        task_type: str = 'Work',
        description: str = '',
    ) -> str:
        """Create a new job. Returns job_id."""
        if self.use_db:
            return self._create_job_db(name, task_type, description)
        return self._create_job_csv(name, task_type, description)

    def _create_job_csv(
        self,
        name: str,
        task_type: str = 'Work',
        description: str = '',
    ) -> str:
        self._reload_csv()
        job_id = f"j{int(datetime.now().timestamp())}{random.randint(0, 999):03d}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        row = {
            'job_id': job_id,
            'name': name,
            'task_type': task_type or 'Work',
            'description': description or '',
            'created_at': now_str,
            'updated_at': now_str,
        }
        self._jobs_df = pd.concat([
            self._jobs_df,
            pd.DataFrame([row])
        ], ignore_index=True)
        self._save_csv()
        return job_id

    def _create_job_db(
        self,
        name: str,
        task_type: str = 'Work',
        description: str = '',
    ) -> str:
        try:
            job_id = f"j{int(datetime.now().timestamp())}{random.randint(0, 999):03d}"
            with self.db_session() as session:
                job = self.Job(
                    job_id=job_id,
                    name=name,
                    task_type=task_type or 'Work',
                    description=description or '',
                )
                session.add(job)
                session.commit()
            return job_id
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in create_job: {e}") from e
            print(f"[JobManager] Database error in create_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            return self._create_job_csv(name, task_type, description)

    def get_job(self, job_id: str) -> Optional[dict]:
        """Return a job by id as a dict, or None."""
        if self.use_db:
            return self._get_job_db(job_id)
        return self._get_job_csv(job_id)

    def _get_job_csv(self, job_id: str) -> Optional[dict]:
        self._reload_csv()
        rows = self._jobs_df[self._jobs_df['job_id'] == job_id]
        return rows.iloc[0].to_dict() if not rows.empty else None

    def _get_job_db(self, job_id: str) -> Optional[dict]:
        try:
            with self.db_session() as session:
                job = session.query(self.Job).filter(self.Job.job_id == job_id).first()
                return job.to_dict() if job else None
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_job: {e}") from e
            print(f"[JobManager] Database error in get_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            return self._get_job_csv(job_id)

    def get_all_jobs(self, task_type: Optional[str] = None) -> List[dict]:
        """Return all jobs, optionally filtered by task_type."""
        if self.use_db:
            return self._get_all_jobs_db(task_type)
        return self._get_all_jobs_csv(task_type)

    def _get_all_jobs_csv(self, task_type: Optional[str] = None) -> List[dict]:
        self._reload_csv()
        df = self._jobs_df.copy()
        if task_type:
            df = df[df['task_type'].str.strip().str.lower() == task_type.strip().lower()]
        return df.to_dict(orient='records')

    def _get_all_jobs_db(self, task_type: Optional[str] = None) -> List[dict]:
        try:
            with self.db_session() as session:
                query = session.query(self.Job)
                if task_type:
                    query = query.filter(self.Job.task_type == task_type)
                jobs = query.order_by(self.Job.name).all()
                return [j.to_dict() for j in jobs]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_all_jobs: {e}") from e
            print(f"[JobManager] Database error in get_all_jobs: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            return self._get_all_jobs_csv(task_type)

    def update_job(self, job_id: str, **kwargs: object) -> None:
        """Update a job. Allowed keys: name, task_type, description."""
        allowed = {'name', 'task_type', 'description'}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        if self.use_db:
            self._update_job_db(job_id, **updates)
        else:
            self._update_job_csv(job_id, **updates)

    def _update_job_csv(self, job_id: str, **kwargs: object) -> None:
        self._reload_csv()
        mask = self._jobs_df['job_id'] == job_id
        if not mask.any():
            return
        for k, v in kwargs.items():
            if k in self._jobs_df.columns:
                self._jobs_df.loc[mask, k] = v
        self._jobs_df.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save_csv()

    def _update_job_db(self, job_id: str, **kwargs: object) -> None:
        try:
            with self.db_session() as session:
                job = session.query(self.Job).filter(self.Job.job_id == job_id).first()
                if job:
                    for k, v in kwargs.items():
                        if hasattr(job, k):
                            setattr(job, k, v)
                    session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in update_job: {e}") from e
            print(f"[JobManager] Database error in update_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            self._update_job_csv(job_id, **kwargs)

    def delete_job(self, job_id: str) -> None:
        """Delete a job and its task mappings. Fails if job does not exist."""
        if self.use_db:
            self._delete_job_db(job_id)
        else:
            self._delete_job_csv(job_id)

    def _delete_job_csv(self, job_id: str) -> None:
        self._reload_csv()
        self._jobs_df = self._jobs_df[self._jobs_df['job_id'] != job_id]
        self._mapping_df = self._mapping_df[self._mapping_df['job_id'] != job_id]
        self._save_csv()

    def _delete_job_db(self, job_id: str) -> None:
        try:
            with self.db_session() as session:
                session.query(self.JobTaskMapping).filter(
                    self.JobTaskMapping.job_id == job_id
                ).delete()
                session.query(self.Job).filter(self.Job.job_id == job_id).delete()
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in delete_job: {e}") from e
            print(f"[JobManager] Database error in delete_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            self._delete_job_csv(job_id)

    def assign_task_to_job(self, task_id: str, job_id: str) -> None:
        """Assign a task to a job (idempotent)."""
        if self.use_db:
            self._assign_task_to_job_db(task_id, job_id)
        else:
            self._assign_task_to_job_csv(task_id, job_id)

    def _assign_task_to_job_csv(self, task_id: str, job_id: str) -> None:
        self._reload_csv()
        if self._jobs_df[self._jobs_df['job_id'] == job_id].empty:
            raise ValueError(f"Job {job_id} does not exist")
        existing = self._mapping_df[
            (self._mapping_df['job_id'] == job_id) & (self._mapping_df['task_id'] == task_id)
        ]
        if existing.empty:
            row = {
                'job_id': job_id,
                'task_id': task_id,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            self._mapping_df = pd.concat([
                self._mapping_df,
                pd.DataFrame([row])
            ], ignore_index=True)
            self._save_csv()

    def _assign_task_to_job_db(self, task_id: str, job_id: str) -> None:
        try:
            with self.db_session() as session:
                if session.query(self.Job).filter(self.Job.job_id == job_id).first() is None:
                    raise ValueError(f"Job {job_id} does not exist")
                existing = session.query(self.JobTaskMapping).filter(
                    self.JobTaskMapping.job_id == job_id,
                    self.JobTaskMapping.task_id == task_id,
                ).first()
                if not existing:
                    m = self.JobTaskMapping(job_id=job_id, task_id=task_id)
                    session.add(m)
                    session.commit()
        except ValueError:
            raise
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in assign_task_to_job: {e}") from e
            print(f"[JobManager] Database error in assign_task_to_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            self._assign_task_to_job_csv(task_id, job_id)

    def remove_task_from_job(self, task_id: str, job_id: str) -> None:
        """Remove a task from a job."""
        if self.use_db:
            self._remove_task_from_job_db(task_id, job_id)
        else:
            self._remove_task_from_job_csv(task_id, job_id)

    def _remove_task_from_job_csv(self, task_id: str, job_id: str) -> None:
        self._reload_csv()
        self._mapping_df = self._mapping_df[
            ~((self._mapping_df['job_id'] == job_id) & (self._mapping_df['task_id'] == task_id))
        ]
        self._save_csv()

    def _remove_task_from_job_db(self, task_id: str, job_id: str) -> None:
        try:
            with self.db_session() as session:
                session.query(self.JobTaskMapping).filter(
                    self.JobTaskMapping.job_id == job_id,
                    self.JobTaskMapping.task_id == task_id,
                ).delete()
                session.commit()
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in remove_task_from_job: {e}") from e
            print(f"[JobManager] Database error in remove_task_from_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            self._remove_task_from_job_csv(task_id, job_id)

    def get_tasks_for_job(
        self,
        job_id: str,
        user_id: Optional[int] = None,
    ) -> List[dict]:
        """Return list of task dicts assigned to this job. Optionally filter by user_id (DB only)."""
        if self.use_db:
            return self._get_tasks_for_job_db(job_id, user_id)
        return self._get_tasks_for_job_csv(job_id)

    def _get_tasks_for_job_csv(self, job_id: str) -> List[dict]:
        self._reload_csv()
        task_ids = self._mapping_df[self._mapping_df['job_id'] == job_id]['task_id'].tolist()
        if not task_ids:
            return []
        from backend.task_manager import TaskManager
        tm = TaskManager(use_csv=True)
        try:
            all_tasks = tm.get_all(user_id=None)
        except ValueError:
            all_tasks = []
        if all_tasks is None:
            return []
        if isinstance(all_tasks, pd.DataFrame):
            if all_tasks.empty:
                return []
            out = all_tasks[all_tasks['task_id'].isin(task_ids)]
            return out.to_dict(orient='records')
        return [t for t in all_tasks if isinstance(t, dict) and t.get('task_id') in task_ids]

    def _get_tasks_for_job_db(
        self,
        job_id: str,
        user_id: Optional[int] = None,
    ) -> List[dict]:
        try:
            from sqlalchemy import or_
            with self.db_session() as session:
                mapping = session.query(self.JobTaskMapping.task_id).filter(
                    self.JobTaskMapping.job_id == job_id
                ).all()
                task_ids = [m[0] for m in mapping]
                if not task_ids:
                    return []
                query = session.query(self.Task).filter(self.Task.task_id.in_(task_ids))
                if user_id is not None:
                    query = query.filter(or_(self.Task.user_id == user_id, self.Task.user_id.is_(None)))
                tasks = query.all()
                return [t.to_dict() for t in tasks]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_tasks_for_job: {e}") from e
            print(f"[JobManager] Database error in get_tasks_for_job: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            return self._get_tasks_for_job_csv(job_id)

    def get_jobs_for_task(self, task_id: str) -> List[dict]:
        """Return list of job dicts that include this task."""
        if self.use_db:
            return self._get_jobs_for_task_db(task_id)
        return self._get_jobs_for_task_csv(task_id)

    def _get_jobs_for_task_csv(self, task_id: str) -> List[dict]:
        self._reload_csv()
        job_ids = self._mapping_df[self._mapping_df['task_id'] == task_id]['job_id'].tolist()
        if not job_ids:
            return []
        jobs = [self.get_job(jid) for jid in job_ids]
        return [j for j in jobs if j is not None]

    def _get_jobs_for_task_db(self, task_id: str) -> List[dict]:
        try:
            with self.db_session() as session:
                mapping = session.query(self.JobTaskMapping.job_id).filter(
                    self.JobTaskMapping.task_id == task_id
                ).all()
                job_ids = [m[0] for m in mapping]
                if not job_ids:
                    return []
                jobs = session.query(self.Job).filter(self.Job.job_id.in_(job_ids)).all()
                return [j.to_dict() for j in jobs]
        except Exception as e:
            if self.strict_mode:
                raise RuntimeError(f"Database error in get_jobs_for_task: {e}") from e
            print(f"[JobManager] Database error in get_jobs_for_task: {e}, falling back to CSV")
            self.use_db = False
            self._init_csv()
            return self._get_jobs_for_task_csv(task_id)
