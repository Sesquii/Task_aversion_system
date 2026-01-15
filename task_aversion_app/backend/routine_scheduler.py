# backend/routine_scheduler.py
"""
Routine scheduler service for automatically initializing tasks based on their schedule.
"""
import os
import json
from datetime import datetime, time as dt_time, timedelta
from typing import List, Optional
import threading
import time as time_module

from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager


class RoutineScheduler:
    """
    Schedules and automatically initializes routine tasks based on their schedule.
    
    Checks every minute for tasks that should be initialized:
    - Daily tasks at their specified time
    - Weekly tasks on specified days at their specified time
    """
    
    def __init__(self):
        self.task_manager = TaskManager()
        self.instance_manager = InstanceManager()
        self.running = False
        self.thread = None
        self.check_interval = 60  # Check every 60 seconds
        
    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("[RoutineScheduler] Started routine scheduler")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[RoutineScheduler] Stopped routine scheduler")
    
    def _run_loop(self):
        """Main scheduler loop - runs in background thread."""
        while self.running:
            try:
                self._check_and_initialize_tasks()
            except Exception as e:
                print(f"[RoutineScheduler] Error in scheduler loop: {e}")
            
            # Sleep for check interval
            time_module.sleep(self.check_interval)
    
    def _check_and_initialize_tasks(self):
        """Check for tasks that should be initialized now and initialize them."""
        now = datetime.now()
        current_time = now.time()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Get all tasks
        # Note: RoutineScheduler is a background service that needs to check tasks for all users
        # For data isolation, we use CSV mode for background services
        # TODO: Consider iterating over all users for proper multi-user database support
        try:
            all_tasks = self.task_manager.get_all(user_id=None)
        except ValueError:
            # Database mode requires user_id - use CSV mode for background services
            import os
            original_use_csv = os.getenv('USE_CSV', '')
            os.environ['USE_CSV'] = '1'  # Temporarily use CSV mode
            try:
                from backend.task_manager import TaskManager
                csv_task_manager = TaskManager()
                all_tasks = csv_task_manager.get_all(user_id=None)
            finally:
                # Restore original setting
                if original_use_csv:
                    os.environ['USE_CSV'] = original_use_csv
                elif 'USE_CSV' in os.environ:
                    del os.environ['USE_CSV']
        
        if all_tasks is None or all_tasks.empty:
            return
        
        for _, task_row in all_tasks.iterrows():
            try:
                task = task_row.to_dict()
                routine_frequency = task.get('routine_frequency', 'none') or 'none'
                
                if routine_frequency == 'none':
                    continue
                
                # Parse routine time
                routine_time_str = task.get('routine_time', '00:00') or '00:00'
                try:
                    hour, minute = map(int, routine_time_str.split(':'))
                    scheduled_time = dt_time(hour, minute)
                except (ValueError, AttributeError):
                    print(f"[RoutineScheduler] Invalid time format for task {task.get('task_id')}: {routine_time_str}")
                    continue
                
                # Check if this task should be initialized now
                should_initialize = False
                
                # Parse routine days (used for both daily and weekly)
                routine_days_str = task.get('routine_days_of_week', '[]') or '[]'
                try:
                    routine_days = json.loads(routine_days_str) if isinstance(routine_days_str, str) else routine_days_str
                    if not isinstance(routine_days, list):
                        routine_days = []
                except (json.JSONDecodeError, TypeError):
                    routine_days = []
                
                if routine_frequency == 'daily':
                    # Daily: check if current time matches scheduled time (within 1 minute window)
                    # If days are selected, only run on those days; if empty, run every day
                    if not routine_days or current_weekday in routine_days:
                        time_diff = abs((datetime.combine(now.date(), current_time) - 
                                       datetime.combine(now.date(), scheduled_time)).total_seconds())
                        if time_diff <= self.check_interval:
                            should_initialize = True
                
                elif routine_frequency == 'weekly':
                    # Weekly: check if today is a selected day and time matches
                    if current_weekday in routine_days:
                        # Today is a selected day, check time
                        time_diff = abs((datetime.combine(now.date(), current_time) - 
                                       datetime.combine(now.date(), scheduled_time)).total_seconds())
                        if time_diff <= self.check_interval:
                            should_initialize = True
                
                if should_initialize:
                    self._initialize_routine_task(task, now)
                    
            except Exception as e:
                print(f"[RoutineScheduler] Error processing task {task.get('task_id', 'unknown')}: {e}")
                continue
    
    def _initialize_routine_task(self, task: dict, scheduled_time: datetime):
        """
        Initialize a routine task instance.
        
        Args:
            task: Task template dictionary
            scheduled_time: When the task was scheduled to be initialized
        """
        task_id = task.get('task_id')
        task_name = task.get('name', 'Unknown Task')
        
        # Get user_id from task for data isolation (extract early for filtering)
        task_user_id = task.get('user_id')
        if task_user_id is None:
            # Task has no user_id - this shouldn't happen in database mode
            # but we'll allow it for CSV mode compatibility
            print(f"[RoutineScheduler] WARNING: Task {task_name} has no user_id, creating instance without user_id")
        
        # Check if we already initialized this task today (avoid duplicates)
        # Look for instances created today for this task
        today_start = scheduled_time.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Get instances for this task, filtered by user_id for data isolation
        # Use _load_instances or get_instance methods if available, otherwise filter DataFrame
        try:
            # Try to use a method that respects user_id filtering
            if hasattr(self.instance_manager, '_load_instances'):
                # Convert user_id to int if it's a string
                user_id_int = None
                if task_user_id is not None:
                    try:
                        user_id_int = int(task_user_id) if isinstance(task_user_id, str) and task_user_id.isdigit() else task_user_id
                    except (ValueError, TypeError):
                        pass
                
                all_instances = self.instance_manager._load_instances(user_id=user_id_int)
            else:
                # Fallback to DataFrame access with user_id filtering
                self.instance_manager._reload()
                all_instances = self.instance_manager.df
                if task_user_id is not None and 'user_id' in all_instances.columns:
                    # Filter by user_id for data isolation
                    all_instances = all_instances[all_instances['user_id'] == task_user_id]
        except Exception as e:
            print(f"[RoutineScheduler] Error loading instances: {e}, falling back to direct DataFrame access")
            self.instance_manager._reload()
            all_instances = self.instance_manager.df
            if task_user_id is not None and 'user_id' in all_instances.columns:
                all_instances = all_instances[all_instances['user_id'] == task_user_id]
        
        if not all_instances.empty:
            task_instances = all_instances[all_instances['task_id'] == task_id]
            
            # Check if any instance was created today
            if not task_instances.empty:
                for _, instance_row in task_instances.iterrows():
                    created_at_str = instance_row.get('created_at', '')
                    if created_at_str:
                        try:
                            created_at = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M")
                            if today_start <= created_at < today_end:
                                # Already initialized today, skip
                                print(f"[RoutineScheduler] Task {task_name} already initialized today, skipping")
                                return
                        except (ValueError, TypeError):
                            pass
        
        # Create new instance
        default_estimate = task.get('default_estimate_minutes') or 0
        try:
            default_estimate = int(default_estimate)
        except (TypeError, ValueError):
            default_estimate = 0
        
        instance_id = self.instance_manager.create_instance(
            task_id=task_id,
            task_name=task_name,
            task_version=task.get('version') or 1,
            predicted={'time_estimate_minutes': default_estimate},
            user_id=task_user_id
        )
        
        print(f"[RoutineScheduler] Initialized routine task: {task_name} (instance: {instance_id}, user_id: {task_user_id})")
    
    def get_scheduled_tasks(self) -> List[dict]:
        """
        Get all tasks with active routine schedules.
        
        Returns:
            List of task dictionaries with routine schedules
        """
        # Note: RoutineScheduler is a background service that needs to check tasks for all users
        # For data isolation, we use CSV mode for background services
        # TODO: Consider iterating over all users for proper multi-user database support
        try:
            all_tasks = self.task_manager.get_all(user_id=None)
        except ValueError:
            # Database mode requires user_id - use CSV mode for background services
            import os
            original_use_csv = os.getenv('USE_CSV', '')
            os.environ['USE_CSV'] = '1'  # Temporarily use CSV mode
            try:
                from backend.task_manager import TaskManager
                csv_task_manager = TaskManager()
                all_tasks = csv_task_manager.get_all(user_id=None)
            finally:
                # Restore original setting
                if original_use_csv:
                    os.environ['USE_CSV'] = original_use_csv
                elif 'USE_CSV' in os.environ:
                    del os.environ['USE_CSV']
        if all_tasks is None or all_tasks.empty:
            return []
        
        scheduled = []
        for _, task_row in all_tasks.iterrows():
            task = task_row.to_dict()
            routine_frequency = task.get('routine_frequency', 'none') or 'none'
            if routine_frequency != 'none':
                scheduled.append(task)
        
        return scheduled


# Global scheduler instance
_scheduler_instance: Optional[RoutineScheduler] = None


def get_scheduler() -> RoutineScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = RoutineScheduler()
    return _scheduler_instance


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop()

