"""Productivity hours tracking and goal management.

Tracks weekly productive hours (Work and Self Care tasks) and compares against user goals.
Supports hybrid initialization (auto-estimate with manual adjustment).
"""
import os
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List
from pathlib import Path

from .instance_manager import InstanceManager
from .task_manager import TaskManager
from .user_state import UserStateManager


class ProductivityTracker:
    """Track weekly productivity hours and manage goal settings."""
    
    def __init__(self):
        self.instance_manager = InstanceManager()
        self.task_manager = TaskManager()
        self.user_state = UserStateManager()
        self.default_user_id = "default_user"
    
    def calculate_weekly_productivity_hours(
        self, 
        user_id: str,
        week_start_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Calculate weekly productive hours for a given week.
        
        Args:
            user_id: User ID
            week_start_date: Start date of the week (default: current Monday)
            
        Returns:
            Dict with:
            - total_hours (float)
            - total_minutes (float)
            - days_with_data (int)
            - daily_averages (List[Dict[str, Any]])
            - task_count (int)
            - breakdown_by_type (Dict[str, float])
        """
        if week_start_date is None:
            # Start from Monday of current week
            today = date.today()
            days_since_monday = today.weekday()  # Monday is 0
            week_start_date = today - timedelta(days=days_since_monday)
        
        week_end_date = week_start_date + timedelta(days=7)
        
        # Get all completed instances in the date range
        instances_df = self._get_completed_instances(user_id)
        if instances_df.empty:
            return {
                'total_hours': 0.0,
                'total_minutes': 0.0,
                'days_with_data': 0,
                'daily_averages': [],
                'task_count': 0,
                'breakdown_by_type': {'work': 0.0, 'self_care': 0.0}
            }
        
        # Filter by date range and productive task types
        instances_df['completed_at_dt'] = pd.to_datetime(instances_df['completed_at'], errors='coerce')
        instances_df['completed_date'] = instances_df['completed_at_dt'].dt.date
        
        week_instances = instances_df[
            (instances_df['completed_date'] >= week_start_date) &
            (instances_df['completed_date'] < week_end_date)
        ].copy()
        
        if week_instances.empty:
            return {
                'total_hours': 0.0,
                'total_minutes': 0.0,
                'days_with_data': 0,
                'daily_averages': [],
                'task_count': 0,
                'breakdown_by_type': {'work': 0.0, 'self_care': 0.0}
            }
        
        # Get task types
        tasks_df = self.task_manager.get_all()
        task_type_map = {}
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            for _, row in tasks_df.iterrows():
                task_id = row.get('task_id', '')
                task_type = row.get('task_type', 'Work')
                task_type_map[task_id] = str(task_type).strip().lower()
        
        # Filter to productive tasks (Work and Self Care)
        week_instances['task_type'] = week_instances['task_id'].map(task_type_map).fillna('work')
        productive_types = ['work', 'self care', 'selfcare', 'self-care']
        productive_instances = week_instances[
            week_instances['task_type'].isin(productive_types)
        ].copy()
        
        # Extract time_actual_minutes
        def _get_time_minutes(row):
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('time_actual_minutes', 0) or 0)
            # Fallback: try duration_minutes column if available
            if 'duration_minutes' in row and pd.notna(row['duration_minutes']):
                try:
                    return float(row['duration_minutes'])
                except (ValueError, TypeError):
                    pass
            return 0.0
        
        productive_instances['time_minutes'] = productive_instances.apply(_get_time_minutes, axis=1)
        productive_instances = productive_instances[productive_instances['time_minutes'] > 0]
        
        if productive_instances.empty:
            return {
                'total_hours': 0.0,
                'total_minutes': 0.0,
                'days_with_data': 0,
                'daily_averages': [],
                'task_count': 0,
                'breakdown_by_type': {'work': 0.0, 'self_care': 0.0}
            }
        
        # Calculate totals
        total_minutes = productive_instances['time_minutes'].sum()
        total_hours = total_minutes / 60.0
        
        # Daily breakdown
        daily_totals = productive_instances.groupby('completed_date')['time_minutes'].sum()
        days_with_data = len(daily_totals)
        daily_averages = [
            {
                'date': str(day),
                'hours': round(minutes / 60.0, 2),
                'minutes': round(minutes, 1)
            }
            for day, minutes in daily_totals.items()
        ]
        
        # Breakdown by task type
        breakdown_by_type = {}
        for task_type in productive_types:
            type_instances = productive_instances[productive_instances['task_type'] == task_type]
            type_minutes = type_instances['time_minutes'].sum()
            type_key = 'work' if task_type == 'work' else 'self_care'
            breakdown_by_type[type_key] = round(type_minutes / 60.0, 2)
        
        return {
            'total_hours': round(total_hours, 2),
            'total_minutes': round(total_minutes, 1),
            'days_with_data': days_with_data,
            'daily_averages': daily_averages,
            'task_count': len(productive_instances),
            'breakdown_by_type': breakdown_by_type
        }
    
    def _get_completed_instances(self, user_id: str) -> pd.DataFrame:
        """Get all completed task instances as DataFrame.
        
        Uses the same pattern as analytics.py: defaults to database unless USE_CSV is set.
        """
        import json
        
        # Default to database (SQLite) unless USE_CSV is explicitly set
        use_csv = os.getenv('USE_CSV', '').lower() in ('1', 'true', 'yes')
        
        if use_csv:
            # CSV backend (explicitly requested)
            use_db = False
        else:
            # Database backend (default)
            # Ensure DATABASE_URL is set to default SQLite if not already set
            if not os.getenv('DATABASE_URL'):
                # Use the same default as database.py
                os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'
            use_db = True
        
        def _safe_json(cell):
            """Safely parse JSON cell to dict."""
            if isinstance(cell, dict):
                return cell
            if pd.isna(cell) or cell == '':
                return {}
            try:
                if isinstance(cell, str):
                    return json.loads(cell)
                return {}
            except (json.JSONDecodeError, TypeError):
                return {}
        
        if use_db:
            # Load from database
            try:
                from .database import get_session, TaskInstance
                session = get_session()
                try:
                    instances = session.query(TaskInstance).filter(
                        TaskInstance.is_completed == True,
                        TaskInstance.completed_at.isnot(None)
                    ).all()
                    
                    if not instances:
                        return pd.DataFrame()
                    
                    # Convert to list of dicts
                    data = [inst.to_dict() for inst in instances]
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(data).fillna('')
                    
                    # Convert actual/predicted JSON strings to dicts (same as analytics.py)
                    if 'actual' in df.columns:
                        df['actual_dict'] = df['actual'].apply(_safe_json)
                    else:
                        df['actual_dict'] = pd.Series([{}] * len(df))
                    
                    if 'predicted' in df.columns:
                        df['predicted_dict'] = df['predicted'].apply(_safe_json)
                    else:
                        df['predicted_dict'] = pd.Series([{}] * len(df))
                    
                    return df
                finally:
                    session.close()
            except Exception as e:
                print(f"[ProductivityTracker] Database error: {e}")
                import traceback
                traceback.print_exc()
                return pd.DataFrame()
        else:
            # CSV backend (explicitly requested via USE_CSV)
            self.instance_manager._reload()
            completed = self.instance_manager.df[
                (self.instance_manager.df['status'] == 'completed') &
                (self.instance_manager.df['completed_at'].notna())
            ].copy()
            
            # Parse JSON fields (same pattern as analytics.py)
            if 'actual' in completed.columns:
                completed['actual_dict'] = completed['actual'].apply(_safe_json)
            else:
                completed['actual_dict'] = pd.Series([{}] * len(completed))
            
            if 'predicted' in completed.columns:
                completed['predicted_dict'] = completed['predicted'].apply(_safe_json)
            else:
                completed['predicted_dict'] = pd.Series([{}] * len(completed))
            
            return completed
    
    def get_first_day_productive_hours(self, user_id: str) -> Optional[float]:
        """Get productive hours from user's first tracked day.
        
        Returns:
            Hours (float) or None if no data available
        """
        instances_df = self._get_completed_instances(user_id)
        if instances_df.empty:
            return None
        
        instances_df['completed_at_dt'] = pd.to_datetime(instances_df['completed_at'], errors='coerce')
        instances_df = instances_df[instances_df['completed_at_dt'].notna()]
        
        if instances_df.empty:
            return None
        
        # Find earliest date
        earliest_date = instances_df['completed_at_dt'].dt.date.min()
        first_day_instances = instances_df[
            instances_df['completed_at_dt'].dt.date == earliest_date
        ]
        
        # Get task types and filter to productive
        tasks_df = self.task_manager.get_all()
        task_type_map = {}
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            for _, row in tasks_df.iterrows():
                task_id = row.get('task_id', '')
                task_type = row.get('task_type', 'Work')
                task_type_map[task_id] = str(task_type).strip().lower()
        
        first_day_instances['task_type'] = first_day_instances['task_id'].map(task_type_map).fillna('work')
        productive_types = ['work', 'self care', 'selfcare', 'self-care']
        productive_first_day = first_day_instances[
            first_day_instances['task_type'].isin(productive_types)
        ]
        
        # Sum time
        def _get_time_minutes(row):
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('time_actual_minutes', 0) or 0)
            return 0.0
        
        productive_first_day['time_minutes'] = productive_first_day.apply(_get_time_minutes, axis=1)
        total_minutes = productive_first_day['time_minutes'].sum()
        
        if total_minutes <= 0:
            return None
        
        return round(total_minutes / 60.0, 2)
    
    def estimate_starting_hours_auto(
        self,
        user_id: str,
        factor: float = 10.0
    ) -> Optional[float]:
        """Auto-estimate starting hours from first day data.
        
        Args:
            user_id: User ID
            factor: Multiplier for first day (default 10.0 to account for underreporting)
            
        Returns:
            Estimated weekly hours or None
        """
        first_day_hours = self.get_first_day_productive_hours(user_id)
        if first_day_hours is None:
            return None
        
        estimated_weekly = first_day_hours * factor
        # Cap at 60 hours/week maximum for auto-estimates
        estimated_weekly = min(estimated_weekly, 60.0)
        
        return round(estimated_weekly, 2)
    
    def compare_to_goal(
        self,
        user_id: str,
        week_start_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Compare actual weekly productivity to goal.
        
        Args:
            user_id: User ID
            week_start_date: Start date of week (default: current Monday)
            
        Returns:
            Dict with:
            - actual_hours (float)
            - goal_hours (float)
            - difference (float, actual - goal)
            - percentage_of_goal (float, 0-100+)
            - status (str: 'above', 'on_track', 'below', 'no_goal', 'no_data')
        """
        # Get actual hours
        weekly_data = self.calculate_weekly_productivity_hours(user_id, week_start_date)
        actual_hours = weekly_data['total_hours']
        
        # Get goal hours
        goal_settings = self.user_state.get_productivity_goal_settings(user_id)
        goal_hours = goal_settings.get('goal_hours_per_week', 40.0)
        
        if goal_hours <= 0:
            return {
                'actual_hours': actual_hours,
                'goal_hours': 0.0,
                'difference': actual_hours,
                'percentage_of_goal': 0.0,
                'status': 'no_goal'
            }
        
        if actual_hours <= 0:
            return {
                'actual_hours': 0.0,
                'goal_hours': goal_hours,
                'difference': -goal_hours,
                'percentage_of_goal': 0.0,
                'status': 'no_data'
            }
        
        difference = actual_hours - goal_hours
        percentage = (actual_hours / goal_hours) * 100.0
        
        if percentage >= 115.0:
            status = 'above'
        elif percentage >= 85.0:
            status = 'on_track'
        else:
            status = 'below'
        
        return {
            'actual_hours': actual_hours,
            'goal_hours': goal_hours,
            'difference': round(difference, 2),
            'percentage_of_goal': round(percentage, 1),
            'status': status
        }
    
    def calculate_productivity_points_target(
        self,
        user_id: str,
        goal_hours_per_week: float,
        weeks_for_average: int = 4
    ) -> Dict[str, Any]:
        """Calculate productivity points target based on goal hours and historical productivity score per hour.
        
        Args:
            user_id: User ID
            goal_hours_per_week: Goal productive hours per week
            weeks_for_average: Number of recent weeks to use for average calculation (default 4)
            
        Returns:
            Dict with:
            - target_points (float): Target productivity points for goal hours
            - avg_score_per_hour (float): Average productivity score per hour from recent weeks
            - weeks_used (int): Number of weeks with data used for calculation
            - confidence (str): 'high', 'medium', 'low' based on data availability
        """
        from datetime import timedelta, date
        
        # Get completed instances and calculate productivity scores
        instances_df = self._get_completed_instances(user_id)
        if instances_df.empty:
            return {
                'target_points': 0.0,
                'avg_score_per_hour': 0.0,
                'weeks_used': 0,
                'confidence': 'low'
            }
        
        # Filter to productive tasks and calculate scores
        # We need to calculate productivity scores for tasks, so import Analytics
        from .analytics import Analytics
        analytics = Analytics()
        
        # Get task types
        tasks_df = self.task_manager.get_all()
        task_type_map = {}
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            for _, row in tasks_df.iterrows():
                task_id = row.get('task_id', '')
                task_type = row.get('task_type', 'Work')
                task_type_map[task_id] = str(task_type).strip().lower()
        
        instances_df['task_type'] = instances_df['task_id'].map(task_type_map).fillna('work')
        productive_types = ['work', 'self care', 'selfcare', 'self-care']
        productive_instances = instances_df[
            instances_df['task_type'].isin(productive_types)
        ].copy()
        
        if productive_instances.empty:
            return {
                'target_points': 0.0,
                'avg_score_per_hour': 0.0,
                'weeks_used': 0,
                'confidence': 'low'
            }
        
        # Parse dates
        productive_instances['completed_at_dt'] = pd.to_datetime(productive_instances['completed_at'], errors='coerce')
        productive_instances = productive_instances[productive_instances['completed_at_dt'].notna()]
        productive_instances['completed_date'] = productive_instances['completed_at_dt'].dt.date
        
        # Calculate weekly productivity scores and hours for recent weeks
        today = date.today()
        weekly_stats = []
        
        for i in range(weeks_for_average):
            week_start = today - timedelta(days=today.weekday() + (i * 7))
            week_end = week_start + timedelta(days=7)
            
            week_instances = productive_instances[
                (productive_instances['completed_date'] >= week_start) &
                (productive_instances['completed_date'] < week_end)
            ].copy()
            
            if week_instances.empty:
                continue
            
            # Calculate hours for this week
            def _get_time_minutes(row):
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, dict):
                    return float(actual_dict.get('time_actual_minutes', 0) or 0)
                return 0.0
            
            week_instances['time_minutes'] = week_instances.apply(_get_time_minutes, axis=1)
            week_instances = week_instances[week_instances['time_minutes'] > 0]
            
            if week_instances.empty:
                continue
            
            week_hours = week_instances['time_minutes'].sum() / 60.0
            
            # Calculate productivity scores for this week's instances
            # We need work_play_time_per_day and self_care_tasks_per_day for the score calculation
            # For simplicity, calculate without those parameters (they're optional)
            week_instances['productivity_score'] = week_instances.apply(
                lambda row: analytics.calculate_productivity_score(
                    row,
                    self_care_tasks_per_day={},  # Simplified - won't affect work tasks
                    weekly_avg_time=0.0,  # Simplified
                    work_play_time_per_day=None,
                    play_penalty_threshold=2.0,
                    productivity_settings=None,
                    weekly_work_summary=None,
                    goal_hours_per_week=None,
                    weekly_productive_hours=None
                ),
                axis=1
            )
            
            week_total_score = week_instances['productivity_score'].fillna(0).sum()
            
            if week_hours > 0:
                weekly_stats.append({
                    'week_start': week_start,
                    'total_score': week_total_score,
                    'total_hours': week_hours,
                    'score_per_hour': week_total_score / week_hours
                })
        
        if not weekly_stats:
            return {
                'target_points': 0.0,
                'avg_score_per_hour': 0.0,
                'weeks_used': 0,
                'confidence': 'low'
            }
        
        # Calculate average score per hour
        avg_score_per_hour = sum(w['score_per_hour'] for w in weekly_stats) / len(weekly_stats)
        
        # Calculate target points
        target_points = goal_hours_per_week * avg_score_per_hour
        
        # Determine confidence
        if len(weekly_stats) >= 4:
            confidence = 'high'
        elif len(weekly_stats) >= 2:
            confidence = 'medium'
        else:
            confidence = 'low'
        
        return {
            'target_points': round(target_points, 1),
            'avg_score_per_hour': round(avg_score_per_hour, 2),
            'weeks_used': len(weekly_stats),
            'confidence': confidence
        }

    def record_weekly_snapshot(
        self,
        user_id: str,
        week_start_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Record a weekly snapshot of productivity metrics for historical tracking.
        
        Args:
            user_id: User ID
            week_start_date: Start date of week to record (default: current week's Monday)
        
        Returns:
            Dict with the recorded entry data
        """
        if week_start_date is None:
            today = date.today()
            week_start_date = today - timedelta(days=today.weekday())
        
        # Get weekly data
        weekly_data = self.calculate_weekly_productivity_hours(user_id, week_start_date)
        actual_hours = weekly_data.get('total_hours', 0.0)
        
        # Get goal hours
        goal_settings = self.user_state.get_productivity_goal_settings(user_id)
        goal_hours = goal_settings.get('goal_hours_per_week', 40.0)
        
        # Calculate productivity score and points for this week
        from .analytics import Analytics
        analytics = Analytics()
        
        # Get completed instances for this week
        instances_df = self._get_completed_instances(user_id)
        if instances_df.empty:
            productivity_score = 0.0
            productivity_points = 0.0
        else:
            # Parse dates
            instances_df['completed_at_dt'] = pd.to_datetime(instances_df['completed_at'], errors='coerce')
            instances_df = instances_df[instances_df['completed_at_dt'].notna()]
            instances_df['completed_date'] = instances_df['completed_at_dt'].dt.date
            
            # Filter to this week
            week_end = week_start_date + timedelta(days=7)
            week_instances = instances_df[
                (instances_df['completed_date'] >= week_start_date) &
                (instances_df['completed_date'] < week_end)
            ].copy()
            
            if week_instances.empty:
                productivity_score = 0.0
                productivity_points = 0.0
            else:
                # Calculate productivity scores (simplified - without complex parameters)
                week_instances['productivity_score'] = week_instances.apply(
                    lambda row: analytics.calculate_productivity_score(
                        row,
                        self_care_tasks_per_day={},
                        weekly_avg_time=0.0,
                        work_play_time_per_day=None,
                        play_penalty_threshold=2.0,
                        productivity_settings=None,
                        weekly_work_summary=None,
                        goal_hours_per_week=goal_hours if goal_hours > 0 else None,
                        weekly_productive_hours=actual_hours if actual_hours > 0 else None
                    ),
                    axis=1
                )
                
                productivity_score = week_instances['productivity_score'].fillna(0).sum()
                
                # Productivity points = productivity score (they're the same metric)
                productivity_points = productivity_score
        
        # Record in history
        week_start_str = week_start_date.isoformat()
        self.user_state.add_productivity_history_entry(
            user_id,
            week_start_str,
            goal_hours,
            actual_hours,
            productivity_score,
            productivity_points
        )
        
        return {
            'week_start': week_start_str,
            'goal_hours': goal_hours,
            'actual_hours': actual_hours,
            'productivity_score': productivity_score,
            'productivity_points': productivity_points
        }
    
    def get_productivity_history(
        self,
        user_id: str,
        weeks: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get historical productivity tracking data.
        
        Args:
            user_id: User ID
            weeks: Optional number of recent weeks to return (default: all)
        
        Returns:
            List of weekly snapshots, sorted by week_start (oldest first)
        """
        history = self.user_state.get_productivity_history(user_id)
        
        if weeks is not None and weeks > 0:
            # Return last N weeks
            history = history[-weeks:]
        
        return history
    
    def get_or_record_current_week(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Get current week's snapshot from history, or record it if missing.
        
        Args:
            user_id: User ID
        
        Returns:
            Current week's snapshot data
        """
        today = date.today()
        current_week_start = today - timedelta(days=today.weekday())
        week_start_str = current_week_start.isoformat()
        
        # Check if we already have this week's data
        history = self.get_productivity_history(user_id)
        for entry in history:
            if entry.get('week_start') == week_start_str:
                return entry
        
        # Record current week if not found
        return self.record_weekly_snapshot(user_id, current_week_start)
    
    def calculate_baseline_productivity_score(
        self,
        completion_pct: float,
        task_type: str,
        time_actual_minutes: float = 0.0,
        time_estimate_minutes: float = 0.0,
        self_care_tasks_today: int = 1
    ) -> Dict[str, Any]:
        """Calculate baseline productivity score (prioritizes baseline formula).
        
        This is the core formula without optional enhancements:
        score = completion_pct × task_type_multiplier
        
        Args:
            completion_pct: Completion percentage (0-100)
            task_type: Task type ('work', 'self_care', 'play', etc.)
            time_actual_minutes: Actual time taken in minutes
            time_estimate_minutes: Estimated time in minutes
            self_care_tasks_today: Number of self care tasks completed today (for self care multiplier)
            
        Returns:
            Dict with:
            - baseline_score (float): Calculated baseline score
            - multiplier (float): Task type multiplier used
            - completion_time_ratio (float): Ratio used for work task multiplier calculation
            - formula_breakdown (str): Human-readable formula breakdown
        """
        # Calculate completion/time ratio
        if time_estimate_minutes > 0 and time_actual_minutes > 0:
            completion_time_ratio = (completion_pct * time_estimate_minutes) / (100.0 * time_actual_minutes)
        else:
            completion_time_ratio = 1.0
        
        # Normalize task type
        task_type_lower = str(task_type).strip().lower()
        
        # Calculate multiplier based on task type
        if task_type_lower == 'work':
            # Work: 3.0x to 5.0x based on completion/time ratio
            if completion_time_ratio <= 1.0:
                multiplier = 3.0
            elif completion_time_ratio >= 1.5:
                multiplier = 5.0
            else:
                # Smooth transition between 1.0 and 1.5
                smooth_factor = (completion_time_ratio - 1.0) / 0.5
                multiplier = 3.0 + (2.0 * smooth_factor)
            baseline_score = completion_pct * multiplier
            formula_breakdown = f"Work task: {completion_pct:.0f}% × {multiplier:.2f}x (ratio: {completion_time_ratio:.2f}) = {baseline_score:.2f}"
        
        elif task_type_lower in ['self care', 'selfcare', 'self-care']:
            # Self care: multiplier = number of self care tasks today
            multiplier = float(self_care_tasks_today)
            baseline_score = completion_pct * multiplier
            formula_breakdown = f"Self care task: {completion_pct:.0f}% × {multiplier:.1f}x (tasks today: {self_care_tasks_today}) = {baseline_score:.2f}"
        
        elif task_type_lower == 'play':
            # Play: neutral (no multiplier in baseline)
            multiplier = 1.0
            baseline_score = completion_pct * multiplier
            formula_breakdown = f"Play task: {completion_pct:.0f}% × {multiplier:.1f}x (neutral) = {baseline_score:.2f}"
        
        else:
            # Default: no multiplier
            multiplier = 1.0
            baseline_score = completion_pct * multiplier
            formula_breakdown = f"Default task: {completion_pct:.0f}% × {multiplier:.1f}x = {baseline_score:.2f}"
        
        return {
            'baseline_score': round(baseline_score, 2),
            'multiplier': round(multiplier, 2),
            'completion_time_ratio': round(completion_time_ratio, 2),
            'formula_breakdown': formula_breakdown
        }
    
    def calculate_productivity_score_with_enhancements(
        self,
        baseline_score: float,
        time_estimate_minutes: Optional[float] = None,
        time_actual_minutes: Optional[float] = None,
        completion_percentage: Optional[float] = None,
        weekly_curve: str = 'flattened_square',
        weekly_curve_strength: float = 1.0,
        goal_hours_per_week: Optional[float] = None,
        weekly_productive_hours: Optional[float] = None
    ) -> Dict[str, Any]:
        """Apply optional enhancements to baseline productivity score.
        
        Args:
            baseline_score: Baseline score from calculate_baseline_productivity_score
            time_estimate_minutes: Optional estimated time for the task (for efficiency calculation)
            time_actual_minutes: Optional actual time taken (for efficiency calculation)
            completion_percentage: Optional completion percentage (for efficiency calculation)
            weekly_curve: Curve type ('linear' or 'flattened_square')
            weekly_curve_strength: Strength of efficiency adjustment (0.0-2.0)
            goal_hours_per_week: Optional goal hours for goal-based adjustment
            weekly_productive_hours: Optional actual hours for goal comparison
            
        Returns:
            Dict with:
            - final_score (float): Score after enhancements
            - baseline_score (float): Original baseline score
            - enhancements_applied (List[str]): List of enhancements applied
            - enhancement_details (Dict): Details of each enhancement
        """
        import math
        
        final_score = baseline_score
        enhancements_applied = []
        enhancement_details = {}
        
        # Efficiency bonus/penalty (based on task estimate and completion percentage)
        # Uses completion_time_ratio which accounts for both completion % and time
        if time_estimate_minutes is not None and time_estimate_minutes > 0 and time_actual_minutes is not None and time_actual_minutes > 0:
            completion_pct = completion_percentage or 100.0
            # Calculate completion_time_ratio
            completion_time_ratio = (completion_pct * time_estimate_minutes) / (100.0 * time_actual_minutes)
            efficiency_ratio = completion_time_ratio
            efficiency_percentage_diff = (efficiency_ratio - 1.0) * 100.0
            
            if weekly_curve == 'flattened_square':
                # Invert: positive diff (efficient) should give bonus, negative (inefficient) should give penalty
                effect = math.copysign((abs(efficiency_percentage_diff) ** 2) / 100.0, efficiency_percentage_diff)
                efficiency_multiplier = 1.0 - (0.01 * weekly_curve_strength * -effect)
            else:
                # Linear - Invert: positive diff (efficient) should give bonus, negative (inefficient) should give penalty
                efficiency_multiplier = 1.0 - (0.01 * weekly_curve_strength * -efficiency_percentage_diff)
            
            # Cap both penalty and bonus to prevent extreme scores
            # Penalty: max 50% reduction (min multiplier = 0.5)
            # Bonus: max 50% increase (max multiplier = 1.5)
            efficiency_multiplier = max(0.5, min(1.5, efficiency_multiplier))
            
            final_score = final_score * efficiency_multiplier
            enhancements_applied.append('efficiency_bonus')
            enhancement_details['efficiency_bonus'] = {
                'multiplier': round(efficiency_multiplier, 3),
                'efficiency_ratio': round(efficiency_ratio, 3),
                'completion_time_ratio': round(completion_time_ratio, 3),
                'description': f"Efficiency adjustment: {efficiency_multiplier:.3f}x (ratio: {efficiency_ratio:.3f}, {efficiency_percentage_diff:+.1f}% from perfect)"
            }
        
        # Goal-based adjustment
        if goal_hours_per_week is not None and goal_hours_per_week > 0 and weekly_productive_hours is not None:
            goal_achievement_ratio = weekly_productive_hours / goal_hours_per_week
            
            if goal_achievement_ratio >= 1.2:
                goal_multiplier = 1.2
            elif goal_achievement_ratio >= 1.0:
                goal_multiplier = 1.0 + (goal_achievement_ratio - 1.0) * 1.0
            elif goal_achievement_ratio >= 0.8:
                goal_multiplier = 0.9 + (goal_achievement_ratio - 0.8) * 0.5
            else:
                goal_multiplier = 0.8 + (goal_achievement_ratio / 0.8) * 0.1
                goal_multiplier = max(0.8, goal_multiplier)
            
            final_score = final_score * goal_multiplier
            enhancements_applied.append('goal_adjustment')
            enhancement_details['goal_adjustment'] = {
                'multiplier': round(goal_multiplier, 3),
                'achievement_ratio': round(goal_achievement_ratio, 2),
                'description': f"Goal adjustment: {goal_multiplier:.3f}x ({goal_achievement_ratio*100:.1f}% of goal)"
            }
        
        return {
            'final_score': round(final_score, 2),
            'baseline_score': round(baseline_score, 2),
            'enhancements_applied': enhancements_applied,
            'enhancement_details': enhancement_details
        }

