#!/usr/bin/env python3
"""Export database data to CSV files."""
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set database URL if not already set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

import pandas as pd
from backend.database import get_session, Task, TaskInstance, Emotion

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def export_to_csv():
    """Export all database tables to CSV files."""
    session = get_session()
    
    try:
        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        
        print(f"[Export] Exporting database data to CSV files in {DATA_DIR}...\n")
        
        # Export Tasks
        try:
            tasks = session.query(Task).all()
            if tasks:
                tasks_data = [task.to_dict() for task in tasks]
                tasks_df = pd.DataFrame(tasks_data)
                tasks_file = os.path.join(DATA_DIR, 'tasks.csv')
                tasks_df.to_csv(tasks_file, index=False)
                print(f"[Export] Exported {len(tasks_data)} tasks to {tasks_file}")
            else:
                print("[Export] No tasks found in database")
        except Exception as e:
            print(f"[Export] Error exporting tasks: {e}")
        
        # Export Task Instances
        try:
            instances = session.query(TaskInstance).all()
            if instances:
                instances_data = [instance.to_dict() for instance in instances]
                instances_df = pd.DataFrame(instances_data)
                instances_file = os.path.join(DATA_DIR, 'task_instances.csv')
                instances_df.to_csv(instances_file, index=False)
                print(f"[Export] Exported {len(instances_data)} task instances to {instances_file}")
            else:
                print("[Export] No task instances found in database")
        except Exception as e:
            print(f"[Export] Error exporting task instances: {e}")
        
        # Export Emotions
        try:
            emotions = session.query(Emotion).all()
            if emotions:
                emotions_data = [emotion.to_dict() for emotion in emotions]
                emotions_df = pd.DataFrame(emotions_data)
                emotions_file = os.path.join(DATA_DIR, 'emotions.csv')
                emotions_df.to_csv(emotions_file, index=False)
                print(f"[Export] Exported {len(emotions_data)} emotions to {emotions_file}")
            else:
                print("[Export] No emotions found in database")
        except Exception as e:
            print(f"[Export] Error exporting emotions: {e}")
        
        print(f"\n[Export] Export complete!")
        print(f"[Export] CSV files saved to: {DATA_DIR}")
        
    except Exception as e:
        print(f"[Export] Error during export: {e}")
        raise
    finally:
        session.close()

if __name__ == '__main__':
    export_to_csv()
