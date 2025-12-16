# backend/data_archival.py
"""
Data Archival System
Handles archiving pre-gap data and calculating summary statistics.
"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional

from .gap_detector import GapDetector

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
ARCHIVE_DIR = os.path.join(DATA_DIR, 'archived')


class DataArchival:
    """Handles archiving and summarizing pre-gap data."""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        self.archive_dir = ARCHIVE_DIR
        self.gap_detector = GapDetector()
        os.makedirs(self.archive_dir, exist_ok=True)
    
    def get_gap_date(self) -> Optional[datetime]:
        """Get the end date of the largest gap (start of post-gap period)."""
        largest_gap = self.gap_detector.get_largest_gap()
        if not largest_gap:
            return None
        return largest_gap['gap_end']
    
    def load_instances(self) -> pd.DataFrame:
        """Load task instances."""
        instances_file = os.path.join(self.data_dir, 'task_instances.csv')
        if not os.path.exists(instances_file):
            return pd.DataFrame()
        
        df = pd.read_csv(instances_file, dtype=str, low_memory=False)
        if 'created_at' in df.columns:
            df['created_at_parsed'] = pd.to_datetime(df['created_at'], errors='coerce')
        return df
    
    def load_tasks(self) -> pd.DataFrame:
        """Load tasks."""
        tasks_file = os.path.join(self.data_dir, 'tasks.csv')
        if not os.path.exists(tasks_file):
            return pd.DataFrame()
        return pd.read_csv(tasks_file, dtype=str, low_memory=False)
    
    def calculate_pre_gap_averages(self, instances: pd.DataFrame, gap_date: datetime) -> Dict:
        """Calculate averages from pre-gap data."""
        pre_gap = instances[instances['created_at_parsed'] < gap_date].copy()
        
        if len(pre_gap) == 0:
            return {}
        
        # Parse JSON columns
        def _safe_json(x):
            if pd.isna(x) or x == '':
                return {}
            try:
                if isinstance(x, str):
                    return json.loads(x)
                return x if isinstance(x, dict) else {}
            except:
                return {}
        
        pre_gap['actual_parsed'] = pre_gap['actual'].apply(_safe_json) if 'actual' in pre_gap.columns else pd.Series([{}] * len(pre_gap))
        pre_gap['predicted_parsed'] = pre_gap['predicted'].apply(_safe_json) if 'predicted' in pre_gap.columns else pd.Series([{}] * len(pre_gap))
        
        # Get completed instances
        completed = pre_gap[pre_gap['is_completed'].str.lower() == 'true'] if 'is_completed' in pre_gap.columns else pre_gap
        
        # Extract metrics
        relief_values = []
        cognitive_values = []
        emotional_values = []
        stress_values = []
        
        for idx, row in completed.iterrows():
            actual_dict = row.get('actual_parsed', {}) if isinstance(row.get('actual_parsed'), dict) else {}
            
            # Relief
            relief = actual_dict.get('actual_relief') or actual_dict.get('relief')
            if relief is not None:
                if 0 <= relief <= 10:
                    relief = relief * 10
                relief_values.append(relief)
            
            # Cognitive
            cognitive = actual_dict.get('actual_cognitive') or actual_dict.get('cognitive_load')
            if cognitive is not None:
                if 0 <= cognitive <= 10:
                    cognitive = cognitive * 10
                cognitive_values.append(cognitive)
            
            # Emotional
            emotional = actual_dict.get('actual_emotional') or actual_dict.get('emotional_load')
            if emotional is not None:
                if 0 <= emotional <= 10:
                    emotional = emotional * 10
                emotional_values.append(emotional)
        
        # Calculate stress (average of cognitive + emotional)
        for idx, row in completed.iterrows():
            actual_dict = row.get('actual_parsed', {}) if isinstance(row.get('actual_parsed'), dict) else {}
            cognitive = actual_dict.get('actual_cognitive') or actual_dict.get('cognitive_load', 0)
            emotional = actual_dict.get('actual_emotional') or actual_dict.get('emotional_load', 0)
            
            if isinstance(cognitive, (int, float)) and isinstance(emotional, (int, float)):
                if 0 <= cognitive <= 10:
                    cognitive = cognitive * 10
                if 0 <= emotional <= 10:
                    emotional = emotional * 10
                stress = (cognitive + emotional) / 2
                stress_values.append(stress)
        
        # Calculate averages
        averages = {
            'total_instances': len(pre_gap),
            'completed_instances': len(completed),
            'date_range': {
                'start': pre_gap['created_at_parsed'].min().isoformat() if 'created_at_parsed' in pre_gap.columns else None,
                'end': pre_gap['created_at_parsed'].max().isoformat() if 'created_at_parsed' in pre_gap.columns else None
            },
            'averages': {
                'relief': {
                    'mean': sum(relief_values) / len(relief_values) if relief_values else None,
                    'count': len(relief_values),
                    'min': min(relief_values) if relief_values else None,
                    'max': max(relief_values) if relief_values else None
                },
                'cognitive_load': {
                    'mean': sum(cognitive_values) / len(cognitive_values) if cognitive_values else None,
                    'count': len(cognitive_values),
                    'min': min(cognitive_values) if cognitive_values else None,
                    'max': max(cognitive_values) if cognitive_values else None
                },
                'emotional_load': {
                    'mean': sum(emotional_values) / len(emotional_values) if emotional_values else None,
                    'count': len(emotional_values),
                    'min': min(emotional_values) if emotional_values else None,
                    'max': max(emotional_values) if emotional_values else None
                },
                'stress_level': {
                    'mean': sum(stress_values) / len(stress_values) if stress_values else None,
                    'count': len(stress_values),
                    'min': min(stress_values) if stress_values else None,
                    'max': max(stress_values) if stress_values else None
                }
            },
            'task_breakdown': {}
        }
        
        # Task-specific averages
        if 'task_id' in completed.columns:
            for task_id in completed['task_id'].dropna().unique():
                task_instances = completed[completed['task_id'] == task_id]
                task_relief = []
                task_cognitive = []
                task_emotional = []
                
                for idx, row in task_instances.iterrows():
                    actual_dict = row.get('actual_parsed', {}) if isinstance(row.get('actual_parsed'), dict) else {}
                    
                    relief = actual_dict.get('actual_relief') or actual_dict.get('relief')
                    if relief is not None:
                        if 0 <= relief <= 10:
                            relief = relief * 10
                        task_relief.append(relief)
                    
                    cognitive = actual_dict.get('actual_cognitive') or actual_dict.get('cognitive_load')
                    if cognitive is not None:
                        if 0 <= cognitive <= 10:
                            cognitive = cognitive * 10
                        task_cognitive.append(cognitive)
                    
                    emotional = actual_dict.get('actual_emotional') or actual_dict.get('emotional_load')
                    if emotional is not None:
                        if 0 <= emotional <= 10:
                            emotional = emotional * 10
                        task_emotional.append(emotional)
                
                if task_relief or task_cognitive or task_emotional:
                    averages['task_breakdown'][task_id] = {
                        'relief_mean': sum(task_relief) / len(task_relief) if task_relief else None,
                        'cognitive_mean': sum(task_cognitive) / len(task_cognitive) if task_cognitive else None,
                        'emotional_mean': sum(task_emotional) / len(task_emotional) if task_emotional else None,
                        'instance_count': len(task_instances)
                    }
        
        return averages
    
    def archive_pre_gap_data(self):
        """Archive pre-gap data and create summary."""
        gap_date = self.get_gap_date()
        if not gap_date:
            raise ValueError("No gap detected. Cannot archive pre-gap data.")
        
        instances = self.load_instances()
        tasks = self.load_tasks()
        
        if instances.empty:
            raise ValueError("No instances to archive.")
        
        # Split data
        pre_gap_instances = instances[instances['created_at_parsed'] < gap_date].copy() if 'created_at_parsed' in instances.columns else pd.DataFrame()
        post_gap_instances = instances[instances['created_at_parsed'] >= gap_date].copy() if 'created_at_parsed' in instances.columns else instances.copy()
        
        # Calculate averages
        averages = self.calculate_pre_gap_averages(instances, gap_date)
        
        # Create archive timestamp
        archive_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_subdir = os.path.join(self.archive_dir, f'pre_gap_{archive_timestamp}')
        os.makedirs(archive_subdir, exist_ok=True)
        
        # Save archived data
        if not pre_gap_instances.empty:
            pre_gap_instances.to_csv(
                os.path.join(archive_subdir, 'task_instances.csv'),
                index=False
            )
        
        # Save averages summary
        with open(os.path.join(archive_subdir, 'averages_summary.json'), 'w') as f:
            json.dump(averages, f, indent=2, default=str)
        
        # Save metadata
        metadata = {
            'archive_date': datetime.now().isoformat(),
            'gap_end_date': gap_date.isoformat(),
            'pre_gap_instances': len(pre_gap_instances),
            'post_gap_instances': len(post_gap_instances),
            'archive_location': archive_subdir
        }
        
        with open(os.path.join(archive_subdir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        # Update active instances file (keep only post-gap)
        instances_file = os.path.join(self.data_dir, 'task_instances.csv')
        if not post_gap_instances.empty:
            # Remove parsed column before saving
            if 'created_at_parsed' in post_gap_instances.columns:
                post_gap_instances = post_gap_instances.drop(columns=['created_at_parsed'])
            post_gap_instances.to_csv(instances_file, index=False)
        else:
            # If no post-gap data, keep a minimal structure
            empty_df = pd.DataFrame(columns=instances.columns)
            empty_df.to_csv(instances_file, index=False)
        
        # Save averages to main data directory for easy access
        averages_file = os.path.join(self.data_dir, 'pre_gap_averages.json')
        with open(averages_file, 'w') as f:
            json.dump(averages, f, indent=2, default=str)
        
        return {
            'archive_location': archive_subdir,
            'averages': averages,
            'metadata': metadata
        }

