#!/usr/bin/env python3
"""
Debug script to show productivity score breakdown for each task instance.
Shows which tasks are contributing positive/negative scores and why.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List

# Add the task_aversion_app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.analytics import Analytics
from backend.task_manager import TaskManager

def safe_get(d: dict, key: str, default=None):
    """Safely get value from dict, handling None."""
    if not isinstance(d, dict):
        return default
    return d.get(key, default)

def format_dict(d: dict) -> str:
    """Format dict for display."""
    if not isinstance(d, dict):
        return str(d)
    return json.dumps(d, indent=2, default=str)

def main():
    print("=" * 80)
    print("PRODUCTIVITY SCORE DEBUG REPORT")
    print("=" * 80)
    print()
    
    # Initialize managers
    analytics = Analytics()
    task_manager = TaskManager()
    
    # Load all instances (using analytics method which handles both DB and CSV)
    # Get user_id for data isolation
    from backend.auth import get_current_user
    user_id = get_current_user()
    
    print("[INFO] Loading task instances...")
    df = analytics._load_instances(user_id=user_id)
    
    if df.empty:
        print("[ERROR] No task instances found!")
        return
    
    print(f"[INFO] Found {len(df)} total task instances")
    
    # Load tasks to get task_type
    # Note: Debug script - using user_id=None for analysis across all data
    tasks_df = task_manager.get_all(user_id=None)
    if not tasks_df.empty and 'task_type' in tasks_df.columns:
        df = df.merge(
            tasks_df[['task_id', 'task_type', 'name']],
            on='task_id',
            how='left'
        )
        df['task_type'] = df['task_type'].fillna('Work')
    else:
        df['task_type'] = 'Work'
        df['name'] = df.get('task_name', 'Unknown')
    
    # Filter to completed/cancelled tasks (those with completed_at or cancelled_at)
    has_completion = (
        df['completed_at'].astype(str).str.len() > 0
    ) | (
        df['cancelled_at'].astype(str).str.len() > 0
    )
    completed = df[has_completion].copy()
    
    print(f"[INFO] Found {len(completed)} completed/cancelled task instances")
    print()
    
    if completed.empty:
        print("[WARNING] No completed or cancelled tasks found!")
        return
    
    # Parse JSON fields
    def _safe_json(cell):
        if isinstance(cell, dict):
            return cell
        if pd.isna(cell) or cell == '':
            return {}
        try:
            return json.loads(cell) if isinstance(cell, str) else {}
        except:
            return {}
    
    completed['actual_dict'] = completed['actual'].apply(_safe_json)
    completed['predicted_dict'] = completed['predicted'].apply(_safe_json)
    
    # Get status
    completed['status'] = completed.apply(
        lambda row: 'cancelled' if str(row.get('cancelled_at', '')).strip() else 'completed',
        axis=1
    )
    
    # Prepare data for productivity score calculation
    # Count self care tasks per day
    self_care_tasks_per_day = {}
    completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
    self_care_tasks = completed[
        completed['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
    ].copy()
    if not self_care_tasks.empty:
        self_care_tasks['completed_at_dt'] = pd.to_datetime(self_care_tasks['completed_at'], errors='coerce')
        self_care_tasks = self_care_tasks[self_care_tasks['completed_at_dt'].notna()]
        if not self_care_tasks.empty:
            self_care_tasks['date'] = self_care_tasks['completed_at_dt'].dt.date
            daily_counts = self_care_tasks.groupby('date').size()
            for date, count in daily_counts.items():
                self_care_tasks_per_day[date.isoformat()] = int(count)
    
    # Calculate work/play time per day
    work_play_time_per_day = {}
    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
    valid_for_work_play = completed[
        completed['completed_at_dt'].notna()
    ].copy()
    
    if not valid_for_work_play.empty:
        def _get_actual_time(row):
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, dict):
                return float(actual_dict.get('time_actual_minutes', 0) or 0)
            return 0.0
        valid_for_work_play['time_for_work_play'] = valid_for_work_play.apply(_get_actual_time, axis=1)
        valid_for_work_play = valid_for_work_play[valid_for_work_play['time_for_work_play'] > 0]
        
        if not valid_for_work_play.empty:
            valid_for_work_play['date'] = valid_for_work_play['completed_at_dt'].dt.date
            for date, group in valid_for_work_play.groupby('date'):
                date_str = date.isoformat()
                work_time = group[group['task_type_normalized'] == 'work']['time_for_work_play'].sum()
                play_time = group[group['task_type_normalized'] == 'play']['time_for_work_play'].sum()
                work_play_time_per_day[date_str] = {
                    'work_time': float(work_time),
                    'play_time': float(play_time)
                }
    
    # Calculate weekly average
    def _get_actual_time_for_avg(row):
        actual_dict = row.get('actual_dict', {})
        if isinstance(actual_dict, dict):
            return actual_dict.get('time_actual_minutes', None)
        return None
    
    completed['time_actual_for_avg'] = completed.apply(_get_actual_time_for_avg, axis=1)
    completed['time_actual_for_avg'] = pd.to_numeric(completed['time_actual_for_avg'], errors='coerce')
    valid_times = completed[completed['time_actual_for_avg'].notna() & (completed['time_actual_for_avg'] > 0)]
    weekly_avg_time = valid_times['time_actual_for_avg'].mean() if not valid_times.empty else 0.0
    
    # Calculate weekly work summary
    weekly_work_summary = {}
    if work_play_time_per_day:
        total_work_time = sum(day.get('work_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
        total_play_time = sum(day.get('play_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
        days_count = len(work_play_time_per_day)
        weekly_work_summary = {
            'total_work_time_minutes': float(total_work_time),
            'total_play_time_minutes': float(total_play_time),
            'days_count': int(days_count),
        }
    
    print(f"[INFO] Weekly average time: {weekly_avg_time:.1f} minutes")
    print(f"[INFO] Work/play time per day: {len(work_play_time_per_day)} days")
    print()
    
    # Calculate productivity score for each task
    print("=" * 80)
    print("TASK-BY-TASK PRODUCTIVITY SCORE BREAKDOWN")
    print("=" * 80)
    print()
    
    scores = []
    total_score = 0.0
    
    # Sort by completed_at (most recent first)
    completed['sort_date'] = pd.to_datetime(completed['completed_at'], errors='coerce')
    completed = completed.sort_values('sort_date', ascending=False, na_position='last')
    
    for idx, row in completed.iterrows():
        try:
            score = analytics.calculate_productivity_score(
                row,
                self_care_tasks_per_day,
                weekly_avg_time,
                work_play_time_per_day,
                productivity_settings=analytics.productivity_settings,
                weekly_work_summary=weekly_work_summary,
                goal_hours_per_week=None,
                weekly_productive_hours=None
            )
            
            # Get task details
            task_name = row.get('name', row.get('task_name', 'Unknown'))
            task_type = row.get('task_type', 'Work')
            status = row.get('status', 'completed')
            completed_at = row.get('completed_at', '')
            cancelled_at = row.get('cancelled_at', '')
            
            # Get time estimates
            predicted_dict = row.get('predicted_dict', {})
            actual_dict = row.get('actual_dict', {})
            
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            
            # Get cancellation details if cancelled
            cancellation_category = None
            penalty_multiplier = None
            if status == 'cancelled':
                cancellation_category = actual_dict.get('cancellation_category', 'other')
                from backend.user_state import UserStateManager
                user_state = UserStateManager()
                penalties = user_state.get_cancellation_penalties("default_user")
                if not penalties:
                    default_penalties = {
                        'development_test': 0.0,
                        'accidental_initialization': 0.0,
                        'deferred_to_plan': 0.1,
                        'did_while_another_active': 0.0,
                        'failed_to_complete': 0.3,
                        'other': 0.5
                    }
                    penalty_multiplier = default_penalties.get(cancellation_category, 0.5)
                else:
                    penalty_multiplier = penalties.get(cancellation_category, 0.5)
            
            scores.append({
                'task_name': task_name,
                'task_type': task_type,
                'status': status,
                'completed_at': completed_at,
                'cancelled_at': cancelled_at,
                'time_estimate': time_estimate,
                'time_actual': time_actual,
                'completion_pct': completion_pct,
                'productivity_score': score,
                'cancellation_category': cancellation_category,
                'penalty_multiplier': penalty_multiplier
            })
            
            total_score += score
            
        except Exception as e:
            print(f"[ERROR] Failed to calculate score for task {row.get('task_name', 'Unknown')}: {e}")
            import traceback
            traceback.print_exc()
    
    # Sort by score (most negative first, then most positive)
    scores.sort(key=lambda x: x['productivity_score'])
    
    # Print summary
    print(f"TOTAL PRODUCTIVITY SCORE: {total_score:.2f}")
    print()
    
    # Group by status
    cancelled_scores = [s for s in scores if s['status'] == 'cancelled']
    completed_scores = [s for s in scores if s['status'] == 'completed']
    
    cancelled_total = sum(s['productivity_score'] for s in cancelled_scores)
    completed_total = sum(s['productivity_score'] for s in completed_scores)
    
    print(f"  From completed tasks: {completed_total:.2f} ({len(completed_scores)} tasks)")
    print(f"  From cancelled tasks: {cancelled_total:.2f} ({len(cancelled_scores)} tasks)")
    print()
    
    # Show cancelled tasks first (these are likely the problem)
    if cancelled_scores:
        print("=" * 80)
        print("CANCELLED TASKS (Negative Scores)")
        print("=" * 80)
        print()
        
        for s in cancelled_scores:
            print(f"Task: {s['task_name']}")
            print(f"  Type: {s['task_type']}")
            print(f"  Cancelled at: {s['cancelled_at']}")
            print(f"  Category: {s['cancellation_category']}")
            print(f"  Time estimate: {s['time_estimate']:.1f} minutes")
            print(f"  Penalty multiplier: {s['penalty_multiplier']}")
            print(f"  Productivity score: {s['productivity_score']:.2f}")
            if s['penalty_multiplier']:
                expected_penalty = -(s['time_estimate'] / 10.0) * s['penalty_multiplier']
                print(f"  Expected penalty: {expected_penalty:.2f} (calculated as: -(time_estimate/10) * multiplier)")
            print()
    
    # Show top negative completed tasks
    negative_completed = [s for s in completed_scores if s['productivity_score'] < 0]
    if negative_completed:
        print("=" * 80)
        print("COMPLETED TASKS WITH NEGATIVE SCORES")
        print("=" * 80)
        print()
        
        for s in negative_completed[:10]:  # Show top 10
            print(f"Task: {s['task_name']}")
            print(f"  Type: {s['task_type']}")
            print(f"  Completed at: {s['completed_at']}")
            print(f"  Time estimate: {s['time_estimate']:.1f} minutes")
            print(f"  Time actual: {s['time_actual']:.1f} minutes")
            print(f"  Completion %: {s['completion_pct']:.1f}%")
            print(f"  Productivity score: {s['productivity_score']:.2f}")
            print()
    
    # Show top positive completed tasks
    positive_completed = [s for s in completed_scores if s['productivity_score'] > 0]
    if positive_completed:
        print("=" * 80)
        print(f"TOP 10 POSITIVE SCORING TASKS")
        print("=" * 80)
        print()
        
        # Sort by score descending
        positive_completed.sort(key=lambda x: x['productivity_score'], reverse=True)
        
        for s in positive_completed[:10]:
            print(f"Task: {s['task_name']}")
            print(f"  Type: {s['task_type']}")
            print(f"  Completed at: {s['completed_at']}")
            print(f"  Time estimate: {s['time_estimate']:.1f} minutes")
            print(f"  Time actual: {s['time_actual']:.1f} minutes")
            print(f"  Completion %: {s['completion_pct']:.1f}%")
            print(f"  Productivity score: {s['productivity_score']:.2f}")
            print()
    
    # Show recent tasks (last 7 days)
    print("=" * 80)
    print("RECENT TASKS (Last 7 Days)")
    print("=" * 80)
    print()
    
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_scores = []
    for s in scores:
        try:
            date_str = s['completed_at'] or s['cancelled_at']
            if date_str:
                task_date = pd.to_datetime(date_str, errors='coerce')
                if pd.notna(task_date) and task_date >= seven_days_ago:
                    recent_scores.append(s)
        except:
            pass
    
    if recent_scores:
        recent_total = sum(s['productivity_score'] for s in recent_scores)
        print(f"Total score from last 7 days: {recent_total:.2f} ({len(recent_scores)} tasks)")
        print()
        
        for s in recent_scores:
            status_marker = "[CANCELLED]" if s['status'] == 'cancelled' else "[COMPLETED]"
            print(f"{status_marker} {s['task_name']} ({s['task_type']})")
            print(f"  Date: {s['completed_at'] or s['cancelled_at']}")
            print(f"  Score: {s['productivity_score']:.2f}")
            if s['status'] == 'cancelled':
                print(f"  Category: {s['cancellation_category']}, Penalty: {s['penalty_multiplier']}")
            print()
    else:
        print("No tasks found in the last 7 days.")
    
    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)

if __name__ == '__main__':
    main()
