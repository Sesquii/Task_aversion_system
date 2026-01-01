#!/usr/bin/env python3
"""
Analyze productivity scores for December 14th specifically.
Compares old vs new efficiency calculation to identify anomalies.
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
import math

# Add the task_aversion_app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.analytics import Analytics
from backend.task_manager import TaskManager

def calculate_old_efficiency_multiplier(time_actual, time_estimate, weekly_avg_time, completion_pct, curve_type='flattened_square', strength=1.0):
    """Calculate efficiency multiplier using OLD method (weekly average comparison)."""
    if weekly_avg_time > 0 and time_actual > 0:
        time_percentage_diff = ((time_actual - weekly_avg_time) / weekly_avg_time) * 100.0
        if curve_type == 'flattened_square':
            effect = math.copysign((abs(time_percentage_diff) ** 2) / 100.0, time_percentage_diff)
            multiplier = 1.0 - (0.01 * strength * effect)
        else:
            multiplier = 1.0 - (0.01 * strength * time_percentage_diff)
        return multiplier
    return 1.0

def calculate_new_efficiency_multiplier(time_actual, time_estimate, completion_pct, curve_type='flattened_square', strength=1.0):
    """Calculate efficiency multiplier using NEW method (task estimate comparison)."""
    if time_estimate > 0 and time_actual > 0:
        completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
        efficiency_ratio = completion_time_ratio
        efficiency_percentage_diff = (efficiency_ratio - 1.0) * 100.0
        
        if curve_type == 'flattened_square':
            effect = math.copysign((abs(efficiency_percentage_diff) ** 2) / 100.0, efficiency_percentage_diff)
            multiplier = 1.0 - (0.01 * strength * -effect)
        else:
            multiplier = 1.0 - (0.01 * strength * -efficiency_percentage_diff)
        
        return max(0.5, multiplier)
    return 1.0

def main():
    print("=" * 80)
    print("DECEMBER 14TH PRODUCTIVITY SCORE ANALYSIS")
    print("=" * 80)
    print()
    
    # Initialize managers
    analytics = Analytics()
    task_manager = TaskManager()
    
    # Load all instances
    print("[INFO] Loading task instances...")
    df = analytics._load_instances()
    
    if df.empty:
        print("[ERROR] No task instances found!")
        return
    
    # Load tasks to get task_type
    tasks_df = task_manager.get_all()
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
    
    # Filter to December 14th tasks
    target_date = '2025-12-14'
    df['completed_at_dt'] = pd.to_datetime(df['completed_at'], errors='coerce')
    df['date_str'] = df['completed_at_dt'].dt.date.astype(str)
    
    dec14_tasks = df[df['date_str'] == target_date].copy()
    
    if dec14_tasks.empty:
        print(f"[WARNING] No tasks found for {target_date}")
        return
    
    print(f"[INFO] Found {len(dec14_tasks)} tasks on {target_date}")
    print()
    
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
    
    dec14_tasks['actual_dict'] = dec14_tasks['actual'].apply(_safe_json)
    dec14_tasks['predicted_dict'] = dec14_tasks['predicted'].apply(_safe_json)
    
    # Get weekly average for old calculation
    all_completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
    all_completed['actual_dict'] = all_completed['actual'].apply(_safe_json)
    
    def _get_actual_time(row):
        actual_dict = row.get('actual_dict', {})
        if isinstance(actual_dict, dict):
            return actual_dict.get('time_actual_minutes', None)
        return None
    
    all_completed['time_actual_for_avg'] = all_completed.apply(_get_actual_time, axis=1)
    all_completed['time_actual_for_avg'] = pd.to_numeric(all_completed['time_actual_for_avg'], errors='coerce')
    valid_times = all_completed[all_completed['time_actual_for_avg'].notna() & (all_completed['time_actual_for_avg'] > 0)]
    weekly_avg_time = valid_times['time_actual_for_avg'].mean() if not valid_times.empty else 0.0
    
    print(f"[INFO] Weekly average time: {weekly_avg_time:.1f} minutes")
    print()
    
    # Prepare data for productivity score calculation
    self_care_tasks_per_day = {}
    work_play_time_per_day = {}
    
    # Calculate work/play time per day
    all_completed['completed_at_dt'] = pd.to_datetime(all_completed['completed_at'], errors='coerce')
    valid_for_work_play = all_completed[all_completed['completed_at_dt'].notna()].copy()
    valid_for_work_play['time_for_work_play'] = valid_for_work_play.apply(_get_actual_time, axis=1)
    valid_for_work_play = valid_for_work_play[valid_for_work_play['time_for_work_play'] > 0]
    
    if not valid_for_work_play.empty:
        valid_for_work_play['date'] = valid_for_work_play['completed_at_dt'].dt.date
        for date, group in valid_for_work_play.groupby('date'):
            date_str = date.isoformat()
            work_time = group[group['task_type'].str.lower() == 'work']['time_for_work_play'].sum()
            play_time = group[group['task_type'].str.lower() == 'play']['time_for_work_play'].sum()
            work_play_time_per_day[date_str] = {
                'work_time': float(work_time),
                'play_time': float(play_time)
            }
    
    # Calculate weekly work summary
    weekly_work_summary = {}
    if work_play_time_per_day:
        total_work_time = sum(day.get('work_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
        days_count = len(work_play_time_per_day)
        weekly_work_summary = {
            'total_work_time_minutes': float(total_work_time),
            'days_count': int(days_count),
        }
    
    print("=" * 80)
    print(f"TASKS ON {target_date} - DETAILED BREAKDOWN")
    print("=" * 80)
    print()
    
    total_old_score = 0.0
    total_new_score = 0.0
    
    for idx, row in dec14_tasks.iterrows():
        try:
            # Get task details
            task_name = row.get('name', row.get('task_name', 'Unknown'))
            task_type = row.get('task_type', 'Work')
            completed_at = row.get('completed_at', '')
            
            # Get time estimates
            predicted_dict = row.get('predicted_dict', {})
            actual_dict = row.get('actual_dict', {})
            
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            
            # Calculate completion_time_ratio
            if time_estimate > 0 and time_actual > 0:
                completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
            else:
                completion_time_ratio = 1.0
            
            # Calculate productivity score using NEW method
            new_score = analytics.calculate_productivity_score(
                row,
                self_care_tasks_per_day,
                weekly_avg_time,
                work_play_time_per_day,
                productivity_settings=analytics.productivity_settings,
                weekly_work_summary=weekly_work_summary,
                goal_hours_per_week=None,
                weekly_productive_hours=None
            )
            
            # Calculate what the score would be with OLD method
            # First, calculate base score (same for both)
            task_type_lower = str(task_type).strip().lower()
            if task_type_lower == 'work':
                if completion_time_ratio <= 1.0:
                    base_multiplier = 3.0
                elif completion_time_ratio >= 1.5:
                    base_multiplier = 5.0
                else:
                    smooth_factor = (completion_time_ratio - 1.0) / 0.5
                    base_multiplier = 3.0 + (2.0 * smooth_factor)
                base_score = completion_pct * base_multiplier
            elif task_type_lower in ['self care', 'selfcare', 'self-care']:
                try:
                    completed_date = pd.to_datetime(completed_at).date()
                    date_str = completed_date.isoformat()
                    base_multiplier = float(self_care_tasks_per_day.get(date_str, 1))
                except:
                    base_multiplier = 1.0
                base_score = completion_pct * base_multiplier
            else:
                base_score = completion_pct
            
            # Apply OLD efficiency multiplier (weekly average comparison)
            old_efficiency_mult = calculate_old_efficiency_multiplier(
                time_actual, time_estimate, weekly_avg_time, completion_pct,
                curve_type='flattened_square', strength=1.0
            )
            old_score = base_score * old_efficiency_mult
            
            # Apply NEW efficiency multiplier (task estimate comparison)
            new_efficiency_mult = calculate_new_efficiency_multiplier(
                time_actual, time_estimate, completion_pct,
                curve_type='flattened_square', strength=1.0
            )
            new_score_calc = base_score * new_efficiency_mult
            
            total_old_score += old_score
            total_new_score += new_score
            
            print(f"Task: {task_name}")
            print(f"  Type: {task_type}")
            print(f"  Time estimate: {time_estimate:.1f} min")
            print(f"  Time actual: {time_actual:.1f} min")
            print(f"  Completion %: {completion_pct:.1f}%")
            print(f"  Completion_time_ratio: {completion_time_ratio:.3f}")
            print(f"  Base score: {base_score:.2f} (completion_pct × type_multiplier)")
            print()
            print(f"  OLD METHOD (weekly avg comparison):")
            print(f"    Weekly avg: {weekly_avg_time:.1f} min")
            print(f"    Time diff from avg: {((time_actual - weekly_avg_time) / weekly_avg_time * 100) if weekly_avg_time > 0 else 0:.1f}%")
            print(f"    Efficiency multiplier: {old_efficiency_mult:.3f}")
            print(f"    Score: {old_score:.2f}")
            print()
            print(f"  NEW METHOD (task estimate comparison):")
            print(f"    Efficiency ratio: {completion_time_ratio:.3f}")
            print(f"    Efficiency multiplier: {new_efficiency_mult:.3f}")
            print(f"    Score (calculated): {new_score_calc:.2f}")
            print(f"    Score (actual): {new_score:.2f}")
            print(f"    Difference: {new_score - old_score:+.2f}")
            print()
            print("-" * 80)
            print()
            
        except Exception as e:
            print(f"[ERROR] Failed to analyze task {row.get('task_name', 'Unknown')}: {e}")
            import traceback
            traceback.print_exc()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tasks on {target_date}: {len(dec14_tasks)}")
    print(f"Total score (OLD method): {total_old_score:.2f}")
    print(f"Total score (NEW method): {total_new_score:.2f}")
    print(f"Difference: {total_new_score - total_old_score:+.2f}")
    print()

if __name__ == '__main__':
    main()
