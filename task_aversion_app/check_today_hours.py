#!/usr/bin/env python3
"""Check today's productivity hours from the database."""
import os
import sys
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set database URL if not already set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

from backend.database import get_session, TaskInstance
from backend.task_manager import TaskManager

def check_today_hours():
    """Check hours worked today."""
    session = get_session()
    today = date.today()
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    try:
        # Get all completed instances
        instances = session.query(TaskInstance).filter(
            TaskInstance.is_completed == True,
            TaskInstance.completed_at.isnot(None)
        ).all()
        
        print(f"\n{'='*60}")
        print(f"PRODUCTIVITY HOURS CHECK - {today}")
        print(f"{'='*60}\n")
        print(f"Total completed instances in database: {len(instances)}\n")
        
        # Filter to today's instances
        today_instances = [i for i in instances if i.completed_at and i.completed_at.date() == today]
        print(f"Today's completed instances: {len(today_instances)}\n")
        
        # Get task types for filtering
        task_manager = TaskManager()
        tasks_df = task_manager.get_all()
        task_type_map = {}
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            for _, row in tasks_df.iterrows():
                task_id = row.get('task_id', '')
                task_type = row.get('task_type', 'Work')
                task_type_map[task_id] = task_type
        
        # Calculate productivity time (Work and Self care tasks only)
        total_minutes = 0
        productivity_instances = []
        
        for inst in today_instances:
            # Get time from actual dict or duration_minutes column
            actual = inst.actual or {}
            time_min = actual.get('time_actual_minutes', None)
            if time_min is None:
                time_min = inst.duration_minutes
            
            if time_min is None or time_min == 0:
                continue
            
            # Get task type
            task_type = task_type_map.get(inst.task_id, 'Work')
            task_type_normalized = str(task_type).strip().lower()
            
            # Only count Work and Self care tasks for productivity
            if task_type_normalized in ['work', 'self care', 'selfcare', 'self-care']:
                total_minutes += float(time_min or 0)
                productivity_instances.append({
                    'task_name': inst.task_name,
                    'task_type': task_type,
                    'time_minutes': float(time_min or 0),
                    'completed_at': inst.completed_at
                })
        
        # Print today's instances
        if productivity_instances:
            print("Today's productivity tasks:")
            print("-" * 60)
            for inst in productivity_instances:
                print(f"  {inst['task_name']} ({inst['task_type']})")
                print(f"    Time: {inst['time_minutes']:.1f} minutes ({inst['time_minutes']/60:.2f} hours)")
                print(f"    Completed: {inst['completed_at']}")
                print()
        else:
            print("No productivity tasks completed today.\n")
        
        print(f"TOTAL PRODUCTIVITY TIME TODAY:")
        print(f"  {total_minutes:.1f} minutes ({total_minutes/60:.2f} hours)")
        print()
        
        # Also check last 7 days for context
        last_7d_instances = [i for i in instances if i.completed_at and i.completed_at >= seven_days_ago]
        last_7d_minutes = 0
        
        for inst in last_7d_instances:
            actual = inst.actual or {}
            time_min = actual.get('time_actual_minutes', None)
            if time_min is None:
                time_min = inst.duration_minutes
            
            if time_min is None or time_min == 0:
                continue
            
            task_type = task_type_map.get(inst.task_id, 'Work')
            task_type_normalized = str(task_type).strip().lower()
            
            if task_type_normalized in ['work', 'self care', 'selfcare', 'self-care']:
                last_7d_minutes += float(time_min or 0)
        
        print(f"Last 7 days productivity time: {last_7d_minutes:.1f} minutes ({last_7d_minutes/60:.2f} hours)")
        print(f"Average per day: {last_7d_minutes/7:.1f} minutes ({last_7d_minutes/7/60:.2f} hours)")
        print()
        
        # Show instances by date for debugging
        print("Completed instances by date (last 7 days):")
        print("-" * 60)
        date_groups = {}
        for inst in last_7d_instances:
            inst_date = inst.completed_at.date()
            if inst_date not in date_groups:
                date_groups[inst_date] = []
            date_groups[inst_date].append(inst)
        
        for inst_date in sorted(date_groups.keys(), reverse=True):
            insts = date_groups[inst_date]
            total_day_minutes = 0
            for inst in insts:
                actual = inst.actual or {}
                time_min = actual.get('time_actual_minutes', None) or inst.duration_minutes or 0
                task_type = task_type_map.get(inst.task_id, 'Work')
                task_type_normalized = str(task_type).strip().lower()
                if task_type_normalized in ['work', 'self care', 'selfcare', 'self-care']:
                    total_day_minutes += float(time_min or 0)
            
            date_label = "TODAY" if inst_date == today else str(inst_date)
            print(f"{date_label}: {len(insts)} instances, {total_day_minutes:.1f} min ({total_day_minutes/60:.2f} hrs)")
        
        print(f"\n{'='*60}\n")
        
    finally:
        session.close()

if __name__ == '__main__':
    check_today_hours()
