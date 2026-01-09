#!/usr/bin/env python
"""
Analyze existing tasks and their descriptions to help with prioritization.
Shows task definitions, initialization patterns, and usage statistics.
"""
import os
import sys
from datetime import datetime
from collections import defaultdict, Counter

# Set up path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set DATABASE_URL if not set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

from backend.database import get_session, Task, TaskInstance, init_db
from backend.task_manager import TaskManager

def format_text(text, max_length=100):
    """Format text for display, truncating if too long."""
    if not text:
        return "(no description)"
    text = str(text).strip()
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

def analyze_tasks():
    """Analyze all tasks and their usage patterns."""
    print("=" * 80)
    print("TASK ANALYSIS REPORT")
    print("=" * 80)
    print()
    
    # Initialize database
    init_db()
    
    # Get all tasks
    with get_session() as session:
        all_tasks = session.query(Task).order_by(Task.created_at.desc()).all()
        all_instances = session.query(TaskInstance).all()
    
    if not all_tasks:
        print("[INFO] No tasks found in database.")
        return
    
    print(f"Total Tasks: {len(all_tasks)}")
    print(f"Total Task Instances: {len(all_instances)}")
    print()
    
    # Group instances by task_id
    instances_by_task = defaultdict(list)
    for instance in all_instances:
        instances_by_task[instance.task_id].append(instance)
    
    # Count statistics
    initialized_tasks = set()
    completed_tasks = set()
    active_tasks = set()
    
    for instance in all_instances:
        if instance.initialized_at:
            initialized_tasks.add(instance.task_id)
        if instance.is_completed:
            completed_tasks.add(instance.task_id)
        if instance.status == 'active' and not instance.is_completed:
            active_tasks.add(instance.task_id)
    
    print("=" * 80)
    print("TASK USAGE STATISTICS")
    print("=" * 80)
    print(f"Tasks with initialized instances: {len(initialized_tasks)}")
    print(f"Tasks with completed instances: {len(completed_tasks)}")
    print(f"Tasks with active instances: {len(active_tasks)}")
    print(f"Tasks never initialized: {len(all_tasks) - len(initialized_tasks)}")
    print()
    
    # Task type breakdown
    task_types = Counter(task.task_type for task in all_tasks)
    print("Task Type Breakdown:")
    for task_type, count in task_types.most_common():
        print(f"  {task_type}: {count}")
    print()
    
    # Recurring vs one-time
    recurring_count = sum(1 for task in all_tasks if task.is_recurring)
    print(f"Recurring tasks: {recurring_count}")
    print(f"One-time tasks: {len(all_tasks) - recurring_count}")
    print()
    
    print("=" * 80)
    print("ALL TASKS WITH DESCRIPTIONS")
    print("=" * 80)
    print()
    
    # Sort tasks: initialized first, then by creation date
    def sort_key(task):
        has_instances = task.task_id in initialized_tasks
        return (not has_instances, task.created_at or datetime.min)
    
    sorted_tasks = sorted(all_tasks, key=sort_key)
    
    for idx, task in enumerate(sorted_tasks, 1):
        instances = instances_by_task.get(task.task_id, [])
        initialized_count = sum(1 for i in instances if i.initialized_at)
        completed_count = sum(1 for i in instances if i.is_completed)
        active_count = sum(1 for i in instances if i.status == 'active' and not i.is_completed)
        
        # Status indicator
        status_indicators = []
        if task.task_id in initialized_tasks:
            status_indicators.append("[INITIALIZED]")
        if task.task_id in completed_tasks:
            status_indicators.append("[COMPLETED]")
        if task.task_id in active_tasks:
            status_indicators.append("[ACTIVE]")
        if not status_indicators:
            status_indicators.append("[NEVER INITIALIZED]")
        
        status_str = " ".join(status_indicators)
        
        print(f"{idx}. {task.name} {status_str}")
        print(f"   Task ID: {task.task_id}")
        print(f"   Type: {task.type} | Task Type: {task.task_type} | Recurring: {task.is_recurring}")
        print(f"   Instances: {len(instances)} total ({initialized_count} initialized, {completed_count} completed, {active_count} active)")
        
        # Description
        description = format_text(task.description, max_length=200)
        print(f"   Description: {description}")
        
        # Additional details if available
        if task.categories:
            cats = task.categories if isinstance(task.categories, list) else []
            if cats:
                print(f"   Categories: {', '.join(cats)}")
        
        if task.default_estimate_minutes:
            print(f"   Default Estimate: {task.default_estimate_minutes} minutes")
        
        if task.routine_frequency and task.routine_frequency != 'none':
            print(f"   Routine: {task.routine_frequency} at {task.routine_time}")
        
        if task.notes:
            notes = format_text(task.notes, max_length=150)
            print(f"   Notes: {notes}")
        
        print()
    
    print("=" * 80)
    print("TASKS BY INITIALIZATION STATUS")
    print("=" * 80)
    print()
    
    # Never initialized
    never_initialized = [t for t in all_tasks if t.task_id not in initialized_tasks]
    if never_initialized:
        print(f"NEVER INITIALIZED ({len(never_initialized)} tasks):")
        for task in never_initialized:
            print(f"  - {task.name} ({task.task_type})")
            desc = format_text(task.description, max_length=80)
            if desc != "(no description)":
                print(f"    {desc}")
        print()
    
    # Most used tasks
    task_usage = [(task, len(instances_by_task.get(task.task_id, []))) for task in all_tasks]
    task_usage.sort(key=lambda x: x[1], reverse=True)
    
    print("MOST USED TASKS (by instance count):")
    for task, count in task_usage[:10]:
        print(f"  {task.name}: {count} instances")
    print()
    
    # Tasks with descriptions vs without
    with_desc = [t for t in all_tasks if t.description and t.description.strip()]
    without_desc = [t for t in all_tasks if not t.description or not t.description.strip()]
    
    print("=" * 80)
    print("DESCRIPTION COVERAGE")
    print("=" * 80)
    print(f"Tasks with descriptions: {len(with_desc)}")
    print(f"Tasks without descriptions: {len(without_desc)}")
    
    if without_desc:
        print("\nTasks missing descriptions:")
        for task in without_desc:
            print(f"  - {task.name} ({task.task_type})")
    print()

if __name__ == '__main__':
    try:
        analyze_tasks()
    except Exception as e:
        print(f"[ERROR] Failed to analyze tasks: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
