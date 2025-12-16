# backend/gap_detector.py
"""
Gap Detection System for Task Aversion App
Detects temporal gaps in data collection and provides user options for handling them.
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PREFERENCES_FILE = os.path.join(DATA_DIR, 'user_preferences.csv')


class GapDetector:
    """Detects and manages data gaps in task instance collection."""
    
    def __init__(self, gap_threshold_days: int = 7):
        """
        Initialize gap detector.
        
        Args:
            gap_threshold_days: Minimum gap duration in days to be considered significant (default: 7)
        """
        self.gap_threshold_days = gap_threshold_days
        self.instances_file = os.path.join(DATA_DIR, 'task_instances.csv')
        self.preferences_file = PREFERENCES_FILE
    
    def load_instances(self) -> pd.DataFrame:
        """Load task instances from CSV."""
        if not os.path.exists(self.instances_file):
            return pd.DataFrame()
        
        df = pd.read_csv(self.instances_file, dtype=str, low_memory=False)
        if 'created_at' in df.columns:
            df['created_at_parsed'] = pd.to_datetime(df['created_at'], errors='coerce')
        return df
    
    def detect_gaps(self, instances: Optional[pd.DataFrame] = None) -> List[Dict]:
        """
        Detect temporal gaps in task instance data.
        
        Args:
            instances: Optional dataframe of instances. If None, loads from file.
            
        Returns:
            List of gap dictionaries with keys: gap_days, gap_start, gap_end, 
            instances_before, instances_after
        """
        if instances is None:
            instances = self.load_instances()
        
        if instances.empty or 'created_at_parsed' not in instances.columns:
            return []
        
        # Sort by creation date
        instances = instances.sort_values('created_at_parsed').dropna(subset=['created_at_parsed'])
        
        if len(instances) < 2:
            return []
        
        # Calculate gaps between consecutive instances
        instances['gap_days'] = instances['created_at_parsed'].diff().dt.total_seconds() / 86400
        
        # Find significant gaps
        large_gaps = instances[instances['gap_days'] > self.gap_threshold_days].copy()
        
        gaps = []
        for idx, row in large_gaps.iterrows():
            gap_start = instances.loc[instances.index < idx, 'created_at_parsed'].max()
            gap_end = row['created_at_parsed']
            
            gap_info = {
                'gap_days': round(row['gap_days'], 1),
                'gap_start': gap_start,
                'gap_end': gap_end,
                'instances_before': len(instances[instances.index < idx]),
                'instances_after': len(instances[instances.index > idx]),
                'gap_start_str': gap_start.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(gap_start) else None,
                'gap_end_str': gap_end.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(gap_end) else None
            }
            gaps.append(gap_info)
        
        return gaps
    
    def get_largest_gap(self, instances: Optional[pd.DataFrame] = None) -> Optional[Dict]:
        """Get the largest gap detected."""
        gaps = self.detect_gaps(instances)
        if not gaps:
            return None
        return max(gaps, key=lambda x: x['gap_days'])
    
    def has_gap(self, instances: Optional[pd.DataFrame] = None) -> bool:
        """Check if any significant gaps exist."""
        return len(self.detect_gaps(instances)) > 0
    
    def get_gap_handling_preference(self) -> Optional[str]:
        """
        Get user's gap handling preference.
        
        Returns:
            'continue_as_is', 'fresh_start', or None if not set
        """
        if not os.path.exists(self.preferences_file):
            return None
        
        try:
            prefs_df = pd.read_csv(self.preferences_file, dtype=str)
            if 'gap_handling' in prefs_df.columns and len(prefs_df) > 0:
                return prefs_df.iloc[0]['gap_handling']
        except Exception:
            pass
        
        return None
    
    def set_gap_handling_preference(self, preference: str):
        """
        Set user's gap handling preference.
        
        Args:
            preference: 'continue_as_is' or 'fresh_start'
        """
        if preference not in ['continue_as_is', 'fresh_start']:
            raise ValueError(f"Invalid preference: {preference}. Must be 'continue_as_is' or 'fresh_start'")
        
        # Load or create preferences
        if os.path.exists(self.preferences_file):
            try:
                prefs_df = pd.read_csv(self.preferences_file, dtype=str)
            except Exception:
                prefs_df = pd.DataFrame()
        else:
            prefs_df = pd.DataFrame()
        
        # Ensure gap_handling column exists
        if 'gap_handling' not in prefs_df.columns:
            prefs_df['gap_handling'] = None
        
        # Set preference (update first row or create new)
        if len(prefs_df) == 0:
            prefs_df = pd.DataFrame([{'gap_handling': preference}])
        else:
            prefs_df.at[0, 'gap_handling'] = preference
        
        # Save
        os.makedirs(os.path.dirname(self.preferences_file), exist_ok=True)
        prefs_df.to_csv(self.preferences_file, index=False)
    
    def needs_gap_decision(self) -> bool:
        """Check if user needs to make a gap handling decision."""
        if self.get_gap_handling_preference() is not None:
            return False  # Already decided
        return self.has_gap()
    
    def get_gap_summary(self, instances: Optional[pd.DataFrame] = None) -> Dict:
        """
        Get summary of gap information for display.
        
        Returns:
            Dictionary with gap information and recommendations
        """
        gaps = self.detect_gaps(instances)
        largest_gap = self.get_largest_gap(instances)
        preference = self.get_gap_handling_preference()
        
        return {
            'has_gaps': len(gaps) > 0,
            'gap_count': len(gaps),
            'gaps': gaps,
            'largest_gap': largest_gap,
            'preference': preference,
            'needs_decision': self.needs_gap_decision()
        }

