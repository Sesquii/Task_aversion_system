# backend/analytics.py
from __future__ import annotations

import copy
import json
import math
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import warnings
# Suppress pandas warnings that flood the terminal
# FutureWarning about downcasting in fillna operations
warnings.filterwarnings('ignore', category=FutureWarning, message='.*Downcasting.*')
# SettingWithCopyWarning about modifying DataFrame slices (pandas raises this as a generic Warning)
warnings.filterwarnings('ignore', message='.*SettingWithCopyWarning.*')
warnings.filterwarnings('ignore', message='.*A value is trying to be set on a copy of a slice.*')
from scipy import stats

from .task_schema import TASK_ATTRIBUTES, attribute_defaults
from .gap_detector import GapDetector
from .user_state import UserStateManager

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# Execution Score Formula Version
EXECUTION_SCORE_VERSION = '1.2'

# Productivity Score Formula Version
PRODUCTIVITY_SCORE_VERSION = '1.1'


class Analytics:
    """Central analytics + lightweight recommendation helper."""
    
    # Note: All inputs now use 0-100 scale natively.
    # Old data may have 0-10 scale values, but we use them as-is (no scaling).
    # This is acceptable since old 0-10 data was only used for a short time.
    
    # Cache for expensive operations
    # User-specific caches: {user_id: cache_value}
    _relief_summary_cache = {}  # {user_id: cache_value}
    _relief_summary_cache_time = {}  # {user_id: timestamp}
    _composite_scores_cache = {}  # {user_id: cache_value}
    _composite_scores_cache_time = {}  # {user_id: timestamp}
    _cache_ttl_seconds = 300  # Cache for 5 minutes (optimized for dashboard performance)
    
    # Cache for _load_instances() - separate caches for all vs completed_only, keyed by user_id
    _instances_cache_all = {}  # {user_id: cache_value}
    _instances_cache_all_time = {}  # {user_id: timestamp}
    _instances_cache_completed = {}  # {user_id: cache_value}
    _instances_cache_completed_time = {}  # {user_id: timestamp}
    
    # Cache for get_dashboard_metrics(), keyed by user_id
    _dashboard_metrics_cache = {}  # {user_id: cache_value}
    _dashboard_metrics_cache_time = {}  # {user_id: timestamp}
    
    # Cache for calculate_time_tracking_consistency_score(), keyed by user_id
    _time_tracking_cache = {}  # {user_id: cache_value}
    _time_tracking_cache_time = {}  # {user_id: timestamp}
    _time_tracking_cache_params = {}  # {user_id: (days, target_sleep_hours)} - Store params to invalidate on param change
    
    # Cache for chart data methods, keyed by user_id
    _trend_series_cache = {}  # {user_id: cache_value}
    _trend_series_cache_time = {}  # {user_id: timestamp}
    _attribute_distribution_cache = {}  # {user_id: cache_value}
    _attribute_distribution_cache_time = {}  # {user_id: timestamp}
    _stress_dimension_cache = {}  # {user_id: cache_value}
    _stress_dimension_cache_time = {}  # {user_id: timestamp}
    
    # Cache for rankings (keyed by user_id, then metric/top_n)
    _rankings_cache = {}  # {user_id: {(metric, top_n): (result, timestamp)}}
    _leaderboard_cache = {}  # {user_id: cache_value}
    _leaderboard_cache_time = {}  # {user_id: timestamp}
    _leaderboard_cache_top_n = {}  # {user_id: top_n}
    
    @staticmethod
    def calculate_difficulty_bonus(
        current_aversion: Optional[float],
        stress_level: Optional[float] = None,
        mental_energy: Optional[float] = None,
        task_difficulty: Optional[float] = None
    ) -> float:
        """Calculate difficulty bonus based on aversion and task load.
        
        Rewards completing difficult tasks (high aversion + high load).
        Uses exponential scaling with flat/low exponent for smooth curve.
        Higher weight to aversion (0.7) vs load (0.3).
        
        Formula: bonus = 1.0 * (1 - exp(-(w_aversion * aversion + w_load * load) / k))
        - Max bonus = 1.0 (so multiplier ranges 1.0 to 2.0)
        - Uses exponential decay for smooth, diminishing returns curve
        
        Args:
            current_aversion: Current aversion value (0-100) or None
            stress_level: Stress level (0-100) or None (preferred if available)
            mental_energy: Mental energy needed (0-100) or None
            task_difficulty: Task difficulty (0-100) or None
        
        Returns:
            Difficulty bonus (0.0 to 1.0), where 1.0 = 100% bonus = 2x multiplier
        """
        import math
        
        if current_aversion is None:
            return 0.0
        
        # Normalize aversion to 0-100
        aversion = max(0.0, min(100.0, float(current_aversion)))
        
        # Calculate load (prefer stress_level, fallback to mental_energy + task_difficulty)
        load = 0.0
        if stress_level is not None:
            load = max(0.0, min(100.0, float(stress_level)))
        elif mental_energy is not None or task_difficulty is not None:
            mental = max(0.0, min(100.0, float(mental_energy))) if mental_energy is not None else 50.0
            difficulty = max(0.0, min(100.0, float(task_difficulty))) if task_difficulty is not None else 50.0
            load = (mental + difficulty) / 2.0
        
        # Weights: aversion gets higher weight (0.7) vs load (0.3)
        w_aversion = 0.7
        w_load = 0.3
        
        # Combined difficulty score
        combined_difficulty = (w_aversion * aversion) + (w_load * load)
        
        # Exponential decay formula: 1 - exp(-x/k)
        # k = 50.0 provides smooth curve that approaches 1.0 at high difficulty
        k = 50.0
        difficulty_bonus = 1.0 * (1.0 - math.exp(-combined_difficulty / k))
        
        # Clamp to 0.0 - 1.0 (max bonus = 1.0 = 100% = 2x multiplier)
        return max(0.0, min(1.0, difficulty_bonus))
    
    @staticmethod
    def calculate_improvement_multiplier(
        initial_aversion: Optional[float],
        current_aversion: Optional[float]
    ) -> float:
        """Calculate improvement multiplier based on aversion reduction over time.
        
        Uses exponential decay formula for logarithmic scaling that shows
        diminishing returns (early improvements count more).
        
        Formula: improvement_bonus = 1.0 * (1 - exp(-improvement / k))
        - Max bonus = 1.0 (so multiplier ranges 1.0 to 2.0)
        - k = 30.0 provides smooth curve (tuning parameter)
        
        Args:
            initial_aversion: Initial aversion value (0-100) from first time doing task, or None
            current_aversion: Current aversion value (0-100), or None
        
        Returns:
            Improvement bonus (0.0 to 1.0), where 1.0 = 100% bonus = 2x multiplier
        """
        import math
        
        if initial_aversion is None or current_aversion is None:
            return 0.0
        
        # Normalize to 0-100
        initial = max(0.0, min(100.0, float(initial_aversion)))
        current = max(0.0, min(100.0, float(current_aversion)))
        
        # Calculate improvement (positive = reduced aversion = better)
        improvement = initial - current
        
        if improvement <= 0:
            return 0.0
        
        # Exponential decay formula: 1 - exp(-improvement / k)
        # k = 30.0 provides smooth curve that approaches 1.0 at high improvement
        k = 30.0
        improvement_bonus = 1.0 * (1.0 - math.exp(-improvement / k))
        
        # Clamp to 0.0 - 1.0 (max bonus = 1.0 = 100% = 2x multiplier)
        return max(0.0, min(1.0, improvement_bonus))
    
    @staticmethod
    def calculate_overall_improvement_ratio(
        current_self_care_per_day: float,
        avg_self_care_per_day: float,
        current_relief_score: Optional[float],
        avg_relief_score: float,
        high_performing_metrics: Optional[Dict[str, float]] = None,
        poor_performing_metrics: Optional[Dict[str, float]] = None,
        metric_weights: Optional[Dict[str, float]] = None
    ) -> float:
        """Calculate overarching improvement ratio from multiple performance factors.
        
        Combines:
        1. Self-care frequency improvement (more self-care than average)
        2. Relief score improvement (higher relief than average)
        3. Overall performance balance (high-performing vs poor-performing metrics)
        
        Formula uses exponential decay for smooth scaling with max bonus = 1.0.
        
        Args:
            current_self_care_per_day: Current self-care tasks per day
            avg_self_care_per_day: Average self-care tasks per day (baseline)
            current_relief_score: Current relief score (0-100) or None
            avg_relief_score: Average relief score (baseline, 0-100)
            high_performing_metrics: Dict of metric_name -> value for metrics performing well
            poor_performing_metrics: Dict of metric_name -> value for metrics performing poorly
            metric_weights: Optional weights for each metric (default: equal weights)
        
        Returns:
            Overall improvement ratio (0.0 to 1.0), where 1.0 = 100% bonus = 2x multiplier
        """
        import math
        
        if avg_self_care_per_day <= 0:
            avg_self_care_per_day = 1.0  # Avoid division by zero
        
        # 1. Self-care frequency improvement
        # Improvement = (current - average) / average (percentage improvement)
        self_care_improvement = (current_self_care_per_day - avg_self_care_per_day) / avg_self_care_per_day
        # Only positive improvements count (doing more than average)
        self_care_improvement = max(0.0, self_care_improvement)
        # Scale to 0-100 range for consistency (cap at 200% improvement = 2x average)
        self_care_normalized = min(100.0, self_care_improvement * 100.0)
        
        # 2. Relief score improvement
        relief_improvement = 0.0
        if current_relief_score is not None:
            relief_diff = current_relief_score - avg_relief_score
            # Only positive improvements count (higher relief than average)
            relief_improvement = max(0.0, relief_diff)
            # Already in 0-100 range
        
        # 3. Overall performance balance
        performance_balance = 0.0
        if high_performing_metrics or poor_performing_metrics:
            high_score = 0.0
            poor_score = 0.0
            
            # Calculate weighted high-performing score
            if high_performing_metrics:
                weights = metric_weights or {}
                total_weight = 0.0
                for metric_name, value in high_performing_metrics.items():
                    weight = weights.get(metric_name, 1.0)
                    # Normalize value to 0-100 if needed (assuming metrics are 0-100 scale)
                    normalized_value = max(0.0, min(100.0, float(value)))
                    high_score += normalized_value * weight
                    total_weight += weight
                if total_weight > 0:
                    high_score = high_score / total_weight
            
            # Calculate weighted poor-performing score
            if poor_performing_metrics:
                weights = metric_weights or {}
                total_weight = 0.0
                for metric_name, value in poor_performing_metrics.items():
                    weight = weights.get(metric_name, 1.0)
                    # Normalize value to 0-100 if needed
                    normalized_value = max(0.0, min(100.0, float(value)))
                    poor_score += normalized_value * weight
                    total_weight += weight
                if total_weight > 0:
                    poor_score = poor_score / total_weight
            
            # Balance = high_score - poor_score (positive = better performance)
            # Normalize to 0-100 range
            performance_balance = max(0.0, min(100.0, high_score - poor_score + 50.0))
        
        # Combine improvements with weights
        # Weights: self-care (0.3), relief (0.4), performance balance (0.3)
        w_self_care = 0.3
        w_relief = 0.4
        w_performance = 0.3
        
        # Weighted average of improvements
        combined_improvement = (
            (self_care_normalized * w_self_care) +
            (relief_improvement * w_relief) +
            (performance_balance * w_performance)
        )
        
        # Exponential decay formula: 1 - exp(-improvement / k)
        # k = 40.0 provides smooth curve that approaches 1.0 at high improvement
        k = 40.0
        improvement_ratio = 1.0 * (1.0 - math.exp(-combined_improvement / k))
        
        # Clamp to 0.0 - 1.0 (max bonus = 1.0 = 100% = 2x multiplier)
        return max(0.0, min(1.0, improvement_ratio))
    
    def calculate_overall_improvement_from_instance(
        self,
        row: pd.Series,
        avg_self_care_per_day: float,
        avg_relief_score: float,
        completed_instances: Optional[pd.DataFrame] = None,
        user_id: Optional[int] = None
    ) -> float:
        """Calculate overall improvement ratio from a task instance row.
        
        Helper method that extracts data from a task instance and calculates
        the overall improvement ratio using calculate_overall_improvement_ratio().
        
        Args:
            row: Task instance row with task_type, relief_score, completed_at, etc.
            avg_self_care_per_day: Average self-care tasks per day (baseline)
            avg_relief_score: Average relief score (baseline, 0-100)
            completed_instances: Optional DataFrame of all completed instances for metric calculation
            user_id: User ID for data isolation (required for database mode)
        
        Returns:
            Overall improvement ratio (0.0 to 1.0)
        """
        # Get user_id if not provided
        if user_id is None:
            user_id = self._get_user_id(user_id)
        
        # Get current self-care count for today
        current_self_care = 0.0
        task_type = str(row.get('task_type', '')).strip().lower()
        completed_at = row.get('completed_at', '')
        
        # If this is a self-care task and we have completion date, count today's self-care tasks
        if task_type in ['self care', 'selfcare', 'self-care'] and completed_at:
            try:
                from datetime import datetime
                completed_date = pd.to_datetime(completed_at).date()
                today = datetime.now().date()
                
                if completed_date == today and completed_instances is not None:
                    # Count self-care tasks completed today
                    completed_instances['completed_at_dt'] = pd.to_datetime(
                        completed_instances['completed_at'], errors='coerce'
                    )
                    today_instances = completed_instances[
                        completed_instances['completed_at_dt'].dt.date == today
                    ]
                    
                    # Get task types for today's instances
                    from .task_manager import TaskManager
                    task_manager = TaskManager()
                    tasks_df = task_manager.get_all(user_id=user_id)
                    
                    if not tasks_df.empty and 'task_type' in tasks_df.columns:
                        today_with_type = today_instances.merge(
                            tasks_df[['task_id', 'task_type']],
                            on='task_id',
                            how='left'
                        )
                        today_with_type['task_type'] = today_with_type['task_type'].fillna('Work')
                        today_with_type['task_type_normalized'] = (
                            today_with_type['task_type'].astype(str).str.strip().str.lower()
                        )
                        self_care_today = today_with_type[
                            today_with_type['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
                        ]
                        current_self_care = float(len(self_care_today))
            except (ValueError, TypeError, AttributeError):
                pass
        
        # Get current relief score
        current_relief = pd.to_numeric(row.get('relief_score', 0), errors='coerce')
        if pd.isna(current_relief):
            current_relief = None
        else:
            current_relief = float(current_relief)
        
        # Calculate high-performing and poor-performing metrics
        high_metrics = {}
        poor_metrics = {}
        
        if completed_instances is not None:
            # Calculate averages for comparison
            completed_instances['relief_score_numeric'] = pd.to_numeric(
                completed_instances['relief_score'], errors='coerce'
            )
            completed_instances['stress_level_numeric'] = pd.to_numeric(
                completed_instances.get('stress_level', 0), errors='coerce'
            )
            completed_instances['net_wellbeing_numeric'] = pd.to_numeric(
                completed_instances.get('net_wellbeing', 0), errors='coerce'
            )
            completed_instances['stress_efficiency_numeric'] = pd.to_numeric(
                completed_instances.get('stress_efficiency', 0), errors='coerce'
            )
            
            # Compare current instance to averages
            avg_stress = completed_instances['stress_level_numeric'].mean() if 'stress_level_numeric' in completed_instances.columns else 50.0
            avg_net_wellbeing = completed_instances['net_wellbeing_numeric'].mean() if 'net_wellbeing_numeric' in completed_instances.columns else 0.0
            avg_stress_efficiency = completed_instances['stress_efficiency_numeric'].mean() if 'stress_efficiency_numeric' in completed_instances.columns else 1.0
            
            # Current values
            current_stress = pd.to_numeric(row.get('stress_level', 0), errors='coerce') or avg_stress
            current_net_wellbeing = pd.to_numeric(row.get('net_wellbeing', 0), errors='coerce') or avg_net_wellbeing
            current_stress_efficiency = pd.to_numeric(row.get('stress_efficiency', 0), errors='coerce') or avg_stress_efficiency
            
            # High-performing: lower stress, higher net wellbeing, higher stress efficiency
            if current_stress < avg_stress:
                high_metrics['stress_level'] = avg_stress - current_stress  # Improvement amount
            if current_net_wellbeing > avg_net_wellbeing:
                high_metrics['net_wellbeing'] = current_net_wellbeing - avg_net_wellbeing
            if current_stress_efficiency > avg_stress_efficiency:
                high_metrics['stress_efficiency'] = current_stress_efficiency - avg_stress_efficiency
            
            # Poor-performing: higher stress, lower net wellbeing, lower stress efficiency
            if current_stress > avg_stress:
                poor_metrics['stress_level'] = current_stress - avg_stress
            if current_net_wellbeing < avg_net_wellbeing:
                poor_metrics['net_wellbeing'] = avg_net_wellbeing - current_net_wellbeing
            if current_stress_efficiency < avg_stress_efficiency:
                poor_metrics['stress_efficiency'] = avg_stress_efficiency - current_stress_efficiency
        
        # Calculate overall improvement ratio
        return self.calculate_overall_improvement_ratio(
            current_self_care_per_day=current_self_care,
            avg_self_care_per_day=avg_self_care_per_day,
            current_relief_score=current_relief,
            avg_relief_score=avg_relief_score,
            high_performing_metrics=high_metrics if high_metrics else None,
            poor_performing_metrics=poor_metrics if poor_metrics else None
        )
    
    @staticmethod
    def calculate_aversion_multiplier(
        initial_aversion: Optional[float],
        current_aversion: Optional[float],
        stress_level: Optional[float] = None,
        mental_energy: Optional[float] = None,
        task_difficulty: Optional[float] = None
    ) -> float:
        """Calculate combined aversion multiplier from difficulty bonus and improvement.
        
        Combines difficulty bonus (rewarding hard tasks) and improvement multiplier
        (rewarding progress over time) into a single multiplier.
        
        Formula: multiplier = 1.0 + difficulty_bonus + improvement_bonus
        - Max multiplier = 2.0 (when both bonuses are 1.0)
        - Min multiplier = 1.0 (when both bonuses are 0.0)
        
        This replaces the old formula that mixed difficulty and improvement incorrectly.
        
        Args:
            initial_aversion: Initial aversion value (0-100) from first time doing task, or None
            current_aversion: Current aversion value (0-100), or None
            stress_level: Stress level (0-100) or None (for difficulty calculation)
            mental_energy: Mental energy needed (0-100) or None (for difficulty calculation)
            task_difficulty: Task difficulty (0-100) or None (for difficulty calculation)
        
        Returns:
            Combined multiplier (1.0 to 2.0)
        """
        # Calculate difficulty bonus (rewards completing difficult tasks)
        difficulty_bonus = Analytics.calculate_difficulty_bonus(
            current_aversion=current_aversion,
            stress_level=stress_level,
            mental_energy=mental_energy,
            task_difficulty=task_difficulty
        )
        
        # Calculate improvement bonus (rewards progress over time)
        # This can be either:
        # 1. Aversion-based improvement (reduced aversion over time)
        # 2. Overall improvement ratio (self-care, relief, performance balance)
        # For now, use aversion-based improvement
        improvement_bonus = Analytics.calculate_improvement_multiplier(
            initial_aversion=initial_aversion,
            current_aversion=current_aversion
        )
        
        # Combine bonuses: use maximum to ensure max bonus = 1.0 (max multiplier = 2.0)
        # This rewards either high difficulty OR high improvement (or both)
        # Alternative: weighted average (0.6 * difficulty + 0.4 * improvement)
        # Using max() ensures we don't exceed 1.0 bonus limit
        total_bonus = max(difficulty_bonus, improvement_bonus)
        
        # If both are significant, add small bonus (diminishing returns)
        if difficulty_bonus > 0.3 and improvement_bonus > 0.3:
            # Small additional bonus when both are present (max 0.1 extra)
            combined_bonus = min(1.0, total_bonus + 0.1)
        else:
            combined_bonus = total_bonus
        
        multiplier = 1.0 + combined_bonus
        
        # Clamp to 1.0 - 2.0 range (max bonus = 1.0 = 100% = 2x multiplier)
        return max(1.0, min(2.0, multiplier))
    
    @staticmethod
    def get_task_type_multiplier(task_type: Optional[str]) -> float:
        """Get task type multiplier for points calculation.
        
        Args:
            task_type: Task type string ('Work', 'Self care', 'Play', etc.)
            
        Returns:
            Multiplier value (work: 1.0, self care: 3.0, play: 0.5, default: 1.0)
        """
        if task_type is None:
            return 1.0
        
        task_type_lower = str(task_type).strip().lower()
        
        if task_type_lower == 'work':
            return 1.0
        elif task_type_lower in ['self care', 'selfcare', 'self-care']:
            return 3.0
        elif task_type_lower == 'play':
            return 0.5
        else:
            return 1.0
    
    def calculate_productivity_score(self, row: pd.Series, self_care_tasks_per_day: Dict[str, int], weekly_avg_time: float = 0.0, 
                                     work_play_time_per_day: Optional[Dict[str, Dict[str, float]]] = None,
                                     play_penalty_threshold: float = 2.0,
                                     productivity_settings: Optional[Dict[str, any]] = None,
                                     weekly_work_summary: Optional[Dict[str, float]] = None,
                                     goal_hours_per_week: Optional[float] = None,
                                     weekly_productive_hours: Optional[float] = None) -> float:
        """Calculate productivity score based on completion percentage vs time ratio.
        
        Version: 1.1 (2025-12-27)
        - Efficiency multiplier now compares to task's own estimate (not weekly average)
        - Accounts for completion percentage in efficiency calculation
        - Penalty capped at 50% reduction to prevent negative scores
        
        See docs/productivity_score_v1.1.md for complete version history.
        
        Penalty Calibration:
        - Play penalty: -0.003x per percentage (max -0.3x for 100% completion = -30 score)
        - Idle penalty: Applied via tracking consistency multiplier (0.0 to 1.0)
          - 50% idle time: ~0.63x multiplier (37% reduction)
          - 75% idle time: ~0.39x multiplier (61% reduction)
          - 100% idle time: 0.0x multiplier (100% reduction)
        - Play penalty is calibrated to be less severe than idle penalty
        - Sleep up to target (8 hours) is excluded from idle time calculation
        
        Args:
            row: Task instance row with actual_dict, predicted_dict, task_type, completed_at
            self_care_tasks_per_day: Dictionary mapping date strings to count of self care tasks completed that day
            weekly_avg_time: Weekly average productivity time in minutes (for bonus/penalty calculation)
            work_play_time_per_day: Dictionary mapping date strings to dict with 'work_time' and 'play_time' in minutes
            play_penalty_threshold: Threshold multiplier for play penalty (default 2.0 = play must exceed work by 2x)
            productivity_settings: Optional productivity settings dict
            weekly_work_summary: Optional weekly work summary dict
            goal_hours_per_week: Optional goal hours per week (if provided, applies goal-based adjustment)
            weekly_productive_hours: Optional weekly productive hours total (required if goal_hours_per_week provided)
            
        Returns:
            Productivity score (can be negative for productivity penalty from play tasks)
        """
        try:
            # Check if task is cancelled and apply cancellation penalty
            status = str(row.get('status', 'active')).lower()
            if status == 'cancelled':
                actual_dict = row.get('actual_dict', {})
                if not isinstance(actual_dict, dict):
                    actual_dict = {}
                
                # Get cancellation category
                cancellation_category = actual_dict.get('cancellation_category', 'other')
                
                # Get penalty multiplier from user settings
                user_state = UserStateManager()
                penalties = user_state.get_cancellation_penalties("default_user")
                
                # Default penalties if not configured
                if not penalties:
                    default_penalties = {
                        'development_test': 0.0,
                        'accidental_initialization': 0.0,
                        'deferred_to_plan': 0.1,
                        'did_while_another_active': 0.0,
                        'failed_to_complete': 1.0,
                        'other': 0.5
                    }
                    penalty_multiplier = default_penalties.get(cancellation_category, 0.5)
                else:
                    penalty_multiplier = penalties.get(cancellation_category, 0.5)
                
                # Get estimated time for the task
                predicted_dict = row.get('predicted_dict', {})
                if not isinstance(predicted_dict, dict):
                    predicted_dict = {}
                time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
                
                # Calculate penalty: negative score based on estimated time and penalty multiplier
                # Base penalty is the estimated time (in minutes), scaled by penalty multiplier
                # Convert to score units (divide by 10 to get reasonable scale)
                penalty_score = -(time_estimate / 10.0) * penalty_multiplier
                
                return penalty_score
            
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_type = row.get('task_type', 'Work')
            completed_at = row.get('completed_at', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            # Get completion percentage and time data
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            
            # Normalize task type
            task_type_lower = str(task_type).strip().lower()
            
            # Calculate completion/time ratio
            # Ratio = (completion_percent / 100) / (time_actual / time_estimate)
            # = (completion_percent * time_estimate) / (100 * time_actual)
            if time_estimate > 0 and time_actual > 0:
                completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
            else:
                # If no time data, assume 1.0 ratio
                completion_time_ratio = 1.0
            
            # Get work/play time for the day (if available)
            work_time_today = 0.0
            play_time_today = 0.0
            if work_play_time_per_day:
                try:
                    completed_date = pd.to_datetime(completed_at).date()
                    date_str = completed_date.isoformat()
                    day_data = work_play_time_per_day.get(date_str, {})
                    work_time_today = float(day_data.get('work_time', 0) or 0)
                    play_time_today = float(day_data.get('play_time', 0) or 0)
                except (ValueError, TypeError, AttributeError):
                    pass
            
            # Load productivity settings (fallback to defaults)
            settings = productivity_settings or self.productivity_settings or {}
            weekly_curve = settings.get('weekly_curve', 'flattened_square')
            weekly_curve_strength = float(settings.get('weekly_curve_strength', 1.0) or 1.0)
            weekly_burnout_threshold_hours = float(settings.get('weekly_burnout_threshold_hours', 42.0) or 42.0)
            daily_burnout_cap_multiplier = float(settings.get('daily_burnout_cap_multiplier', 2.0) or 2.0)

            # Weekly work summary (for burnout logic)
            weekly_total_work = 0.0
            days_count = 0
            if weekly_work_summary:
                weekly_total_work = float(weekly_work_summary.get('total_work_time_minutes', 0.0) or 0.0)
                days_count = int(weekly_work_summary.get('days_count', 0) or 0)

            # Apply multipliers based on task type
            if task_type_lower == 'work':
                # Work: Smooth multiplier transition from 3x to 5x based on completion_time_ratio
                # Smooth transition: 3.0 + (2.0 * smooth_factor) where smooth_factor transitions from 0 to 1
                # Transition happens between ratio 1.0 and 1.5 (smooth over 0.5 range)
                # Cap ratio at 1.5 to prevent extreme multipliers from very fast completions
                capped_ratio = min(completion_time_ratio, 1.5)
                if capped_ratio <= 1.0:
                    multiplier = 3.0
                elif capped_ratio >= 1.5:
                    multiplier = 5.0
                else:
                    # Smooth transition between 1.0 and 1.5
                    smooth_factor = (capped_ratio - 1.0) / 0.5  # 0.0 to 1.0
                    multiplier = 3.0 + (2.0 * smooth_factor)
                
                # Burnout penalty (weekly-first with daily cap)
                # Only apply when weekly total exceeds threshold AND today's work > daily cap
                if weekly_total_work > 0:
                    weekly_threshold_minutes = weekly_burnout_threshold_hours * 60.0
                    days_count = max(days_count, len(work_play_time_per_day or {}) or 1)
                    daily_avg_work = weekly_total_work / float(max(1, days_count))
                    daily_cap = daily_avg_work * daily_burnout_cap_multiplier

                    if (weekly_total_work > weekly_threshold_minutes) and (work_time_today > daily_cap):
                        excess_week = weekly_total_work - weekly_threshold_minutes
                        # Exponential decay on weekly excess; capped to 50% reduction
                        penalty_factor = 1.0 - math.exp(-excess_week / 300.0)
                        multiplier = multiplier * (1.0 - penalty_factor * 0.5)
                
                # Base score is completion percentage
                base_score = completion_pct
                score = base_score * multiplier
            
            elif task_type_lower in ['self care', 'selfcare', 'self-care']:
                # Self care: multiplier = number of self care tasks completed per day
                # Get date from completed_at
                try:
                    completed_date = pd.to_datetime(completed_at).date()
                    date_str = completed_date.isoformat()
                    multiplier = float(self_care_tasks_per_day.get(date_str, 1))
                except (ValueError, TypeError, AttributeError):
                    multiplier = 1.0
                # Base score is completion percentage
                base_score = completion_pct
                score = base_score * multiplier
            
            elif task_type_lower == 'play':
                # Productivity penalty from play: only applies when play exceeds work by threshold
                # Check if play time exceeds work time by the threshold
                if work_time_today > 0:
                    play_work_ratio = play_time_today / work_time_today
                    apply_penalty = play_work_ratio > play_penalty_threshold
                else:
                    # If no work time, apply penalty if play time exists (all play, no work)
                    apply_penalty = play_time_today > 0
                
                if apply_penalty:
                    # Productivity penalty from play: -0.003x multiplier per percentage of time completed compared to estimated time
                    # Percentage = (time_actual / time_estimate) * 100
                    # This creates a negative score (penalty) for play tasks
                    # Calibrated to be less severe than idle penalty: play penalty maxes out at -0.3x for 100% completion,
                    # while idle penalty can reduce productivity by up to 100% (multiplier 0.0) when all time is untracked
                    if time_estimate > 0:
                        time_percentage = (time_actual / time_estimate) * 100.0
                    else:
                        time_percentage = 100.0
                    multiplier = -0.003 * time_percentage
                    # Base score is completion percentage
                    base_score = completion_pct
                    score = base_score * multiplier
                else:
                    # No penalty: play is within acceptable ratio to work
                    # Just use completion percentage (neutral score)
                    score = completion_pct
            
            else:
                # Default: no multiplier
                score = completion_pct
            
            # Apply efficiency bonus/penalty based on completion efficiency
            # Uses completion_time_ratio which accounts for both completion % and time
            # Ratio = (completion_pct * time_estimate) / (100 * time_actual)
            # Ratio > 1.0 = efficient (more completion per unit time)
            # Ratio < 1.0 = inefficient (less completion per unit time)
            # Supports linear (legacy) or flattened square response curves
            # Cap penalty to prevent negative scores (max 50% reduction)
            if time_estimate > 0 and time_actual > 0:
                # Calculate efficiency based on completion_time_ratio
                # Ratio of 1.0 = perfectly efficient (completed as expected)
                # Ratio > 1.0 = bonus (completed more efficiently)
                # Ratio < 1.0 = penalty (completed less efficiently)
                efficiency_ratio = completion_time_ratio
                
                # Convert ratio to percentage difference from 1.0 (perfect efficiency)
                # If ratio = 1.0, diff = 0% (no change)
                # If ratio = 0.5, diff = -50% (50% penalty)
                # If ratio = 2.0, diff = +100% (100% bonus)
                efficiency_percentage_diff = (efficiency_ratio - 1.0) * 100.0

                if weekly_curve == 'flattened_square':
                    # Softer square response; large deviations grow faster but scaled down
                    # Invert: positive diff (efficient) should give bonus, negative (inefficient) should give penalty
                    effect = math.copysign((abs(efficiency_percentage_diff) ** 2) / 100.0, efficiency_percentage_diff)
                    efficiency_multiplier = 1.0 - (0.01 * weekly_curve_strength * -effect)
                else:
                    # Linear response (legacy)
                    # Invert: positive diff (efficient) should give bonus, negative (inefficient) should give penalty
                    efficiency_multiplier = 1.0 - (0.01 * weekly_curve_strength * -efficiency_percentage_diff)
                
                # Cap both penalty and bonus to prevent extreme scores
                # Penalty: max 50% reduction (min multiplier = 0.5)
                # Bonus: max 50% increase (max multiplier = 1.5)
                efficiency_multiplier = max(0.5, min(1.5, efficiency_multiplier))

                score = score * efficiency_multiplier
            
            # Apply goal-based adjustment if goal hours and weekly productive hours are provided
            # This provides a bonus/penalty based on weekly goal achievement
            if goal_hours_per_week is not None and goal_hours_per_week > 0 and weekly_productive_hours is not None:
                goal_achievement_ratio = weekly_productive_hours / goal_hours_per_week
                # Modest adjustment: ±20% max based on goal achievement
                # 100% goal achievement = no change (multiplier = 1.0)
                # 120%+ = +20% bonus (multiplier = 1.2)
                # 80-100% = linear interpolation (0.9 to 1.0)
                # <80% = penalty down to -20% at 0% (multiplier = 0.8 minimum)
                if goal_achievement_ratio >= 1.2:
                    goal_multiplier = 1.2  # 20% bonus for exceeding goal significantly
                elif goal_achievement_ratio >= 1.0:
                    # Linear: 1.0 -> 1.0, 1.2 -> 1.2
                    goal_multiplier = 1.0 + (goal_achievement_ratio - 1.0) * 1.0
                elif goal_achievement_ratio >= 0.8:
                    # Linear: 0.8 -> 0.9, 1.0 -> 1.0
                    goal_multiplier = 0.9 + (goal_achievement_ratio - 0.8) * 0.5
                else:
                    # Below 80%: linear penalty down to 0.8 at 0%
                    # Linear: 0.0 -> 0.8, 0.8 -> 0.9
                    goal_multiplier = 0.8 + (goal_achievement_ratio / 0.8) * 0.1
                    goal_multiplier = max(0.8, goal_multiplier)  # Cap at 0.8 minimum
                
                score = score * goal_multiplier
            
            return score
        
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            return 0.0
    
    def calculate_grit_score(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score with:
        - Persistence factor (continuing despite obstacles) - NEW in v1.2
        - Focus factor (current attention state, emotion-based) - NEW in v1.2
        - Passion factor (relief vs emotional load) - existing
        - Time bonus (taking longer, dedication) - existing
        
        Grit = persistence + focus + passion + time_bonus
        
        Returns:
            Grit score (higher = more grit/persistence with passion), 0 on error.
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # --- Persistence multiplier: sqrt→log growth with familiarity decay ---
            # Raw growth: power curve to approximate anchors (2x~1.02, 10x~1.22, 25x~1.6, 50x~2.6, 100x~4.1)
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            # Familiarity decay after 100+ completions: taper as it becomes routine
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)  # 300→0.5, 500→0.33, 1000→~0.18
            else:
                decay = 1.0
            persistence_multiplier = max(1.0, min(5.0, raw_multiplier * decay))
            
            # --- Time bonus: difficulty-weighted, diminishing returns, fades after many reps ---
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)  # up to 1.8x at 2x longer
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)  # diminishing beyond 2x
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    # Difficulty weighting (harder tasks get more credit)
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    # Fade time bonus after many repetitions (negligible after ~50)
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)  # 10→1.0, 50→0.5, 90→~0.31
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            # --- Passion factor: relief vs emotional load (balanced, modest range) ---
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm  # positive if relief outweighs emotional load
            passion_factor = 1.0 + passion_delta * 0.5  # modest weighting
            # If not fully completed, dampen passion a bit
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            # Calculate persistence factor (continuing despite obstacles)
            persistence_factor = self.calculate_persistence_factor(
                row=row,
                task_completion_counts=task_completion_counts
            )
            # Returns 0.0-1.0, scale to 0.5-1.5 range to provide boost
            persistence_factor_scaled = 0.5 + persistence_factor * 1.0
            
            # Calculate focus factor (current attention state, emotion-based)
            focus_factor = self.calculate_focus_factor(row)
            # Returns 0.0-1.0, scale to 0.5-1.5 range to provide boost
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # Get disappointment factor (from stored value or calculate from net_relief)
            disappointment_factor = 0.0
            if 'disappointment_factor' in row.index:
                try:
                    disappointment_factor = float(row.get('disappointment_factor', 0) or 0)
                except (ValueError, TypeError):
                    disappointment_factor = 0.0
            else:
                # Calculate from net_relief if available
                try:
                    expected_relief = float(predicted_dict.get('expected_relief', 0) or 0)
                    actual_relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
                    net_relief = actual_relief - expected_relief
                    if net_relief < 0:
                        disappointment_factor = -net_relief
                except (ValueError, TypeError, KeyError):
                    disappointment_factor = 0.0
            
            # --- Disappointment resilience: v1.6a (current implementation) ---
            # Based on research: disappointment with completion=100% indicates grit/resilience
            # Disappointment with completion<100% indicates lack of grit (giving up)
            disappointment_resilience = 1.0
            if disappointment_factor > 0:
                if completion_pct >= 100.0:
                    # Persistent disappointment: completing despite unmet expectations
                    # Reward: up to 1.5x multiplier for high disappointment
                    disappointment_resilience = 1.0 + (disappointment_factor / 200.0)
                    disappointment_resilience = min(1.5, disappointment_resilience)  # Cap at 1.5x
                else:
                    # Abandonment disappointment: giving up due to disappointment
                    # Penalty: reduce grit score
                    disappointment_resilience = 1.0 - (disappointment_factor / 300.0)
                    disappointment_resilience = max(0.67, disappointment_resilience)  # Cap at 0.67x
            
            # Base score from completion percentage
            base_score = completion_pct
            
            # Grit score = persistence * focus * passion * time_bonus * disappointment_resilience
            grit_score = base_score * (
                persistence_factor_scaled *  # 0.5-1.5 range (persistence boost)
                focus_factor_scaled *        # 0.5-1.5 range (focus boost)
                passion_factor *             # 0.5-1.5 range (passion factor)
                time_bonus *                 # 1.0+ range (time bonus)
                disappointment_resilience     # 0.67-1.5 range (disappointment resilience/penalty)
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    def _calculate_grit_score_base(self, row: pd.Series, task_completion_counts: Dict[str, int], 
                                    disappointment_max_bonus: float = 1.5, 
                                    disappointment_min_penalty: float = 0.67,
                                    use_exponential_scaling: bool = False,
                                    base_score_multiplier: float = 1.0) -> float:
        """Base function for calculating grit score with configurable disappointment resilience caps.
        
        This is a helper function used by v1.6 variants to avoid code duplication.
        
        Args:
            row: Task instance row
            task_completion_counts: Dict mapping task_id to completion count
            disappointment_max_bonus: Maximum bonus multiplier for persistent disappointment (default 1.5)
            disappointment_min_penalty: Minimum penalty multiplier for abandonment disappointment (default 0.67)
        
        Returns:
            Grit score
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # --- Persistence multiplier: sqrt→log growth with familiarity decay ---
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
            else:
                decay = 1.0
            persistence_multiplier = max(1.0, min(5.0, raw_multiplier * decay))
            
            # --- Time bonus: difficulty-weighted, diminishing returns, fades after many reps ---
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            # --- Passion factor: relief vs emotional load ---
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm
            passion_factor = 1.0 + passion_delta * 0.5
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            # Calculate persistence and focus factors
            persistence_factor = self.calculate_persistence_factor(row=row, task_completion_counts=task_completion_counts)
            persistence_factor_scaled = 0.5 + persistence_factor * 1.0
            focus_factor = self.calculate_focus_factor(row)
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # Get disappointment factor
            disappointment_factor = 0.0
            if 'disappointment_factor' in row.index:
                try:
                    disappointment_factor = float(row.get('disappointment_factor', 0) or 0)
                except (ValueError, TypeError):
                    disappointment_factor = 0.0
            else:
                try:
                    expected_relief = float(predicted_dict.get('expected_relief', 0) or 0)
                    actual_relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
                    net_relief = actual_relief - expected_relief
                    if net_relief < 0:
                        disappointment_factor = -net_relief
                except (ValueError, TypeError, KeyError):
                    disappointment_factor = 0.0
            
            # --- Disappointment resilience with configurable caps ---
            disappointment_resilience = 1.0
            if disappointment_factor > 0:
                if completion_pct >= 100.0:
                    # Persistent disappointment: reward completing despite disappointment
                    if use_exponential_scaling:
                        # Exponential scaling: 1.0 + (1 - exp(-disappointment_factor / k)) * bonus_range
                        # k chosen so that at disappointment=100, we approach max_bonus
                        # Use k = 144 (100/ln(2)) for consistent exponential curve
                        # Then scale the exponential result to reach max_bonus at disappointment=100
                        bonus_range = disappointment_max_bonus - 1.0
                        k = 144.0  # Consistent exponential parameter
                        # Exponential curve: 0 to 1 as disappointment goes from 0 to infinity
                        exponential_factor = 1.0 - math.exp(-disappointment_factor / k)
                        # Scale to bonus_range: at disappointment=100, exponential_factor ≈ 0.51
                        # To reach max_bonus at disappointment=100, scale by (max_bonus-1)/0.51
                        # But simpler: scale so that at disappointment=100, we get close to max_bonus
                        scale_factor = bonus_range / (1.0 - math.exp(-100.0 / k))  # Normalize to disappointment=100
                        disappointment_resilience = 1.0 + (exponential_factor * scale_factor)
                        disappointment_resilience = min(disappointment_max_bonus, disappointment_resilience)
                    else:
                        # Linear scaling: 1.0 + (disappointment_factor / 200.0)
                        disappointment_resilience = 1.0 + (disappointment_factor / 200.0)
                        disappointment_resilience = min(disappointment_max_bonus, disappointment_resilience)
                else:
                    # Abandonment disappointment: penalize giving up (always linear)
                    disappointment_resilience = 1.0 - (disappointment_factor / 300.0)
                    disappointment_resilience = max(disappointment_min_penalty, disappointment_resilience)
            
            # Calculate final grit score
            base_score = completion_pct * base_score_multiplier
            grit_score = base_score * (
                persistence_factor_scaled *
                focus_factor_scaled *
                passion_factor *
                time_bonus *
                disappointment_resilience
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    def calculate_grit_score_v1_6a(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.6a: Original caps (1.5x bonus, 0.67x penalty).
        
        Disappointment resilience:
        - Persistent disappointment (completion >= 100%): up to 1.5x (50% bonus)
        - Abandonment disappointment (completion < 100%): down to 0.67x (33% penalty)
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=1.5, 
                                               disappointment_min_penalty=0.67)
    
    def calculate_grit_score_v1_6b(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.6b: Reduced positive cap (1.3x bonus, 0.67x penalty).
        
        Disappointment resilience:
        - Persistent disappointment (completion >= 100%): up to 1.3x (30% bonus)
        - Abandonment disappointment (completion < 100%): down to 0.67x (33% penalty)
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=1.3, 
                                               disappointment_min_penalty=0.67)
    
    def calculate_grit_score_v1_6c(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.6c: Balanced caps (1.2x bonus, 0.8x penalty).
        
        Disappointment resilience:
        - Persistent disappointment (completion >= 100%): up to 1.2x (20% bonus)
        - Abandonment disappointment (completion < 100%): down to 0.8x (20% penalty)
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=1.2, 
                                               disappointment_min_penalty=0.8)
    
    def calculate_grit_score_v1_6d(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.6d: Exponential scaling up to 1.5x bonus, 0.67x penalty.
        
        Disappointment resilience:
        - Persistent disappointment (completion >= 100%): exponential scaling up to 1.5x (50% bonus)
        - Abandonment disappointment (completion < 100%): linear down to 0.67x (33% penalty)
        - Exponential formula: 1.0 + (1 - exp(-disappointment/144)) * 0.5
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=1.5, 
                                               disappointment_min_penalty=0.67,
                                               use_exponential_scaling=True)
    
    def calculate_grit_score_v1_6e(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.6e: Exponential scaling up to 2.0x bonus, 0.67x penalty.
        
        Disappointment resilience:
        - Persistent disappointment (completion >= 100%): exponential scaling up to 2.0x (100% bonus)
        - Abandonment disappointment (completion < 100%): linear down to 0.67x (33% penalty)
        - Exponential formula: 1.0 + (1 - exp(-disappointment/144)) * 1.0
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=2.0, 
                                               disappointment_min_penalty=0.67,
                                               use_exponential_scaling=True)
    
    def calculate_grit_score_v1_7a(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.7a: v1.6e with 1.1x base score multiplier.
        
        Adds 10% multiplier to base score (completion_pct) before applying other factors.
        This increases all scores by 10% while maintaining relative differences.
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=2.0, 
                                               disappointment_min_penalty=0.67,
                                               use_exponential_scaling=True,
                                               base_score_multiplier=1.1)
    
    def calculate_grit_score_v1_7b(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.7b: Exponential scaling up to 2.1x bonus, 0.67x penalty.
        
        Disappointment resilience:
        - Persistent disappointment (completion >= 100%): exponential scaling up to 2.1x (110% bonus)
        - Abandonment disappointment (completion < 100%): linear down to 0.67x (33% penalty)
        - Higher cap than v1.6e to provide stronger bonuses for high disappointment
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=2.1, 
                                               disappointment_min_penalty=0.67,
                                               use_exponential_scaling=True)
    
    def calculate_grit_score_v1_7c(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.7c: v1.7a + v1.7b combined.
        
        - 1.1x base score multiplier
        - Exponential scaling up to 2.1x bonus
        - Applies both enhancements from v1.7a and v1.7b
        """
        return self._calculate_grit_score_base(row, task_completion_counts, 
                                               disappointment_max_bonus=2.1, 
                                               disappointment_min_penalty=0.67,
                                               use_exponential_scaling=True,
                                               base_score_multiplier=1.1)
    
    def calculate_grit_score_v1_3(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
        """Calculate grit score v1.3 with:
        - Perseverance factor (continuing despite obstacles) - renamed from persistence_factor
        - Persistence factor (completion count multiplier) - NEW, integrated into consistency
        - Focus factor (current attention state, emotion-based)
        - Passion factor (relief vs emotional load)
        - Time bonus (taking longer, dedication)
        
        Changes from v1.2:
        - Renamed persistence_factor → perseverance_factor (obstacle overcoming)
        - Renamed persistence_multiplier → persistence_factor (completion count)
        - Integrated persistence_factor into consistency component of perseverance_factor
        - Adjusted weights in perseverance_factor calculation
        
        Grit = base_score * (perseverance * focus * passion * time_bonus)
        
        Returns:
            Grit score (higher = more grit/persistence with passion), 0 on error.
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # --- Persistence factor: completion count multiplier (power curve with familiarity decay) ---
            # Raw growth: power curve to approximate anchors (2x~1.02, 10x~1.22, 25x~1.6, 50x~2.6, 100x~4.1)
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            # Familiarity decay after 100+ completions: taper as it becomes routine
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)  # 300→0.5, 500→0.33, 1000→~0.18
            else:
                decay = 1.0
            persistence_factor = max(1.0, min(5.0, raw_multiplier * decay))
            
            # --- Time bonus: difficulty-weighted, diminishing returns, fades after many reps ---
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)  # up to 1.8x at 2x longer
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)  # diminishing beyond 2x
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    # Difficulty weighting (harder tasks get more credit)
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    # Fade time bonus after many repetitions (negligible after ~50)
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)  # 10→1.0, 50→0.5, 90→~0.31
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            # --- Passion factor: relief vs emotional load (balanced, modest range) ---
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm  # positive if relief outweighs emotional load
            passion_factor = 1.0 + passion_delta * 0.5  # modest weighting
            # If not fully completed, dampen passion a bit
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            # Calculate perseverance factor (continuing despite obstacles) - v1.3 with persistence_factor integration
            perseverance_factor = self.calculate_perseverance_factor_v1_3(
                row=row,
                task_completion_counts=task_completion_counts,
                persistence_factor=persistence_factor
            )
            # Returns 0.0-1.0, scale to 0.5-1.5 range to provide boost
            perseverance_factor_scaled = 0.5 + perseverance_factor * 1.0
            
            # Calculate focus factor (current attention state, emotion-based)
            focus_factor = self.calculate_focus_factor(row)
            # Returns 0.0-1.0, scale to 0.5-1.5 range to provide boost
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # Base score from completion percentage
            base_score = completion_pct
            
            # Grit score = perseverance * focus * passion * time_bonus
            grit_score = base_score * (
                perseverance_factor_scaled *  # 0.5-1.5 range (perseverance boost)
                focus_factor_scaled *         # 0.5-1.5 range (focus boost)
                passion_factor *             # 0.5-1.5 range (passion factor)
                time_bonus                   # 1.0+ range (time bonus)
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    def calculate_grit_score_v1_4(self, row: pd.Series, task_completion_counts: Dict[str, int], 
                                  perseverance_threshold: float = 0.75, 
                                  persistence_threshold: float = 2.0,
                                  synergy_strength: float = 0.15) -> float:
        """Calculate grit score v1.4 with synergy multiplier for tasks with both high perseverance and persistence.
        
        Changes from v1.3:
        - Added synergy multiplier for tasks with BOTH high perseverance AND high persistence
        - Synergy multiplier: 1.0 + (perseverance_bonus * persistence_bonus * synergy_strength)
        - Rewards the combination of obstacle overcoming AND repeated completion
        
        Grit = base_score * (perseverance * focus * passion * time_bonus * synergy_multiplier)
        
        Args:
            row: Task instance row
            task_completion_counts: Dict mapping task_id to completion count
            perseverance_threshold: Threshold for "high" perseverance (default: 0.75, 75th percentile)
            persistence_threshold: Threshold for "high" persistence (default: 2.0, approximately 25+ completions)
            synergy_strength: Strength of synergy bonus (default: 0.15 = 15% max bonus)
        
        Returns:
            Grit score (higher = more grit/persistence with passion), 0 on error.
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # --- Persistence factor: completion count multiplier (power curve with familiarity decay) ---
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
            else:
                decay = 1.0
            persistence_factor = max(1.0, min(5.0, raw_multiplier * decay))
            
            # --- Time bonus: difficulty-weighted, diminishing returns, fades after many reps ---
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            # --- Passion factor: relief vs emotional load ---
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm
            passion_factor = 1.0 + passion_delta * 0.5
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            # Calculate perseverance factor (continuing despite obstacles) - v1.3 with persistence_factor integration
            perseverance_factor = self.calculate_perseverance_factor_v1_3(
                row=row,
                task_completion_counts=task_completion_counts,
                persistence_factor=persistence_factor
            )
            perseverance_factor_scaled = 0.5 + perseverance_factor * 1.0
            
            # Calculate focus factor (current attention state, emotion-based)
            focus_factor = self.calculate_focus_factor(row)
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # --- NEW in v1.4: Synergy multiplier for tasks with BOTH high perseverance AND high persistence ---
            synergy_multiplier = 1.0
            
            # Check if both are "high" (above thresholds)
            is_high_perseverance = perseverance_factor >= perseverance_threshold
            is_high_persistence = persistence_factor >= persistence_threshold
            
            if is_high_perseverance and is_high_persistence:
                # Calculate bonuses (0.0-1.0 range) based on how far above threshold
                # Perseverance: 0.0-1.0 range, threshold typically 0.75
                perseverance_bonus = max(0.0, min(1.0, (perseverance_factor - perseverance_threshold) / (1.0 - perseverance_threshold)))
                
                # Persistence: 1.0-5.0 range, threshold typically 2.0
                persistence_bonus = max(0.0, min(1.0, (persistence_factor - persistence_threshold) / (5.0 - persistence_threshold)))
                
                # Synergy multiplier: 1.0 + (bonus_product * strength)
                # When both are maxed: 1.0 + (1.0 * 1.0 * 0.15) = 1.15 (15% bonus)
                synergy_multiplier = 1.0 + (perseverance_bonus * persistence_bonus * synergy_strength)
            
            # Base score from completion percentage
            base_score = completion_pct
            
            # Grit score = perseverance * focus * passion * time_bonus * synergy_multiplier
            grit_score = base_score * (
                perseverance_factor_scaled *  # 0.5-1.5 range (perseverance boost)
                focus_factor_scaled *         # 0.5-1.5 range (focus boost)
                passion_factor *              # 0.5-1.5 range (passion factor)
                time_bonus *                  # 1.0+ range (time bonus)
                synergy_multiplier            # 1.0-1.15 range (synergy bonus, NEW in v1.4)
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    def _calculate_perseverance_persistence_stats(self, instances_df: Optional[pd.DataFrame] = None, user_id: Optional[int] = None) -> Dict[str, Dict[str, float]]:
        """Calculate statistics (mean, median, std) for perseverance and persistence factors.
        
        Used for dynamic threshold calculation and exponential bonus scaling.
        
        Args:
            instances_df: Optional DataFrame of instances. If None, loads from database/CSV.
            user_id: Optional user_id for data isolation. If None, tries to get from auth.
        
        Returns:
            Dict with 'perseverance' and 'persistence' keys, each containing:
            - 'mean': Mean value
            - 'median': Median value
            - 'std': Standard deviation
            - 'count': Number of instances
        """
        try:
            if instances_df is None:
                user_id = self._get_user_id(user_id)
                instances_df = self._load_instances(user_id=user_id)
            
            # Filter completed instances
            if 'completed_at' not in instances_df.columns:
                # Return defaults if completed_at column is missing
                return {
                    'perseverance': {'mean': 0.600, 'median': 0.600, 'std': 0.05, 'count': 0},
                    'persistence': {'mean': 1.165, 'median': 1.165, 'std': 0.3, 'count': 0}
                }
            completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy()
            if completed.empty:
                # Return defaults if no data
                return {
                    'perseverance': {'mean': 0.600, 'median': 0.600, 'std': 0.05, 'count': 0},
                    'persistence': {'mean': 1.165, 'median': 1.165, 'std': 0.3, 'count': 0}
                }
            
            # Calculate completion counts
            completion_counts = {}
            completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
            completed = completed.dropna(subset=['completed_at_dt'])
            if not completed.empty:
                counts = completed.groupby('task_id').size()
                completion_counts = counts.to_dict()
            
            # Calculate factors for all completed instances (vectorized)
            # Vectorize persistence_factor calculation
            if not completed.empty and 'task_id' in completed.columns:
                task_ids = completed['task_id'].fillna('')
                completion_counts_series = task_ids.map(lambda tid: completion_counts.get(tid, 1))
                
                # Vectorized persistence_factor calculation
                completion_minus_one = (completion_counts_series - 1).clip(lower=0)
                raw_multiplier = 1.0 + 0.015 * (completion_minus_one ** 1.001)
                decay = np.where(
                    completion_counts_series > 100,
                    1.0 / (1.0 + (completion_counts_series - 100) / 200.0),
                    1.0
                )
                persistence_factors = (raw_multiplier * decay).clip(1.0, 5.0)
                persistence_values = persistence_factors.tolist()
                
                # Perseverance factor still needs per-row calculation (calls complex method)
                perseverance_values = []
                for idx, row in completed.iterrows():
                    try:
                        persistence_factor = float(persistence_factors.loc[idx])
                        perseverance_factor = self.calculate_perseverance_factor_v1_3(
                            row=row,
                            task_completion_counts=completion_counts,
                            persistence_factor=persistence_factor
                        )
                        perseverance_values.append(perseverance_factor)
                    except Exception:
                        continue
            else:
                perseverance_values = []
                persistence_values = []
            
            # Calculate statistics
            if perseverance_values:
                perseverance_stats = {
                    'mean': float(np.mean(perseverance_values)),
                    'median': float(np.median(perseverance_values)),
                    'std': float(np.std(perseverance_values)) if len(perseverance_values) > 1 else 0.05,
                    'count': len(perseverance_values)
                }
            else:
                perseverance_stats = {'mean': 0.600, 'median': 0.600, 'std': 0.05, 'count': 0}
            
            if persistence_values:
                persistence_stats = {
                    'mean': float(np.mean(persistence_values)),
                    'median': float(np.median(persistence_values)),
                    'std': float(np.std(persistence_values)) if len(persistence_values) > 1 else 0.3,
                    'count': len(persistence_values)
                }
            else:
                persistence_stats = {'mean': 1.165, 'median': 1.165, 'std': 0.3, 'count': 0}
            
            return {
                'perseverance': perseverance_stats,
                'persistence': persistence_stats
            }
        except Exception as e:
            # Return defaults on error
            return {
                'perseverance': {'mean': 0.600, 'median': 0.600, 'std': 0.05, 'count': 0},
                'persistence': {'mean': 1.165, 'median': 1.165, 'std': 0.3, 'count': 0}
            }
    
    def _detect_suddenly_challenging(self, row: pd.Series, task_id: str, 
                                     lookback_instances: int = 10, user_id: Optional[int] = None) -> Tuple[bool, float]:
        """Detect if this task instance represents a sudden challenge on a routine task.
        
        A "suddenly challenging" scenario occurs when:
        1. Task has been completed many times (routine)
        2. Current load is significantly higher than recent average
        3. This represents overcoming an unexpected obstacle
        
        Args:
            row: Current task instance row
            task_id: Task identifier
            lookback_instances: Number of recent instances to compare against
            user_id: Optional user_id for data isolation. If None, tries to get from auth.
        
        Returns:
            Tuple of (is_suddenly_challenging: bool, challenge_bonus: float)
            challenge_bonus ranges from 0.0 (no bonus) to 0.25 (25% bonus for extreme challenge)
        """
        try:
            actual_dict = row.get('actual_dict', {})
            if isinstance(actual_dict, str):
                actual_dict = json.loads(actual_dict)
            
            cognitive_load = float(actual_dict.get('cognitive_load', 0) or 0)
            emotional_load = float(actual_dict.get('emotional_load', 0) or 0)
            current_load = (cognitive_load + emotional_load) / 2.0
            
            if current_load < 50:  # Not challenging enough
                return False, 0.0
            
            # Get recent instances of this task
            user_id = self._get_user_id(user_id)
            all_instances = self._load_instances(user_id=user_id)
            
            # Filter to this task, completed instances
            if 'completed_at' not in all_instances.columns:
                return False, 0.0
            task_instances = all_instances[
                (all_instances['task_id'] == task_id) & 
                (all_instances['completed_at'].astype(str).str.len() > 0)
            ].copy()
            
            if len(task_instances) < 5:  # Need at least 5 completions to establish baseline
                return False, 0.0
            
            # Get recent load values (excluding current) - vectorized extraction
            # Filter out current instance first
            task_instances_filtered = task_instances[task_instances.index != row.name].copy()
            
            if task_instances_filtered.empty:
                return False, 0.0
            
            # Vectorized extraction of load values from actual_dict
            def extract_load_from_dict(d):
                if isinstance(d, str):
                    try:
                        d = json.loads(d)
                    except:
                        return None
                if not isinstance(d, dict):
                    return None
                cognitive = float(d.get('cognitive_load', 0) or 0)
                emotional = float(d.get('emotional_load', 0) or 0)
                return (cognitive + emotional) / 2.0
            
            if 'actual_dict' in task_instances_filtered.columns:
                recent_loads = task_instances_filtered['actual_dict'].apply(extract_load_from_dict)
                recent_loads = recent_loads.dropna().tolist()
            else:
                recent_loads = []
            
            if len(recent_loads) < 3:  # Need at least 3 recent values
                return False, 0.0
            
            # Calculate baseline (mean of recent loads)
            baseline_load = np.mean(recent_loads)
            baseline_std = np.std(recent_loads) if len(recent_loads) > 1 else 10.0
            
            # Check if current load is significantly higher (2+ standard deviations)
            if current_load > baseline_load + (2.0 * baseline_std):
                # Calculate challenge bonus based on how extreme the spike is
                spike_amount = current_load - baseline_load
                spike_sds = spike_amount / baseline_std if baseline_std > 0 else 0
                
                # Exponential bonus: 2 SD = 8%, 3 SD = 15%, 4 SD = 20%, 5+ SD = 25%
                if spike_sds >= 5.0:
                    challenge_bonus = 0.25
                elif spike_sds >= 4.0:
                    challenge_bonus = 0.20
                elif spike_sds >= 3.0:
                    challenge_bonus = 0.15
                elif spike_sds >= 2.0:
                    challenge_bonus = 0.08
                else:
                    challenge_bonus = 0.0
                
                return True, challenge_bonus
            
            return False, 0.0
        except Exception:
            return False, 0.0
    
    def calculate_grit_score_v1_5a_median(self, row: pd.Series, task_completion_counts: Dict[str, int],
                                         stats_cache: Optional[Dict] = None) -> float:
        """Calculate grit score v1.5a with median-based thresholds and exponential SD bonuses.
        
        Changes from v1.4:
        - Uses median (not 75th percentile) for thresholds
        - Exponential bonuses based on standard deviations above median
        - Detects "suddenly challenging" scenarios (routine task with sudden high load)
        - Dynamic recalibration from historical data
        
        Args:
            row: Task instance row
            task_completion_counts: Dict mapping task_id to completion count
            stats_cache: Optional pre-calculated statistics (for performance)
        
        Returns:
            Grit score (higher = more grit/persistence with passion), 0 on error.
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # Calculate persistence_factor
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
            else:
                decay = 1.0
            persistence_factor = max(1.0, min(5.0, raw_multiplier * decay))
            
            # Calculate perseverance_factor
            perseverance_factor = self.calculate_perseverance_factor_v1_3(
                row=row,
                task_completion_counts=task_completion_counts,
                persistence_factor=persistence_factor
            )
            perseverance_factor_scaled = 0.5 + perseverance_factor * 1.0
            
            # Get statistics (median-based)
            if stats_cache is None:
                user_id_for_stats = self._get_user_id(None)
                stats = self._calculate_perseverance_persistence_stats(user_id=user_id_for_stats)
            else:
                stats = stats_cache
            
            perseverance_median = stats['perseverance']['median']
            perseverance_std = stats['perseverance']['std']
            persistence_median = stats['persistence']['median']
            persistence_std = stats['persistence']['std']
            
            # Time bonus, passion factor, focus factor (same as v1.3)
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm
            passion_factor = 1.0 + passion_delta * 0.5
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            focus_factor = self.calculate_focus_factor(row)
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # --- v1.5a: Median-based exponential SD synergy bonus ---
            synergy_multiplier = 1.0
            
            # Check if both are above median
            is_high_perseverance = perseverance_factor >= perseverance_median
            is_high_persistence = persistence_factor >= persistence_median
            
            if is_high_perseverance and is_high_persistence:
                # Calculate standard deviations above median
                perseverance_sds = (perseverance_factor - perseverance_median) / perseverance_std if perseverance_std > 0 else 0
                persistence_sds = (persistence_factor - persistence_median) / persistence_std if persistence_std > 0 else 0
                
                # Exponential bonuses: 1 SD = 2%, 2 SD = 5%, 3 SD = 10%, 4+ SD = 15%
                def sd_to_bonus(sds):
                    if sds <= 0:
                        return 0.0
                    elif sds >= 4.0:
                        return 0.15
                    elif sds >= 3.0:
                        return 0.10 + (sds - 3.0) * 0.05  # 10-15%
                    elif sds >= 2.0:
                        return 0.05 + (sds - 2.0) * 0.05  # 5-10%
                    elif sds >= 1.0:
                        return 0.02 + (sds - 1.0) * 0.03  # 2-5%
                    else:
                        return sds * 0.02  # 0-2%
                
                perseverance_bonus = sd_to_bonus(perseverance_sds)
                persistence_bonus = sd_to_bonus(persistence_sds)
                
                # Synergy: multiplicative with exponential scaling
                # Base synergy: 3% minimum
                base_synergy = 0.03
                synergy_component = (perseverance_bonus * persistence_bonus) ** 0.9  # Adjusted from 0.7 to 0.9
                synergy_component = min(0.12, synergy_component)  # Cap at 12%
                
                # Load bonus (high load = more impressive)
                cognitive_load = float(actual_dict.get('cognitive_load', 0) or 0)
                emotional_load = float(actual_dict.get('emotional_load', 0) or 0)
                combined_load = (cognitive_load + emotional_load) / 2.0
                load_bonus = min(0.10, combined_load / 1000.0)  # Up to 10% for load=100
                
                # Detect "suddenly challenging" scenario
                user_id_for_detect = self._get_user_id(None)
                is_sudden_challenge, challenge_bonus = self._detect_suddenly_challenging(row, task_id, user_id=user_id_for_detect)
                
                # Calculate total bonus (all components)
                total_bonus = base_synergy + synergy_component + load_bonus
                if is_sudden_challenge:
                    total_bonus += challenge_bonus
                
                # Cap total bonus at 25% for ALL factors combined
                total_bonus = min(0.25, total_bonus)
                synergy_multiplier = 1.0 + total_bonus
            
            base_score = completion_pct
            
            grit_score = base_score * (
                perseverance_factor_scaled *
                focus_factor_scaled *
                passion_factor *
                time_bonus *
                synergy_multiplier
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    def calculate_grit_score_v1_5b_mean(self, row: pd.Series, task_completion_counts: Dict[str, int],
                                       stats_cache: Optional[Dict] = None) -> float:
        """Calculate grit score v1.5b with mean-based thresholds and exponential SD bonuses.
        
        Same as v1.5a but uses mean instead of median for thresholds.
        Mean is more sensitive to outliers, median is more robust.
        
        Args:
            row: Task instance row
            task_completion_counts: Dict mapping task_id to completion count
            stats_cache: Optional pre-calculated statistics (for performance)
        
        Returns:
            Grit score (higher = more grit/persistence with passion), 0 on error.
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # Calculate persistence_factor
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
            else:
                decay = 1.0
            persistence_factor = max(1.0, min(5.0, raw_multiplier * decay))
            
            # Calculate perseverance_factor
            perseverance_factor = self.calculate_perseverance_factor_v1_3(
                row=row,
                task_completion_counts=task_completion_counts,
                persistence_factor=persistence_factor
            )
            perseverance_factor_scaled = 0.5 + perseverance_factor * 1.0
            
            # Get statistics (mean-based)
            if stats_cache is None:
                user_id_for_stats = self._get_user_id(None)
                stats = self._calculate_perseverance_persistence_stats(user_id=user_id_for_stats)
            else:
                stats = stats_cache
            
            perseverance_mean = stats['perseverance']['mean']
            perseverance_std = stats['perseverance']['std']
            persistence_mean = stats['persistence']['mean']
            persistence_std = stats['persistence']['std']
            
            # Time bonus, passion factor, focus factor (same as v1.3)
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm
            passion_factor = 1.0 + passion_delta * 0.5
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            focus_factor = self.calculate_focus_factor(row)
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # --- v1.5b: Mean-based exponential SD synergy bonus ---
            synergy_multiplier = 1.0
            
            # Check if both are above mean
            is_high_perseverance = perseverance_factor >= perseverance_mean
            is_high_persistence = persistence_factor >= persistence_mean
            
            if is_high_perseverance and is_high_persistence:
                # Calculate standard deviations above mean
                perseverance_sds = (perseverance_factor - perseverance_mean) / perseverance_std if perseverance_std > 0 else 0
                persistence_sds = (persistence_factor - persistence_mean) / persistence_std if persistence_std > 0 else 0
                
                # Exponential bonuses: 1 SD = 2%, 2 SD = 5%, 3 SD = 10%, 4+ SD = 15%
                def sd_to_bonus(sds):
                    if sds <= 0:
                        return 0.0
                    elif sds >= 4.0:
                        return 0.15
                    elif sds >= 3.0:
                        return 0.10 + (sds - 3.0) * 0.05  # 10-15%
                    elif sds >= 2.0:
                        return 0.05 + (sds - 2.0) * 0.05  # 5-10%
                    elif sds >= 1.0:
                        return 0.02 + (sds - 1.0) * 0.03  # 2-5%
                    else:
                        return sds * 0.02  # 0-2%
                
                perseverance_bonus = sd_to_bonus(perseverance_sds)
                persistence_bonus = sd_to_bonus(persistence_sds)
                
                # Synergy: multiplicative with exponential scaling
                base_synergy = 0.03
                synergy_component = (perseverance_bonus * persistence_bonus) ** 0.9  # Adjusted from 0.7 to 0.9
                synergy_component = min(0.12, synergy_component)
                
                # Load bonus
                cognitive_load = float(actual_dict.get('cognitive_load', 0) or 0)
                emotional_load = float(actual_dict.get('emotional_load', 0) or 0)
                combined_load = (cognitive_load + emotional_load) / 2.0
                load_bonus = min(0.10, combined_load / 1000.0)  # Up to 10% for load=100
                
                # Detect "suddenly challenging" scenario
                user_id_for_detect = self._get_user_id(None)
                is_sudden_challenge, challenge_bonus = self._detect_suddenly_challenging(row, task_id, user_id=user_id_for_detect)
                
                # Calculate total bonus (all components)
                total_bonus = base_synergy + synergy_component + load_bonus
                if is_sudden_challenge:
                    total_bonus += challenge_bonus
                
                # Cap total bonus at 25% for ALL factors combined
                total_bonus = min(0.25, total_bonus)
                synergy_multiplier = 1.0 + total_bonus
            
            base_score = completion_pct
            
            grit_score = base_score * (
                perseverance_factor_scaled *
                focus_factor_scaled *
                passion_factor *
                time_bonus *
                synergy_multiplier
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    def calculate_grit_score_v1_5c_hybrid(self, row: pd.Series, task_completion_counts: Dict[str, int],
                                          stats_cache: Optional[Dict] = None) -> float:
        """Calculate grit score v1.5c with hybrid thresholds (persistence=median, perseverance=mean).
        
        Design Decision: 
        - Persistence uses MEDIAN (robust to outliers, represents typical completion count)
        - Perseverance uses MEAN (sensitive to improvements, captures gradual trends)
        
        Changes from v1.5a/v1.5b:
        - Hybrid threshold approach (best of both)
        - Synergy exponent: 0.9 (was 0.7)
        - Suddenly challenging: up to 25% bonus (was 15%)
        - Load bonus: up to 10% (was 5%)
        - Total cap: 25% for ALL bonuses combined
        
        Args:
            row: Task instance row
            task_completion_counts: Dict mapping task_id to completion count
            stats_cache: Optional pre-calculated statistics (for performance)
        
        Returns:
            Grit score (higher = more grit/persistence with passion), 0 on error.
        """
        import math
        try:
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            task_id = row.get('task_id', '')
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
            time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)
            completion_count = max(1, int(task_completion_counts.get(task_id, 1) or 1))
            
            # Calculate persistence_factor
            raw_multiplier = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
            if completion_count > 100:
                decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
            else:
                decay = 1.0
            persistence_factor = max(1.0, min(5.0, raw_multiplier * decay))
            
            # Calculate perseverance_factor
            perseverance_factor = self.calculate_perseverance_factor_v1_3(
                row=row,
                task_completion_counts=task_completion_counts,
                persistence_factor=persistence_factor
            )
            perseverance_factor_scaled = 0.5 + perseverance_factor * 1.0
            
            # Get statistics (HYBRID: persistence=median, perseverance=mean)
            if stats_cache is None:
                user_id_for_stats = self._get_user_id(None)
                stats = self._calculate_perseverance_persistence_stats(user_id=user_id_for_stats)
            else:
                stats = stats_cache
            
            # HYBRID THRESHOLDS
            perseverance_threshold = stats['perseverance']['mean']  # MEAN for perseverance
            perseverance_std = stats['perseverance']['std']
            persistence_threshold = stats['persistence']['median']  # MEDIAN for persistence
            persistence_std = stats['persistence']['std']
            
            # Time bonus, passion factor, focus factor (same as v1.3)
            time_bonus = 1.0
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                if time_ratio > 1.0:
                    excess = time_ratio - 1.0
                    if excess <= 1.0:
                        base_time_bonus = 1.0 + (excess * 0.8)
                    else:
                        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)
                    base_time_bonus = min(3.0, base_time_bonus)
                    
                    task_difficulty = float(actual_dict.get('task_difficulty', predicted_dict.get('task_difficulty', 50)) or 50)
                    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
                    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
                    
                    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
                    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
            
            relief = float(actual_dict.get('actual_relief', actual_dict.get('relief_score', 0)) or 0)
            emotional = float(actual_dict.get('actual_emotional', actual_dict.get('emotional_load', 0)) or 0)
            relief_norm = max(0.0, min(1.0, relief / 100.0))
            emotional_norm = max(0.0, min(1.0, emotional / 100.0))
            passion_delta = relief_norm - emotional_norm
            passion_factor = 1.0 + passion_delta * 0.5
            if completion_pct < 100:
                passion_factor *= 0.9
            passion_factor = max(0.5, min(1.5, passion_factor))
            
            focus_factor = self.calculate_focus_factor(row)
            focus_factor_scaled = 0.5 + focus_factor * 1.0
            
            # --- v1.5c: Hybrid thresholds with exponential SD synergy bonus ---
            synergy_multiplier = 1.0
            
            # Check if both are above their respective thresholds
            is_high_perseverance = perseverance_factor >= perseverance_threshold  # MEAN threshold
            is_high_persistence = persistence_factor >= persistence_threshold      # MEDIAN threshold
            
            if is_high_perseverance and is_high_persistence:
                # Calculate standard deviations above threshold
                perseverance_sds = (perseverance_factor - perseverance_threshold) / perseverance_std if perseverance_std > 0 else 0
                persistence_sds = (persistence_factor - persistence_threshold) / persistence_std if persistence_std > 0 else 0
                
                # Exponential bonuses: 1 SD = 2%, 2 SD = 5%, 3 SD = 10%, 4+ SD = 15%
                def sd_to_bonus(sds):
                    if sds <= 0:
                        return 0.0
                    elif sds >= 4.0:
                        return 0.15
                    elif sds >= 3.0:
                        return 0.10 + (sds - 3.0) * 0.05  # 10-15%
                    elif sds >= 2.0:
                        return 0.05 + (sds - 2.0) * 0.05  # 5-10%
                    elif sds >= 1.0:
                        return 0.02 + (sds - 1.0) * 0.03  # 2-5%
                    else:
                        return sds * 0.02  # 0-2%
                
                perseverance_bonus = sd_to_bonus(perseverance_sds)
                persistence_bonus = sd_to_bonus(persistence_sds)
                
                # Synergy: multiplicative with exponential scaling (exponent = 0.9)
                base_synergy = 0.03
                synergy_component = (perseverance_bonus * persistence_bonus) ** 0.9  # 0.9 exponent
                synergy_component = min(0.12, synergy_component)  # Cap at 12%
                
                # Load bonus (high load = more impressive) - up to 10%
                cognitive_load = float(actual_dict.get('cognitive_load', 0) or 0)
                emotional_load = float(actual_dict.get('emotional_load', 0) or 0)
                combined_load = (cognitive_load + emotional_load) / 2.0
                load_bonus = min(0.10, combined_load / 1000.0)  # Up to 10% for load=100
                
                # Detect "suddenly challenging" scenario - up to 25% bonus
                user_id_for_detect = self._get_user_id(None)
                is_sudden_challenge, challenge_bonus = self._detect_suddenly_challenging(row, task_id, user_id=user_id_for_detect)
                
                # Calculate total bonus (all components)
                total_bonus = base_synergy + synergy_component + load_bonus
                if is_sudden_challenge:
                    total_bonus += challenge_bonus
                
                # Cap total bonus at 25% for ALL factors combined
                total_bonus = min(0.25, total_bonus)
                synergy_multiplier = 1.0 + total_bonus
            
            base_score = completion_pct
            
            grit_score = base_score * (
                perseverance_factor_scaled *
                focus_factor_scaled *
                passion_factor *
                time_bonus *
                synergy_multiplier
            )
            
            return float(grit_score)
        
        except (KeyError, TypeError, ValueError, AttributeError):
            return 0.0
    
    @staticmethod
    def calculate_spontaneous_aversion_threshold(baseline_aversion: float) -> float:
        """Calculate progressive threshold for detecting spontaneous aversion.
        
        Formula:
        - 0-25: 10 + 10% of baseline
        - 25-50: 5 + 10% of baseline
        - 50-100: 10% of baseline
        
        Args:
            baseline_aversion: Baseline aversion value (0-100)
            
        Returns:
            Threshold value above which spontaneous aversion is detected
        """
        baseline = max(0.0, min(100.0, float(baseline_aversion)))
        
        if baseline <= 25:
            threshold = 10.0 + (baseline * 0.10)
        elif baseline <= 50:
            threshold = 5.0 + (baseline * 0.10)
        else:
            threshold = baseline * 0.10
        
        return threshold
    
    @staticmethod
    def detect_spontaneous_aversion(baseline_aversion: Optional[float], current_aversion: Optional[float]) -> Tuple[bool, float]:
        """Detect if current aversion represents spontaneous aversion (obstacle).
        
        Args:
            baseline_aversion: Baseline aversion value (0-100) or None
            current_aversion: Current aversion value (0-100) or None
            
        Returns:
            Tuple of (is_spontaneous: bool, spike_amount: float)
        """
        if baseline_aversion is None or current_aversion is None:
            return False, 0.0
        
        baseline = max(0.0, min(100.0, float(baseline_aversion)))
        current = max(0.0, min(100.0, float(current_aversion)))
        
        threshold = Analytics.calculate_spontaneous_aversion_threshold(baseline)
        spike_amount = current - baseline
        
        is_spontaneous = spike_amount > threshold
        
        return is_spontaneous, max(0.0, spike_amount)
    
    @staticmethod
    def calculate_obstacles_bonus_multiplier(spike_amount: float) -> float:
        """Calculate weekly bonus multiplier based on obstacles overcome.
        
        Formula: 10% bonus per threshold level
        - Threshold 1: 10-20 spike = 10% bonus
        - Threshold 2: 20-30 spike = 20% bonus
        - Threshold 3: 30-40 spike = 30% bonus
        - etc.
        
        Args:
            spike_amount: Amount of spontaneous aversion spike (current - baseline)
            
        Returns:
            Bonus multiplier (1.0 = no bonus, 1.1 = 10% bonus, etc.)
        """
        if spike_amount <= 0:
            return 1.0
        
        # Calculate threshold level (every 10 points = 1 level)
        threshold_level = int(spike_amount / 10.0)
        
        # 10% bonus per level
        bonus_multiplier = 1.0 + (threshold_level * 0.10)
        
        return bonus_multiplier
    
    def calculate_thoroughness_factor(self, user_id: str = 'default', days: int = 30) -> float:
        """Calculate thoroughness/notetaking factor based on note-taking behavior.
        
        Factors considered:
        1. Percentage of tasks with notes (description + notes field)
        2. Average note length/thoroughness
        3. Count of popup trigger 7.1 (no sliders adjusted) - negative factor
        
        Formula:
        - Base factor from note coverage: 0.5 (no notes) to 1.0 (all tasks have notes)
        - Note length bonus: +0.0 to +0.3 based on average note length
        - Popup penalty: Progressive penalty starting mild, increasing over time, capped at -0.2
          Uses quadratic progression: penalty = -0.2 * (count / 15.0)^2
          This gives: 1 popup = -0.0009, 5 popups = -0.022, 10 popups = -0.089, 15+ popups = -0.2 (max)
        
        Args:
            user_id: User identifier (default: 'default')
            days: Number of days to look back for popup data (default: 30)
        
        Returns:
            Thoroughness factor (0.5 to 1.3), where 1.0 = baseline thoroughness
        """
        # #region agent log
        import time as time_module
        thoroughness_func_start = time_module.perf_counter()
        try:
            import json as json_module
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'analytics.py:calculate_thoroughness_factor', 'message': 'calculate_thoroughness_factor entry', 'data': {'user_id': user_id, 'days': days}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
        except: pass
        # #endregion
        try:
            from .task_manager import TaskManager
            from .database import get_session, PopupTrigger
            
            task_manager = TaskManager()
            # Convert string user_id to int for TaskManager.get_all()
            # TaskManager expects int user_id for database mode
            user_id_int = None
            if isinstance(user_id, str) and user_id.isdigit():
                user_id_int = int(user_id)
            elif user_id != "default":
                # Try to get current user if user_id is not "default"
                user_id_int = self._get_user_id(None)
            else:
                # For "default", try to get current authenticated user
                user_id_int = self._get_user_id(None)
            tasks_df = task_manager.get_all(user_id=user_id_int)
            
            if tasks_df.empty:
                return 1.0  # Default neutral factor if no tasks
            
            # Filter out test tasks
            if 'name' in tasks_df.columns:
                tasks_df = tasks_df[~tasks_df['name'].apply(lambda x: Analytics._is_test_task(x) if pd.notna(x) else False)]
            
            if tasks_df.empty:
                return 1.0
            
            total_tasks = len(tasks_df)
            
            # 1. Calculate percentage of tasks with notes (vectorized)
            # Vectorized extraction of description and notes lengths
            if 'description' in tasks_df.columns:
                description_lengths = tasks_df['description'].fillna('').astype(str).str.strip().str.len()
            else:
                description_lengths = pd.Series(0, index=tasks_df.index)
            
            if 'notes' in tasks_df.columns:
                notes_lengths = tasks_df['notes'].fillna('').astype(str).str.strip().str.len()
            else:
                notes_lengths = pd.Series(0, index=tasks_df.index)
            
            # Vectorized calculation: has_notes if either description or notes has content
            has_notes_mask = (description_lengths > 0) | (notes_lengths > 0)
            tasks_with_notes = int(has_notes_mask.sum())
            
            # Total note length (sum of description + notes for tasks with notes)
            total_note_length = int((description_lengths + notes_lengths)[has_notes_mask].sum())
            note_count = tasks_with_notes
            
            # Note coverage: percentage of tasks with any notes
            note_coverage = (tasks_with_notes / total_tasks) if total_tasks > 0 else 0.0
            
            # Base factor from coverage: 0.5 (no notes) to 1.0 (all tasks have notes)
            base_factor = 0.5 + (note_coverage * 0.5)
            
            # 2. Note length bonus: average note length
            avg_note_length = (total_note_length / note_count) if note_count > 0 else 0.0
            
            # Normalize note length: 0 chars = 0.0, 500 chars = 0.3 bonus
            # Using exponential decay for diminishing returns
            if avg_note_length > 0:
                # Scale: 0-500 chars maps to 0.0-0.3 bonus
                # Using sqrt for smooth curve (500 chars = 0.3, 1000 chars = ~0.42, but capped at 0.3)
                length_ratio = min(1.0, avg_note_length / 500.0)
                length_bonus = 0.3 * (1.0 - math.exp(-length_ratio * 2.0))  # Exponential decay
            else:
                length_bonus = 0.0
            
            # 3. Popup penalty: count of trigger 7.1 (no sliders adjusted)
            popup_penalty = 0.0
            try:
                from .database import PopupResponse
                with get_session() as session:
                    cutoff_date = datetime.utcnow() - timedelta(days=days)
                    
                    # Get total count of trigger 7.1 responses for this user in the time period
                    # Using PopupResponse to get actual popup occurrences (more accurate than PopupTrigger.count)
                    popup_count = session.query(PopupResponse).filter(
                        PopupResponse.trigger_id == '7.1',
                        PopupResponse.user_id == user_id,
                        PopupResponse.created_at >= cutoff_date
                    ).count()
                    
                    # Progressive penalty: starts mild, gets worse over time, caps at -0.2
                    # Uses power curve: penalty = -0.2 * (popup_ratio^2) for progressive increase
                    # This means: 1 popup = -0.002, 5 popups = -0.05, 10 popups = -0.2 (max)
                    if popup_count > 0:
                        # Scale: 0-10 popups maps to 0.0 to -0.2 penalty
                        popup_ratio = min(1.0, popup_count / 10.0)
                        # Power curve: starts mild, increases progressively, caps at -0.2
                        # Using power of 2 for progressive curve (can adjust exponent for steeper/gentler)
                        popup_penalty = -0.2 * (popup_ratio ** 2.0)
            except Exception as e:
                # If database access fails, skip popup penalty
                print(f"[Analytics] Could not access popup data for thoroughness factor: {e}")
                popup_penalty = 0.0
            
            # Combine factors
            thoroughness_factor = base_factor + length_bonus + popup_penalty
            
            # Clamp to reasonable range (0.5 to 1.3)
            thoroughness_factor = max(0.5, min(1.3, thoroughness_factor))
            
            # #region agent log
            thoroughness_func_duration = time_module.perf_counter() - thoroughness_func_start
            try:
                import json as json_module
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'analytics.py:calculate_thoroughness_factor', 'message': 'calculate_thoroughness_factor exit', 'data': {'duration_seconds': thoroughness_func_duration, 'factor_value': thoroughness_factor}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            
            return float(thoroughness_factor)
        
        except Exception as e:
            print(f"[Analytics] Error calculating thoroughness factor: {e}")
            # #region agent log
            thoroughness_func_duration = time_module.perf_counter() - thoroughness_func_start
            try:
                import json as json_module
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'analytics.py:calculate_thoroughness_factor', 'message': 'calculate_thoroughness_factor error', 'data': {'duration_seconds': thoroughness_func_duration, 'error': str(e)}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            return 1.0  # Default neutral factor on error
    
    def calculate_thoroughness_score(self, user_id: str = 'default', days: int = 30) -> float:
        """Calculate thoroughness/notetaking score (0-100) for display purposes.
        
        Converts the thoroughness factor to a 0-100 score where:
        - 0 = minimum thoroughness (factor 0.5)
        - 50 = baseline thoroughness (factor 1.0)
        - 100 = maximum thoroughness (factor 1.3)
        
        Args:
            user_id: User identifier (default: 'default')
            days: Number of days to look back for popup data (default: 30)
        
        Returns:
            Thoroughness score (0-100)
        """
        factor = self.calculate_thoroughness_factor(user_id=user_id, days=days)
        
        # Convert factor (0.5-1.3) to score (0-100)
        # Factor 0.5 → Score 0
        # Factor 1.0 → Score 50
        # Factor 1.3 → Score 100
        if factor <= 1.0:
            # Linear mapping: 0.5-1.0 → 0-50
            score = ((factor - 0.5) / 0.5) * 50.0
        else:
            # Linear mapping: 1.0-1.3 → 50-100
            score = 50.0 + ((factor - 1.0) / 0.3) * 50.0
        
        return max(0.0, min(100.0, score))
    
    @staticmethod
    def _is_test_task(task_name: str) -> bool:
        """Check if a task is a test/dev task that should be excluded from calculations.
        
        Args:
            task_name: Name of the task
            
        Returns:
            True if task should be excluded, False otherwise
        """
        if not task_name:
            return False
        
        try:
            # Handle pandas NaN and None values
            if pd.isna(task_name) if hasattr(pd, 'isna') else (task_name is None or str(task_name).lower() == 'nan'):
                return False
        except (TypeError, ValueError):
            pass
        
        task_name_lower = str(task_name).lower().strip()
        if not task_name_lower or task_name_lower == 'nan':
            return False
        
        test_patterns = ['test', 'devtest', 'dev test', 'example', 'fix', 'completion test', 'dev']
        
        for pattern in test_patterns:
            if pattern in task_name_lower:
                return True
        
        return False
    
    @staticmethod
    def calculate_obstacles_scores(
        baseline_aversion: Optional[float],
        current_aversion: Optional[float],
        expected_relief: Optional[float],
        actual_relief: Optional[float]
    ) -> Dict[str, float]:
        """Calculate multiple obstacles overcome scores using different formulas for comparison.
        
        Returns a dictionary with multiple scoring methods to assess which best captures
        the psychological meaning of overcoming obstacles.
        
        All formulas weight spike amount more heavily than relief, especially when relief is low.
        This creates positive correlation: higher spike + lower relief = more impressive = higher score.
        
        Formula variants:
        1. "expected_only": Uses expected_relief (decision-making context)
        2. "actual_only": Uses actual_relief (outcome-based)
        3. "minimum": Uses min(expected, actual) - most conservative/impressive
        4. "average": Uses (expected + actual) / 2 - balanced
        5. "net_penalty": Uses expected_relief but penalizes if actual < expected (disappointment)
        6. "net_bonus": Uses expected_relief but rewards if actual > expected (surprise benefit)
        7. "net_weighted": Uses expected_relief weighted by net relief factor
        
        Base formula for all: score = spike_amount × multiplier / 50.0
        Multiplier: 1 + (spike_amount / 100) × (1 - relief_proportion) × 9
        
        Args:
            baseline_aversion: Baseline aversion value (0-100) or None
            current_aversion: Current aversion value (0-100) or None
            expected_relief: Expected relief score (0-100) or None
            actual_relief: Actual relief score (0-100) or None
            
        Returns:
            Dictionary with keys: 'expected_only', 'actual_only', 'minimum', 'average', 
            'net_penalty', 'net_bonus', 'net_weighted', each with score value
        """
        is_spontaneous, spike_amount = Analytics.detect_spontaneous_aversion(
            baseline_aversion, current_aversion
        )
        
        if not is_spontaneous or spike_amount <= 0:
            return {
                'expected_only': 0.0,
                'actual_only': 0.0,
                'minimum': 0.0,
                'average': 0.0,
                'net_penalty': 0.0,
                'net_bonus': 0.0,
                'net_weighted': 0.0
            }
        
        # Normalize inputs
        spike_amount = max(0.0, min(100.0, float(spike_amount)))
        expected_relief = max(0.0, min(100.0, float(expected_relief))) if expected_relief is not None else None
        actual_relief = max(0.0, min(100.0, float(actual_relief))) if actual_relief is not None else None
        
        # Calculate net relief (actual - expected)
        net_relief = None
        if expected_relief is not None and actual_relief is not None:
            net_relief = actual_relief - expected_relief  # Can be negative
        
        def _calculate_score_with_relief(relief_value: Optional[float]) -> float:
            """Calculate obstacles score using a specific relief value."""
            if relief_value is None:
                return 0.0
            
            relief_proportion = relief_value / 100.0
            spike_proportion = spike_amount / 100.0
            
            # Multiplier: 1x to 10x based on spike and inverse of relief
            multiplier = 1.0 + (spike_proportion * (1.0 - relief_proportion) * 9.0)
            
            # Base score: spike_amount × multiplier / 50.0
            score = (spike_amount * multiplier) / 50.0
            return score
        
        # 1. Expected only (decision-making context)
        score_expected = _calculate_score_with_relief(expected_relief)
        
        # 2. Actual only (outcome-based)
        score_actual = _calculate_score_with_relief(actual_relief)
        
        # 3. Minimum (most conservative - rewards only when both are low)
        relief_min = None
        if expected_relief is not None and actual_relief is not None:
            relief_min = min(expected_relief, actual_relief)
        elif expected_relief is not None:
            relief_min = expected_relief
        elif actual_relief is not None:
            relief_min = actual_relief
        score_minimum = _calculate_score_with_relief(relief_min)
        
        # 4. Average (balanced approach)
        relief_avg = None
        if expected_relief is not None and actual_relief is not None:
            relief_avg = (expected_relief + actual_relief) / 2.0
        elif expected_relief is not None:
            relief_avg = expected_relief
        elif actual_relief is not None:
            relief_avg = actual_relief
        score_average = _calculate_score_with_relief(relief_avg)
        
        # 5. Net penalty (uses expected, but penalizes if actual < expected)
        # If you got less than expected, that's MORE impressive (you did it for less reward)
        score_net_penalty = score_expected
        if net_relief is not None and net_relief < 0:
            # Penalty factor: the more you got less than expected, the more impressive
            # Add bonus multiplier based on how much less you got
            penalty_factor = abs(net_relief) / 100.0  # 0.0 to 1.0
            bonus_multiplier = 1.0 + (penalty_factor * 0.5)  # Up to 1.5x bonus
            score_net_penalty = score_expected * bonus_multiplier
        
        # 6. Net bonus (uses expected, but rewards if actual > expected)
        # If you got more than expected, that's a pleasant surprise
        score_net_bonus = score_expected
        if net_relief is not None and net_relief > 0:
            # Bonus factor: getting more than expected is good, but less impressive for obstacles
            # So we reduce the bonus (or keep it neutral)
            bonus_factor = net_relief / 100.0  # 0.0 to 1.0
            bonus_multiplier = 1.0 - (bonus_factor * 0.2)  # Slight reduction (0.8x to 1.0x)
            score_net_bonus = score_expected * bonus_multiplier
        
        # 7. Net weighted (uses expected, weighted by net relief factor)
        # Considers both expected relief and how it relates to actual
        score_net_weighted = score_expected
        if net_relief is not None:
            # Weight expected relief by net relief factor
            # Negative net (got less) = more impressive = higher weight
            # Positive net (got more) = less impressive for obstacles = lower weight
            net_factor = 1.0 - (net_relief / 200.0)  # Range: 0.5 (big positive) to 1.5 (big negative)
            net_factor = max(0.5, min(1.5, net_factor))  # Clamp to reasonable range
            score_net_weighted = score_expected * net_factor
        
        return {
            'expected_only': round(score_expected, 2),
            'actual_only': round(score_actual, 2),
            'minimum': round(score_minimum, 2),
            'average': round(score_average, 2),
            'net_penalty': round(score_net_penalty, 2),
            'net_bonus': round(score_net_bonus, 2),
            'net_weighted': round(score_net_weighted, 2)
        }
    
    @staticmethod
    def calculate_obstacles_score(
        baseline_aversion: Optional[float],
        current_aversion: Optional[float],
        relief_score: float
    ) -> float:
        """Legacy method: Calculate obstacles overcome score using single relief value.
        
        This is kept for backward compatibility. New code should use calculate_obstacles_scores()
        to get multiple formula variants for comparison.
        
        Uses the same formula as 'expected_only' variant.
        """
        scores = Analytics.calculate_obstacles_scores(
            baseline_aversion, current_aversion, relief_score, None
        )
        return scores['expected_only']

    def __init__(self):
        self.instances_file = os.path.join(DATA_DIR, 'task_instances.csv')
        self.tasks_file = os.path.join(DATA_DIR, 'tasks.csv')
        # Load user-level productivity settings (defaults to shared user)
        self.user_state = UserStateManager()
        self.default_user_id = "default_user"
        self.productivity_settings = self._load_productivity_settings()

    def _load_productivity_settings(self) -> Dict[str, any]:
        """Load persisted productivity settings or use sensible defaults."""
        defaults = {
            "weekly_curve": "flattened_square",  # linear | flattened_square
            "weekly_curve_strength": 1.5,  # Increased from 1.0 to provide stronger efficiency bonuses
            "weekly_burnout_threshold_hours": 42.0,  # 6h/day baseline
            "daily_burnout_cap_multiplier": 2.0,
        }
        try:
            stored = self.user_state.get_productivity_settings(self.default_user_id) or {}
            return {**defaults, **stored}
        except Exception:
            return defaults

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------
    def _apply_gap_filtering(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply gap filtering based on user preference."""
        if df.empty or 'created_at' not in df.columns:
            return df
        
        gap_detector = GapDetector()
        preference = gap_detector.get_gap_handling_preference()
        
        # If no preference set or continue_as_is, return all data (gap will be excluded from trends elsewhere)
        if preference != 'fresh_start':
            return df
        
        # For fresh_start, only return post-gap data
        largest_gap = gap_detector.get_largest_gap()
        if not largest_gap:
            return df
        
        gap_end = largest_gap['gap_end']
        df['created_at_parsed'] = pd.to_datetime(df['created_at'], errors='coerce')
        df_filtered = df[df['created_at_parsed'] >= gap_end].copy()
        
        # Remove parsed column before returning
        if 'created_at_parsed' in df_filtered.columns:
            df_filtered = df_filtered.drop(columns=['created_at_parsed'])
        
        return df_filtered
    
    def _invalidate_instances_cache(self, user_id: Optional[int] = None):
        """Invalidate the instances cache. Call this when instances are created/updated/deleted.
        
        Args:
            user_id: Optional user_id to invalidate cache for specific user. If None, clears all user caches.
        """
        if user_id is not None:
            cache_key = user_id if user_id is not None else "default"
            if cache_key in self._instances_cache_all:
                del self._instances_cache_all[cache_key]
            if cache_key in self._instances_cache_all_time:
                del self._instances_cache_all_time[cache_key]
            if cache_key in self._instances_cache_completed:
                del self._instances_cache_completed[cache_key]
            if cache_key in self._instances_cache_completed_time:
                del self._instances_cache_completed_time[cache_key]
            if cache_key in self._dashboard_metrics_cache:
                del self._dashboard_metrics_cache[cache_key]
            if cache_key in self._dashboard_metrics_cache_time:
                del self._dashboard_metrics_cache_time[cache_key]
        else:
            # Clear all user caches
            self._instances_cache_all.clear()
            self._instances_cache_all_time.clear()
            self._instances_cache_completed.clear()
            self._instances_cache_completed_time.clear()
            self._dashboard_metrics_cache.clear()
            self._dashboard_metrics_cache_time.clear()
        # Invalidate chart and ranking caches too
        self._trend_series_cache = None
        # Clear all user-specific caches
        self._trend_series_cache.clear()
        self._trend_series_cache_time.clear()
        self._attribute_distribution_cache.clear()
        self._attribute_distribution_cache_time.clear()
        self._stress_dimension_cache.clear()
        self._stress_dimension_cache_time.clear()
        self._rankings_cache.clear()
        self._leaderboard_cache.clear()
        self._leaderboard_cache_time.clear()
        self._leaderboard_cache_top_n.clear()
        # Also invalidate relief_summary cache since it depends on instances
        Analytics._relief_summary_cache.clear()
        Analytics._relief_summary_cache_time.clear()
    
    @staticmethod
    def _invalidate_relief_summary_cache(user_id: Optional[int] = None):
        """Invalidate the relief_summary cache. Call this when productivity/relief calculations need refresh.
        
        Args:
            user_id: Optional user_id to invalidate cache for specific user. If None, clears all user caches.
        """
        if user_id is not None:
            cache_key = user_id if user_id is not None else "default"
            if cache_key in Analytics._relief_summary_cache:
                del Analytics._relief_summary_cache[cache_key]
            if cache_key in Analytics._relief_summary_cache_time:
                del Analytics._relief_summary_cache_time[cache_key]
        else:
            # Clear all user caches
            Analytics._relief_summary_cache.clear()
            Analytics._relief_summary_cache_time.clear()
    
    def _get_user_id(self, user_id: Optional[int] = None) -> Optional[int]:
        """Get user_id from parameter or current authenticated user.
        
        Args:
            user_id: Optional user_id parameter. If None, tries to get from auth.
        
        Returns:
            user_id if available, None otherwise (data will gracefully not load)
        """
        if user_id is not None:
            return user_id
        
        try:
            from backend.auth import get_current_user
            return get_current_user()
        except Exception as e:
            print(f"[Analytics] WARNING: Could not get user_id from auth: {e}")
            return None
    
    def _load_instances(self, completed_only: bool = False, user_id: Optional[int] = None) -> pd.DataFrame:
        """Load instances from database or CSV.
        
        Uses caching to avoid repeated database queries. Cache is TTL-based (5 minutes)
        and can be invalidated by calling _invalidate_instances_cache().
        
        Args:
            completed_only: If True, only load completed instances (optimization for relief_summary)
            user_id: User ID to filter by (required for data isolation)
        """
        import time
        
        # Check cache first - cache is now user-specific, keyed by user_id
        cache_key = user_id if user_id is not None else "default"
        current_time = time.time()
        
        if completed_only:
            # Check completed instances cache for this user
            if (cache_key in self._instances_cache_completed and 
                cache_key in self._instances_cache_completed_time and
                (current_time - self._instances_cache_completed_time[cache_key]) < self._cache_ttl_seconds):
                return self._instances_cache_completed[cache_key].copy()
        else:
            # Check all instances cache for this user
            if (cache_key in self._instances_cache_all and 
                cache_key in self._instances_cache_all_time and
                (current_time - self._instances_cache_all_time[cache_key]) < self._cache_ttl_seconds):
                return self._instances_cache_all[cache_key].copy()
        
        # Cache miss or expired - load from database/CSV
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
        
        if use_db:
            # Load from database
            # CRITICAL: Require user_id for data isolation - try to get from auth if not provided
            if user_id is None:
                try:
                    from backend.auth import get_current_user
                    user_id = get_current_user()
                except Exception as e:
                    print(f"[Analytics] WARNING: Could not get user_id from auth: {e}")
                    user_id = None
            
            if user_id is None:
                print("[Analytics] WARNING: _load_instances() called without user_id - returning empty for security")
                return pd.DataFrame()
            
            try:
                from backend.database import get_session, TaskInstance
                session = get_session()
                try:
                    # OPTIMIZATION: Only load completed instances if requested
                    # OPTIMIZATION: Use indexed column for filtering
                    # CRITICAL: Always include user_id filter in initial query for security and performance
                    if completed_only:
                        # Filter to only completed instances at database level (much faster)
                        # Uses index on completed_at for fast filtering
                        query = session.query(TaskInstance).filter(
                            TaskInstance.user_id == user_id,
                            TaskInstance.completed_at.isnot(None),
                            TaskInstance.completed_at != ''
                        )
                    else:
                        query = session.query(TaskInstance).filter(
                            TaskInstance.user_id == user_id
                        )
                    
                    instances = query.all()
                    if not instances:
                        return pd.DataFrame()
                    
                    # Convert to list of dicts
                    data = [instance.to_dict() for instance in instances]
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(data).fillna('')
                    
                    # Ensure all required columns exist
                    attr_defaults = attribute_defaults()
                    def _ensure_column(col: str, default):
                        if col not in df.columns:
                            df[col] = default
                    
                    for attr, default in attr_defaults.items():
                        _ensure_column(attr, default)
                    _ensure_column('status', 'active')
                    
                    # Apply gap filtering
                    df = self._apply_gap_filtering(df)
                    
                    # Process JSON fields (same as CSV path)
                    def _safe_json(cell: str) -> Dict:
                        if isinstance(cell, dict):
                            return cell
                        cell = cell or '{}'
                        try:
                            return json.loads(cell)
                        except Exception:
                            return {}
                    
                    df['predicted_dict'] = df['predicted'].apply(_safe_json) if 'predicted' in df.columns else {}
                    df['actual_dict'] = df['actual'].apply(_safe_json) if 'actual' in df.columns else {}
                    
                    # Fill attribute columns from JSON payloads if CSV column empty (same logic as CSV path)
                    for attr in TASK_ATTRIBUTES:
                        column = attr.key
                        df[column] = df[column].replace('', pd.NA)
                        df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get(column)))
                        df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get(column)))
                        # Special handling for relief_score
                        if column == 'relief_score':
                            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_relief')))
                        # Handle cognitive load components
                        if column == 'mental_energy_needed':
                            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_mental_energy') or r.get('actual_cognitive')))
                            df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_mental_energy') or r.get('expected_cognitive_load') or r.get('expected_cognitive')))
                        if column == 'task_difficulty':
                            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_difficulty') or r.get('actual_cognitive')))
                            df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_difficulty') or r.get('expected_cognitive_load') or r.get('expected_cognitive')))
                        if column == 'emotional_load':
                            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_emotional')))
                            df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_emotional_load') or r.get('expected_emotional')))
                        if column == 'duration_minutes':
                            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('time_actual_minutes')))
                            df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('time_estimate_minutes')))
                        df[column] = df[column].fillna(attr.default)
                        if attr.dtype == 'numeric':
                            df[column] = pd.to_numeric(df[column], errors='coerce')
                            df[column] = df[column].fillna(attr.default)
                    
                    # Handle physical_load
                    if 'physical_load' not in df.columns:
                        df['physical_load'] = pd.NA
                    df['physical_load'] = df['physical_load'].replace('', pd.NA)
                    df['physical_load'] = df['physical_load'].fillna(df['actual_dict'].apply(lambda r: r.get('actual_physical')))
                    df['physical_load'] = df['physical_load'].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_physical_load')))
                    df['physical_load'] = pd.to_numeric(df['physical_load'], errors='coerce')
                    df['physical_load'] = df['physical_load'].fillna(0.0)
                    
                    # Extract expected_aversion from JSON
                    df['expected_aversion'] = df['predicted_dict'].apply(lambda r: r.get('expected_aversion') if isinstance(r, dict) else None)
                    df['expected_aversion'] = pd.to_numeric(df['expected_aversion'], errors='coerce')
                    df['expected_aversion'] = df['expected_aversion'].fillna(0.0)  # Default to 0 if missing
                    
                    # Calculate derived columns (same as CSV path below)
                    # Extract and normalize cognitive load components
                    if 'mental_energy_needed' not in df.columns:
                        df['mental_energy_needed'] = pd.NA
                    if 'task_difficulty' not in df.columns:
                        df['task_difficulty'] = pd.NA
                    
                    df['mental_energy_needed'] = pd.to_numeric(df['mental_energy_needed'], errors='coerce')
                    df['task_difficulty'] = pd.to_numeric(df['task_difficulty'], errors='coerce')
                    
                    # Note: All inputs now use 0-100 scale natively.
                    # Old data may have 0-10 scale values, but we use them as-is (no scaling).
                    
                    df['mental_energy_needed'] = df['mental_energy_needed'].fillna(50.0)
                    df['task_difficulty'] = df['task_difficulty'].fillna(50.0)
                    
                    # Calculate stress_level
                    df['relief_score_numeric'] = pd.to_numeric(df['relief_score'], errors='coerce').fillna(0.0)
                    df['mental_energy_numeric'] = pd.to_numeric(df['mental_energy_needed'], errors='coerce').fillna(50.0)
                    df['task_difficulty_numeric'] = pd.to_numeric(df['task_difficulty'], errors='coerce').fillna(50.0)
                    df['emotional_load_numeric'] = pd.to_numeric(df['emotional_load'], errors='coerce').fillna(0.0)
                    df['physical_load_numeric'] = pd.to_numeric(df['physical_load'], errors='coerce').fillna(0.0)
                    df['expected_aversion_numeric'] = pd.to_numeric(df['expected_aversion'], errors='coerce').fillna(0.0)
                    
                    df['stress_level'] = (
                        (df['mental_energy_numeric'] * 0.5 + 
                         df['task_difficulty_numeric'] * 0.5 + 
                         df['emotional_load_numeric'] + 
                         df['physical_load_numeric'] + 
                         df['expected_aversion_numeric'] * 2.0) / 5.0
                    )
                    
                    # Calculate net_wellbeing
                    # DIFFERENCE FROM RELIEF SCORE:
                    # - Relief Score: Raw measure of relief felt after task completion (0-100)
                    # - Net Wellbeing: Relief MINUS stress, showing the NET benefit/cost of the task
                    #   - Positive net wellbeing = task provided more relief than stress (beneficial)
                    #   - Negative net wellbeing = task caused more stress than relief (costly)
                    #   - Zero = neutral (relief exactly equals stress)
                    df['net_wellbeing'] = df['relief_score_numeric'] - df['stress_level']
                    
                    # Calculate net_wellbeing_normalized
                    df['net_wellbeing_normalized'] = 50.0 + (df['net_wellbeing'] / 2.0)
                    
                    # Calculate stress_efficiency
                    stress_safe = pd.to_numeric(df['stress_level'], errors='coerce')
                    stress_safe = stress_safe.mask(stress_safe <= 0, np.nan)
                    relief_safe = pd.to_numeric(df['relief_score_numeric'], errors='coerce')
                    df['stress_efficiency'] = (relief_safe / stress_safe).round(4)
                    
                    df['stress_efficiency_raw'] = df['stress_efficiency']
                    se_valid = df['stress_efficiency'].dropna()
                    if not se_valid.empty:
                        se_min = se_valid.min()
                        se_max = se_valid.max()
                        if pd.notna(se_min) and pd.notna(se_max):
                            if se_max > se_min:
                                df['stress_efficiency'] = ((df['stress_efficiency'] - se_min) / (se_max - se_min)) * 100.0
                            else:
                                df['stress_efficiency'] = 100.0
                        df['stress_efficiency'] = df['stress_efficiency'].round(2)
                    
                    # Calculate expected_relief: relief predicted before task (from predicted_dict)
                    # Vectorized extraction from predicted_dict column
                    if 'predicted_dict' in df.columns:
                        # Extract expected_relief directly from dict column (vectorized)
                        df['expected_relief'] = df['predicted_dict'].apply(
                            lambda d: d.get('expected_relief', None) if isinstance(d, dict) else None
                        )
                    else:
                        df['expected_relief'] = None
                    df['expected_relief'] = pd.to_numeric(df['expected_relief'], errors='coerce')
                    
                    # Calculate net_relief: actual relief minus expected relief
                    # Use stored value if available, otherwise calculate
                    if 'net_relief' in df.columns:
                        df['net_relief'] = pd.to_numeric(df['net_relief'], errors='coerce')
                    else:
                        df['net_relief'] = None
                    
                    # Fill missing net_relief by calculating from expected/actual relief
                    missing_net_relief = df['net_relief'].isna()
                    if missing_net_relief.any():
                        df.loc[missing_net_relief, 'net_relief'] = (
                            df.loc[missing_net_relief, 'relief_score_numeric'] - 
                            df.loc[missing_net_relief, 'expected_relief']
                        )
                    
                    # Positive = actual relief exceeded expectations (pleasant surprise)
                    # Negative = actual relief fell short of expectations (disappointment)
                    # Zero = actual relief matched expectations (accurate prediction)
                    
                    # Use stored serendipity_factor if available, otherwise calculate
                    if 'serendipity_factor' in df.columns:
                        df['serendipity_factor'] = pd.to_numeric(df['serendipity_factor'], errors='coerce')
                    else:
                        df['serendipity_factor'] = None
                    
                    # Fill missing serendipity_factor by calculating from net_relief
                    # Vectorized: serendipity = max(0, net_relief) - only positive net_relief counts
                    missing_serendipity = df['serendipity_factor'].isna()
                    if missing_serendipity.any():
                        net_relief_series = pd.to_numeric(df.loc[missing_serendipity, 'net_relief'], errors='coerce').fillna(0.0)
                        df.loc[missing_serendipity, 'serendipity_factor'] = net_relief_series.clip(lower=0.0)
                    # Ensure all values are non-negative (vectorized)
                    df['serendipity_factor'] = pd.to_numeric(df['serendipity_factor'], errors='coerce').fillna(0.0).clip(lower=0.0)
                    
                    # Use stored disappointment_factor if available, otherwise calculate
                    if 'disappointment_factor' in df.columns:
                        df['disappointment_factor'] = pd.to_numeric(df['disappointment_factor'], errors='coerce')
                    else:
                        df['disappointment_factor'] = None
                    
                    # Fill missing disappointment_factor by calculating from net_relief
                    # Vectorized: disappointment = max(0, -net_relief) - only negative net_relief counts
                    missing_disappointment = df['disappointment_factor'].isna()
                    if missing_disappointment.any():
                        net_relief_series = pd.to_numeric(df.loc[missing_disappointment, 'net_relief'], errors='coerce').fillna(0.0)
                        df.loc[missing_disappointment, 'disappointment_factor'] = (-net_relief_series).clip(lower=0.0)
                    # Ensure all values are non-negative (vectorized)
                    df['disappointment_factor'] = pd.to_numeric(df['disappointment_factor'], errors='coerce').fillna(0.0).clip(lower=0.0)
                    
                    # Calculate stress_relief_correlation_score: measures inverse correlation
                    stress_norm = pd.to_numeric(df['stress_level'], errors='coerce').fillna(50.0)
                    relief_norm = pd.to_numeric(df['relief_score_numeric'], errors='coerce').fillna(50.0)
                    correlation_raw = (relief_norm - stress_norm + 100.0) / 2.0
                    df['stress_relief_correlation_score'] = correlation_raw.clip(0.0, 100.0).round(2)
                    
                    # Calculate behavioral_score (simplified version - full version is in CSV path)
                    # Vectorized: directly convert existing column if present
                    if 'behavioral_score' in df.columns:
                        df['behavioral_score'] = pd.to_numeric(df['behavioral_score'], errors='coerce')
                    else:
                        df['behavioral_score'] = pd.NA
                    
                    # Handle cognitive_load backward compatibility
                    if 'cognitive_load' in df.columns:
                        cognitive_numeric = pd.to_numeric(df['cognitive_load'], errors='coerce')
                        cognitive_scaled = cognitive_numeric.copy()
                        # Note: All inputs now use 0-100 scale natively.
                        # Old data may have 0-10 scale values, but we use them as-is (no scaling).
                        
                        if 'mental_energy_needed' in df.columns:
                            mental_numeric = pd.to_numeric(df['mental_energy_needed'], errors='coerce')
                            missing_mental = mental_numeric.isna() | (mental_numeric == 0)
                            has_cognitive = cognitive_scaled.notna() & (cognitive_scaled != 0)
                            df.loc[has_cognitive & missing_mental, 'mental_energy_needed'] = cognitive_scaled.loc[has_cognitive & missing_mental]
                        
                        if 'task_difficulty' in df.columns:
                            difficulty_numeric = pd.to_numeric(df['task_difficulty'], errors='coerce')
                            missing_difficulty = difficulty_numeric.isna() | (difficulty_numeric == 0)
                            has_cognitive = cognitive_scaled.notna() & (cognitive_scaled != 0)
                            df.loc[has_cognitive & missing_difficulty, 'task_difficulty'] = cognitive_scaled.loc[has_cognitive & missing_difficulty]
                    
                    # Store in cache before returning
                    import time
                    if completed_only:
                        # Cache is now user-specific, keyed by user_id
                        cache_key = user_id if user_id is not None else "default"
                        self._instances_cache_completed[cache_key] = df.copy()
                        self._instances_cache_completed_time[cache_key] = time.time()
                    else:
                        # Cache is now user-specific, keyed by user_id
                        cache_key = user_id if user_id is not None else "default"
                        self._instances_cache_all[cache_key] = df.copy()
                        self._instances_cache_all_time[cache_key] = time.time()
                    
                    return df
                finally:
                    session.close()
            except Exception as e:
                print(f"[Analytics] Error loading instances from database: {e}, falling back to CSV")
                # Fall through to CSV loading
        
        # CSV fallback
        if not os.path.exists(self.instances_file):
            return pd.DataFrame()

        df = pd.read_csv(self.instances_file).fillna('')
        attr_defaults = attribute_defaults()

        def _ensure_column(col: str, default):
            if col not in df.columns:
                df[col] = default

        for attr, default in attr_defaults.items():
            _ensure_column(attr, default)
        _ensure_column('status', 'active')
        
        # Apply gap filtering based on user preference
        df = self._apply_gap_filtering(df)

        def _safe_json(cell: str) -> Dict:
            if isinstance(cell, dict):
                return cell
            cell = cell or '{}'
            try:
                return json.loads(cell)
            except Exception:
                return {}

        df['predicted_dict'] = df['predicted'].apply(_safe_json) if 'predicted' in df.columns else {}
        df['actual_dict'] = df['actual'].apply(_safe_json) if 'actual' in df.columns else {}

        # Fill attribute columns from JSON payloads if CSV column empty
        for attr in TASK_ATTRIBUTES:
            column = attr.key
            df[column] = df[column].replace('', pd.NA)
            df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get(column)))
            df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get(column)))
            # Special handling for relief_score: check for actual_relief in JSON if relief_score is missing
            # IMPORTANT: relief_score should ONLY come from actual_relief, never from expected_relief
            # expected_relief should stay in predicted JSON only
            if column == 'relief_score':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_relief')))
                # DO NOT use expected_relief as fallback - relief_score is for actual values only
                # df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_relief')))  # REMOVED
            # Handle new cognitive load components (mental_energy_needed and task_difficulty)
            if column == 'mental_energy_needed':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_mental_energy') or r.get('actual_cognitive')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_mental_energy') or r.get('expected_cognitive_load') or r.get('expected_cognitive')))
            if column == 'task_difficulty':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_difficulty') or r.get('actual_cognitive')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_difficulty') or r.get('expected_cognitive_load') or r.get('expected_cognitive')))
            
            # Similar for emotional_load
            if column == 'emotional_load':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_emotional')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_emotional_load') or r.get('expected_emotional')))
            # Similar for duration_minutes
            if column == 'duration_minutes':
                df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('time_actual_minutes')))
                df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('time_estimate_minutes')))
            df[column] = df[column].fillna(attr.default)
            if attr.dtype == 'numeric':
                df[column] = pd.to_numeric(df[column], errors='coerce')
                # Replace NaN with default after numeric conversion
                df[column] = df[column].fillna(attr.default)

        # Backward compatibility: if old cognitive_load exists, use it for both new components
        # This allows existing data to work with the new schema
        if 'cognitive_load' in df.columns:
            cognitive_numeric = pd.to_numeric(df['cognitive_load'], errors='coerce')
            cognitive_scaled = cognitive_numeric.copy()
            # Note: All inputs now use 0-100 scale natively.
            # Old data may have 0-10 scale values, but we use them as-is (no scaling).
            
            # Use cognitive_load for missing mental_energy_needed
            if 'mental_energy_needed' in df.columns:
                mental_numeric = pd.to_numeric(df['mental_energy_needed'], errors='coerce')
                missing_mental = mental_numeric.isna() | (mental_numeric == 0)
                has_cognitive = cognitive_scaled.notna() & (cognitive_scaled != 0)
                df.loc[has_cognitive & missing_mental, 'mental_energy_needed'] = cognitive_scaled.loc[has_cognitive & missing_mental]
            
            # Use cognitive_load for missing task_difficulty
            if 'task_difficulty' in df.columns:
                difficulty_numeric = pd.to_numeric(df['task_difficulty'], errors='coerce')
                missing_difficulty = difficulty_numeric.isna() | (difficulty_numeric == 0)
                has_cognitive = cognitive_scaled.notna() & (cognitive_scaled != 0)
                df.loc[has_cognitive & missing_difficulty, 'task_difficulty'] = cognitive_scaled.loc[has_cognitive & missing_difficulty]

        # Extract physical_load from JSON if not in CSV columns
        if 'physical_load' not in df.columns:
            df['physical_load'] = pd.NA
        df['physical_load'] = df['physical_load'].replace('', pd.NA)
        df['physical_load'] = df['physical_load'].fillna(df['actual_dict'].apply(lambda r: r.get('actual_physical')))
        df['physical_load'] = df['physical_load'].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_physical_load')))
        df['physical_load'] = pd.to_numeric(df['physical_load'], errors='coerce')
        df['physical_load'] = df['physical_load'].fillna(0.0)  # Default to 0 if missing

        # Extract expected_aversion from JSON for stress calculation
        # Use expected_aversion from predicted_dict (what was set during initialization)
        df['expected_aversion'] = df['predicted_dict'].apply(lambda r: r.get('expected_aversion') if isinstance(r, dict) else None)
        df['expected_aversion'] = pd.to_numeric(df['expected_aversion'], errors='coerce')
        df['expected_aversion'] = df['expected_aversion'].fillna(0.0)  # Default to 0 if missing

        # Extract and normalize new cognitive load components (per Cognitive Load Theory)
        # mental_energy_needed = Germane load, task_difficulty = Intrinsic load
        # Extraneous load is excluded from stress calculation for now
        if 'mental_energy_needed' not in df.columns:
            df['mental_energy_needed'] = pd.NA
        if 'task_difficulty' not in df.columns:
            df['task_difficulty'] = pd.NA
        
        # Normalize to 0-100 if they're on 0-10 scale (backward compatibility)
        df['mental_energy_needed'] = pd.to_numeric(df['mental_energy_needed'], errors='coerce')
        df['task_difficulty'] = pd.to_numeric(df['task_difficulty'], errors='coerce')
        
        # Note: All inputs now use 0-100 scale natively.
        # Old data may have 0-10 scale values, but we use them as-is (no scaling).
        
        df['mental_energy_needed'] = df['mental_energy_needed'].fillna(50.0)  # Default to 50 if missing
        df['task_difficulty'] = df['task_difficulty'].fillna(50.0)  # Default to 50 if missing

        # Calculate stress_level: weighted average with cognitive components at 0.5 weight each
        # Per Cognitive Load Theory: mental_energy_needed (Germane) and task_difficulty (Intrinsic) 
        # are components of what was previously "cognitive_load", so each gets 0.5 weight
        # Aversion is weighted 2x to increase correlation from 0.20 to ~0.40 (middle of expected 0.35-0.45 range)
        df['relief_score_numeric'] = pd.to_numeric(df['relief_score'], errors='coerce').fillna(0.0)
        df['mental_energy_numeric'] = pd.to_numeric(df['mental_energy_needed'], errors='coerce').fillna(50.0)
        df['task_difficulty_numeric'] = pd.to_numeric(df['task_difficulty'], errors='coerce').fillna(50.0)
        df['emotional_load_numeric'] = pd.to_numeric(df['emotional_load'], errors='coerce').fillna(0.0)
        df['physical_load_numeric'] = pd.to_numeric(df['physical_load'], errors='coerce').fillna(0.0)
        df['expected_aversion_numeric'] = pd.to_numeric(df['expected_aversion'], errors='coerce').fillna(0.0)
        
        df['stress_level'] = (
            (df['mental_energy_numeric'] * 0.5 + 
             df['task_difficulty_numeric'] * 0.5 + 
             df['emotional_load_numeric'] + 
             df['physical_load_numeric'] + 
             df['expected_aversion_numeric'] * 2.0) / 5.0
        )
        
        # Calculate net_wellbeing: relief minus stress (can be positive or negative)
        # DIFFERENCE FROM RELIEF SCORE:
        # - Relief Score: Raw measure of relief felt after task completion (0-100)
        # - Net Wellbeing: Relief MINUS stress, showing the NET benefit/cost of the task
        #   - Positive net wellbeing = task provided more relief than stress (beneficial)
        #   - Negative net wellbeing = task caused more stress than relief (costly)
        #   - Zero = neutral (relief exactly equals stress)
        # Range: -100 to +100, where 0 = neutral (relief = stress)
        df['net_wellbeing'] = df['relief_score_numeric'] - df['stress_level']
        
        # Calculate net_wellbeing_normalized: normalized to 0-100 scale with 50 as neutral
        # Range: 0-100, where 50 = neutral (relief = stress), >50 = beneficial, <50 = costly
        df['net_wellbeing_normalized'] = 50.0 + (df['net_wellbeing'] / 2.0)
        
        # Calculate stress_efficiency: relief per unit of stress (ratio). If stress_level
        # is zero or missing, leave the metric empty to avoid infinities. Ensure numeric dtype.
        stress_safe = pd.to_numeric(df['stress_level'], errors='coerce')
        stress_safe = stress_safe.mask(stress_safe <= 0, np.nan)  # keep float dtype
        relief_safe = pd.to_numeric(df['relief_score_numeric'], errors='coerce')
        df['stress_efficiency'] = (relief_safe / stress_safe).round(4)

        # Keep raw ratio and provide a 0-100 normalized version (min-max across observed rows)
        df['stress_efficiency_raw'] = df['stress_efficiency']
        se_valid = df['stress_efficiency'].dropna()
        if not se_valid.empty:
            se_min = se_valid.min()
            se_max = se_valid.max()
            if pd.notna(se_min) and pd.notna(se_max):
                if se_max > se_min:
                    df['stress_efficiency'] = ((df['stress_efficiency'] - se_min) / (se_max - se_min)) * 100.0
                else:
                    # All values identical; treat them as 100 for visibility
                    df['stress_efficiency'] = 100.0
            df['stress_efficiency'] = df['stress_efficiency'].round(2)
        
        # Calculate expected_relief: relief predicted before task (from predicted_dict)
        def _get_expected_relief_from_dict(row):
            try:
                predicted_dict = row.get('predicted_dict', {})
                if isinstance(predicted_dict, dict):
                    return predicted_dict.get('expected_relief', None)
            except (KeyError, TypeError):
                pass
            return None
        
        df['expected_relief'] = df.apply(_get_expected_relief_from_dict, axis=1)
        df['expected_relief'] = pd.to_numeric(df['expected_relief'], errors='coerce')
        
        # Calculate net_relief: actual relief minus expected relief
        # Use stored value if available, otherwise calculate
        if 'net_relief' in df.columns:
            df['net_relief'] = pd.to_numeric(df['net_relief'], errors='coerce')
        else:
            df['net_relief'] = None
        
        # Fill missing net_relief by calculating from expected/actual relief
        missing_net_relief = df['net_relief'].isna()
        if missing_net_relief.any():
            df.loc[missing_net_relief, 'net_relief'] = (
                df.loc[missing_net_relief, 'relief_score_numeric'] - 
                df.loc[missing_net_relief, 'expected_relief']
            )
        
        # Positive = actual relief exceeded expectations (pleasant surprise)
        # Negative = actual relief fell short of expectations (disappointment)
        # Zero = actual relief matched expectations (accurate prediction)
        
        # Use stored serendipity_factor if available, otherwise calculate
        if 'serendipity_factor' in df.columns:
            df['serendipity_factor'] = pd.to_numeric(df['serendipity_factor'], errors='coerce')
        else:
            df['serendipity_factor'] = None
        
        # Fill missing serendipity_factor by calculating from net_relief
        missing_serendipity = df['serendipity_factor'].isna()
        if missing_serendipity.any():
            df.loc[missing_serendipity, 'serendipity_factor'] = df.loc[missing_serendipity, 'net_relief'].apply(
                lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0
            )
        # Ensure all values are non-negative
        df['serendipity_factor'] = df['serendipity_factor'].fillna(0.0)
        df['serendipity_factor'] = df['serendipity_factor'].apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
        
        # Use stored disappointment_factor if available, otherwise calculate
        if 'disappointment_factor' in df.columns:
            df['disappointment_factor'] = pd.to_numeric(df['disappointment_factor'], errors='coerce')
        else:
            df['disappointment_factor'] = None
        
        # Fill missing disappointment_factor by calculating from net_relief
        missing_disappointment = df['disappointment_factor'].isna()
        if missing_disappointment.any():
            df.loc[missing_disappointment, 'disappointment_factor'] = df.loc[missing_disappointment, 'net_relief'].apply(
                lambda x: max(0.0, -float(x)) if pd.notna(x) else 0.0
            )
        # Ensure all values are non-negative
        df['disappointment_factor'] = df['disappointment_factor'].fillna(0.0)
        df['disappointment_factor'] = df['disappointment_factor'].apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
        
        # Calculate stress_relief_correlation_score: measures inverse correlation
        # Formula: 100 - (stress_level + relief_score) / 2, normalized to show inverse relationship
        # When stress is high and relief is low, score is low (poor correlation)
        # When stress is low and relief is high, score is high (good inverse correlation)
        # Range: 0-100, where higher = better inverse correlation
        stress_norm = pd.to_numeric(df['stress_level'], errors='coerce').fillna(50.0)
        relief_norm = pd.to_numeric(df['relief_score_numeric'], errors='coerce').fillna(50.0)
        # Inverse correlation: high stress + low relief = low score, low stress + high relief = high score
        # Normalize: 100 - (stress + (100 - relief)) / 2 = 100 - (stress + 100 - relief) / 2
        # Simplified: (relief - stress + 100) / 2, then normalize to 0-100
        correlation_raw = (relief_norm - stress_norm + 100.0) / 2.0
        # Normalize to 0-100 range (theoretical range is 0-100, but clamp for safety)
        df['stress_relief_correlation_score'] = correlation_raw.clip(0.0, 100.0).round(2)
        
        # Auto-calculate behavioral_score: how well you adhered to planned behaviour
        # Now includes obstacles overcome component for significant bonus
        # 0 = maximum procrastination, 50 = neutral (perfect adherence), 100 = maximum overachievement
        # Range: 0-100 (50 = neutral), can exceed 100 with obstacles bonus
        def _calculate_behavioral_score(row):
            try:
                # Get completion percentage
                actual_dict = row.get('actual_dict', {})
                predicted_dict = row.get('predicted_dict', {})
                
                completion_pct = actual_dict.get('completion_percent', 100)
                completion_pct = float(completion_pct) if completion_pct else 100.0
                
                # Get time data
                time_actual = actual_dict.get('time_actual_minutes', 0)
                time_estimate = predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0)
                time_actual = float(time_actual) if time_actual else 0.0
                time_estimate = float(time_estimate) if time_estimate else 0.0
                
                # Get procrastination score (0-10 scale)
                procrast_score = pd.to_numeric(row.get('procrastination_score', 0), errors='coerce') or 0.0
                
                # Calculate obstacles component (significant bonus for overcoming obstacles)
                obstacles_component = 0.0
                task_id = row.get('task_id')
                if task_id:
                    from .instance_manager import InstanceManager
                    im = InstanceManager()
                    # Get baseline aversion (use robust for behavioral score)
                    baseline_aversion = im.get_baseline_aversion_robust(task_id)
                    expected_aversion = predicted_dict.get('expected_aversion')
                    relief_score = pd.to_numeric(row.get('relief_score', 0), errors='coerce') or 0.0
                    
                    if baseline_aversion is not None and expected_aversion is not None:
                        is_spontaneous, spike_amount = Analytics.detect_spontaneous_aversion(
                            baseline_aversion, expected_aversion
                        )
                        if is_spontaneous and spike_amount > 0 and completion_pct >= 50:
                            # Significant bonus for overcoming obstacles
                            # Scale: 0 to +15 bonus points (can push score above 100)
                            # Higher spike and higher relief = bigger bonus
                            obstacles_bonus = min(15.0, (spike_amount / 10.0) * (relief_score / 10.0) * 2.0)
                            obstacles_component = obstacles_bonus
                
                # Calculate components (each contributes to -10 to +10 range internally)
                # 1. Completion component: -5 to +5 based on completion percentage
                #    100% = 0, <100% = negative, >100% = positive (if possible)
                completion_component = ((completion_pct - 100.0) / 100.0) * 5.0
                completion_component = max(-5.0, min(5.0, completion_component))
                
                # 2. Time efficiency component: -5 to +5 based on actual vs expected time
                #    Faster than expected = positive, slower = negative
                time_component = 0.0
                if time_estimate > 0 and time_actual > 0:
                    time_ratio = time_estimate / max(time_actual, 0.1)  # >1 if faster, <1 if slower
                    # Convert to -5 to +5 scale
                    # If took exactly expected time: 0
                    # If took 2x expected: -2.5
                    # If took 0.5x expected: +2.5
                    time_component = ((time_ratio - 1.0) * 5.0)
                    time_component = max(-5.0, min(5.0, time_component))
                
                # 3. Procrastination component: -5 to 0 based on delay
                #    No delay = 0, high delay = -5
                procrast_component = -(procrast_score / 10.0) * 5.0
                procrast_component = max(-5.0, min(0.0, procrast_component))
                
                # Combine components (weighted average) - still in -10 to +10 range
                # Completion and time efficiency are equally important
                # Procrastination adds negative bias
                behavioral_deviation = (completion_component * 0.4) + (time_component * 0.4) + (procrast_component * 0.2)
                
                # Clamp to -10 to +10 range
                behavioral_deviation = max(-10.0, min(10.0, behavioral_deviation))
                
                # Convert to 0-100 scale where 50 = neutral (0 deviation)
                # Formula: 50 + (deviation * 5)
                # -10 → 0, 0 → 50, +10 → 100
                behavioral_score = 50.0 + (behavioral_deviation * 5.0)
                
                # Add obstacles bonus (can push above 100)
                behavioral_score += obstacles_component
                
                # Clamp to 0-115 range (allows obstacles bonus to push to 115)
                behavioral_score = max(0.0, min(115.0, behavioral_score))
                
                return round(behavioral_score, 2)
            except Exception as e:
                # Return 50 (neutral) if calculation fails
                return 50.0
        
        df['behavioral_score'] = df.apply(_calculate_behavioral_score, axis=1)
        # Normalize behavioral_score relative to observed best/worst so the most
        # proactive instance maps to 100 and the worst procrastination maps to 0.
        # Keep the raw value for inspection if needed.
        df['behavioral_score_raw'] = df['behavioral_score']
        min_bs = df['behavioral_score'].min()
        max_bs = df['behavioral_score'].max()
        if pd.notna(min_bs) and pd.notna(max_bs) and max_bs > min_bs:
            df['behavioral_score'] = ((df['behavioral_score'] - min_bs) / (max_bs - min_bs)) * 100.0
        # If all values are identical, leave the original (already 0-100) scale.
        df['behavioral_score'] = df['behavioral_score'].round(2)

        df['status'] = df['status'].replace('', 'active').str.lower()
        
        # Store in cache before returning (CSV path)
        import time
        if completed_only:
            # Filter to completed instances for CSV path
            if 'completed_at' in df.columns:
                df = df[df['completed_at'].astype(str).str.strip() != '']
            self._instances_cache_completed = df.copy()
            self._instances_cache_completed_time = time.time()
        else:
            self._instances_cache_all = df.copy()
            self._instances_cache_all_time = time.time()
        
        return df

    # ------------------------------------------------------------------
    # Dashboard summaries
    # ------------------------------------------------------------------
    def active_summary(self, user_id: Optional[int] = None) -> Dict[str, Optional[str]]:
        """Get summary of active tasks.
        
        Args:
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Dict with active_count and oldest_active timestamp
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        if df.empty:
            return {'active_count': 0, 'oldest_active': None}
        active = df[
            (df['status'].isin(['active', 'in_progress'])) &
            (df['is_deleted'] != 'True')
        ]
        return {
            'active_count': int(len(active)),
            'oldest_active': active['created_at'].min() if not active.empty else None,
        }

    def _expand_metric_dependencies(self, requested_metrics: List[str]) -> set:
        """Expand requested metrics to include all dependencies.
        
        Args:
            requested_metrics: List of metric keys (can be 'category.key' or just 'key')
        
        Returns:
            Set of expanded metric keys including dependencies
        """
        expanded = set()
        
        # Map of metric -> dependencies (metrics that must be calculated for this one)
        dependencies = {
            'adjusted_wellbeing': {'avg_net_wellbeing', 'general_aversion_score'},
            'adjusted_wellbeing_normalized': {'adjusted_wellbeing', 'avg_net_wellbeing', 'general_aversion_score'},
            'composite_productivity_score': {'work_volume_score', 'work_consistency_score', 'avg_base_productivity'},
            'volumetric_productivity_score': {'avg_base_productivity', 'work_volume_score'},
            'volumetric_potential_score': {'avg_base_productivity', 'work_volume_score'},
            'productivity_potential_score': {'avg_base_productivity', 'work_volume_score', 'work_consistency_score'},
        }
        
        # Normalize requested metrics (handle both 'category.key' and 'key' formats)
        normalized = set()
        for metric in requested_metrics:
            if '.' in metric:
                # Format: 'category.key'
                parts = metric.split('.', 1)
                normalized.add(parts[1])  # Just the key
            else:
                # Format: 'key'
                normalized.add(metric)
        
        # Expand dependencies recursively
        to_process = set(normalized)
        while to_process:
            current = to_process.pop()
            if current not in expanded:
                expanded.add(current)
                # Add dependencies
                if current in dependencies:
                    for dep in dependencies[current]:
                        if dep not in expanded:
                            to_process.add(dep)
        
        return expanded
    
    def get_dashboard_metrics(self, metrics: Optional[List[str]] = None, user_id: Optional[int] = None) -> Dict[str, Dict[str, Optional[float]]]:
        """Get dashboard metrics, optionally calculating only specific metrics.
        
        Uses caching to avoid repeated calculations. Cache is TTL-based (5 minutes).
        
        Args:
            metrics: Optional list of metric keys to calculate. If None, calculates all metrics.
                    Metric keys can be in format 'category.key' (e.g., 'quality.avg_relief')
                    or just 'key' (will search all categories).
                    Examples:
                    - ['quality.avg_relief', 'quality.avg_stress_level']
                    - ['work_volume_score', 'completion_rate']
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Dict with same structure as before, but only contains requested metrics (or all if metrics=None)
        """
        user_id = self._get_user_id(user_id)
        import time
        start = time.perf_counter()
        
        # Check cache first (always cache full result, then filter if needed)
        # Cache is now user-specific, keyed by user_id
        current_time = time.time()
        cache_key = user_id if user_id is not None else "default"
        if (cache_key in self._dashboard_metrics_cache and 
            cache_key in self._dashboard_metrics_cache_time and
            (current_time - self._dashboard_metrics_cache_time[cache_key]) < self._cache_ttl_seconds):
            # Cache hit - filter if specific metrics requested
            if metrics is not None:
                # Filter cached result to requested metrics
                requested_metrics = self._expand_metric_dependencies(metrics)
                def needs_metric(key: str) -> bool:
                    return key in requested_metrics
                
                # Filter the cached result
                filtered_result = {}
                cached_data = self._dashboard_metrics_cache[cache_key]
                if 'counts' in cached_data:
                    filtered_result['counts'] = {}
                    for key in ['active', 'completed_7d', 'total_created', 'total_completed', 'completion_rate', 'daily_self_care_tasks', 'avg_daily_self_care_tasks']:
                        if needs_metric(key) and key in cached_data['counts']:
                            filtered_result['counts'][key] = cached_data['counts'][key]
                
                # Similar filtering for other sections...
                # For simplicity, if metrics are requested, we'll recalculate (more accurate)
                # But for common case of metrics=None, we use cache
                pass  # Will fall through to calculation
            else:
                # No filtering needed, return cached full result
                duration = (time.perf_counter() - start) * 1000
                print(f"[Analytics] get_dashboard_metrics (cached): {duration:.2f}ms")
                return self._dashboard_metrics_cache[cache_key].copy()
        
        # Determine which metrics to calculate
        if metrics is not None:
            requested_metrics = self._expand_metric_dependencies(metrics)
            
            # Helper function to check if a metric is needed
            def needs_metric(key: str) -> bool:
                """Check if a metric key is in the requested set."""
                return key in requested_metrics
        else:
            requested_metrics = None  # Calculate all
            
            # Helper function that always returns True when calculating all
            def needs_metric(key: str) -> bool:
                return True
        
        df = self._load_instances(user_id=user_id)
        if df.empty:
            return {
                'counts': {'active': 0, 'completed_7d': 0, 'total_created': 0, 'total_completed': 0, 'completion_rate': 0.0, 'daily_self_care_tasks': 0, 'avg_daily_self_care_tasks': 0.0},
                'quality': {'avg_relief': 0.0, 'avg_cognitive_load': 0.0, 'avg_stress_level': 0.0, 'avg_net_wellbeing': 0.0, 'avg_net_wellbeing_normalized': 50.0, 'avg_stress_efficiency': None, 'avg_aversion': 0.0, 'adjusted_wellbeing': 0.0, 'adjusted_wellbeing_normalized': 50.0, 'thoroughness_score': 50.0, 'thoroughness_factor': 1.0},
                'time': {'median_duration': 0.0, 'avg_delay': 0.0, 'estimation_accuracy': 0.0},
                'aversion': {'general_aversion_score': 0.0},
                'productivity_volume': {
                    'avg_daily_work_time': 0.0,
                    'work_volume_score': 0.0,
                    'work_consistency_score': 50.0,
                    'productivity_potential_score': 0.0,
                    'work_volume_gap': 0.0,
                    'composite_productivity_score': 0.0,
                },
            }
        active = df[df['status'].isin(['active', 'in_progress'])]
        if 'completed_at' in df.columns:
            completed = df[df['completed_at'].astype(str).str.len() > 0]
            completed_7d = completed[
                pd.to_datetime(completed['completed_at']) >= datetime.now() - pd.Timedelta(days=7)
            ]
        else:
            completed = pd.DataFrame()
            completed_7d = pd.DataFrame()

        def _median(series):
            clean = pd.to_numeric(series, errors='coerce').dropna()
            return round(float(clean.median()), 2) if not clean.empty else 0.0

        def _avg(series):
            clean = pd.to_numeric(series, errors='coerce').dropna()
            return round(float(clean.mean()), 2) if not clean.empty else 0.0

        df['delay_minutes'] = (
            pd.to_datetime(df['started_at'].replace('', pd.NA))
            - pd.to_datetime(df['created_at'].replace('', pd.NA))
        ).dt.total_seconds() / 60

        # Calculate completion rate
        total_created = len(df[df['created_at'].astype(str).str.len() > 0])
        total_completed = len(completed)
        completion_rate = (total_completed / total_created * 100.0) if total_created > 0 else 0.0
        
        # Calculate time estimation accuracy
        completed_with_time = completed.copy()
        completed_with_time['time_actual_num'] = pd.to_numeric(
            completed_with_time['duration_minutes'], errors='coerce'
        )
        completed_with_time['time_estimate_num'] = completed_with_time['predicted_dict'].apply(
            lambda d: float(d.get('time_estimate_minutes') or d.get('estimate') or 0) if isinstance(d, dict) else 0
        )
        # Filter to rows with both actual and estimate > 0
        valid_time_comparisons = completed_with_time[
            (completed_with_time['time_actual_num'] > 0) & 
            (completed_with_time['time_estimate_num'] > 0)
        ]
        time_accuracy = 0.0
        if not valid_time_comparisons.empty:
            # Calculate ratio: actual / estimate (1.0 = perfect, >1 = took longer, <1 = took less)
            time_accuracy = _avg(valid_time_comparisons['time_actual_num'] / valid_time_comparisons['time_estimate_num'])
        
        # Calculate life balance (only if needed)
        life_balance = {}
        if needs_metric('life_balance_score') or needs_metric('balance_score'):
            life_balance = self.get_life_balance()
        else:
            life_balance = {'balance_score': 50.0}  # Default value
        
        # Calculate daily work volume metrics (only if needed)
        work_volume_metrics = {}
        avg_daily_work_time = 0.0
        work_volume_score = 0.0
        work_consistency_score = 50.0
        if (needs_metric('work_volume_score') or needs_metric('work_consistency_score') or 
            needs_metric('avg_daily_work_time') or needs_metric('productivity_potential_score') or
            needs_metric('composite_productivity_score') or needs_metric('volumetric_productivity_score')):
            work_volume_metrics = self.get_daily_work_volume_metrics(days=30)
            avg_daily_work_time = work_volume_metrics.get('avg_daily_work_time', 0.0)
            work_volume_score = work_volume_metrics.get('work_volume_score', 0.0)
            work_consistency_score = work_volume_metrics.get('work_consistency_score', 50.0)
        
        # Calculate average base productivity score from completed tasks (only if needed)
        # This is needed for volumetric productivity calculation
        avg_base_productivity = 0.0
        if (needs_metric('avg_base_productivity') or needs_metric('volumetric_productivity_score') or
            needs_metric('volumetric_potential_score') or needs_metric('productivity_potential_score') or
            needs_metric('composite_productivity_score')) and not completed.empty:
            # Calculate productivity score for each completed task
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all(user_id=user_id)
            
            # Get self care tasks per day for productivity calculation
            self_care_tasks_per_day = {}
            if not tasks_df.empty and 'task_type' in tasks_df.columns:
                completed_with_type = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
                completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
                
                self_care_completed = completed_with_type[
                    completed_with_type['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
                ].copy()
                
                if not self_care_completed.empty:
                    self_care_completed['completed_at_dt'] = pd.to_datetime(self_care_completed['completed_at'], errors='coerce')
                    self_care_completed = self_care_completed[self_care_completed['completed_at_dt'].notna()]
                    if not self_care_completed.empty:
                        self_care_completed['date'] = self_care_completed['completed_at_dt'].dt.date
                        daily_counts = self_care_completed.groupby('date').size()
                        self_care_tasks_per_day = {str(date): int(count) for date, count in daily_counts.items()}
            
            # Get work/play time per day
            work_play_time_per_day = {}
            if not tasks_df.empty and 'task_type' in tasks_df.columns:
                completed_with_type = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
                completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
                
                # Parse dates and group by date and task type
                completed_with_type['completed_at_dt'] = pd.to_datetime(completed_with_type['completed_at'], errors='coerce')
                completed_with_type = completed_with_type[completed_with_type['completed_at_dt'].notna()]
                completed_with_type['date'] = completed_with_type['completed_at_dt'].dt.date
                completed_with_type['duration_numeric'] = pd.to_numeric(completed_with_type['duration_minutes'], errors='coerce').fillna(0.0)
                
                for date, group in completed_with_type.groupby('date'):
                    date_str = str(date)
                    work_time = group[group['task_type_normalized'] == 'work']['duration_numeric'].sum()
                    play_time = group[group['task_type_normalized'] == 'play']['duration_numeric'].sum()
                    work_play_time_per_day[date_str] = {
                        'work_time': float(work_time),
                        'play_time': float(play_time)
                    }
            
            # Calculate productivity scores for completed tasks
            productivity_scores = []
            for _, row in completed.iterrows():
                try:
                    prod_score = self.calculate_productivity_score(
                        row=row,
                        self_care_tasks_per_day=self_care_tasks_per_day,
                        work_play_time_per_day=work_play_time_per_day
                    )
                    if prod_score > 0:  # Only include positive scores
                        productivity_scores.append(prod_score)
                except Exception:
                    pass
            
            if productivity_scores:
                avg_base_productivity = sum(productivity_scores) / len(productivity_scores)
        
        # Calculate volumetric productivity score (only if needed)
        volumetric_productivity = 0.0
        volumetric_potential = 0.0
        productivity_potential = {'potential_score': 0.0, 'gap_hours': 0.0}
        composite_productivity = 0.0
        
        if (needs_metric('volumetric_productivity_score') or needs_metric('volumetric_potential_score') or
            needs_metric('productivity_potential_score') or needs_metric('composite_productivity_score')):
            # Calculate volumetric productivity score (integrates volume into productivity)
            volumetric_productivity = self.calculate_volumetric_productivity_score(
                base_productivity_score=avg_base_productivity,
                work_volume_score=work_volume_score
            )
            
            # Calculate average efficiency score for productivity potential (legacy, still used)
            efficiency_summary = self.get_efficiency_summary()
            avg_efficiency_score = efficiency_summary.get('avg_efficiency', 0.0)
            
            # Get target hours from user settings
            target_hours_per_day = self.get_target_hours_per_day("default_user")
            target_hours_per_day_decimal = target_hours_per_day / 60.0  # Convert to hours
            
            # Calculate target volume score based on target hours
            # Volume score formula: 0-2h (0-25), 2-4h (25-50), 4-6h (50-75), 6-8h+ (75-100)
            target_minutes = target_hours_per_day
            if target_minutes <= 120:
                target_volume_score = (target_minutes / 120) * 25
            elif target_minutes <= 240:
                target_volume_score = 25 + ((target_minutes - 120) / 120) * 25
            elif target_minutes <= 360:
                target_volume_score = 50 + ((target_minutes - 240) / 120) * 25
            else:
                target_volume_score = 75 + min(25, ((target_minutes - 360) / 120) * 25)
            target_volume_score = max(0.0, min(100.0, target_volume_score))
            
            # Calculate productivity potential using volumetric productivity
            # Potential = volumetric productivity at target volume
            volumetric_potential = self.calculate_volumetric_productivity_score(
                base_productivity_score=avg_base_productivity,
                work_volume_score=target_volume_score
            )
            
            # Calculate productivity potential - uses goal setting
            productivity_potential = self.calculate_productivity_potential(
                avg_efficiency_score=avg_efficiency_score,
                avg_daily_work_time=avg_daily_work_time,
                target_hours_per_day=target_hours_per_day,
                user_id="default_user"
            )
            
            # Update potential score to use volumetric potential
            productivity_potential['potential_score'] = volumetric_potential
            productivity_potential['current_score'] = volumetric_productivity
            
            # Calculate composite productivity score using volumetric productivity
            # Normalize volumetric productivity to 0-100 range for composite
            normalized_volumetric = min(100.0, volumetric_productivity / 7.5) if volumetric_productivity > 0 else 0.0
            composite_productivity = self.calculate_composite_productivity_score(
                efficiency_score=normalized_volumetric * 2.0,  # Convert back to efficiency-like scale
                volume_score=work_volume_score,
                consistency_score=work_consistency_score
            )
        
        # Calculate thoroughness/notetaking score (only if needed)
        thoroughness_score = 50.0
        thoroughness_factor = 1.0
        if needs_metric('thoroughness_score') or needs_metric('thoroughness_factor'):
            thoroughness_score = self.calculate_thoroughness_score(user_id='default', days=30)
            thoroughness_factor = self.calculate_thoroughness_factor(user_id='default', days=30)
        
        # Calculate daily self care tasks metrics (only if needed)
        daily_self_care_tasks = 0
        avg_daily_self_care_tasks = 0.0
        if needs_metric('daily_self_care_tasks') or needs_metric('avg_daily_self_care_tasks') or needs_metric('self_care_frequency'):
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all(user_id=user_id)
            
            if not tasks_df.empty and 'task_type' in tasks_df.columns:
                # Join completed tasks with task types
                completed_with_type = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
                completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
                
                # Filter to self care tasks
                self_care_tasks = completed_with_type[
                    completed_with_type['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
                ].copy()
                
                if not self_care_tasks.empty:
                    # Parse completed_at dates
                    self_care_tasks['completed_at_dt'] = pd.to_datetime(self_care_tasks['completed_at'], errors='coerce')
                    self_care_tasks = self_care_tasks[self_care_tasks['completed_at_dt'].notna()]
                    
                    if not self_care_tasks.empty:
                        self_care_tasks['date'] = self_care_tasks['completed_at_dt'].dt.date
                        
                        # Count self care tasks for today
                        today = datetime.now().date()
                        today_self_care = self_care_tasks[self_care_tasks['date'] == today]
                        daily_self_care_tasks = len(today_self_care)
                        
                        # Calculate average daily self care tasks over last 30 days
                        thirty_days_ago = datetime.now() - timedelta(days=30)
                        recent_self_care = self_care_tasks[
                            self_care_tasks['completed_at_dt'] >= thirty_days_ago
                        ]
                        
                        if not recent_self_care.empty:
                            daily_counts = recent_self_care.groupby('date').size()
                            avg_daily_self_care_tasks = round(float(daily_counts.mean()), 2) if not daily_counts.empty else 0.0
        else:
            # If not needed, we still need tasks_df for other calculations, but skip self-care
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all(user_id=user_id)
        
        # Calculate average aversion from completed tasks (expected_aversion at time of completion)
        completed_aversion = completed['predicted_dict'].apply(
            lambda d: float(d.get('expected_aversion', 0)) if isinstance(d, dict) else 0
        )
        completed_aversion = pd.to_numeric(completed_aversion, errors='coerce')
        avg_aversion_completed = _avg(completed_aversion)
        
        # Calculate general aversion score (average expected_aversion from active/upcoming tasks)
        # This represents how averse you are to tasks you expect to do in general
        active_aversion = active['predicted_dict'].apply(
            lambda d: float(d.get('expected_aversion', 0)) if isinstance(d, dict) else 0
        )
        active_aversion = pd.to_numeric(active_aversion, errors='coerce')
        general_aversion_score = _avg(active_aversion) if not active.empty else 0.0
        
        # If no active tasks, use all tasks with predicted data as fallback
        if general_aversion_score == 0.0 or pd.isna(general_aversion_score):
            all_aversion = df['predicted_dict'].apply(
                lambda d: float(d.get('expected_aversion', 0)) if isinstance(d, dict) else 0
            )
            all_aversion = pd.to_numeric(all_aversion, errors='coerce')
            general_aversion_score = _avg(all_aversion)
        
        # Calculate adjusted wellbeing that factors in general aversion
        # Higher general aversion = lower adjusted wellbeing (calibration factor)
        # Formula: adjusted_wellbeing = net_wellbeing - (general_aversion * calibration_factor)
        # Calibration factor of 0.3 means: general_aversion of 50 reduces wellbeing by 15 points
        # This accounts for the psychological burden of dreading upcoming tasks
        calibration_factor = 0.3
        avg_net_wellbeing = _avg(df['net_wellbeing'])
        # Handle NaN case for general_aversion_score
        if pd.isna(general_aversion_score):
            general_aversion_score = 0.0
        adjusted_wellbeing = avg_net_wellbeing - (general_aversion_score * calibration_factor)
        adjusted_wellbeing_normalized = 50.0 + (adjusted_wellbeing / 2.0)
        # Clamp to 0-100 range
        adjusted_wellbeing_normalized = max(0.0, min(100.0, adjusted_wellbeing_normalized))
        
        # Build result dictionary
        result = {}
        
        # Counts (always calculate basic ones, conditionally calculate self-care)
        if requested_metrics is None or any(needs_metric(k) for k in ['active', 'completed_7d', 'total_created', 'total_completed', 'completion_rate', 'daily_self_care_tasks', 'avg_daily_self_care_tasks']):
            result['counts'] = {
                'active': int(len(active)),
                'completed_7d': int(len(completed_7d)),
                'total_created': int(total_created),
                'total_completed': int(total_completed),
                'completion_rate': round(completion_rate, 1),
            }
            if needs_metric('daily_self_care_tasks') or needs_metric('avg_daily_self_care_tasks') or needs_metric('self_care_frequency'):
                result['counts']['daily_self_care_tasks'] = daily_self_care_tasks
                result['counts']['avg_daily_self_care_tasks'] = avg_daily_self_care_tasks
        
        # Quality metrics
        if requested_metrics is None or any(needs_metric(k) for k in ['avg_relief', 'avg_cognitive_load', 'avg_stress_level', 'avg_net_wellbeing', 'avg_net_wellbeing_normalized', 'avg_stress_efficiency', 'avg_aversion', 'adjusted_wellbeing', 'adjusted_wellbeing_normalized', 'thoroughness_score', 'thoroughness_factor']):
            result['quality'] = {}
            if needs_metric('avg_relief'):
                result['quality']['avg_relief'] = _avg(df['relief_score'])
            if needs_metric('avg_cognitive_load'):
                result['quality']['avg_cognitive_load'] = _avg(df['cognitive_load'])
            if needs_metric('avg_stress_level'):
                result['quality']['avg_stress_level'] = _avg(df['stress_level'])
            if needs_metric('avg_net_wellbeing'):
                result['quality']['avg_net_wellbeing'] = _avg(df['net_wellbeing'])
            if needs_metric('avg_net_wellbeing_normalized'):
                result['quality']['avg_net_wellbeing_normalized'] = _avg(df['net_wellbeing_normalized'])
            if needs_metric('avg_stress_efficiency'):
                result['quality']['avg_stress_efficiency'] = _avg(df['stress_efficiency'])
            if needs_metric('avg_aversion'):
                result['quality']['avg_aversion'] = round(avg_aversion_completed, 1)
            if needs_metric('adjusted_wellbeing'):
                result['quality']['adjusted_wellbeing'] = round(adjusted_wellbeing, 2)
            if needs_metric('adjusted_wellbeing_normalized'):
                result['quality']['adjusted_wellbeing_normalized'] = round(adjusted_wellbeing_normalized, 2)
            if needs_metric('thoroughness_score'):
                result['quality']['thoroughness_score'] = round(thoroughness_score, 1)
            if needs_metric('thoroughness_factor'):
                result['quality']['thoroughness_factor'] = round(thoroughness_factor, 3)
        
        # Time metrics
        if requested_metrics is None or any(needs_metric(k) for k in ['median_duration', 'avg_delay', 'estimation_accuracy']):
            result['time'] = {}
            if needs_metric('median_duration'):
                result['time']['median_duration'] = _median(df['duration_minutes'])
            if needs_metric('avg_delay'):
                result['time']['avg_delay'] = _avg(df['delay_minutes'])
            if needs_metric('estimation_accuracy'):
                result['time']['estimation_accuracy'] = round(time_accuracy, 2)
        
        # Life balance
        if needs_metric('life_balance_score') or needs_metric('balance_score'):
            result['life_balance'] = life_balance
        
        # Aversion
        if needs_metric('general_aversion_score'):
            result['aversion'] = {
                'general_aversion_score': round(general_aversion_score, 1),
            }
        
        # Productivity volume (only if needed)
        if requested_metrics is None or any(needs_metric(k) for k in ['avg_daily_work_time', 'work_volume_score', 'work_consistency_score', 'productivity_potential_score', 'work_volume_gap', 'composite_productivity_score', 'avg_base_productivity', 'volumetric_productivity_score', 'volumetric_potential_score']):
            result['productivity_volume'] = {}
            if needs_metric('avg_daily_work_time'):
                result['productivity_volume']['avg_daily_work_time'] = round(avg_daily_work_time, 1)
            if needs_metric('work_volume_score'):
                result['productivity_volume']['work_volume_score'] = round(work_volume_score, 1)
            if needs_metric('work_consistency_score'):
                result['productivity_volume']['work_consistency_score'] = round(work_consistency_score, 1)
            if needs_metric('productivity_potential_score'):
                result['productivity_volume']['productivity_potential_score'] = round(productivity_potential.get('potential_score', 0.0), 1)
            if needs_metric('work_volume_gap'):
                result['productivity_volume']['work_volume_gap'] = round(productivity_potential.get('gap_hours', 0.0), 1)
            if needs_metric('composite_productivity_score'):
                result['productivity_volume']['composite_productivity_score'] = round(composite_productivity, 1)
            if needs_metric('avg_base_productivity'):
                result['productivity_volume']['avg_base_productivity'] = round(avg_base_productivity, 1)
            if needs_metric('volumetric_productivity_score'):
                result['productivity_volume']['volumetric_productivity_score'] = round(volumetric_productivity, 1)
            if needs_metric('volumetric_potential_score'):
                result['productivity_volume']['volumetric_potential_score'] = round(volumetric_potential, 1)
        
        # Store full result in cache (only if metrics=None, otherwise cache is less useful)
        # Cache is now user-specific, keyed by user_id
        if metrics is None:
            import time
            cache_key = user_id if user_id is not None else "default"
            self._dashboard_metrics_cache[cache_key] = result.copy()
            self._dashboard_metrics_cache_time[cache_key] = time.time()
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_dashboard_metrics: {duration:.2f}ms")
        return result

    def get_life_balance(self, user_id: Optional[int] = None) -> Dict[str, any]:
        """Calculate life balance metric comparing work and play task amounts.
        
        Args:
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Dict with work_count, play_count, work_time_minutes, play_time_minutes,
            balance_score (0-100, where 50 = balanced), and ratio
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        
        if df.empty:
            return {
                'work_count': 0,
                'play_count': 0,
                'self_care_count': 0,
                'work_time_minutes': 0.0,
                'play_time_minutes': 0.0,
                'self_care_time_minutes': 0.0,
                'balance_score': 50.0,
                'work_play_ratio': 0.0,
            }
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        if tasks_df.empty or 'task_type' not in tasks_df.columns:
            return {
                'work_count': 0,
                'play_count': 0,
                'self_care_count': 0,
                'work_time_minutes': 0.0,
                'play_time_minutes': 0.0,
                'self_care_time_minutes': 0.0,
                'balance_score': 50.0,
                'work_play_ratio': 0.0,
            }
        
        # Join instances with tasks to get task_type
        merged = df.merge(
            tasks_df[['task_id', 'task_type']],
            on='task_id',
            how='left'
        )
        
        # Filter to completed tasks only
        if 'completed_at' not in merged.columns:
            return {
                'work_count': 0,
                'play_count': 0,
                'self_care_count': 0,
                'work_time_minutes': 0.0,
                'play_time_minutes': 0.0,
                'self_care_time_minutes': 0.0,
                'balance_score': 50.0,
                'work_play_ratio': 0.0,
            }
        completed = merged[merged['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'work_count': 0,
                'play_count': 0,
                'self_care_count': 0,
                'work_time_minutes': 0.0,
                'play_time_minutes': 0.0,
                'self_care_time_minutes': 0.0,
                'balance_score': 50.0,
                'work_play_ratio': 0.0,
            }
        
        # Fill missing task_type with 'Work' as default
        completed['task_type'] = completed['task_type'].fillna('Work')
        
        # Normalize task_type to lowercase for comparison
        completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
        
        # Get duration in minutes
        completed['duration_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce').fillna(0.0)
        
        # Count tasks by type (case-insensitive)
        work_tasks = completed[completed['task_type_normalized'] == 'work']
        play_tasks = completed[completed['task_type_normalized'] == 'play']
        self_care_tasks = completed[completed['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])]
        
        work_count = len(work_tasks)
        play_count = len(play_tasks)
        self_care_count = len(self_care_tasks)
        
        # Calculate time spent
        work_time = work_tasks['duration_numeric'].sum()
        play_time = play_tasks['duration_numeric'].sum()
        self_care_time = self_care_tasks['duration_numeric'].sum()
        
        # Calculate work/play ratio (work / (work + play))
        total_work_play_time = work_time + play_time
        if total_work_play_time > 0:
            work_play_ratio = work_time / total_work_play_time
        else:
            work_play_ratio = 0.5  # Neutral if no data
        
        # Calculate balance score (0-100 scale)
        # 50 = perfectly balanced (50% work, 50% play)
        # 0 = all play, 100 = all work
        # Formula: 50 + (work_play_ratio - 0.5) * 100
        balance_score = 50.0 + ((work_play_ratio - 0.5) * 100.0)
        balance_score = max(0.0, min(100.0, balance_score))
        
        return {
            'work_count': int(work_count),
            'play_count': int(play_count),
            'self_care_count': int(self_care_count),
            'work_time_minutes': round(float(work_time), 1),
            'play_time_minutes': round(float(play_time), 1),
            'self_care_time_minutes': round(float(self_care_time), 1),
            'balance_score': round(balance_score, 1),
            'work_play_ratio': round(work_play_ratio, 3),
        }

    def get_daily_work_volume_metrics(self, days: int = 30, user_id: Optional[int] = None) -> Dict[str, any]:
        """Calculate daily work volume metrics including average work time, volume score, and consistency.
        
        Uses work time history data to calculate metrics. Includes all days in the period
        (with 0 for days with no work) for accurate consistency calculation.
        
        Args:
            days: Number of days to analyze (default 30)
            user_id: Optional user_id. If None, gets from authenticated session.
            
        Returns:
            Dict with:
            - avg_daily_work_time: Average work time per day (only counting days with work)
            - work_volume_score: Volume score (0-100)
            - work_consistency_score: Consistency score (0-100, based on variance)
            - daily_work_times: List of daily work times (only days with work > 0)
            - daily_work_times_history: List of all daily work times (including 0s for no-work days)
            - work_days_count: Number of days with work > 0
            - total_days: Total days in period
            - variance: Calculated variance value
            - days_with_work: Same as work_days_count
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        
        # Calculate date range for history (needed for all return cases)
        cutoff_date = datetime.now() - timedelta(days=days)
        date_range = pd.date_range(start=cutoff_date.date(), end=datetime.now().date(), freq='D')
        all_dates = [d.date() for d in date_range]
        empty_history = [0.0] * len(all_dates)  # Empty history for early returns
        
        if df.empty or user_id is None:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        if tasks_df.empty or 'task_type' not in tasks_df.columns:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Join instances with tasks to get task_type
        merged = df.merge(
            tasks_df[['task_id', 'task_type']],
            on='task_id',
            how='left'
        )
        
        # Filter to completed work tasks only
        if 'completed_at' not in merged.columns:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        completed = merged[merged['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Fill missing task_type with 'Work' as default
        completed['task_type'] = completed['task_type'].fillna('Work')
        completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
        
        # Get duration in minutes
        completed['duration_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce').fillna(0.0)
        
        # Filter to work tasks
        work_tasks = completed[completed['task_type_normalized'] == 'work'].copy()
        
        if work_tasks.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Parse completed_at dates
        work_tasks['completed_at_dt'] = pd.to_datetime(work_tasks['completed_at'], errors='coerce')
        work_tasks = work_tasks[work_tasks['completed_at_dt'].notna()]
        
        if work_tasks.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Filter to last N days
        recent_work = work_tasks[work_tasks['completed_at_dt'] >= cutoff_date].copy()
        
        if recent_work.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': empty_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Group by date and sum work time per day
        recent_work['date'] = recent_work['completed_at_dt'].dt.date
        daily_work = recent_work.groupby('date')['duration_numeric'].sum()
        
        # Create complete daily work times history (include 0 for days with no work)
        # This is the "history" - all days in the period with their work times
        # Use the all_dates already calculated above
        daily_work_dict = {date: float(time) for date, time in daily_work.items()}
        daily_work_times_history = [daily_work_dict.get(date, 0.0) for date in all_dates]
        
        # Also keep list of only days with work > 0 for volume calculation
        # This is used for calculating average (only count days with actual work)
        daily_work_times = [float(time) for time in daily_work.values if time > 0]
        work_days_count = len(daily_work_times)
        
        if work_days_count == 0:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'daily_work_times_history': daily_work_times_history,
                'work_days_count': 0,
                'variance': 0.0,
                'days_with_work': 0,
                'total_days': len(all_dates),
            }
        
        # Calculate average daily work time (only counting days with work)
        avg_daily_work_time = sum(daily_work_times) / work_days_count
        
        # Calculate work volume score (0-100)
        # 0-2 hours/day = 0-25 (low volume)
        # 2-4 hours/day = 25-50 (moderate)
        # 4-6 hours/day = 50-75 (good)
        # 6-8 hours/day = 75-100 (high volume)
        if avg_daily_work_time <= 120:  # 2 hours
            work_volume_score = (avg_daily_work_time / 120) * 25
        elif avg_daily_work_time <= 240:  # 4 hours
            work_volume_score = 25 + ((avg_daily_work_time - 120) / 120) * 25
        elif avg_daily_work_time <= 360:  # 6 hours
            work_volume_score = 50 + ((avg_daily_work_time - 240) / 120) * 25
        else:  # 6+ hours
            work_volume_score = 75 + min(25, ((avg_daily_work_time - 360) / 120) * 25)
        
        work_volume_score = max(0.0, min(100.0, work_volume_score))
        
        # Calculate work consistency score (0-100)
        # Use complete work time history (including 0s) for variance calculation
        # This gives a better measure of consistency (penalizes days with no work)
        variance = 0.0
        if len(daily_work_times_history) > 1:
            variance = np.var(daily_work_times_history)
            # Normalize variance: assume max reasonable variance is 4 hours (240 min) squared
            # Lower variance = higher score
            max_variance = 240.0 ** 2
            consistency_score = max(0.0, min(100.0, 100.0 * (1.0 - min(1.0, variance / max_variance))))
        elif len(daily_work_times_history) == 1:
            # Single day = perfect consistency
            consistency_score = 100.0
            variance = 0.0
        else:
            # No data
            consistency_score = 50.0
            variance = 0.0
        
        return {
            'avg_daily_work_time': round(float(avg_daily_work_time), 1),
            'work_volume_score': round(float(work_volume_score), 1),
            'work_consistency_score': round(float(consistency_score), 1),
            'daily_work_times': daily_work_times,  # Only days with work > 0
            'daily_work_times_history': daily_work_times_history,  # All days including zeros
            'work_days_count': work_days_count,
            'variance': round(float(variance), 2),
            'days_with_work': work_days_count,
            'total_days': len(daily_work_times_history),
        }

    def get_target_hours_per_day(self, user_id: str = "default_user") -> float:
        """Get target hours per day from goal hours per week setting.
        
        Converts weekly goal to daily target. Assumes 5 work days per week.
        
        Args:
            user_id: User ID to get settings for
            
        Returns:
            Target hours per day in minutes (default: 360 = 6 hours if goal is 30 hours/week)
        """
        goal_settings = UserStateManager().get_productivity_goal_settings(user_id)
        goal_hours_per_week = goal_settings.get('goal_hours_per_week', 30.0)  # Default 30h/week = 6h/day
        
        # Convert weekly goal to daily target (assume 5 work days per week)
        target_hours_per_day = (goal_hours_per_week / 5.0) * 60.0  # Convert to minutes
        
        return target_hours_per_day
    
    def calculate_productivity_potential(self, avg_efficiency_score: float, avg_daily_work_time: float, 
                                         target_hours_per_day: Optional[float] = None,
                                         user_id: str = "default_user") -> Dict[str, any]:
        """Calculate productivity potential based on current efficiency and target work time.
        
        Args:
            avg_efficiency_score: Average efficiency score from completed tasks
            avg_daily_work_time: Current average daily work time in minutes
            target_hours_per_day: Target work hours per day in minutes (if None, uses goal setting)
            user_id: User ID to get settings for (if target_hours_per_day is None)
            
        Returns:
            Dict with potential_score, current_score, multiplier, and gap_hours
        """
        if target_hours_per_day is None:
            target_hours_per_day = self.get_target_hours_per_day(user_id)
        if avg_daily_work_time <= 0:
            return {
                'potential_score': 0.0,
                'current_score': 0.0,
                'multiplier': 0.0,
                'gap_hours': target_hours_per_day / 60.0,
            }
        
        # Current productivity score (efficiency * current hours)
        current_score = avg_efficiency_score * (avg_daily_work_time / 60.0)
        
        # Potential productivity score (efficiency * target hours)
        potential_score = avg_efficiency_score * (target_hours_per_day / 60.0)
        
        # Multiplier: how much more you could achieve
        multiplier = target_hours_per_day / max(avg_daily_work_time, 1.0)
        
        # Gap in hours
        gap_hours = (target_hours_per_day - avg_daily_work_time) / 60.0
        
        return {
            'potential_score': round(float(potential_score), 1),
            'current_score': round(float(current_score), 1),
            'multiplier': round(float(multiplier), 2),
            'gap_hours': round(float(gap_hours), 1),
        }

    def calculate_time_tracking_consistency_score(
        self, 
        days: int = 7,
        target_sleep_hours: float = 8.0,
        user_id: Optional[int] = None
    ) -> Dict[str, any]:
        """Calculate time tracking consistency score based on tracked vs untracked time.
        
        Penalizes untracked time (time not logged as work/play/self_care/sleep).
        Rewards sleep up to target_sleep_hours (default 8 hours).
        Sleep beyond target_sleep_hours is treated as untracked time.
        
        Formula:
        - Tracked time = work + play + self_care + sleep (capped at target_sleep_hours)
        - Untracked time = 24 hours - tracked time
        - Score = 100 * (1 - untracked_proportion)
        - Score is penalized more heavily as untracked time increases
        
        Args:
            days: Number of days to analyze (default 7)
            target_sleep_hours: Target sleep hours per day to reward (default 8.0)
            user_id: Optional user_id. If None, gets from authenticated session.
            
        Returns:
            Dict with:
            - tracking_consistency_score (0-100): Overall score
            - avg_tracked_time_minutes: Average tracked time per day
            - avg_untracked_time_minutes: Average untracked time per day
            - avg_sleep_time_minutes: Average sleep time per day
            - tracking_coverage: Proportion of day tracked (0-1)
            - daily_scores: List of daily scores
        """
        import time
        start = time.perf_counter()
        
        user_id = self._get_user_id(user_id)
        
        # Check cache (keyed by user_id and parameters)
        cache_key = user_id if user_id is not None else "default"
        params_key = (days, target_sleep_hours)
        current_time = time.time()
        if (cache_key in self._time_tracking_cache and 
            cache_key in self._time_tracking_cache_time and
            cache_key in self._time_tracking_cache_params and
            self._time_tracking_cache_params[cache_key] == params_key and
            (current_time - self._time_tracking_cache_time[cache_key]) < self._cache_ttl_seconds):
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] calculate_time_tracking_consistency_score (cached): {duration:.2f}ms")
            return self._time_tracking_cache[cache_key].copy()
        df = self._load_instances(user_id=user_id)
        
        if df.empty or user_id is None:
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,  # 24 hours
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        if tasks_df.empty or 'task_type' not in tasks_df.columns:
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        
        # Join instances with tasks to get task_type
        merged = df.merge(
            tasks_df[['task_id', 'task_type']],
            on='task_id',
            how='left'
        )
        
        # Filter to completed tasks only
        if 'completed_at' not in merged.columns:
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        completed = merged[merged['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        
        # Parse completion dates
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        
        # Filter to recent days
        cutoff_date = datetime.now() - timedelta(days=days)
        completed = completed[completed['completed_at_dt'] >= cutoff_date].copy()
        
        if completed.empty:
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        
        # Fill missing task_type with 'Work' as default
        completed['task_type'] = completed['task_type'].fillna('Work')
        completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
        
        # Get duration in minutes
        completed['duration_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce').fillna(0.0)
        
        # Group by date
        completed['date'] = completed['completed_at_dt'].dt.date
        
        # Calculate daily tracked time
        target_sleep_minutes = target_sleep_hours * 60.0
        minutes_per_day = 24.0 * 60.0  # 1440 minutes
        
        daily_data = []
        daily_scores = []
        
        for date, group in completed.groupby('date'):
            # Calculate time by category
            work_time = group[group['task_type_normalized'] == 'work']['duration_numeric'].sum()
            play_time = group[group['task_type_normalized'] == 'play']['duration_numeric'].sum()
            self_care_time = group[group['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])]['duration_numeric'].sum()
            sleep_time = group[group['task_type_normalized'] == 'sleep']['duration_numeric'].sum()
            
            # Cap sleep at target (reward up to target, treat excess as untracked)
            rewarded_sleep = min(sleep_time, target_sleep_minutes)
            excess_sleep = max(0.0, sleep_time - target_sleep_minutes)
            
            # Tracked time = work + play + self_care + rewarded_sleep
            tracked_time = work_time + play_time + self_care_time + rewarded_sleep
            
            # Untracked time = 24 hours - tracked time (including excess sleep)
            untracked_time = minutes_per_day - tracked_time
            
            # Calculate tracking coverage (proportion of day tracked)
            tracking_coverage = tracked_time / minutes_per_day
            
            # Score: penalize untracked time more heavily
            # Use exponential penalty: score = 100 * (1 - exp(-tracking_coverage * k))
            # k = 2.0 makes it so 50% coverage ≈ 63 score, 75% coverage ≈ 78 score, 90% coverage ≈ 83 score
            k = 2.0
            daily_score = 100.0 * (1.0 - math.exp(-tracking_coverage * k))
            daily_score = max(0.0, min(100.0, daily_score))
            
            daily_data.append({
                'date': date,
                'work_time': work_time,
                'play_time': play_time,
                'self_care_time': self_care_time,
                'sleep_time': sleep_time,
                'rewarded_sleep': rewarded_sleep,
                'tracked_time': tracked_time,
                'untracked_time': untracked_time,
                'tracking_coverage': tracking_coverage,
                'score': daily_score,
            })
            daily_scores.append(daily_score)
        
        if not daily_data:
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] calculate_time_tracking_consistency_score: {duration:.2f}ms (no data)")
            return {
                'tracking_consistency_score': 0.0,
                'avg_tracked_time_minutes': 0.0,
                'avg_untracked_time_minutes': 1440.0,
                'avg_sleep_time_minutes': 0.0,
                'tracking_coverage': 0.0,
                'daily_scores': [],
            }
        
        # Calculate averages
        avg_tracked = sum(d['tracked_time'] for d in daily_data) / len(daily_data)
        avg_untracked = sum(d['untracked_time'] for d in daily_data) / len(daily_data)
        avg_sleep = sum(d['sleep_time'] for d in daily_data) / len(daily_data)
        avg_coverage = sum(d['tracking_coverage'] for d in daily_data) / len(daily_data)
        overall_score = sum(daily_scores) / len(daily_scores) if daily_scores else 0.0
        
        result = {
            'tracking_consistency_score': round(float(overall_score), 1),
            'avg_tracked_time_minutes': round(float(avg_tracked), 1),
            'avg_untracked_time_minutes': round(float(avg_untracked), 1),
            'avg_sleep_time_minutes': round(float(avg_sleep), 1),
            'tracking_coverage': round(float(avg_coverage), 3),
            'daily_scores': [round(float(s), 1) for s in daily_scores],
        }
        
        # Store in cache
        self._time_tracking_cache[cache_key] = result.copy()
        self._time_tracking_cache_time[cache_key] = time.time()
        self._time_tracking_cache_params[cache_key] = params_key
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] calculate_time_tracking_consistency_score: {duration:.2f}ms")
        return result

    def calculate_composite_score(
        self,
        components: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
        normalize_components: bool = True
    ) -> Dict[str, any]:
        """Calculate composite score from multiple weighted components.
        
        Combines scores, bonuses, and penalties into a single normalized score (0-100).
        Each component can be weighted independently.
        
        Args:
            components: Dict of component_name -> score_value
                - Scores should be in 0-100 range (will be normalized if normalize_components=True)
                - Can include bonuses (positive) and penalties (negative)
            weights: Optional dict of component_name -> weight (default: equal weights)
                - Weights are normalized to sum to 1.0
            normalize_components: If True, clamp components to 0-100 range before weighting
            
        Returns:
            Dict with:
            - composite_score (0-100): Final normalized composite score
            - weighted_sum: Sum of weighted components before normalization
            - component_contributions: Dict of component_name -> weighted_contribution
            - normalized_weights: Dict of component_name -> normalized_weight
        """
        if not components:
            return {
                'composite_score': 0.0,
                'weighted_sum': 0.0,
                'component_contributions': {},
                'normalized_weights': {},
            }
        
        # Normalize weights (default: equal weights)
        if weights is None:
            weights = {name: 1.0 for name in components.keys()}
        
        # Ensure all components have weights
        for name in components.keys():
            if name not in weights:
                weights[name] = 1.0
        
        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight == 0:
            normalized_weights = {name: 1.0 / len(components) for name in components.keys()}
        else:
            normalized_weights = {name: weight / total_weight for name, weight in weights.items()}
        
        # Normalize components to 0-100 range if requested
        normalized_components = {}
        for name, value in components.items():
            if normalize_components:
                # Clamp to 0-100 range
                normalized_value = max(0.0, min(100.0, float(value)))
            else:
                normalized_value = float(value)
            normalized_components[name] = normalized_value
        
        # Calculate weighted sum
        weighted_sum = sum(
            normalized_components[name] * normalized_weights[name]
            for name in components.keys()
        )
        
        # Calculate component contributions
        component_contributions = {
            name: normalized_components[name] * normalized_weights[name]
            for name in components.keys()
        }
        
        # Final composite score (already in 0-100 range due to normalization)
        composite_score = max(0.0, min(100.0, weighted_sum))
        
        return {
            'composite_score': round(float(composite_score), 1),
            'weighted_sum': round(float(weighted_sum), 1),
            'component_contributions': {k: round(float(v), 2) for k, v in component_contributions.items()},
            'normalized_weights': {k: round(float(v), 3) for k, v in normalized_weights.items()},
        }

    def calculate_volumetric_productivity_score(self, base_productivity_score: float, 
                                                  work_volume_score: float) -> float:
        """Calculate volumetric productivity score by integrating volume factor into base productivity.
        
        This addresses the limitation where productivity potential and composite productivity
        may be misleading because the base productivity score doesn't account for volume.
        
        Args:
            base_productivity_score: Base productivity score from calculate_productivity_score() (0-500+)
            work_volume_score: Work volume score from get_daily_work_volume_metrics() (0-100)
            
        Returns:
            Volumetric productivity score (0-750+ = base × 0.5-1.5x multiplier)
        """
        # Convert volume score (0-100) to multiplier (0.5x to 1.5x)
        # Linear mapping: 0 volume = 0.5x, 50 volume = 1.0x, 100 volume = 1.5x
        volume_multiplier = 0.5 + (work_volume_score / 100.0) * 1.0
        
        # Apply volume multiplier to base productivity score
        volumetric_score = base_productivity_score * volume_multiplier
        
        return round(float(volumetric_score), 1)
    
    def calculate_composite_productivity_score(self, efficiency_score: float, volume_score: float, 
                                                consistency_score: float) -> float:
        """Calculate composite productivity score combining efficiency, volume, and consistency.
        
        NOTE: This method may be misleading because it combines efficiency (per-task) with
        volume (aggregate) without integrating volume into the base productivity calculation.
        Consider using volumetric_productivity_score for more accurate measurements.
        
        Args:
            efficiency_score: Per-task efficiency score (0-100+)
            volume_score: Daily work volume score (0-100)
            consistency_score: Work consistency score (0-100)
            
        Returns:
            Composite productivity score (0-100+)
        """
        # Normalize efficiency score to 0-100 range for combination
        # Assume efficiency scores typically range 0-200, so divide by 2
        normalized_efficiency = min(100.0, efficiency_score / 2.0) if efficiency_score > 0 else 0.0
        
        # Weighted combination: 40% efficiency, 40% volume, 20% consistency
        composite = (normalized_efficiency * 0.4) + (volume_score * 0.4) + (consistency_score * 0.2)
        
        return round(float(composite), 1)

    def get_all_scores_for_composite(self, days: int = 7, metrics: Optional[List[str]] = None, user_id: Optional[int] = None) -> Dict[str, float]:
        """Get all available scores, bonuses, and penalties for composite score calculation.
        
        Returns a dictionary of component_name -> score_value that can be used
        with calculate_composite_score().
        
        Cached for 5 minutes to improve performance (this is an expensive operation).
        
        Args:
            days: Number of days to analyze for time-based metrics
            metrics: Optional list of metric keys to calculate. If None, calculates all metrics.
                    Examples: ['avg_stress_level', 'work_volume_score', 'completion_rate']
            user_id: Optional user_id. If None, gets from authenticated session.
            
        Returns:
            Dict with component_name -> score_value (0-100 range where applicable)
        """
        user_id = self._get_user_id(user_id)
        import time as time_module
        
        start = time_module.perf_counter()
        
        # Determine which metrics to calculate
        if metrics is not None:
            requested_metrics = set(metrics)
            
            # Helper function to check if a metric is needed
            def needs_metric(key: str) -> bool:
                return key in requested_metrics
        else:
            requested_metrics = None
            
            # Helper function that always returns True when calculating all
            def needs_metric(key: str) -> bool:
                return True
        
        # Check cache (only if calculating all metrics)
        # Cache is now user-specific, keyed by user_id
        if requested_metrics is None:
            current_time = time_module.time()
            cache_key = user_id if user_id is not None else "default"
            if (cache_key in Analytics._composite_scores_cache and 
                cache_key in Analytics._composite_scores_cache_time and
                (current_time - Analytics._composite_scores_cache_time[cache_key]) < Analytics._cache_ttl_seconds):
                duration = (time_module.perf_counter() - start) * 1000
                print(f"[Analytics] get_all_scores_for_composite (cached): {duration:.2f}ms")
                return Analytics._composite_scores_cache[cache_key].copy()  # Return copy to prevent mutation
        
        scores = {}
        
        # Determine which dashboard metrics we need
        dashboard_metric_keys = []
        if requested_metrics is None:
            # Need all dashboard metrics
            dashboard_metric_keys = None
        else:
            # Map composite metric names to dashboard metric names
            if needs_metric('avg_stress_level') or needs_metric('avg_net_wellbeing') or needs_metric('avg_stress_efficiency') or needs_metric('avg_relief'):
                dashboard_metric_keys = ['quality.avg_stress_level', 'quality.avg_net_wellbeing_normalized', 'quality.avg_stress_efficiency', 'quality.avg_relief']
            if needs_metric('work_volume_score') or needs_metric('work_consistency_score'):
                dashboard_metric_keys.extend(['productivity_volume.work_volume_score', 'productivity_volume.work_consistency_score'])
            if needs_metric('life_balance_score'):
                dashboard_metric_keys.append('life_balance_score')
            if needs_metric('completion_rate'):
                dashboard_metric_keys.append('counts.completion_rate')
            if needs_metric('self_care_frequency'):
                dashboard_metric_keys.append('counts.avg_daily_self_care_tasks')
        
        # Get dashboard metrics (selectively if requested)
        metrics_data = self.get_dashboard_metrics(metrics=dashboard_metric_keys, user_id=user_id)
        
        # Quality scores (0-100 range)
        if needs_metric('avg_stress_level') or needs_metric('avg_net_wellbeing') or needs_metric('avg_stress_efficiency') or needs_metric('avg_relief'):
            quality = metrics_data.get('quality', {})
            if needs_metric('avg_stress_level'):
                scores['avg_stress_level'] = 100.0 - float(quality.get('avg_stress_level', 50.0))  # Invert: lower stress = higher score
            if needs_metric('avg_net_wellbeing'):
                scores['avg_net_wellbeing'] = float(quality.get('avg_net_wellbeing_normalized', 50.0))
            if needs_metric('avg_stress_efficiency'):
                scores['avg_stress_efficiency'] = float(quality.get('avg_stress_efficiency', 50.0)) if quality.get('avg_stress_efficiency') is not None else 50.0
            if needs_metric('avg_relief'):
                scores['avg_relief'] = float(quality.get('avg_relief', 50.0))
        
        # Productivity scores
        if needs_metric('work_volume_score') or needs_metric('work_consistency_score'):
            productivity_volume = metrics_data.get('productivity_volume', {})
            if needs_metric('work_volume_score'):
                scores['work_volume_score'] = float(productivity_volume.get('work_volume_score', 0.0))
            if needs_metric('work_consistency_score'):
                scores['work_consistency_score'] = float(productivity_volume.get('work_consistency_score', 50.0))
        
        # Life balance
        if needs_metric('life_balance_score'):
            life_balance = metrics_data.get('life_balance', {})
            scores['life_balance_score'] = float(life_balance.get('balance_score', 50.0))
        
        # Relief summary (only if needed)
        if needs_metric('weekly_relief_score'):
            relief_summary = self.get_relief_summary(user_id=user_id)
            # Normalize weekly relief to 0-100 (assuming typical range 0-1000)
            weekly_relief = float(relief_summary.get('weekly_relief_score_with_bonus_robust', 0.0))
            scores['weekly_relief_score'] = min(100.0, weekly_relief / 10.0)  # Scale down if needed
        
        # Time tracking consistency score (only if needed)
        if needs_metric('tracking_consistency_score'):
            tracking_data = self.calculate_time_tracking_consistency_score(days=days, user_id=user_id)
            scores['tracking_consistency_score'] = float(tracking_data.get('tracking_consistency_score', 0.0))
        
        # Counts (normalize to 0-100)
        if needs_metric('completion_rate') or needs_metric('self_care_frequency'):
            counts = metrics_data.get('counts', {})
            if needs_metric('completion_rate'):
                completion_rate = float(counts.get('completion_rate', 0.0))
                scores['completion_rate'] = completion_rate  # Already 0-100
            if needs_metric('self_care_frequency'):
                avg_self_care = float(counts.get('avg_daily_self_care_tasks', 0.0))
                scores['self_care_frequency'] = min(100.0, avg_self_care * 20.0)  # 5 tasks = 100 score
        
        # Execution score (average of recent completed instances)
        # NOTE: Execution score is calculated separately in chunks by the dashboard
        # to allow UI to remain responsive. Use get_execution_score_chunked() instead.
        if needs_metric('execution_score'):
            scores['execution_score'] = 50.0  # Placeholder - will be updated by chunked calculation
        
        # Cache the result (only if calculating all metrics)
        # Cache is now user-specific, keyed by user_id
        if requested_metrics is None:
            cache_key = user_id if user_id is not None else "default"
            Analytics._composite_scores_cache[cache_key] = scores.copy()
            Analytics._composite_scores_cache_time[cache_key] = time_module.time()
        
        duration = (time_module.perf_counter() - start) * 1000
        print(f"[Analytics] get_all_scores_for_composite: {duration:.2f}ms")
        return scores
    
    def get_execution_score_chunked(self, state: Dict[str, any], batch_size: int = 5, user_id: str = "default", persist: bool = True) -> Dict[str, any]:
        """Calculate execution score in chunks to allow UI to remain responsive.
        
        This method processes instances in small batches, allowing the UI to respond
        between batches. State is preserved between calls and can persist across page refreshes.
        
        Args:
            state: Dictionary containing:
                - 'instances': List of instances to process (set on first call or loaded from persistence)
                - 'current_index': Current index in instances list (0 on first call or loaded from persistence)
                - 'execution_scores': List of calculated scores (empty on first call or loaded from persistence)
                - 'completed': Whether all instances have been processed
            batch_size: Number of instances to process per chunk (default 5)
            user_id: User ID for persistence (default "default")
            persist: Whether to save state to user_state (default True)
            
        Returns:
            Updated state dictionary with:
                - 'completed': True if all instances processed, False otherwise
                - 'avg_execution_score': Average score if completed, None otherwise
        """
        import time as time_module
        from .user_state import UserStateManager
        
        # Try to load persisted state if state is empty
        if not state or 'instances' not in state or state.get('instances') is None:
            if persist:
                user_state = UserStateManager()
                persisted = user_state.get_execution_score_chunk_state(user_id)
                if persisted:
                    # Restore progress from persistence
                    state['current_index'] = persisted.get('current_index', 0)
                    state['execution_scores'] = persisted.get('execution_scores', [])
                    state['completed'] = persisted.get('completed', False)
                    # Reload instances list (not persisted due to size)
                    # #region agent log
                    load_instances_start = time_module.perf_counter()
                    try:
                        import json as json_module
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'LOAD', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'loading instances via list_recent_completed', 'data': {'limit': 50}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    from .instance_manager import InstanceManager
                    instance_manager = InstanceManager()
                    # Convert string user_id to int for database queries
                    user_id_int = None
                    if isinstance(user_id, str) and user_id.isdigit():
                        user_id_int = int(user_id)
                    elif user_id != "default":
                        # Try to get current user if user_id is not "default"
                        user_id_int = self._get_user_id(None)
                    else:
                        # For "default", try to get current authenticated user
                        user_id_int = self._get_user_id(None)
                    state['instances'] = instance_manager.list_recent_completed(limit=50, user_id=user_id_int)
                    # #region agent log
                    load_instances_duration = time_module.perf_counter() - load_instances_start
                    try:
                        import json as json_module
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'LOAD', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'instances loaded', 'data': {'duration_seconds': load_instances_duration, 'instance_count': len(state['instances'])}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    # If we had progress, resume from where we left off
                    if state['current_index'] > 0 and not state['completed']:
                        # #region agent log
                        try:
                            import json as json_module
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'CHUNK', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'resuming chunked execution score calculation from persistence', 'data': {'resume_index': state['current_index'], 'total': len(state['instances']), 'scores_so_far': len(state['execution_scores'])}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                        except: pass
                        # #endregion
                        # Don't re-initialize, just continue processing
                    else:
                        # Fresh start
                        state['current_index'] = 0
                        state['execution_scores'] = []
                        state['completed'] = False
                else:
                    # No persisted state - initialize fresh
                    # #region agent log
                    load_instances_start = time_module.perf_counter()
                    try:
                        import json as json_module
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'LOAD', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'loading instances via list_recent_completed', 'data': {'limit': 50}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    from .instance_manager import InstanceManager
                    instance_manager = InstanceManager()
                    # Convert string user_id to int for database queries
                    user_id_int = None
                    if isinstance(user_id, str) and user_id.isdigit():
                        user_id_int = int(user_id)
                    elif user_id != "default":
                        # Try to get current user if user_id is not "default"
                        user_id_int = self._get_user_id(None)
                    else:
                        # For "default", try to get current authenticated user
                        user_id_int = self._get_user_id(None)
                    state['instances'] = instance_manager.list_recent_completed(limit=50, user_id=user_id_int)
                    # #region agent log
                    load_instances_duration = time_module.perf_counter() - load_instances_start
                    try:
                        import json as json_module
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'LOAD', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'instances loaded', 'data': {'duration_seconds': load_instances_duration, 'instance_count': len(state['instances'])}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    state['current_index'] = 0
                    state['execution_scores'] = []
                    state['completed'] = False
            else:
                # Not persisting - initialize fresh
                # #region agent log
                load_instances_start = time_module.perf_counter()
                try:
                    import json as json_module
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'LOAD', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'loading instances via list_recent_completed', 'data': {'limit': 50}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                from .instance_manager import InstanceManager
                instance_manager = InstanceManager()
                # Convert string user_id to int for list_recent_completed()
                user_id_int = None
                if isinstance(user_id, str) and user_id.isdigit():
                    user_id_int = int(user_id)
                elif user_id != "default":
                    # Try to get current user if user_id is not "default"
                    user_id_int = self._get_user_id(None)
                else:
                    # For "default", try to get current authenticated user
                    user_id_int = self._get_user_id(None)
                state['instances'] = instance_manager.list_recent_completed(limit=50, user_id=user_id_int)
                # #region agent log
                load_instances_duration = time_module.perf_counter() - load_instances_start
                try:
                    import json as json_module
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'LOAD', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'instances loaded', 'data': {'duration_seconds': load_instances_duration, 'instance_count': len(state['instances'])}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                state['current_index'] = 0
                state['execution_scores'] = []
                state['completed'] = False
            
            # #region agent log
            try:
                import json as json_module
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'CHUNK', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'starting chunked execution score calculation', 'data': {'instance_count': len(state['instances']), 'batch_size': batch_size, 'resuming': state.get('current_index', 0) > 0}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
            except: pass
            # #endregion
        
        # Process a batch of instances
        instances = state['instances']
        current_index = state['current_index']
        execution_scores = state['execution_scores']
        
        end_index = min(current_index + batch_size, len(instances))
        
        # #region agent log
        try:
            import json as json_module
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'CHUNK', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'processing batch', 'data': {'start_index': current_index, 'end_index': end_index, 'total': len(instances)}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
        except: pass
        # #endregion
        
        # #region agent log
        batch_start_time = time_module.perf_counter()
        try:
            import json as json_module
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'starting batch execution score calculation', 'data': {'batch_start': current_index, 'batch_end': end_index, 'batch_size': end_index - current_index}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
        except: pass
        # #endregion
        
        for idx in range(current_index, end_index):
            # #region agent log
            instance_start = time_module.perf_counter()
            try:
                import json as json_module
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H3', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'calculating execution score for instance', 'data': {'instance_index': idx, 'total_instances': len(instances)}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            try:
                execution_score = self.calculate_execution_score(instances[idx])
                # #region agent log
                instance_duration = time_module.perf_counter() - instance_start
                try:
                    import json as json_module
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H3', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'execution score calculated for instance', 'data': {'instance_index': idx, 'duration_seconds': instance_duration, 'score': execution_score}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                if execution_score is not None:
                    execution_scores.append(execution_score)
            except Exception as e:
                print(f"[Analytics] Error calculating execution score for instance {idx}: {e}")
        
        # #region agent log
        batch_duration = time_module.perf_counter() - batch_start_time
        try:
            import json as json_module
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'batch execution score calculation completed', 'data': {'batch_size': end_index - current_index, 'total_duration_seconds': batch_duration, 'avg_per_instance': batch_duration / (end_index - current_index) if (end_index - current_index) > 0 else 0}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
        except: pass
        # #endregion
        
        state['current_index'] = end_index
        state['execution_scores'] = execution_scores
        
        # Check if we're done
        if end_index >= len(instances):
            state['completed'] = True
            avg_execution_score = sum(execution_scores) / len(execution_scores) if execution_scores else 50.0
            state['avg_execution_score'] = avg_execution_score
            
            # Clear persisted state when completed
            if persist:
                try:
                    user_state = UserStateManager()
                    user_state.update_preference(user_id, "execution_score_chunk_state", "")  # Clear it
                except Exception as e:
                    print(f"[Analytics] Error clearing persisted chunk state: {e}")
            
            # #region agent log
            try:
                import json as json_module
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'CHUNK', 'location': 'analytics.py:get_execution_score_chunked', 'message': 'chunked execution score calculation completed', 'data': {'total_instances': len(instances), 'score_count': len(execution_scores), 'avg_score': avg_execution_score}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
            except: pass
            # #endregion
        else:
            state['completed'] = False
            state['avg_execution_score'] = None
            
            # Persist progress after each chunk
            if persist:
                try:
                    user_state = UserStateManager()
                    user_state.set_execution_score_chunk_state(state, user_id)
                except Exception as e:
                    print(f"[Analytics] Error persisting chunk state: {e}")
        
        return state

    def get_tracking_consistency_multiplier(self, days: int = 7) -> float:
        """Get tracking consistency score as a multiplier (0.0 to 1.0).
        
        Useful for adjusting other scores based on time tracking completeness.
        Returns 1.0 for perfect tracking, 0.0 for no tracking.
        
        Args:
            days: Number of days to analyze (default 7)
            
        Returns:
            Multiplier value (0.0 to 1.0)
        """
        tracking_data = self.calculate_time_tracking_consistency_score(days=days)
        score = tracking_data.get('tracking_consistency_score', 0.0)
        return max(0.0, min(1.0, score / 100.0))

    def calculate_focus_factor(
        self,
        row: Union[pd.Series, Dict]
    ) -> float:
        """Calculate focus factor (0.0-1.0) based on emotion-based indicators only.
        
        Focus is a mental state (ability to concentrate), measured through emotions.
        This is 100% emotion-based - no behavioral components.
        
        Focus-positive emotions: focused, concentrated, determined, engaged, present, mindful, etc.
        Focus-negative emotions: distracted, scattered, unfocused, restless, anxious, overwhelmed, etc.
        
        Args:
            row: Task instance row (pandas Series from CSV or dict from database)
                 Must contain: predicted_dict/actual_dict (or predicted/actual)
        
        Returns:
            Focus factor (0.0-1.0), where 1.0 = high focus, 0.5 = neutral, 0.0 = low focus
        """
        # Handle both pandas Series (CSV) and dict (database) formats
        if isinstance(row, pd.Series):
            predicted_dict = {}
            actual_dict = {}
            if 'predicted_dict' in row and row.get('predicted_dict'):
                try:
                    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
                except (json.JSONDecodeError, TypeError):
                    predicted_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
        else:
            # Database format (dict)
            predicted = row.get('predicted', {})
            actual = row.get('actual', {})
            predicted_dict = predicted if isinstance(predicted, dict) else {}
            actual_dict = actual if isinstance(actual, dict) else {}
        
        # Emotion-Based Focus Score (100% of focus factor)
        emotion_score = 0.5  # Default neutral
        
        try:
            # Try actual emotions first, fallback to predicted
            emotion_values = actual_dict.get('emotion_values', {}) or predicted_dict.get('emotion_values', {})
            
            if emotion_values and isinstance(emotion_values, dict):
                focus_positive = ['focused', 'concentrated', 'determined', 'engaged', 'flow', 
                                 'in the zone', 'present', 'mindful', 'attentive', 'alert', 'sharp', 'absorbed']
                focus_negative = ['distracted', 'scattered', 'overwhelmed', 'frazzled', 
                                  'unfocused', 'disengaged', 'zoned out', 'spaced out', 'restless', 'anxious']
                
                positive_score = 0.0
                negative_score = 0.0
                
                for emotion, value in emotion_values.items():
                    if not emotion or not value:
                        continue
                    try:
                        emotion_lower = str(emotion).lower()
                        value_float = float(value)
                        
                        # Check for focus-positive emotions (substring match)
                        if any(pos in emotion_lower for pos in focus_positive):
                            positive_score += max(0.0, min(100.0, value_float)) / 100.0
                        # Check for focus-negative emotions
                        elif any(neg in emotion_lower for neg in focus_negative):
                            negative_score += max(0.0, min(100.0, value_float)) / 100.0
                    except (ValueError, TypeError):
                        continue
                
                # Net score: positive - negative, normalized to 0-1
                # Cap individual contributions to prevent single emotion from dominating
                positive_score = min(1.0, positive_score)
                negative_score = min(1.0, negative_score)
                emotion_score = 0.5 + (positive_score - negative_score) * 0.5
                emotion_score = max(0.0, min(1.0, emotion_score))
        except Exception as e:
            # On error, use neutral
            emotion_score = 0.5
        
        # Focus factor is 100% emotion-based
        return emotion_score

    def calculate_momentum_factor(
        self,
        row: Union[pd.Series, Dict],
        lookback_hours: int = 24,
        repetition_days: int = 7
    ) -> float:
        """Calculate momentum factor (0.0-1.0) based on behavioral patterns.
        
        Momentum measures building energy through repeated action (behavioral, not mental state).
        Combines four components:
        1. Task clustering (40%): Short gaps between completions
        2. Task volume (30%): Many tasks completed recently
        3. Template consistency (20%): Repeating same template
        4. Acceleration (10%): Tasks getting faster over time
        
        Args:
            row: Task instance row (pandas Series from CSV or dict from database)
                 Must contain: predicted_dict/actual_dict (or predicted/actual),
                 completed_at, task_id, duration_minutes
            lookback_hours: Hours to look back for clustering and volume (default: 24)
            repetition_days: Days to look back for template consistency (default: 7)
        
        Returns:
            Momentum factor (0.0-1.0), where 1.0 = high momentum, 0.5 = neutral, 0.0 = low momentum
        """
        import math
        
        # Handle both pandas Series (CSV) and dict (database) formats
        if isinstance(row, pd.Series):
            predicted_dict = {}
            actual_dict = {}
            if 'predicted_dict' in row and row.get('predicted_dict'):
                try:
                    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
                except (json.JSONDecodeError, TypeError):
                    predicted_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
            completed_at = row.get('completed_at')
            task_id = row.get('task_id')
            duration_minutes = row.get('duration_minutes', 0)
        else:
            # Database format (dict)
            predicted = row.get('predicted', {})
            actual = row.get('actual', {})
            predicted_dict = predicted if isinstance(predicted, dict) else {}
            actual_dict = actual if isinstance(actual, dict) else {}
            completed_at = row.get('completed_at')
            task_id = row.get('task_id')
            duration_minutes = row.get('duration_minutes', 0)
        
        # Default to neutral if missing critical data
        if not completed_at:
            return 0.5
        
        # Parse completion time
        try:
            if isinstance(completed_at, str):
                current_completion_time = pd.to_datetime(completed_at)
            else:
                current_completion_time = completed_at
        except (ValueError, TypeError):
            return 0.5
        
        # 1. Task Clustering Score (40% weight)
        clustering_score = 0.5  # Default neutral
        
        try:
            user_id = self._get_user_id(None)
            df = self._load_instances(user_id=user_id)
            if not df.empty:
                # Get completed tasks only
                completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                
                if not completed.empty:
                    # Parse completed_at timestamps
                    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                    completed = completed.dropna(subset=['completed_at_dt'])
                    
                    # Get recent completions within lookback window
                    cutoff_time = current_completion_time - timedelta(hours=lookback_hours)
                    recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                    recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                    
                    # Sort by completion time
                    recent = recent.sort_values('completed_at_dt')
                    
                    if len(recent) >= 2:
                        # Calculate average gap between completions
                        gaps = []
                        for i in range(1, len(recent)):
                            gap_minutes = (recent.iloc[i]['completed_at_dt'] - 
                                         recent.iloc[i-1]['completed_at_dt']).total_seconds() / 60.0
                            gaps.append(gap_minutes)
                        
                        if gaps:
                            avg_gap = sum(gaps) / len(gaps)
                            
                            # Normalize: shorter gaps = higher score
                            if avg_gap <= 15:
                                clustering_score = 1.0
                            elif avg_gap <= 60:
                                # Linear: 15 min → 1.0, 60 min → 0.5
                                clustering_score = 1.0 - ((avg_gap - 15) / 45.0) * 0.5
                            elif avg_gap <= 240:
                                # Exponential decay: 60 min → 0.5, 240 min → 0.25
                                clustering_score = 0.5 * (1.0 / (avg_gap / 60.0))
                            else:
                                clustering_score = 0.1  # Floor for very long gaps
        except Exception as e:
            # On error, use neutral
            clustering_score = 0.5
        
        # 2. Task Volume Score (30% weight)
        volume_score = 0.5  # Default neutral
        
        try:
            user_id = self._get_user_id(None)
            df = self._load_instances(user_id=user_id)
            if not df.empty:
                # Get completed tasks only
                completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                
                if not completed.empty:
                    # Parse completed_at timestamps
                    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                    completed = completed.dropna(subset=['completed_at_dt'])
                    
                    # Get recent completions within lookback window
                    cutoff_time = current_completion_time - timedelta(hours=lookback_hours)
                    recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                    recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                    
                    total_recent_completions = len(recent)
                    
                    # Volume bonus: 1 task = 0.5, 3 tasks = 0.7, 5 tasks = 0.85, 10+ tasks = 1.0
                    if total_recent_completions <= 1:
                        volume_score = 0.5
                    elif total_recent_completions <= 3:
                        # Linear: 1 → 0.5, 3 → 0.7
                        volume_score = 0.5 + (total_recent_completions - 1) / 2.0 * 0.2
                    elif total_recent_completions <= 5:
                        # Linear: 3 → 0.7, 5 → 0.85
                        volume_score = 0.7 + (total_recent_completions - 3) / 2.0 * 0.15
                    elif total_recent_completions <= 10:
                        # Linear: 5 → 0.85, 10 → 1.0
                        volume_score = 0.85 + (total_recent_completions - 5) / 5.0 * 0.15
                    else:
                        volume_score = 1.0  # Max at 10+ tasks
        except Exception as e:
            # On error, use neutral
            volume_score = 0.5
        
        # 3. Template Consistency Score (20% weight)
        consistency_score = 0.5  # Default neutral
        
        try:
            if task_id:
                user_id = self._get_user_id(None)
                df = self._load_instances(user_id=user_id)
                if not df.empty:
                    # Get completed tasks only
                    completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                    
                    if not completed.empty:
                        # Parse completed_at timestamps
                        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                        completed = completed.dropna(subset=['completed_at_dt'])
                        
                        # Get recent completions within repetition window
                        cutoff_time = current_completion_time - timedelta(days=repetition_days)
                        recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                        recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                        
                        # Count completions of this template
                        same_template_count = len(recent[recent['task_id'] == task_id])
                        
                        # Template consistency: 1 instance = 0.5, 2-5 instances = 0.5→0.8, 6-10 instances = 0.8→1.0, 10+ = 1.0
                        if same_template_count <= 1:
                            consistency_score = 0.5  # Neutral for first completion
                        elif same_template_count <= 5:
                            # Linear: 1 → 0.5, 5 → 0.8
                            consistency_score = 0.5 + (same_template_count - 1) / 4.0 * 0.3
                        elif same_template_count <= 10:
                            # Linear: 5 → 0.8, 10 → 1.0
                            consistency_score = 0.8 + (same_template_count - 5) / 5.0 * 0.2
                        else:
                            consistency_score = 1.0  # Max at 10+ completions
        except Exception as e:
            # On error, use neutral
            consistency_score = 0.5
        
        # 4. Acceleration Score (10% weight) - Tasks getting faster over time
        acceleration_score = 0.5  # Default neutral
        
        try:
            user_id = self._get_user_id(None)
            df = self._load_instances(user_id=user_id)
            if not df.empty and duration_minutes:
                # Get completed tasks only
                completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                
                if not completed.empty:
                    # Parse completed_at timestamps and durations
                    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                    completed = completed.dropna(subset=['completed_at_dt'])
                    completed['duration_numeric'] = pd.to_numeric(completed.get('duration_minutes', 0), errors='coerce')
                    completed = completed.dropna(subset=['duration_numeric'])
                    
                    # Get recent completions within lookback window
                    cutoff_time = current_completion_time - timedelta(hours=lookback_hours)
                    recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                    recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                    
                    if len(recent) >= 3:  # Need at least 3 tasks to measure acceleration
                        # Sort by completion time
                        recent = recent.sort_values('completed_at_dt')
                        
                        # Split into earlier half and later half
                        mid_point = len(recent) // 2
                        earlier = recent.iloc[:mid_point]
                        later = recent.iloc[mid_point:]
                        
                        earlier_avg_duration = earlier['duration_numeric'].mean()
                        later_avg_duration = later['duration_numeric'].mean()
                        
                        if earlier_avg_duration > 0:
                            # Calculate acceleration: negative = getting faster (good), positive = getting slower (bad)
                            duration_change_ratio = (later_avg_duration - earlier_avg_duration) / earlier_avg_duration
                            
                            # Normalize: -0.5 (50% faster) = 1.0, 0 (no change) = 0.5, +0.5 (50% slower) = 0.0
                            if duration_change_ratio <= -0.5:
                                acceleration_score = 1.0  # Max acceleration
                            elif duration_change_ratio <= 0:
                                # Getting faster: -0.5 → 1.0, 0 → 0.5
                                acceleration_score = 0.5 + (abs(duration_change_ratio) / 0.5) * 0.5
                            elif duration_change_ratio <= 0.5:
                                # Getting slower: 0 → 0.5, 0.5 → 0.0
                                acceleration_score = 0.5 - (duration_change_ratio / 0.5) * 0.5
                            else:
                                acceleration_score = 0.0  # Floor for very slow
        except Exception as e:
            # On error, use neutral
            acceleration_score = 0.5
        
        # Combined Momentum Factor
        momentum_factor = (
            clustering_score * 0.4 +      # Task clustering
            volume_score * 0.3 +           # Task volume
            consistency_score * 0.2 +     # Template consistency
            acceleration_score * 0.1      # Acceleration
        )
        
        # Clamp to valid range
        return max(0.0, min(1.0, momentum_factor))

    def calculate_persistence_factor(
        self,
        row: Union[pd.Series, Dict],
        task_completion_counts: Optional[Dict[str, int]] = None,
        lookback_days: int = 30
    ) -> float:
        """Calculate persistence factor (0.0-1.0) based on continuing despite obstacles.
        
        Persistence measures historical patterns of sticking with difficult tasks.
        Combines four components (user-specified weights):
        1. Obstacle overcoming (40% - highest): Completing despite high cognitive/emotional load
        2. Aversion resistance (30%): Completing despite high aversion
        3. Task repetition (20%): Completing same task multiple times
        4. Consistency (10%): Regular completion patterns over time
        
        Args:
            row: Task instance row (pandas Series from CSV or dict from database)
                 Must contain: predicted_dict/actual_dict (or predicted/actual),
                 completed_at, task_id, cognitive_load, emotional_load, initial_aversion
            task_completion_counts: Optional dict mapping task_id to completion count
            lookback_days: Days to look back for historical patterns (default: 30)
        
        Returns:
            Persistence factor (0.0-1.0), where 1.0 = high persistence, 0.5 = neutral, 0.0 = low persistence
        """
        import math
        import numpy as np
        
        # Handle both pandas Series (CSV) and dict (database) formats
        if isinstance(row, pd.Series):
            predicted_dict = {}
            actual_dict = {}
            if 'predicted_dict' in row and row.get('predicted_dict'):
                try:
                    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
                except (json.JSONDecodeError, TypeError):
                    predicted_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
            completed_at = row.get('completed_at')
            task_id = row.get('task_id')
            cognitive_load = row.get('cognitive_load', 0)
            emotional_load = row.get('emotional_load', 0)
            initial_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion') or 0
        else:
            # Database format (dict)
            predicted = row.get('predicted', {})
            actual = row.get('actual', {})
            predicted_dict = predicted if isinstance(predicted, dict) else {}
            actual_dict = actual if isinstance(actual, dict) else {}
            completed_at = row.get('completed_at')
            task_id = row.get('task_id')
            cognitive_load = row.get('cognitive_load', 0)
            emotional_load = row.get('emotional_load', 0)
            initial_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion') or 0
        
        # Default to neutral if missing critical data
        if not completed_at:
            return 0.5
        
        # Parse completion time
        try:
            if isinstance(completed_at, str):
                current_completion_time = pd.to_datetime(completed_at)
            else:
                current_completion_time = completed_at
        except (ValueError, TypeError):
            return 0.5
        
        # 1. Obstacle Overcoming Score (40% weight - highest)
        obstacle_score = 0.5  # Default neutral
        
        try:
            # Get cognitive and emotional load (obstacles)
            cognitive = pd.to_numeric(cognitive_load, errors='coerce') or 0.0
            emotional = pd.to_numeric(emotional_load, errors='coerce') or 0.0
            
            # Combined load (obstacle level)
            combined_load = (cognitive + emotional) / 2.0
            
            # Completion rate: if task was completed, rate = 1.0
            completion_rate = 1.0  # This task was completed, so rate is 1.0
            
            # Obstacle score: higher load + completion = higher persistence
            # Formula: completion_rate * (load / 100.0)
            # High load (80) + completion = 0.8, Low load (20) + completion = 0.2
            if combined_load > 0:
                obstacle_score = completion_rate * (combined_load / 100.0)
                # Normalize: 0-100 load maps to 0.0-1.0 score, but we want to reward high load
                # So: load 0-50 = 0.0-0.5, load 50-100 = 0.5-1.0
                if combined_load <= 50:
                    obstacle_score = combined_load / 100.0  # 0-50 → 0.0-0.5
                else:
                    obstacle_score = 0.5 + ((combined_load - 50) / 50.0) * 0.5  # 50-100 → 0.5-1.0
            else:
                obstacle_score = 0.5  # No load = neutral
        except Exception as e:
            # On error, use neutral
            obstacle_score = 0.5
        
        # 2. Aversion Resistance Score (30% weight)
        aversion_score = 0.5  # Default neutral
        
        try:
            # Get initial aversion
            aversion = pd.to_numeric(initial_aversion, errors='coerce') or 0.0
            
            # Completion rate: if task was completed, rate = 1.0
            completion_rate = 1.0  # This task was completed
            
            # Aversion score: higher aversion + completion = higher persistence
            # Formula: completion_rate * (aversion / 100.0)
            # High aversion (80) + completion = 0.8, Low aversion (20) + completion = 0.2
            if aversion > 0:
                aversion_score = completion_rate * (aversion / 100.0)
                # Normalize: 0-100 aversion maps to 0.0-1.0 score
                # So: aversion 0-50 = 0.0-0.5, aversion 50-100 = 0.5-1.0
                if aversion <= 50:
                    aversion_score = aversion / 100.0  # 0-50 → 0.0-0.5
                else:
                    aversion_score = 0.5 + ((aversion - 50) / 50.0) * 0.5  # 50-100 → 0.5-1.0
            else:
                aversion_score = 0.5  # No aversion = neutral
        except Exception as e:
            # On error, use neutral
            aversion_score = 0.5
        
        # 3. Task Repetition Score (20% weight)
        repetition_score = 0.5  # Default neutral
        
        try:
            if task_id:
                # Use provided completion counts if available, otherwise calculate
                if task_completion_counts and task_id in task_completion_counts:
                    completion_count = task_completion_counts[task_id]
                else:
                    # Calculate from data
                    user_id = self._get_user_id(None)
                    df = self._load_instances(user_id=user_id)
                    if not df.empty:
                        # Get completed tasks only
                        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                        
                        if not completed.empty:
                            # Parse completed_at timestamps
                            completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                            completed = completed.dropna(subset=['completed_at_dt'])
                            
                            # Get recent completions within lookback window
                            cutoff_time = current_completion_time - timedelta(days=lookback_days)
                            recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                            recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                            
                            # Count completions of this template
                            completion_count = len(recent[recent['task_id'] == task_id])
                    else:
                        completion_count = 1  # This is the first completion
                
                # Repetition score: 1 completion = 0.5, 2-5 = 0.5→0.8, 6-10 = 0.8→1.0, 10+ = 1.0
                if completion_count <= 1:
                    repetition_score = 0.5  # Neutral for first completion
                elif completion_count <= 5:
                    # Linear: 1 → 0.5, 5 → 0.8
                    repetition_score = 0.5 + (completion_count - 1) / 4.0 * 0.3
                elif completion_count <= 10:
                    # Linear: 5 → 0.8, 10 → 1.0
                    repetition_score = 0.8 + (completion_count - 5) / 5.0 * 0.2
                else:
                    repetition_score = 1.0  # Max at 10+ completions
        except Exception as e:
            # On error, use neutral
            repetition_score = 0.5
        
        # 4. Consistency Score (10% weight) - Regular completion patterns over time
        consistency_score = 0.5  # Default neutral
        
        try:
            if task_id:
                user_id = self._get_user_id(None)
                df = self._load_instances(user_id=user_id)
                if not df.empty:
                    # Get completed tasks only
                    completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                    
                    if not completed.empty:
                        # Parse completed_at timestamps
                        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                        completed = completed.dropna(subset=['completed_at_dt'])
                        
                        # Get recent completions of this template within lookback window
                        cutoff_time = current_completion_time - timedelta(days=lookback_days)
                        recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                        recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                        recent = recent[recent['task_id'] == task_id].copy()
                        
                        if len(recent) >= 3:  # Need at least 3 completions to measure consistency
                            # Sort by completion time
                            recent = recent.sort_values('completed_at_dt')
                            
                            # Calculate time differences between completions
                            time_diffs = []
                            for i in range(1, len(recent)):
                                diff_days = (recent.iloc[i]['completed_at_dt'] - 
                                           recent.iloc[i-1]['completed_at_dt']).total_seconds() / (24 * 3600)
                                time_diffs.append(diff_days)
                            
                            if time_diffs:
                                # Calculate variance in time differences (lower variance = more consistent)
                                variance = np.var(time_diffs) if len(time_diffs) > 1 else 0.0
                                
                                # Normalize: lower variance = higher consistency
                                # Assume max reasonable variance is 30 days (completions spread over a month)
                                max_variance = 900.0  # 30 days squared
                                consistency_score = 1.0 - min(1.0, variance / max_variance)
                                # Clamp to reasonable range
                                consistency_score = max(0.0, min(1.0, consistency_score))
        except Exception as e:
            # On error, use neutral
            consistency_score = 0.5
        
        # Combined Persistence Factor
        persistence_factor = (
            obstacle_score * 0.4 +        # Obstacle overcoming (highest weight)
            aversion_score * 0.3 +        # Aversion resistance
            repetition_score * 0.2 +      # Task repetition
            consistency_score * 0.1       # Consistency
        )
        
        # Clamp to valid range
        return max(0.0, min(1.0, persistence_factor))
    
    def calculate_perseverance_factor_v1_3(
        self,
        row: Union[pd.Series, Dict],
        task_completion_counts: Optional[Dict[str, int]] = None,
        persistence_factor: float = 1.0,
        lookback_days: int = 30
    ) -> float:
        """Calculate perseverance factor v1.3 (0.0-1.0) based on continuing despite obstacles.
        
        Perseverance measures historical patterns of sticking with difficult tasks.
        Combines four components with adjusted weights:
        1. Obstacle overcoming (40% - highest): Completing despite high cognitive/emotional load
        2. Aversion resistance (30%): Completing despite high aversion
        3. Task repetition (20%): Completing same task multiple times
        4. Consistency (10%): Regular completion patterns over time, scaled by persistence_factor
        
        Changes from v1.2:
        - Renamed from persistence_factor to perseverance_factor
        - Integrated persistence_factor (completion count multiplier) into consistency component
        - Consistency now requires more completions to max out (scaled by persistence_factor)
        
        Args:
            row: Task instance row (pandas Series from CSV or dict from database)
                 Must contain: predicted_dict/actual_dict (or predicted/actual),
                 completed_at, task_id, cognitive_load, emotional_load, initial_aversion
            task_completion_counts: Optional dict mapping task_id to completion count
            persistence_factor: Completion count multiplier (1.0-5.0 range) to scale consistency
            lookback_days: Days to look back for historical patterns (default: 30)
        
        Returns:
            Perseverance factor (0.0-1.0), where 1.0 = high perseverance, 0.5 = neutral, 0.0 = low perseverance
        """
        import math
        import numpy as np
        from datetime import timedelta
        
        # Handle both pandas Series (CSV) and dict (database) formats
        if isinstance(row, pd.Series):
            predicted_dict = {}
            actual_dict = {}
            if 'predicted_dict' in row and row.get('predicted_dict'):
                try:
                    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
                except (json.JSONDecodeError, TypeError):
                    predicted_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
            completed_at = row.get('completed_at')
            task_id = row.get('task_id')
            cognitive_load = row.get('cognitive_load', 0)
            emotional_load = row.get('emotional_load', 0)
            initial_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion') or 0
        else:
            # Database format (dict)
            predicted = row.get('predicted', {})
            actual = row.get('actual', {})
            predicted_dict = predicted if isinstance(predicted, dict) else {}
            actual_dict = actual if isinstance(actual, dict) else {}
            completed_at = row.get('completed_at')
            task_id = row.get('task_id')
            cognitive_load = row.get('cognitive_load', 0)
            emotional_load = row.get('emotional_load', 0)
            initial_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion') or 0
        
        # Default to neutral if missing critical data
        if not completed_at:
            return 0.5
        
        # Parse completion time
        try:
            if isinstance(completed_at, str):
                current_completion_time = pd.to_datetime(completed_at)
            else:
                current_completion_time = completed_at
        except (ValueError, TypeError):
            return 0.5
        
        # 1. Obstacle Overcoming Score (40% weight - highest)
        obstacle_score = 0.5  # Default neutral
        
        try:
            # Get cognitive and emotional load (obstacles)
            cognitive = pd.to_numeric(cognitive_load, errors='coerce') or 0.0
            emotional = pd.to_numeric(emotional_load, errors='coerce') or 0.0
            
            # Combined load (obstacle level)
            combined_load = (cognitive + emotional) / 2.0
            
            # Completion rate: if task was completed, rate = 1.0
            completion_rate = 1.0  # This task was completed, so rate is 1.0
            
            # Obstacle score: higher load + completion = higher perseverance
            if combined_load > 0:
                # Normalize: 0-100 load maps to 0.0-1.0 score, but we want to reward high load
                # So: load 0-50 = 0.0-0.5, load 50-100 = 0.5-1.0
                if combined_load <= 50:
                    obstacle_score = combined_load / 100.0  # 0-50 → 0.0-0.5
                else:
                    obstacle_score = 0.5 + ((combined_load - 50) / 50.0) * 0.5  # 50-100 → 0.5-1.0
            else:
                obstacle_score = 0.5  # No load = neutral
        except Exception as e:
            # On error, use neutral
            obstacle_score = 0.5
        
        # 2. Aversion Resistance Score (30% weight)
        aversion_score = 0.5  # Default neutral
        
        try:
            # Get initial aversion
            aversion = pd.to_numeric(initial_aversion, errors='coerce') or 0.0
            
            # Completion rate: if task was completed, rate = 1.0
            completion_rate = 1.0  # This task was completed
            
            # Aversion score: higher aversion + completion = higher perseverance
            if aversion > 0:
                # Normalize: 0-100 aversion maps to 0.0-1.0 score
                # So: aversion 0-50 = 0.0-0.5, aversion 50-100 = 0.5-1.0
                if aversion <= 50:
                    aversion_score = aversion / 100.0  # 0-50 → 0.0-0.5
                else:
                    aversion_score = 0.5 + ((aversion - 50) / 50.0) * 0.5  # 50-100 → 0.5-1.0
            else:
                aversion_score = 0.5  # No aversion = neutral
        except Exception as e:
            # On error, use neutral
            aversion_score = 0.5
        
        # 3. Task Repetition Score (20% weight)
        repetition_score = 0.5  # Default neutral
        
        try:
            if task_id:
                # Use provided completion counts if available, otherwise calculate
                if task_completion_counts and task_id in task_completion_counts:
                    completion_count = task_completion_counts[task_id]
                else:
                    # Calculate from data
                    user_id = self._get_user_id(None)
                    df = self._load_instances(user_id=user_id)
                    if not df.empty:
                        # Get completed tasks only
                        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                        
                        if not completed.empty:
                            # Parse completed_at timestamps
                            completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                            completed = completed.dropna(subset=['completed_at_dt'])
                            
                            # Get recent completions within lookback window
                            cutoff_time = current_completion_time - timedelta(days=lookback_days)
                            recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                            recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                            
                            # Count completions of this template
                            completion_count = len(recent[recent['task_id'] == task_id])
                    else:
                        completion_count = 1  # This is the first completion
                
                # Repetition score: 1 completion = 0.5, 2-5 = 0.5→0.8, 6-10 = 0.8→1.0, 10+ = 1.0
                if completion_count <= 1:
                    repetition_score = 0.5  # Neutral for first completion
                elif completion_count <= 5:
                    # Linear: 1 → 0.5, 5 → 0.8
                    repetition_score = 0.5 + (completion_count - 1) / 4.0 * 0.3
                elif completion_count <= 10:
                    # Linear: 5 → 0.8, 10 → 1.0
                    repetition_score = 0.8 + (completion_count - 5) / 5.0 * 0.2
                else:
                    repetition_score = 1.0  # Max at 10+ completions
        except Exception as e:
            # On error, use neutral
            repetition_score = 0.5
        
        # 4. Consistency Score (10% weight) - Regular completion patterns over time
        # NEW in v1.3: Scaled by persistence_factor to make it harder to max out
        consistency_score = 0.5  # Default neutral
        
        try:
            if task_id:
                user_id = self._get_user_id(None)
                df = self._load_instances(user_id=user_id)
                if not df.empty:
                    # Get completed tasks only
                    completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                    
                    if not completed.empty:
                        # Parse completed_at timestamps
                        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                        completed = completed.dropna(subset=['completed_at_dt'])
                        
                        # Get recent completions of this template within lookback window
                        cutoff_time = current_completion_time - timedelta(days=lookback_days)
                        recent = completed[completed['completed_at_dt'] >= cutoff_time].copy()
                        recent = recent[recent['completed_at_dt'] <= current_completion_time].copy()
                        recent = recent[recent['task_id'] == task_id].copy()
                        
                        if len(recent) >= 3:  # Need at least 3 completions to measure consistency
                            # Sort by completion time
                            recent = recent.sort_values('completed_at_dt')
                            
                            # Calculate time differences between completions
                            time_diffs = []
                            for i in range(1, len(recent)):
                                diff_days = (recent.iloc[i]['completed_at_dt'] - 
                                           recent.iloc[i-1]['completed_at_dt']).total_seconds() / (24 * 3600)
                                time_diffs.append(diff_days)
                            
                            if time_diffs:
                                # Calculate variance in time differences (lower variance = more consistent)
                                variance = np.var(time_diffs) if len(time_diffs) > 1 else 0.0
                                
                                # Normalize: lower variance = higher consistency
                                # Assume max reasonable variance is 30 days (completions spread over a month)
                                max_variance = 900.0  # 30 days squared
                                base_consistency = 1.0 - min(1.0, variance / max_variance)
                                
                                # NEW in v1.3: Scale by persistence_factor to make consistency harder to max out
                                # Higher persistence_factor (more completions) = need more consistency to max out
                                # Formula: consistency_score = base_consistency / persistence_factor_scaled
                                # Where persistence_factor_scaled maps 1.0-5.0 → 1.0-1.5 (modest scaling)
                                persistence_factor_scaled = 1.0 + (persistence_factor - 1.0) * 0.125  # 1.0→1.0, 5.0→1.5
                                consistency_score = base_consistency / persistence_factor_scaled
                                
                                # Clamp to reasonable range (0.0-1.0)
                                consistency_score = max(0.0, min(1.0, consistency_score))
        except Exception as e:
            # On error, use neutral
            consistency_score = 0.5
        
        # Combined Perseverance Factor (weights unchanged from v1.2)
        perseverance_factor = (
            obstacle_score * 0.4 +        # Obstacle overcoming (highest weight)
            aversion_score * 0.3 +        # Aversion resistance
            repetition_score * 0.2 +      # Task repetition
            consistency_score * 0.1       # Consistency (now scaled by persistence_factor)
        )
        
        # Clamp to valid range
        return max(0.0, min(1.0, perseverance_factor))

    def calculate_daily_scores(self, target_date: Optional[datetime] = None, user_id: Optional[int] = None) -> Dict[str, float]:
        """Calculate daily aggregated scores for a specific date.
        
        Calculates average scores for all tasks completed on that date:
        - Productivity score (average)
        - Execution score (average)
        - Grit score (average)
        - Composite score (if available)
        
        Args:
            target_date: Date to calculate scores for (default: yesterday)
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Dict with 'productivity_score', 'execution_score', 'grit_score', 'composite_score'
        """
        user_id = self._get_user_id(user_id)
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        # Get date string for filtering
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        df = self._load_instances(user_id=user_id)
        if df.empty or user_id is None:
            return {
                'productivity_score': 0.0,
                'execution_score': 0.0,
                'grit_score': 0.0,
                'composite_score': 0.0
            }
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return {
                'productivity_score': 0.0,
                'execution_score': 0.0,
                'grit_score': 0.0,
                'composite_score': 0.0
            }
        
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # Filter to target date
        completed['completed_date'] = completed['completed_at_dt'].dt.date
        target_date_obj = target_date.date() if isinstance(target_date, datetime) else target_date
        day_completions = completed[completed['completed_date'] == target_date_obj].copy()
        
        if day_completions.empty:
            return {
                'productivity_score': 0.0,
                'execution_score': 0.0,
                'grit_score': 0.0,
                'composite_score': 0.0
            }
        
        # Calculate task completion counts for grit score
        from collections import Counter
        task_completion_counts = Counter(day_completions['task_id'].tolist())
        task_completion_counts_dict = dict(task_completion_counts)
        
        # Calculate scores for each completion
        productivity_scores = []
        execution_scores = []
        grit_scores = []
        
        # Get self-care tasks per day for productivity score
        self_care_per_day = {}
        for date_str, group in day_completions.groupby(day_completions['completed_at_dt'].dt.date):
            date_key = date_str.strftime('%Y-%m-%d')
            # Use proper DataFrame column access with fallback
            if 'task_type' in group.columns:
                task_types = group['task_type'].astype(str).str.lower()
            else:
                task_types = pd.Series(['work'] * len(group), index=group.index)
            self_care_count = len(task_types[task_types.isin(['self care', 'selfcare', 'self-care'])])
            self_care_per_day[date_key] = self_care_count
        
        # Calculate work/play time per day for productivity score
        work_play_time = {}
        for date_str, group in day_completions.groupby(day_completions['completed_at_dt'].dt.date):
            date_key = date_str.strftime('%Y-%m-%d')
            # Use proper DataFrame column access with fallback
            if 'task_type' in group.columns:
                task_types = group['task_type'].astype(str).str.lower()
            else:
                task_types = pd.Series(['work'] * len(group), index=group.index)
            durations = pd.to_numeric(group['duration_minutes'], errors='coerce').fillna(0)
            
            # Apply boolean mask properly - ensure indices align
            work_mask = task_types == 'work'
            play_mask = task_types == 'play'
            work_time = durations[work_mask].sum()
            play_time = durations[play_mask].sum()
            work_play_time[date_key] = {'work_time': work_time, 'play_time': play_time}
        
        # Calculate weekly average time for productivity score
        weekly_avg_time = 0.0
        try:
            work_volume_metrics = self.get_daily_work_volume_metrics(days=7)
            weekly_avg_time = work_volume_metrics.get('avg_daily_work_time', 0.0) * 7.0
        except Exception:
            pass
        
        for _, row in day_completions.iterrows():
            try:
                # Productivity score
                prod_score = self.calculate_productivity_score(
                    row=row,
                    self_care_tasks_per_day=self_care_per_day,
                    weekly_avg_time=weekly_avg_time,
                    work_play_time_per_day=work_play_time
                )
                productivity_scores.append(prod_score)
                
                # Execution score
                exec_score = self.calculate_execution_score(
                    row=row,
                    task_completion_counts=task_completion_counts_dict
                )
                execution_scores.append(exec_score)
                
                # Grit score
                grit_score = self.calculate_grit_score(
                    row=row,
                    task_completion_counts=task_completion_counts_dict
                )
                grit_scores.append(grit_score)
            except Exception:
                # Skip if calculation fails
                continue
        
        # Calculate averages
        avg_productivity = sum(productivity_scores) / len(productivity_scores) if productivity_scores else 0.0
        avg_execution = sum(execution_scores) / len(execution_scores) if execution_scores else 0.0
        avg_grit = sum(grit_scores) / len(grit_scores) if grit_scores else 0.0
        
        # Calculate composite score (simplified - average of the three)
        composite_score = (avg_productivity + avg_execution + avg_grit) / 3.0 if (productivity_scores or execution_scores or grit_scores) else 0.0
        
        return {
            'productivity_score': round(avg_productivity, 2),
            'execution_score': round(avg_execution, 2),
            'grit_score': round(avg_grit, 2),
            'composite_score': round(composite_score, 2)
        }
    
    def calculate_daily_productivity_score_with_idle_refresh(
        self,
        target_date: Optional[datetime] = None,
        idle_refresh_hours: float = 8.0,  # Deprecated: kept for backward compatibility, not used
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Calculate daily productivity score with midnight refresh.
        
        This metric calculates a daily productivity score that resets at midnight each day.
        
        For the current day: Accumulates scores from midnight of the current day up to now.
        
        For historical dates: Calculates the full day's score from midnight to end of day.
        
        Args:
            target_date: Date to calculate for (default: today/now for rolling calculation)
            idle_refresh_hours: Deprecated parameter, kept for backward compatibility
            
        Returns:
            Dict with:
            - daily_score (float): Total productivity score for the day
            - segments (List[Dict]): List containing single segment from midnight
            - segment_count (int): Always 1 (single day segment)
            - total_tasks (int): Total tasks completed in the day
        """
        # #region agent log
        import json
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'analytics.py:4302',
                    'message': 'calculate_daily_productivity_score_with_idle_refresh entry',
                    'data': {
                        'target_date': str(target_date) if target_date else None,
                        'idle_refresh_hours': idle_refresh_hours
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        now = datetime.now()
        is_current_day = target_date is None
        
        if target_date is None:
            target_date = now
            target_date_obj = now.date()
        else:
            target_date_obj = target_date.date() if isinstance(target_date, datetime) else target_date
        
        # Get all completed instances
        df = self._load_instances(user_id=user_id)
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'analytics.py:4312',
                    'message': 'After _load_instances',
                    'data': {
                        'df_total_rows': len(df),
                        'df_columns': list(df.columns) if not df.empty else []
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        # Safety check: ensure completed_at column exists
        if df.empty or 'completed_at' not in df.columns:
            return {
                'daily_score': 0.0,
                'segments': [],
                'segment_count': 0,
                'total_tasks': 0
            }
        
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'analytics.py:4313',
                    'message': 'After filtering for completed_at',
                    'data': {
                        'completed_count': len(completed),
                        'sample_completed_at': str(completed['completed_at'].iloc[0]) if not completed.empty else None
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        if completed.empty:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'analytics.py:4315',
                        'message': 'Early return: no completed tasks',
                        'data': {},
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            return {
                'daily_score': 0.0,
                'segments': [],
                'segment_count': 0,
                'total_tasks': 0
            }
        
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'analytics.py:4325',
                    'message': 'After parsing timestamps',
                    'data': {
                        'completed_count': len(completed),
                        'earliest_completion': str(completed['completed_at_dt'].min()) if not completed.empty else None,
                        'latest_completion': str(completed['completed_at_dt'].max()) if not completed.empty else None
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        if completed.empty:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'B',
                        'location': 'analytics.py:4327',
                        'message': 'Early return: no valid timestamps',
                        'data': {},
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            return {
                'daily_score': 0.0,
                'segments': [],
                'segment_count': 0,
                'total_tasks': 0
            }
        
        # For current day: use midnight of current day as segment start
        # For historical dates: use all tasks from that date
        if is_current_day:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'C',
                        'location': 'analytics.py:4337',
                        'message': 'Current day calculation path',
                        'data': {
                            'now': str(now),
                            'target_date_obj': str(target_date_obj)
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            # Use midnight of current day as segment start
            segment_start_time = datetime.combine(target_date_obj, datetime.min.time())
            
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'H2',
                        'location': 'analytics.py:5720',
                        'message': 'Segment start time set to midnight',
                        'data': {
                            'segment_start_time': str(segment_start_time),
                            'now': str(now),
                            'total_completions': len(completed)
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            # Filter to tasks since midnight (up to now)
            before_filter_count = len(completed)
            day_completions = completed[
                (completed['completed_at_dt'] >= segment_start_time) &
                (completed['completed_at_dt'] <= now)
            ].copy()
            
            # #region agent log
            try:
                filtered_times = [str(dt) for dt in day_completions['completed_at_dt'].head(10).tolist()] if not day_completions.empty else []
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'H3',
                        'location': 'analytics.py:5725',
                        'message': 'Filtered tasks after segment start',
                        'data': {
                            'segment_start_time': str(segment_start_time),
                            'now': str(now),
                            'before_filter_count': before_filter_count,
                            'after_filter_count': len(day_completions),
                            'first_10_filtered_times': filtered_times
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
        else:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'B',
                        'location': 'analytics.py:4387',
                        'message': 'Historical date calculation path',
                        'data': {
                            'target_date_obj': str(target_date_obj)
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            # Historical date: use all tasks from that date
            completed['completed_date'] = completed['completed_at_dt'].dt.date
            day_completions = completed[completed['completed_date'] == target_date_obj].copy()
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'analytics.py:4392',
                    'message': 'After date filtering',
                    'data': {
                        'day_completions_count': len(day_completions),
                        'is_current_day': is_current_day
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        if day_completions.empty:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'B',
                        'location': 'analytics.py:4393',
                        'message': 'Early return: day_completions empty after filtering',
                        'data': {},
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            return {
                'daily_score': 0.0,
                'segments': [],
                'segment_count': 0,
                'total_tasks': 0
            }
        
        # Sort by completion time
        day_completions = day_completions.sort_values('completed_at_dt')
        
        # Get task types for productivity score calculation
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Merge task_type if needed
        if 'task_type' not in day_completions.columns and not tasks_df.empty and 'task_type' in tasks_df.columns:
            day_completions = day_completions.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            day_completions['task_type'] = day_completions['task_type'].fillna('Work')
        
        # Prepare data for productivity score calculation
        self_care_tasks_per_day = {}
        if 'task_type' in day_completions.columns:
            day_completions['task_type_normalized'] = day_completions['task_type'].astype(str).str.strip().str.lower()
            self_care_tasks = day_completions[
                day_completions['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
            ]
            if not self_care_tasks.empty:
                date_key = target_date_obj.isoformat()
                self_care_count = len(self_care_tasks)
                self_care_tasks_per_day[date_key] = self_care_count
        
        # Calculate work/play time for the day
        work_play_time_per_day = {}
        if 'task_type' in day_completions.columns:
            def _get_actual_time(row):
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, dict):
                        return float(actual_dict.get('time_actual_minutes', 0) or 0)
                except (KeyError, TypeError, ValueError):
                    pass
                return 0.0
            
            day_completions['time_actual'] = day_completions.apply(_get_actual_time, axis=1)
            date_key = target_date_obj.isoformat()
            work_time = day_completions[
                day_completions['task_type_normalized'] == 'work'
            ]['time_actual'].sum()
            play_time = day_completions[
                day_completions['task_type_normalized'] == 'play'
            ]['time_actual'].sum()
            work_play_time_per_day[date_key] = {
                'work_time': float(work_time),
                'play_time': float(play_time)
            }
        
        # Calculate productivity scores for each task
        weekly_avg_time = 0.0
        try:
            work_volume_metrics = self.get_daily_work_volume_metrics(days=7)
            weekly_avg_time = work_volume_metrics.get('avg_daily_work_time', 0.0) * 7.0
        except Exception:
            pass
        
        # Calculate productivity score for each completion
        day_completions['productivity_score'] = day_completions.apply(
            lambda row: self.calculate_productivity_score(
                row=row,
                self_care_tasks_per_day=self_care_tasks_per_day,
                weekly_avg_time=weekly_avg_time,
                work_play_time_per_day=work_play_time_per_day
            ),
            axis=1
        )
        
        # #region agent log
        try:
            task_scores = []
            for idx, row in day_completions.iterrows():
                task_scores.append({
                    'completed_at': str(row.get('completed_at_dt', '')),
                    'task_id': str(row.get('task_id', '')),
                    'task_name': str(row.get('task_name', ''))[:50],
                    'productivity_score': float(row.get('productivity_score', 0.0) or 0.0),
                    'time_actual': float(row.get('time_actual', 0.0) or 0.0) if 'time_actual' in row else None
                })
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'H4',
                    'location': 'analytics.py:5973',
                    'message': 'Productivity scores calculated for filtered tasks',
                    'data': {
                        'task_count': len(day_completions),
                        'total_score': float(day_completions['productivity_score'].sum()),
                        'task_scores': task_scores
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except Exception as e:
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'H4',
                        'location': 'analytics.py:5973',
                        'message': 'Error logging task scores',
                        'data': {'error': str(e)},
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
        # #endregion
        
        # Calculate total score for the day (single segment from midnight)
        total_score = float(day_completions['productivity_score'].sum())
        
        # Create single segment representing the full day
        if not day_completions.empty:
            segment_start = datetime.combine(target_date_obj, datetime.min.time())
            if is_current_day:
                segment_end = now
            else:
                segment_end = day_completions['completed_at_dt'].max()
            
            segments = [{
                'start_time': segment_start,
                'end_time': segment_end,
                'score': total_score,
                'task_count': len(day_completions)
            }]
        else:
            segments = []
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'D',
                    'location': 'analytics.py:4448',
                    'message': 'Final calculation result',
                    'data': {
                        'total_score': total_score,
                        'segment_count': len(segments),
                        'total_tasks': len(day_completions),
                        'segments': [{'score': s['score'], 'task_count': s['task_count']} for s in segments]
                    },
                    'timestamp': int(datetime.now().timestamp() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        return {
            'daily_score': round(float(total_score), 2),
            'segments': segments,
            'segment_count': len(segments),
            'total_tasks': len(day_completions)
        }
    
    def get_historical_daily_scores(self, score_type: str = 'productivity_score', top_n: int = 10, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get historical daily scores sorted by value.
        
        Args:
            score_type: 'productivity_score', 'execution_score', 'grit_score', or 'composite_score'
            top_n: Number of top scores to return (default: 10)
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            List of dicts with 'date', 'score', sorted by score descending
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        if df.empty or user_id is None:
            return []
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return []
        
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # Group by date and calculate daily scores
        daily_scores = []
        for date_obj, group in completed.groupby(completed['completed_at_dt'].dt.date):
            try:
                daily_score_data = self.calculate_daily_scores(target_date=datetime.combine(date_obj, datetime.min.time()))
                score_value = daily_score_data.get(score_type, 0.0)
                
                if score_value > 0:  # Only include days with valid scores
                    daily_scores.append({
                        'date': date_obj,
                        'score': score_value
                    })
            except Exception:
                continue
        
        # Sort by score descending
        daily_scores.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top N
        return daily_scores[:top_n]
    
    def check_score_milestones(self, target_date: Optional[datetime] = None, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Check if yesterday's scores achieved any milestones.
        
        Compares yesterday's scores to historical bests and returns the best milestone
        (closest to all-time best).
        
        Args:
            target_date: Date to check (default: yesterday)
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Dict with 'score_type', 'yesterday_score', 'all_time_best', 'rank', 'is_all_time_best'
            or None if no milestones
        """
        user_id = self._get_user_id(user_id)
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        # Calculate yesterday's scores
        yesterday_scores = self.calculate_daily_scores(target_date=target_date)
        
        # Check each score type for milestones
        milestones = []
        score_types = ['productivity_score', 'execution_score', 'grit_score', 'composite_score']
        
        for score_type in score_types:
            yesterday_score = yesterday_scores.get(score_type, 0.0)
            if yesterday_score <= 0:
                continue  # Skip if no valid score
            
            # Get historical top 10
            historical = self.get_historical_daily_scores(score_type=score_type, top_n=10)
            
            if not historical:
                # First day with data - it's automatically the best
                milestones.append({
                    'score_type': score_type,
                    'yesterday_score': yesterday_score,
                    'all_time_best': yesterday_score,
                    'rank': 1,
                    'is_all_time_best': True,
                    'distance_to_best': 0.0
                })
                continue
            
            # Find all-time best
            all_time_best = historical[0]['score'] if historical else yesterday_score
            
            # Check if yesterday is all-time best
            is_all_time_best = yesterday_score >= all_time_best
            
            # Find rank in top 10
            rank = None
            for i, entry in enumerate(historical):
                if yesterday_score >= entry['score']:
                    rank = i + 1
                    break
            
            # If not in top 10, check if it's close (within 5% of all-time best)
            if rank is None:
                if yesterday_score >= all_time_best * 0.95:  # Within 5% of best
                    rank = 11  # Just outside top 10 but close
                else:
                    continue  # Not a milestone
            
            # Calculate distance to all-time best (0.0 = tied, 1.0 = 100% away)
            if all_time_best > 0:
                distance_to_best = abs(yesterday_score - all_time_best) / all_time_best
            else:
                distance_to_best = 1.0
            
            milestones.append({
                'score_type': score_type,
                'yesterday_score': yesterday_score,
                'all_time_best': all_time_best,
                'rank': rank,
                'is_all_time_best': is_all_time_best,
                'distance_to_best': distance_to_best
            })
        
        if not milestones:
            return None
        
        # Prioritize: closest to all-time best (lowest distance_to_best)
        # If tied, prefer all-time best, then prefer higher rank
        milestones.sort(key=lambda x: (
            x['distance_to_best'],  # Closest to best first
            not x['is_all_time_best'],  # All-time bests first
            x['rank']  # Lower rank (better) first
        ))
        
        return milestones[0]  # Return best milestone
    
    def calculate_weekly_progress_summary(self, days: int = 7, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Calculate weekly progress summary for the last N days.
        
        Args:
            days: Number of days to include in summary (default: 7)
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Dict with:
            - tasks_completed: Total tasks completed
            - avg_productivity_score: Average productivity score
            - avg_execution_score: Average execution score
            - avg_grit_score: Average grit score
            - avg_composite_score: Average composite score
            - best_day_productivity: Best daily productivity score
            - best_day_execution: Best daily execution score
            - best_day_grit: Best daily grit score
            - productivity_trend: 'up', 'down', or 'stable'
            - execution_trend: 'up', 'down', or 'stable'
            - days_active: Number of days with at least one completion
            - total_work_time: Total work time in minutes
            - total_self_care_time: Total self-care time in minutes
        """
        user_id = self._get_user_id(user_id)
        from datetime import datetime, timedelta
        
        df = self._load_instances(user_id=user_id)
        if df.empty or user_id is None:
            return self._empty_weekly_summary()
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return self._empty_weekly_summary()
        
        # Parse completed_at timestamps
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        
        # Get date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Filter to date range
        week_completions = completed[
            (completed['completed_at_dt'] >= start_date) & 
            (completed['completed_at_dt'] <= end_date)
        ].copy()
        
        if week_completions.empty:
            return self._empty_weekly_summary()
        
        # Calculate daily scores for each day in the week
        daily_scores_list = []
        for i in range(days):
            target_date = start_date + timedelta(days=i)
            daily_scores = self.calculate_daily_scores(target_date=target_date, user_id=user_id)
            if daily_scores.get('productivity_score', 0) > 0 or \
               daily_scores.get('execution_score', 0) > 0 or \
               daily_scores.get('grit_score', 0) > 0:
                daily_scores['date'] = target_date.date()
                daily_scores_list.append(daily_scores)
        
        if not daily_scores_list:
            return self._empty_weekly_summary()
        
        # Calculate averages
        productivity_scores = [d.get('productivity_score', 0) for d in daily_scores_list if d.get('productivity_score', 0) > 0]
        execution_scores = [d.get('execution_score', 0) for d in daily_scores_list if d.get('execution_score', 0) > 0]
        grit_scores = [d.get('grit_score', 0) for d in daily_scores_list if d.get('grit_score', 0) > 0]
        composite_scores = [d.get('composite_score', 0) for d in daily_scores_list if d.get('composite_score', 0) > 0]
        
        avg_productivity = sum(productivity_scores) / len(productivity_scores) if productivity_scores else 0.0
        avg_execution = sum(execution_scores) / len(execution_scores) if execution_scores else 0.0
        avg_grit = sum(grit_scores) / len(grit_scores) if grit_scores else 0.0
        avg_composite = sum(composite_scores) / len(composite_scores) if composite_scores else 0.0
        
        # Find best days
        best_day_productivity = max([d.get('productivity_score', 0) for d in daily_scores_list], default=0.0)
        best_day_execution = max([d.get('execution_score', 0) for d in daily_scores_list], default=0.0)
        best_day_grit = max([d.get('grit_score', 0) for d in daily_scores_list], default=0.0)
        
        # Calculate trends (compare first half vs second half of week)
        if len(daily_scores_list) >= 4:
            mid_point = len(daily_scores_list) // 2
            first_half_prod = [d.get('productivity_score', 0) for d in daily_scores_list[:mid_point] if d.get('productivity_score', 0) > 0]
            second_half_prod = [d.get('productivity_score', 0) for d in daily_scores_list[mid_point:] if d.get('productivity_score', 0) > 0]
            
            first_half_exec = [d.get('execution_score', 0) for d in daily_scores_list[:mid_point] if d.get('execution_score', 0) > 0]
            second_half_exec = [d.get('execution_score', 0) for d in daily_scores_list[mid_point:] if d.get('execution_score', 0) > 0]
            
            if first_half_prod and second_half_prod:
                avg_first_prod = sum(first_half_prod) / len(first_half_prod)
                avg_second_prod = sum(second_half_prod) / len(second_half_prod)
                productivity_trend = 'up' if avg_second_prod > avg_first_prod * 1.05 else ('down' if avg_second_prod < avg_first_prod * 0.95 else 'stable')
            else:
                productivity_trend = 'stable'
            
            if first_half_exec and second_half_exec:
                avg_first_exec = sum(first_half_exec) / len(first_half_exec)
                avg_second_exec = sum(second_half_exec) / len(second_half_exec)
                execution_trend = 'up' if avg_second_exec > avg_first_exec * 1.05 else ('down' if avg_second_exec < avg_first_exec * 0.95 else 'stable')
            else:
                execution_trend = 'stable'
        else:
            productivity_trend = 'stable'
            execution_trend = 'stable'
        
        # Count days active
        days_active = len(daily_scores_list)
        
        # Calculate total work and self-care time
        week_completions['task_type_normalized'] = week_completions.get('task_type', 'Work').astype(str).str.strip().str.lower()
        week_completions['duration_numeric'] = pd.to_numeric(week_completions.get('duration_minutes', 0), errors='coerce').fillna(0.0)
        
        work_time = week_completions[week_completions['task_type_normalized'] == 'work']['duration_numeric'].sum()
        self_care_time = week_completions[week_completions['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])]['duration_numeric'].sum()
        
        return {
            'tasks_completed': len(week_completions),
            'avg_productivity_score': round(avg_productivity, 1),
            'avg_execution_score': round(avg_execution, 1),
            'avg_grit_score': round(avg_grit, 1),
            'avg_composite_score': round(avg_composite, 1),
            'best_day_productivity': round(best_day_productivity, 1),
            'best_day_execution': round(best_day_execution, 1),
            'best_day_grit': round(best_day_grit, 1),
            'productivity_trend': productivity_trend,
            'execution_trend': execution_trend,
            'days_active': days_active,
            'total_work_time': round(work_time, 1),
            'total_self_care_time': round(self_care_time, 1)
        }
    
    def _empty_weekly_summary(self) -> Dict[str, Any]:
        """Return empty weekly summary structure."""
        return {
            'tasks_completed': 0,
            'avg_productivity_score': 0.0,
            'avg_execution_score': 0.0,
            'avg_grit_score': 0.0,
            'avg_composite_score': 0.0,
            'best_day_productivity': 0.0,
            'best_day_execution': 0.0,
            'best_day_grit': 0.0,
            'productivity_trend': 'stable',
            'execution_trend': 'stable',
            'days_active': 0,
            'total_work_time': 0.0,
            'total_self_care_time': 0.0
        }

    def calculate_execution_score(
        self,
        row: Union[pd.Series, Dict],
        task_completion_counts: Optional[Dict[str, int]] = None
    ) -> float:
        """Calculate execution score (0-100) for efficient execution of difficult tasks.
        
        **Formula Version: 1.0 (matches glossary definition)**
        
        Combines four component factors (as defined in glossary):
        1. Difficulty factor: High aversion + high load
        2. Speed factor: Fast execution relative to estimate
        3. Start speed factor: Fast start after initialization (procrastination resistance)
        4. Completion factor: Full completion (100% or close)
        
        Formula (matches glossary): execution_score = 50 * (1.0 + difficulty_factor) * 
                                                      (0.5 + speed_factor * 0.5) * 
                                                      (0.5 + start_speed_factor * 0.5) * 
                                                      completion_factor
        
        Note: Thoroughness factor and momentum factor were removed due to performance issues
        (were being recalculated for each instance, causing significant slowdown).
        The calculate_thoroughness_factor and calculate_momentum_factor methods remain in
        the codebase for potential future use.
        
        Note: Focus factor (emotion-based) is NOT included here - it belongs in grit score.
        
        See: docs/execution_module_v1.0.md for complete formula documentation.
        See: ui/analytics_glossary.py for the glossary definition.
        
        Args:
            row: Task instance row (pandas Series from CSV or dict from database)
                 Must contain: predicted_dict/actual_dict (or predicted/actual),
                 initialized_at, started_at, completed_at
            task_completion_counts: Optional dict for task completion counts (for difficulty)
        
        Returns:
            Execution score (0-100), higher = better execution
        """
        import math
        
        # Handle both pandas Series (CSV) and dict (database) formats
        if isinstance(row, pd.Series):
            predicted_dict = {}
            actual_dict = {}
            if 'predicted_dict' in row and row.get('predicted_dict'):
                try:
                    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
                except (json.JSONDecodeError, TypeError):
                    predicted_dict = {}
            if 'actual_dict' in row and row.get('actual_dict'):
                try:
                    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
                except (json.JSONDecodeError, TypeError):
                    actual_dict = {}
            initialized_at = row.get('initialized_at')
            started_at = row.get('started_at')
            completed_at = row.get('completed_at')
        else:
            # Database format (dict)
            predicted = row.get('predicted', {})
            actual = row.get('actual', {})
            predicted_dict = predicted if isinstance(predicted, dict) else {}
            actual_dict = actual if isinstance(actual, dict) else {}
            initialized_at = row.get('initialized_at')
            started_at = row.get('started_at')
            completed_at = row.get('completed_at')
        
        # 1. Difficulty Factor (reuse existing calculate_difficulty_bonus)
        current_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion')
        stress_level = actual_dict.get('stress_level')
        mental_energy = predicted_dict.get('mental_energy_needed') or predicted_dict.get('cognitive_load')
        task_difficulty = predicted_dict.get('task_difficulty')
        
        difficulty_factor = self.calculate_difficulty_bonus(
            current_aversion=current_aversion,
            stress_level=stress_level,
            mental_energy=mental_energy,
            task_difficulty=task_difficulty
        )
        # Already returns 0.0-1.0, use directly
        
        # 2. Speed Factor (execution efficiency)
        time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
        time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or 
                             predicted_dict.get('estimate', 0) or 0)
        
        if time_estimate > 0 and time_actual > 0:
            time_ratio = time_actual / time_estimate
            
            if time_ratio <= 0.5:
                # Very fast: 2x speed or faster → max bonus
                speed_factor = 1.0
            elif time_ratio <= 1.0:
                # Fast: completed within estimate → linear bonus
                # 0.5 → 1.0, 1.0 → 0.5
                speed_factor = 1.0 - (time_ratio - 0.5) * 1.0
            else:
                # Slow: exceeded estimate → diminishing penalty
                # 1.0 → 0.5, 2.0 → 0.25, 3.0 → 0.125
                speed_factor = 0.5 * (1.0 / time_ratio)
        else:
            speed_factor = 0.5  # Neutral if no time data
        
        # 3. Start Speed Factor (procrastination resistance)
        start_speed_factor = 0.5  # Default neutral
        
        if initialized_at and completed_at:
            try:
                # Parse datetime if needed
                if isinstance(initialized_at, str):
                    init_time = pd.to_datetime(initialized_at)
                else:
                    init_time = initialized_at
                
                if isinstance(completed_at, str):
                    complete_time = pd.to_datetime(completed_at)
                else:
                    complete_time = completed_at
                
                if started_at:
                    if isinstance(started_at, str):
                        start_time = pd.to_datetime(started_at)
                    else:
                        start_time = started_at
                    start_delay_minutes = (start_time - init_time).total_seconds() / 60.0
                else:
                    # No start time: use completion time as proxy
                    start_delay_minutes = (complete_time - init_time).total_seconds() / 60.0
                
                # Normalize: fast start = high score
                if start_delay_minutes <= 5:
                    start_speed_factor = 1.0
                elif start_delay_minutes <= 30:
                    # Linear: 5 min → 1.0, 30 min → 0.8
                    start_speed_factor = 1.0 - ((start_delay_minutes - 5) / 25.0) * 0.2
                elif start_delay_minutes <= 120:
                    # Linear: 30 min → 0.8, 120 min → 0.5
                    start_speed_factor = 0.8 - ((start_delay_minutes - 30) / 90.0) * 0.3
                else:
                    # Exponential decay: 120 min → 0.5, 480 min → ~0.125
                    excess = start_delay_minutes - 120
                    start_speed_factor = 0.5 * math.exp(-excess / 240.0)
            except (ValueError, TypeError, AttributeError) as e:
                # Neutral on error
                start_speed_factor = 0.5
        
        # 4. Completion Factor (quality of completion)
        completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
        
        if completion_pct >= 100.0:
            completion_factor = 1.0
        elif completion_pct >= 90.0:
            # Near-complete: slight penalty
            completion_factor = 0.9 + (completion_pct - 90.0) / 10.0 * 0.1
        elif completion_pct >= 50.0:
            # Partial: moderate penalty
            completion_factor = 0.5 + (completion_pct - 50.0) / 40.0 * 0.4
        else:
            # Low completion: significant penalty
            completion_factor = completion_pct / 50.0 * 0.5
        
        # Combined Formula (matches glossary definition exactly)
        # Base score: 50 points (neutral)
        base_score = 50.0
        
        # Apply factors multiplicatively (all must be high for high score)
        # Formula matches glossary: execution_score = 50 * (1.0 + difficulty_factor) * 
        #                            (0.5 + speed_factor * 0.5) * (0.5 + start_speed_factor * 0.5) * completion_factor
        execution_score = base_score * (
            (1.0 + difficulty_factor) *      # 1.0-2.0 range (difficulty boost)
            (0.5 + speed_factor * 0.5) *     # 0.5-1.0 range (speed boost)
            (0.5 + start_speed_factor * 0.5) *  # 0.5-1.0 range (start speed boost)
            completion_factor                 # 0.0-1.0 range (completion quality)
        )
        
        # Note: Momentum factor removed for performance (was calling _load_instances() multiple times per instance).
        # The calculate_momentum_factor method remains available in the codebase.
        
        # Normalize to 0-100 range
        execution_score = max(0.0, min(100.0, execution_score))
        
        return execution_score

    def get_productivity_time_minutes(self, user_id: Optional[int] = None) -> float:
        """Get productivity time for last 7 days (Work + Self care only).
        
        Lightweight function that only calculates productivity time without
        all the relief calculations. Much faster than get_relief_summary().
        
        Args:
            user_id: Optional user_id. If None, gets from authenticated session.
        
        Returns:
            Productivity time in minutes (float)
        """
        user_id = self._get_user_id(user_id)
        from datetime import timedelta
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return 0.0
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        user_id = self._get_user_id(user_id)
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Join to get task_type
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            completed = completed.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            completed['task_type'] = completed['task_type'].fillna('Work')
            completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
            # Filter to only Work and Self care tasks (exclude Play)
            completed = completed[
                completed['task_type_normalized'].isin(['work', 'self care', 'selfcare', 'self-care'])
            ]
        
        # Get actual time from completed tasks (last 7 days only)
        seven_days_ago = datetime.now() - timedelta(days=7)
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed_last_7d = completed[completed['completed_at_dt'] >= seven_days_ago]
        
        def _get_actual_time(row):
            try:
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed_last_7d = completed_last_7d.copy()
        completed_last_7d['time_actual'] = completed_last_7d.apply(_get_actual_time, axis=1)
        completed_last_7d['time_actual'] = pd.to_numeric(completed_last_7d['time_actual'], errors='coerce')
        
        # Sum productivity time for last 7 days
        productivity_time = completed_last_7d['time_actual'].fillna(0).sum()
        return float(productivity_time)

    def get_relief_summary(self, user_id: Optional[int] = None) -> Dict[str, any]:
        """Calculate relief points, productivity time, and relief statistics.
        
        Results are cached for 30 seconds to improve performance on repeated calls.
        
        Args:
            user_id: Optional user_id. If None, gets from authenticated session.
        """
        user_id = self._get_user_id(user_id)
        import time as time_module
        import traceback
        import json
        total_start = time_module.perf_counter()
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                call_stack = ''.join(traceback.format_stack()[-3:-1])
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'analytics.py:4126',
                    'message': 'get_relief_summary called',
                    'data': {'caller': call_stack.split('\\n')[-2].strip() if call_stack else 'unknown'},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        # Check cache first
        # Cache is now user-specific, keyed by user_id
        cache_key = user_id if user_id is not None else "default"
        current_time = time_module.time()
        if (cache_key in Analytics._relief_summary_cache and 
            cache_key in Analytics._relief_summary_cache_time and
            (current_time - Analytics._relief_summary_cache_time[cache_key]) < Analytics._cache_ttl_seconds):
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'analytics.py:4139',
                        'message': 'get_relief_summary cache hit',
                        'data': {},
                        'timestamp': int(time_module.time() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            duration = (time_module.perf_counter() - total_start) * 1000
            print(f"[Analytics] get_relief_summary (cached): {duration:.2f}ms")
            return Analytics._relief_summary_cache[cache_key]
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'analytics.py:4141',
                    'message': 'get_relief_summary cache miss - calculating',
                    'data': {},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        # Calculate fresh result with timing
        # OPTIMIZATION: Only load completed instances (relief_summary only needs completed tasks)
        load_start = time_module.time()
        df = self._load_instances(completed_only=True, user_id=user_id)
        load_time = (time_module.time() - load_start) * 1000
        print(f"[Analytics] get_relief_summary: _load_instances (completed_only=True): {load_time:.2f}ms")
        
        if df.empty:
            return {
                'productivity_time_minutes': 0.0,
                'default_relief_points': 0.0,
                'net_relief_points': 0.0,
                'positive_relief_count': 0,
                'positive_relief_total': 0.0,
                'positive_relief_avg': 0.0,
                'negative_relief_count': 0,
                'negative_relief_total': 0.0,
                'negative_relief_avg': 0.0,
                'total_relief_duration_score': 0.0,
                'avg_relief_duration_score': 0.0,
                'total_relief_score': 0.0,
                'total_relief_score_no_mult': 0.0,
                'avg_relief_score_no_mult': 0.0,
                'weekly_relief_score': 0.0,
                'weekly_relief_score_with_bonus_robust': 0.0,
                'weekly_relief_score_with_bonus_sensitive': 0.0,
                'total_productivity_points': 0.0,
                'net_productivity_points': 0.0,
                'weekly_productivity_points': 0.0,
                'weekly_productivity_points_with_bonus_robust': 0.0,
                'weekly_productivity_points_with_bonus_sensitive': 0.0,
                'total_productivity_score': 0.0,
                'weekly_productivity_score': 0.0,
                'total_grit_score': 0.0,
                'weekly_grit_score': 0.0,
                'total_obstacles_score_robust': 0.0,
                'total_obstacles_score_sensitive': 0.0,
                'weekly_obstacles_bonus_multiplier_robust': 1.0,
                'weekly_obstacles_bonus_multiplier_sensitive': 1.0,
                'max_obstacle_spike_robust': 0.0,
                'max_obstacle_spike_sensitive': 0.0,
            }
        
        # Get completed tasks only
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'productivity_time_minutes': 0.0,
                'default_relief_points': 0.0,
                'net_relief_points': 0.0,
                'positive_relief_count': 0,
                'positive_relief_total': 0.0,
                'positive_relief_avg': 0.0,
                'negative_relief_count': 0,
                'negative_relief_total': 0.0,
                'negative_relief_avg': 0.0,
                'total_relief_duration_score': 0.0,
                'avg_relief_duration_score': 0.0,
                'total_relief_score': 0.0,
                'total_relief_score_no_mult': 0.0,
                'avg_relief_score_no_mult': 0.0,
                'weekly_relief_score': 0.0,
                'weekly_relief_score_with_bonus_robust': 0.0,
                'weekly_relief_score_with_bonus_sensitive': 0.0,
                'total_productivity_points': 0.0,
                'net_productivity_points': 0.0,
                'weekly_productivity_points': 0.0,
                'weekly_productivity_points_with_bonus_robust': 0.0,
                'weekly_productivity_points_with_bonus_sensitive': 0.0,
                'total_productivity_score': 0.0,
                'weekly_productivity_score': 0.0,
                'total_grit_score': 0.0,
                'weekly_grit_score': 0.0,
                'total_obstacles_score_robust': 0.0,
                'total_obstacles_score_sensitive': 0.0,
                'weekly_obstacles_bonus_multiplier_robust': 1.0,
                'weekly_obstacles_bonus_multiplier_sensitive': 1.0,
                'max_obstacle_spike_robust': 0.0,
                'max_obstacle_spike_sensitive': 0.0,
            }
        
        # Extract expected relief from predicted_dict (OPTIMIZED: vectorized extraction)
        extract_start = time_module.time()
        # Use vectorized operations where possible - faster than .apply()
        if 'predicted_dict' in completed.columns:
            # Convert dict series to list for faster processing
            predicted_list = completed['predicted_dict'].tolist()
            # Use list comprehension (faster than .apply() for dict access)
            completed['expected_relief'] = [
                d.get('expected_relief') if isinstance(d, dict) else None 
                for d in predicted_list
            ]
            completed['initial_aversion'] = [
                d.get('initial_aversion') if isinstance(d, dict) else None 
                for d in predicted_list
            ]
            completed['expected_aversion'] = [
                d.get('expected_aversion') if isinstance(d, dict) else None 
                for d in predicted_list
            ]
        else:
            completed['expected_relief'] = None
            completed['initial_aversion'] = None
            completed['expected_aversion'] = None
        
        # Convert to numeric (vectorized)
        completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
        completed['initial_aversion'] = pd.to_numeric(completed['initial_aversion'], errors='coerce')
        completed['expected_aversion'] = pd.to_numeric(completed['expected_aversion'], errors='coerce')
        
        # Get actual relief from actual_dict (OPTIMIZED: vectorized extraction)
        if 'actual_dict' in completed.columns:
            actual_list = completed['actual_dict'].tolist()
            completed['actual_relief'] = [
                d.get('actual_relief') if isinstance(d, dict) else None 
                for d in actual_list
            ]
        else:
            completed['actual_relief'] = None
        
        # Fallback to relief_score column if actual_dict doesn't have it
        if 'relief_score' in completed.columns:
            completed['actual_relief'] = completed['actual_relief'].fillna(
                pd.to_numeric(completed['relief_score'], errors='coerce')
            )
        completed['actual_relief'] = pd.to_numeric(completed['actual_relief'], errors='coerce')
        extract_time = (time_module.time() - extract_start) * 1000
        print(f"[Analytics] get_relief_summary: extract fields: {extract_time:.2f}ms")
        
        # Filter to rows where we have both expected and actual relief
        has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
        relief_data = completed[has_both].copy()
        
        # Calculate default relief points (actual - expected, can be negative)
        relief_data['default_relief_points'] = relief_data['actual_relief'] - relief_data['expected_relief']
        
        # Apply aversion multipliers to relief points (OPTIMIZED: vectorized)
        multiplier_start = time_module.time()
        # Calculate multipliers for all rows at once (vectorized)
        initial_av = relief_data['initial_aversion'].fillna(0.0)
        expected_av = relief_data['expected_aversion'].fillna(0.0)
        # Vectorized multiplier calculation (faster than .apply())
        relief_data['aversion_mult'] = [
            self.calculate_aversion_multiplier(ia, ea) 
            for ia, ea in zip(initial_av, expected_av)
        ]
        relief_data['default_relief_points'] = relief_data['default_relief_points'] * relief_data['aversion_mult']
        
        # Calculate net relief points (vectorized)
        relief_data['net_relief_points'] = relief_data['default_relief_points'].clip(lower=0.0)
        relief_data['negative_relief_points'] = relief_data['default_relief_points'].clip(upper=0.0)
        multiplier_time = (time_module.time() - multiplier_start) * 1000
        print(f"[Analytics] get_relief_summary: apply multipliers: {multiplier_time:.2f}ms")
        
        # Calculate productivity time (sum of actual time from actual_dict) - LAST 7 DAYS ONLY
        # Productivity includes only Work and Self care tasks, not Play tasks
        from datetime import timedelta
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # Prepare completed tasks with date for later use (includes ALL tasks for relief score)
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        user_id = self._get_user_id(user_id)
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Join instances with tasks to get task_type
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            completed_with_type = completed.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            # Fill missing task_type with 'Work' as default
            completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
            # Normalize task_type to lowercase for comparison
            completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
            # Filter to only Work and Self care tasks (exclude Play)
            productivity_tasks = completed_with_type[
                completed_with_type['task_type_normalized'].isin(['work', 'self care', 'selfcare', 'self-care'])
            ]
            # Also merge task_type into relief_data for multiplier calculation
            relief_data = relief_data.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            relief_data['task_type'] = relief_data['task_type'].fillna('Work')
        else:
            # Fallback: if no task_type available, use all tasks
            productivity_tasks = completed
            relief_data['task_type'] = 'Work'
        
        # Apply task type multipliers to relief points (OPTIMIZED: vectorized)
        task_types = relief_data['task_type'].tolist()
        type_mults = [self.get_task_type_multiplier(tt) for tt in task_types]
        relief_data['default_relief_points'] = relief_data['default_relief_points'] * pd.Series(type_mults, index=relief_data.index)
        
        # OPTIMIZED: Vectorized extraction of time_actual_minutes
        if 'actual_dict' in productivity_tasks.columns:
            actual_list = productivity_tasks['actual_dict'].tolist()
            productivity_tasks = productivity_tasks.copy()
            productivity_tasks['time_actual'] = [
                d.get('time_actual_minutes') if isinstance(d, dict) else None 
                for d in actual_list
            ]
        else:
            productivity_tasks = productivity_tasks.copy()
            productivity_tasks['time_actual'] = None
        productivity_tasks['time_actual'] = pd.to_numeric(productivity_tasks['time_actual'], errors='coerce')
        
        # Filter productivity tasks to last 7 days
        # Note: completed_at_dt is already set on completed, and merge copies it to productivity_tasks
        completed_last_7d = productivity_tasks[productivity_tasks['completed_at_dt'] >= seven_days_ago]
        productivity_time = completed_last_7d['time_actual'].fillna(0).sum()
        
        # Calculate default relief points totals
        default_total = relief_data['default_relief_points'].sum()
        net_total = relief_data['net_relief_points'].sum()
        
        # Separate positive and negative relief
        positive_relief = relief_data[relief_data['default_relief_points'] > 0]
        negative_relief = relief_data[relief_data['default_relief_points'] < 0]
        
        positive_count = len(positive_relief)
        positive_total = positive_relief['default_relief_points'].sum() if positive_count > 0 else 0.0
        positive_avg = positive_total / positive_count if positive_count > 0 else 0.0
        
        negative_count = len(negative_relief)
        negative_total = abs(negative_relief['default_relief_points'].sum()) if negative_count > 0 else 0.0
        negative_avg = abs(pd.to_numeric(negative_relief['default_relief_points'], errors='coerce').mean()) if negative_count > 0 else 0.0
        
        # Get efficiency summary (OPTIMIZED: calculate inline to avoid reloading instances)
        efficiency_start = time_module.time()
        # Calculate efficiency inline from already-loaded completed DataFrame
        if not completed.empty:
            # Calculate efficiency for each completed task (vectorized where possible)
            completed['efficiency_score'] = completed.apply(self.calculate_efficiency_score, axis=1)
            valid_efficiency = completed[completed['efficiency_score'] > 0]
            if not valid_efficiency.empty:
                avg_efficiency = valid_efficiency['efficiency_score'].mean()
                high_efficiency_count = len(valid_efficiency[valid_efficiency['efficiency_score'] >= 70])
                low_efficiency_count = len(valid_efficiency[valid_efficiency['efficiency_score'] < 50])
                # Group by completion status
                efficiency_by_completion = {}
                if 'completed_at' in valid_efficiency.columns:
                    valid_efficiency['completed_at_dt'] = pd.to_datetime(valid_efficiency['completed_at'], errors='coerce')
                    valid_efficiency['is_recent'] = valid_efficiency['completed_at_dt'] >= (datetime.now() - timedelta(days=7))
                    efficiency_by_completion['recent'] = valid_efficiency[valid_efficiency['is_recent']]['efficiency_score'].mean() if valid_efficiency['is_recent'].any() else 0.0
                    efficiency_by_completion['older'] = valid_efficiency[~valid_efficiency['is_recent']]['efficiency_score'].mean() if (~valid_efficiency['is_recent']).any() else 0.0
                else:
                    efficiency_by_completion = {'recent': avg_efficiency, 'older': avg_efficiency}
            else:
                avg_efficiency = 0.0
                high_efficiency_count = 0
                low_efficiency_count = 0
                efficiency_by_completion = {}
        else:
            avg_efficiency = 0.0
            high_efficiency_count = 0
            low_efficiency_count = 0
            efficiency_by_completion = {}
        
        efficiency_summary = {
            'avg_efficiency': avg_efficiency,
            'high_efficiency_count': high_efficiency_count,
            'low_efficiency_count': low_efficiency_count,
            'efficiency_by_completion': efficiency_by_completion,
        }
        efficiency_time = (time_module.time() - efficiency_start) * 1000
        print(f"[Analytics] get_relief_summary: get_efficiency_summary (inline): {efficiency_time:.2f}ms")
        
        # Filter out test/dev tasks from obstacles calculation
        # Keep all tasks for relief calculations, but exclude test tasks from obstacles
        if 'task_name' in relief_data.columns:
            relief_data_for_obstacles = relief_data[
                ~relief_data['task_name'].apply(self._is_test_task)
            ].copy()
        else:
            relief_data_for_obstacles = relief_data.copy()
        
        # Safety check: Ensure task_id column exists
        if 'task_id' not in relief_data_for_obstacles.columns:
            print(f"[Analytics] WARNING: relief_data_for_obstacles missing 'task_id' column. Columns: {list(relief_data_for_obstacles.columns)}")
            print(f"[Analytics] relief_data columns: {list(relief_data.columns) if not relief_data.empty else 'empty'}")
            # If task_id is missing, we can't calculate obstacles scores - skip this section
            relief_data_for_obstacles = pd.DataFrame()  # Empty DataFrame to skip obstacles calculation
        
        # Calculate obstacles overcome scores
        from .instance_manager import InstanceManager
        im = InstanceManager()
        
        # Batch-load baseline aversions (OPTIMIZED: single query instead of N queries)
        baseline_start = time_module.time()
        if relief_data_for_obstacles.empty or 'task_id' not in relief_data_for_obstacles.columns:
            unique_task_ids = []
        else:
            unique_task_ids = relief_data_for_obstacles['task_id'].unique().tolist()
        baseline_aversions = im.get_batch_baseline_aversions(unique_task_ids, user_id) if unique_task_ids else {}
        baseline_time = (time_module.time() - baseline_start) * 1000
        print(f"[Analytics] get_relief_summary: batch baseline aversions ({len(unique_task_ids)} tasks): {baseline_time:.2f}ms")
        
        # Map baseline aversions to rows (OPTIMIZED: vectorized)
        if relief_data_for_obstacles.empty or 'task_id' not in relief_data_for_obstacles.columns:
            # Skip obstacles calculation if no task_id column
            total_obstacles_robust = 0.0
            total_obstacles_sensitive = 0.0
            obstacles_totals = {}
            weekly_obstacles_bonus_multiplier_robust = 1.0
            weekly_obstacles_bonus_multiplier_sensitive = 1.0
            max_obstacle_spike_robust = 0.0
            max_obstacle_spike_sensitive = 0.0
        else:
            task_ids = relief_data_for_obstacles['task_id'].tolist()
            relief_data_for_obstacles['baseline_aversion_robust'] = [
                baseline_aversions.get(tid, {}).get('robust') if tid in baseline_aversions else None
                for tid in task_ids
            ]
            relief_data_for_obstacles['baseline_aversion_sensitive'] = [
                baseline_aversions.get(tid, {}).get('sensitive') if tid in baseline_aversions else None
                for tid in task_ids
            ]
            
            # Calculate obstacles scores using multiple formulas for comparison
            def _calculate_obstacles_scores_robust(row):
                baseline = row.get('baseline_aversion_robust')
                current = row.get('expected_aversion')
                expected_relief = row.get('expected_relief')
                actual_relief = row.get('actual_relief')
                # Convert to float, handling NaN
                expected_relief = float(expected_relief) if expected_relief is not None and not pd.isna(expected_relief) else None
                actual_relief = float(actual_relief) if actual_relief is not None and not pd.isna(actual_relief) else None
                scores = self.calculate_obstacles_scores(baseline, current, expected_relief, actual_relief)
                return scores
            
            def _calculate_obstacles_scores_sensitive(row):
                baseline = row.get('baseline_aversion_sensitive')
                current = row.get('expected_aversion')
                expected_relief = row.get('expected_relief')
                actual_relief = row.get('actual_relief')
                # Convert to float, handling NaN
                expected_relief = float(expected_relief) if expected_relief is not None and not pd.isna(expected_relief) else None
                actual_relief = float(actual_relief) if actual_relief is not None and not pd.isna(actual_relief) else None
                scores = self.calculate_obstacles_scores(baseline, current, expected_relief, actual_relief)
                return scores
            
            # Calculate all score variants
            relief_data_for_obstacles['obstacles_scores_robust'] = relief_data_for_obstacles.apply(_calculate_obstacles_scores_robust, axis=1)
            relief_data_for_obstacles['obstacles_scores_sensitive'] = relief_data_for_obstacles.apply(_calculate_obstacles_scores_sensitive, axis=1)
            
            # Extract individual scores for backward compatibility and new analytics (OPTIMIZED: vectorized)
            score_variants = ['expected_only', 'actual_only', 'minimum', 'average', 'net_penalty', 'net_bonus', 'net_weighted']
            robust_scores_list = relief_data_for_obstacles['obstacles_scores_robust'].tolist()
            sensitive_scores_list = relief_data_for_obstacles['obstacles_scores_sensitive'].tolist()
            for variant in score_variants:
                relief_data_for_obstacles[f'obstacles_score_{variant}_robust'] = [
                    x.get(variant, 0.0) if isinstance(x, dict) else 0.0 
                    for x in robust_scores_list
                ]
                relief_data_for_obstacles[f'obstacles_score_{variant}_sensitive'] = [
                    x.get(variant, 0.0) if isinstance(x, dict) else 0.0 
                    for x in sensitive_scores_list
                ]
            
            # Keep backward compatibility: use expected_only as the default
            relief_data_for_obstacles['obstacles_score_robust'] = relief_data_for_obstacles['obstacles_score_expected_only_robust']
            relief_data_for_obstacles['obstacles_score_sensitive'] = relief_data_for_obstacles['obstacles_score_expected_only_sensitive']
            
            # Calculate total obstacles scores for all variants
            total_obstacles_robust = relief_data_for_obstacles['obstacles_score_robust'].sum()
            total_obstacles_sensitive = relief_data_for_obstacles['obstacles_score_sensitive'].sum()
            
            # Calculate totals for all score variants
            score_variants = ['expected_only', 'actual_only', 'minimum', 'average', 'net_penalty', 'net_bonus', 'net_weighted']
            obstacles_totals = {}
            for variant in score_variants:
                obstacles_totals[f'total_obstacles_{variant}_robust'] = relief_data_for_obstacles[f'obstacles_score_{variant}_robust'].sum()
                obstacles_totals[f'total_obstacles_{variant}_sensitive'] = relief_data_for_obstacles[f'obstacles_score_{variant}_sensitive'].sum()
            
            # Calculate weekly obstacles (last 7 days) for bonus multiplier
            relief_data_for_obstacles['completed_at_dt'] = pd.to_datetime(relief_data_for_obstacles['completed_at'], errors='coerce')
            relief_data_last_7d = relief_data_for_obstacles[relief_data_for_obstacles['completed_at_dt'] >= seven_days_ago]
            
            # Calculate max spike amount for weekly bonus
            def _get_max_spike_robust(row):
                baseline = row.get('baseline_aversion_robust')
                current = row.get('expected_aversion')
                is_spontaneous, spike_amount = self.detect_spontaneous_aversion(baseline, current)
                return spike_amount if is_spontaneous else 0.0
            
            def _get_max_spike_sensitive(row):
                baseline = row.get('baseline_aversion_sensitive')
                current = row.get('expected_aversion')
                is_spontaneous, spike_amount = self.detect_spontaneous_aversion(baseline, current)
                return spike_amount if is_spontaneous else 0.0
            
            if not relief_data_last_7d.empty:
                # Use .copy() to avoid SettingWithCopyWarning
                relief_data_last_7d = relief_data_last_7d.copy()
                relief_data_last_7d['spike_amount_robust'] = relief_data_last_7d.apply(_get_max_spike_robust, axis=1)
                relief_data_last_7d['spike_amount_sensitive'] = relief_data_last_7d.apply(_get_max_spike_sensitive, axis=1)
                max_spike_robust = relief_data_last_7d['spike_amount_robust'].max() if 'spike_amount_robust' in relief_data_last_7d.columns else 0.0
                max_spike_sensitive = relief_data_last_7d['spike_amount_sensitive'].max() if 'spike_amount_sensitive' in relief_data_last_7d.columns else 0.0
            else:
                max_spike_robust = 0.0
                max_spike_sensitive = 0.0
            
            # Calculate weekly bonus multipliers
            weekly_obstacles_bonus_multiplier_robust = self.calculate_obstacles_bonus_multiplier(max_spike_robust)
            weekly_obstacles_bonus_multiplier_sensitive = self.calculate_obstacles_bonus_multiplier(max_spike_sensitive)
            max_obstacle_spike_robust = max_spike_robust
            max_obstacle_spike_sensitive = max_spike_sensitive
        
        # Calculate relief × duration metrics with multipliers
        # Use actual relief_score and duration_minutes from completed tasks
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        completed['duration_minutes_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce')
        
        # Join task_type if not already joined
        if 'task_type' not in completed.columns:
            if not tasks_df.empty and 'task_type' in tasks_df.columns:
                completed = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed['task_type'] = completed['task_type'].fillna('Work')
            else:
                completed['task_type'] = 'Work'
        
        # Calculate multipliers for each task (OPTIMIZED: vectorized)
        initial_av_list = completed['initial_aversion'].fillna(0.0).tolist()
        expected_av_list = completed['expected_aversion'].fillna(0.0).tolist()
        task_type_list = completed['task_type'].fillna('Work').tolist()
        completed['relief_multiplier'] = [
            self.calculate_aversion_multiplier(ia, ea) * self.get_task_type_multiplier(tt)
            for ia, ea, tt in zip(initial_av_list, expected_av_list, task_type_list)
        ]
        
        # Calculate relief_duration_score per task instance (relief_score × duration_minutes × multiplier)
        # Normalize by dividing by 60 to convert minutes to hours scale (keeps scores more reasonable)
        completed['relief_duration_score'] = (
            completed['relief_score_numeric'] * 
            completed['duration_minutes_numeric'] * 
            completed['relief_multiplier']
        ) / 60.0
        
        # Filter to rows with valid relief_duration_score (both relief and duration must be present)
        valid_relief_duration = completed[
            completed['relief_duration_score'].notna() & 
            (completed['relief_duration_score'] != 0)
        ]
        
        # Calculate totals and averages WITH multipliers
        total_relief_duration_score = valid_relief_duration['relief_duration_score'].sum() if not valid_relief_duration.empty else 0.0
        avg_relief_duration_score = pd.to_numeric(valid_relief_duration['relief_duration_score'], errors='coerce').mean() if not valid_relief_duration.empty else 0.0
        
        # Calculate relief scores WITHOUT multipliers (raw relief × duration)
        # This is the accurate baseline without inflation from multipliers
        completed['relief_duration_score_no_mult'] = (
            completed['relief_score_numeric'] * 
            completed['duration_minutes_numeric']
        ) / 60.0
        valid_relief_no_mult = completed[
            completed['relief_duration_score_no_mult'].notna() & 
            (completed['relief_duration_score_no_mult'] != 0)
        ]
        total_relief_score_no_mult = valid_relief_no_mult['relief_duration_score_no_mult'].sum() if not valid_relief_no_mult.empty else 0.0
        avg_relief_score_no_mult = pd.to_numeric(valid_relief_no_mult['relief_duration_score_no_mult'], errors='coerce').mean() if not valid_relief_no_mult.empty else 0.0
        
        # Total relief score WITH multipliers (for backward compatibility, but should be labeled)
        total_relief_score = total_relief_duration_score
        
        # Calculate weekly relief score (sum of relief × duration for last 7 days, WITHOUT multipliers)
        # Note: relief score includes ALL tasks (work, play, self care), not just productivity tasks
        # Weekly relief score should be raw relief × duration, not multiplied by aversion/task type
        completed_last_7d_all = completed[completed['completed_at_dt'] >= seven_days_ago]
        # Calculate weekly relief score without multipliers: just relief × duration / 60
        weekly_relief_score_base = (
            completed_last_7d_all['relief_score_numeric'] * 
            completed_last_7d_all['duration_minutes_numeric']
        ).fillna(0).sum() / 60.0
        
        # Apply weekly obstacles bonus multipliers to weekly relief score
        weekly_relief_score_robust = weekly_relief_score_base * weekly_obstacles_bonus_multiplier_robust
        weekly_relief_score_sensitive = weekly_relief_score_base * weekly_obstacles_bonus_multiplier_sensitive
        
        # Calculate productivity points (similar to relief points but only for Work and Self care tasks)
        # Productivity points = (actual_relief - expected_relief) × aversion_multiplier × task_type_multiplier
        # But task_type_multiplier for productivity: work=2.0, self care=1.0, play=0 (excluded)
        if 'task_type' in relief_data.columns:
            relief_data['task_type_normalized'] = relief_data['task_type'].astype(str).str.strip().str.lower()
            productivity_relief_data = relief_data[
                relief_data['task_type_normalized'].isin(['work', 'self care', 'selfcare', 'self-care'])
            ].copy()
        else:
            productivity_relief_data = pd.DataFrame()
        
        # Calculate productivity multiplier (OPTIMIZED: vectorized)
        if not productivity_relief_data.empty:
            task_type_list = productivity_relief_data['task_type'].fillna('Work').astype(str).str.strip().str.lower().tolist()
            productivity_relief_data['productivity_multiplier'] = [
                2.0 if tt == 'work' else (1.0 if tt in ['self care', 'selfcare', 'self-care'] else 1.0)
                for tt in task_type_list
            ]
            # Productivity points: we need to undo the relief task_type_multiplier and apply productivity multiplier instead
            # default_relief_points already has: (actual - expected) × aversion_mult × relief_task_type_mult
            # We want: (actual - expected) × aversion_mult × productivity_mult
            # So: productivity_points = default_relief_points / relief_task_type_mult × productivity_mult
            # Get the relief task type multiplier that was already applied (OPTIMIZED: vectorized)
            task_type_list = productivity_relief_data['task_type'].fillna('Work').tolist()
            productivity_relief_data['relief_task_type_mult'] = [
                self.get_task_type_multiplier(tt) for tt in task_type_list
            ]
            # Calculate base points without task type multiplier (OPTIMIZED: vectorized)
            # Avoid division by zero - if relief_task_type_mult is 0 or very small, use default_relief_points directly
            default_points = productivity_relief_data['default_relief_points'].tolist()
            relief_mults = productivity_relief_data['relief_task_type_mult'].tolist()
            productivity_relief_data['base_relief_points'] = [
                dp / rm if rm > 0.01 else dp
                for dp, rm in zip(default_points, relief_mults)
            ]
            # Apply productivity multiplier
            productivity_relief_data['productivity_points'] = (
                productivity_relief_data['base_relief_points'] * 
                productivity_relief_data['productivity_multiplier']
            )
            total_productivity_points = productivity_relief_data['productivity_points'].sum()
            net_productivity_points = productivity_relief_data[
                productivity_relief_data['productivity_points'] > 0
            ]['productivity_points'].sum()
            
            # Calculate weekly productivity points (last 7 days)
            productivity_relief_data['completed_at_dt'] = pd.to_datetime(productivity_relief_data['completed_at'], errors='coerce')
            productivity_last_7d = productivity_relief_data[productivity_relief_data['completed_at_dt'] >= seven_days_ago]
            weekly_productivity_points_base = productivity_last_7d['productivity_points'].fillna(0).sum()
            
            # Apply weekly obstacles bonus multipliers
            weekly_productivity_points_robust = weekly_productivity_points_base * weekly_obstacles_bonus_multiplier_robust
            weekly_productivity_points_sensitive = weekly_productivity_points_base * weekly_obstacles_bonus_multiplier_sensitive
        else:
            total_productivity_points = 0.0
            net_productivity_points = 0.0
            weekly_productivity_points_base = 0.0
            weekly_productivity_points_robust = 0.0
            weekly_productivity_points_sensitive = 0.0
        
        # Calculate new productivity score based on completion/time ratio
        # First, ensure completed has task_type
        if 'task_type' not in completed.columns:
            # Load tasks to get task_type if not already loaded
            if 'tasks_df' not in locals():
                from .task_manager import TaskManager
                task_manager = TaskManager()
                tasks_df = task_manager.get_all(user_id=user_id)
            if not tasks_df.empty and 'task_type' in tasks_df.columns:
                completed = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed['task_type'] = completed['task_type'].fillna('Work')
        
        # Count self care tasks per day
        self_care_tasks_per_day = {}
        if 'task_type' in completed.columns:
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
        
        # Calculate work/play time per day for play penalty and work burnout penalty
        work_play_time_per_day = {}
        if 'task_type' in completed.columns:
            # Ensure completed_at_dt exists
            if 'completed_at_dt' not in completed.columns:
                completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
            
            # Get actual time from actual_dict
            def _get_actual_time_for_work_play(row):
                """Get actual time from actual_dict for work/play time calculation."""
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, dict):
                        return float(actual_dict.get('time_actual_minutes', 0) or 0)
                except (KeyError, TypeError, ValueError):
                    pass
                return 0.0
            
            completed['time_for_work_play'] = completed.apply(_get_actual_time_for_work_play, axis=1)
            completed['time_for_work_play'] = pd.to_numeric(completed['time_for_work_play'], errors='coerce').fillna(0.0)
            
            # Filter to completed tasks with valid dates
            valid_for_work_play = completed[
                completed['completed_at_dt'].notna() & 
                (completed['time_for_work_play'] > 0)
            ].copy()
            
            if not valid_for_work_play.empty:
                valid_for_work_play['date'] = valid_for_work_play['completed_at_dt'].dt.date
                
                # Group by date and task type
                for date, group in valid_for_work_play.groupby('date'):
                    date_str = date.isoformat()
                    work_time = group[group['task_type_normalized'] == 'work']['time_for_work_play'].sum()
                    play_time = group[group['task_type_normalized'] == 'play']['time_for_work_play'].sum()
                    work_play_time_per_day[date_str] = {
                        'work_time': float(work_time),
                        'play_time': float(play_time)
                    }

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
        
        # Calculate weekly average productivity time for bonus/penalty calculation
        # Get all completed tasks with actual time
        def _get_actual_time_for_avg(row):
            """Get actual time from actual_dict for weekly average calculation."""
            try:
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed['time_actual_for_avg'] = completed.apply(_get_actual_time_for_avg, axis=1)
        completed['time_actual_for_avg'] = pd.to_numeric(completed['time_actual_for_avg'], errors='coerce')
        
        # Calculate weekly average: average time per task across all completed tasks
        valid_times = completed[completed['time_actual_for_avg'].notna() & (completed['time_actual_for_avg'] > 0)]
        if not valid_times.empty:
            weekly_avg_time = valid_times['time_actual_for_avg'].mean()
        else:
            weekly_avg_time = 0.0
        
        # Get goal hours and weekly productive hours for goal-based adjustment
        goal_hours_per_week = None
        weekly_productive_hours = None
        try:
            # Convert user_id to string for UserStateManager (expects str)
            user_id_str = str(user_id) if user_id is not None else "default_user"
            goal_settings = UserStateManager().get_productivity_goal_settings(user_id_str)
            goal_hours_per_week = goal_settings.get('goal_hours_per_week')
            if goal_hours_per_week:
                goal_hours_per_week = float(goal_hours_per_week)
                # Calculate weekly productive hours (Work + Self Care only)
                from .productivity_tracker import ProductivityTracker
                tracker = ProductivityTracker()
                weekly_data = tracker.calculate_weekly_productivity_hours(user_id_str)
                weekly_productive_hours = weekly_data.get('total_hours', 0.0)
                if weekly_productive_hours <= 0:
                    weekly_productive_hours = None
        except Exception as e:
            # If goal settings or tracker fails, just continue without goal adjustment
            print(f"[Analytics] Error getting goal hours: {e}")
            goal_hours_per_week = None
            weekly_productive_hours = None
        
        # Calculate productivity score for all completed tasks
        # Ensure completed has the required columns
        if 'actual_dict' not in completed.columns or 'predicted_dict' not in completed.columns:
            # If dictionaries aren't available, try to create them
            def _safe_json(cell):
                if isinstance(cell, dict):
                    return cell
                cell = cell or '{}'
                try:
                    return json.loads(cell)
                except Exception:
                    return {}
            
            if 'actual' in completed.columns:
                completed['actual_dict'] = completed['actual'].apply(_safe_json)
            else:
                completed['actual_dict'] = pd.Series([{}] * len(completed))
            
            if 'predicted' in completed.columns:
                completed['predicted_dict'] = completed['predicted'].apply(_safe_json)
            else:
                completed['predicted_dict'] = pd.Series([{}] * len(completed))
        
        completed['productivity_score'] = completed.apply(
            lambda row: self.calculate_productivity_score(
                row,
                self_care_tasks_per_day,
                weekly_avg_time,
                work_play_time_per_day,
                productivity_settings=self.productivity_settings,
                weekly_work_summary=weekly_work_summary,
                goal_hours_per_week=goal_hours_per_week,
                weekly_productive_hours=weekly_productive_hours
            ),
            axis=1
        )
        
        # Calculate totals
        total_productivity_score = completed['productivity_score'].fillna(0).sum()
        
        # Ensure completed_at_dt exists for weekly calculations
        if 'completed_at_dt' not in completed.columns:
            completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Calculate weekly productivity score (last 7 days)
        completed_last_7d_for_score = completed[completed['completed_at_dt'] >= seven_days_ago]
        weekly_productivity_score = completed_last_7d_for_score['productivity_score'].fillna(0).sum()
        
        # Calculate grit score: rewards persistence and taking longer
        # First, count how many times each task has been completed
        task_completion_counts = {}
        if 'task_id' in completed.columns:
            task_counts = completed.groupby('task_id').size()
            for task_id, count in task_counts.items():
                task_completion_counts[task_id] = int(count)
        
        # Calculate grit score for all completed tasks
        completed['grit_score'] = completed.apply(
            lambda row: self.calculate_grit_score(row, task_completion_counts),
            axis=1
        )
        
        # Calculate grit score totals
        total_grit_score = completed['grit_score'].fillna(0).sum()
        
        # Calculate weekly grit score (last 7 days)
        # Recreate the filtered DataFrame after grit_score has been calculated
        completed_last_7d_for_grit = completed[completed['completed_at_dt'] >= seven_days_ago]
        weekly_grit_score = completed_last_7d_for_grit['grit_score'].fillna(0).sum()
        
        result = {
            'productivity_time_minutes': round(float(productivity_time), 1),
            'default_relief_points': round(float(default_total), 2),
            'net_relief_points': round(float(net_total), 2),
            'positive_relief_count': int(positive_count),
            'positive_relief_total': round(float(positive_total), 2),
            'positive_relief_avg': round(float(positive_avg), 2),
            'negative_relief_count': int(negative_count),
            'negative_relief_total': round(float(negative_total), 2),
            'negative_relief_avg': round(float(negative_avg), 2),
            'avg_efficiency': efficiency_summary.get('avg_efficiency', 0.0),
            'high_efficiency_count': efficiency_summary.get('high_efficiency_count', 0),
            'low_efficiency_count': efficiency_summary.get('low_efficiency_count', 0),
            # Relief scores WITH multipliers (inflated, for backward compatibility)
            'total_relief_duration_score': round(float(total_relief_duration_score), 2),
            'avg_relief_duration_score': round(float(avg_relief_duration_score), 2),
            'total_relief_score': round(float(total_relief_score), 2),
            # Relief scores WITHOUT multipliers (accurate baseline)
            'total_relief_score_no_mult': round(float(total_relief_score_no_mult), 2),
            'avg_relief_score_no_mult': round(float(avg_relief_score_no_mult), 2),
            # Weekly relief score (already without multipliers)
            'weekly_relief_score': round(float(weekly_relief_score_base), 2),
            'weekly_relief_score_with_bonus_robust': round(float(weekly_relief_score_robust), 2),
            'weekly_relief_score_with_bonus_sensitive': round(float(weekly_relief_score_sensitive), 2),
            'total_productivity_points': round(float(total_productivity_points), 2),
            'net_productivity_points': round(float(net_productivity_points), 2),
            'weekly_productivity_points': round(float(weekly_productivity_points_base), 2),
            'weekly_productivity_points_with_bonus_robust': round(float(weekly_productivity_points_robust), 2),
            'weekly_productivity_points_with_bonus_sensitive': round(float(weekly_productivity_points_sensitive), 2),
            # New productivity score based on completion/time ratio
            'total_productivity_score': round(float(total_productivity_score), 2),
            'weekly_productivity_score': round(float(weekly_productivity_score), 2),
            # Grit score: rewards persistence and taking longer (separate from productivity)
            'total_grit_score': round(float(total_grit_score), 2),
            'weekly_grit_score': round(float(weekly_grit_score), 2),
            # Obstacles metrics (backward compatibility - uses expected_only)
            'total_obstacles_score_robust': round(float(total_obstacles_robust), 2),
            'total_obstacles_score_sensitive': round(float(total_obstacles_sensitive), 2),
            'weekly_obstacles_bonus_multiplier_robust': round(float(weekly_obstacles_bonus_multiplier_robust), 3),
            'weekly_obstacles_bonus_multiplier_sensitive': round(float(weekly_obstacles_bonus_multiplier_sensitive), 3),
            'max_obstacle_spike_robust': round(float(max_obstacle_spike_robust), 1),
            'max_obstacle_spike_sensitive': round(float(max_obstacle_spike_sensitive), 1),
            # Aversion analytics: all score variants for comparison
            **{k: round(float(v), 2) for k, v in obstacles_totals.items()},
        }
        
        # Update cache before returning
        # Cache is now user-specific, keyed by user_id
        cache_key = user_id if user_id is not None else "default"
        Analytics._relief_summary_cache[cache_key] = result
        Analytics._relief_summary_cache_time[cache_key] = time_module.time()
        
        total_time = (time_module.perf_counter() - total_start) * 1000
        print(f"[Analytics] get_relief_summary: {total_time:.2f}ms")
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'analytics.py:4915',
                    'message': 'get_relief_summary completed',
                    'data': {'total_time_ms': total_time},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        return result

    def get_weekly_hours_history(self) -> Dict[str, any]:
        """Get historical daily productivity hours data for trend analysis (last 90 days).
        
        Productivity includes only Work and Self care tasks, not Play tasks.
        
        Returns:
            Dict with 'dates' (list of date strings), 'hours' (list of hours per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        import time as time_module
        import traceback
        import json
        # #region agent log
        hist_start = time_module.time()
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                call_stack = ''.join(traceback.format_stack()[-3:-1])
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'analytics.py:4919',
                    'message': 'get_weekly_hours_history called',
                    'data': {'caller': call_stack.split('\\n')[-2].strip() if call_stack else 'unknown'},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        user_id = self._get_user_id(None)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'hours': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Load tasks to get task_type and filter to only Work and Self care tasks
        from .task_manager import TaskManager
        task_manager = TaskManager()
        user_id = self._get_user_id(user_id)
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Join instances with tasks to get task_type
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            completed_with_type = completed.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            # Fill missing task_type with 'Work' as default
            completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
            # Normalize task_type to lowercase for comparison
            completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
            # Filter to only Work and Self care tasks (exclude Play)
            completed = completed_with_type[
                completed_with_type['task_type_normalized'].isin(['work', 'self care', 'selfcare', 'self-care'])
            ]
        
        # Get actual time from completed tasks
        def _get_actual_time(row):
            try:
                actual_dict = row['actual_dict']
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except (KeyError, TypeError):
                pass
            return None
        
        # Use .copy() to avoid SettingWithCopyWarning (per pandas docs)
        completed = completed.copy()
        completed['time_actual'] = completed.apply(_get_actual_time, axis=1)
        completed['time_actual'] = pd.to_numeric(completed['time_actual'], errors='coerce')
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows with time and date
        valid = completed[completed['time_actual'].notna() & completed['completed_at_dt'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'hours': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last 90 days
        from datetime import timedelta
        ninety_days_ago = datetime.now() - timedelta(days=90)
        valid = valid[valid['completed_at_dt'] >= ninety_days_ago].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'hours': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by day - only include days with data
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_data = valid.groupby('date')['time_actual'].sum().reset_index()
        daily_data['hours'] = daily_data['time_actual'] / 60.0
        daily_data = daily_data.sort_values('date')
        
        # Filter to last 90 days (but keep only days with data)
        daily_data = daily_data[daily_data['date'] >= ninety_days_ago.date()].copy()
        
        # Format dates as strings
        daily_data['date_str'] = daily_data['date'].astype(str)
        
        # Get current value (last 7 days total) - this stays as weekly total for the main card
        seven_days_ago = datetime.now() - timedelta(days=7)
        current_week_data = valid[valid['completed_at_dt'] >= seven_days_ago]
        current_value = current_week_data['time_actual'].sum() / 60.0 if not current_week_data.empty else 0.0
        
        # Calculate weekly average (average of daily hours over last 7 days with data)
        # This is the average daily value, used for chart comparison
        last_7_days = daily_data.tail(7) if len(daily_data) >= 7 else daily_data
        weekly_average = pd.to_numeric(last_7_days['hours'], errors='coerce').mean() if not last_7_days.empty else 0.0
        
        # Calculate 3-month average accounting for untracked days
        # Find the earliest date with data (tracking start date)
        if not daily_data.empty:
            earliest_date = daily_data['date'].min()
            # Use the more recent of: tracking start date or 90 days ago
            analysis_start = max(earliest_date, ninety_days_ago.date())
            today = datetime.now().date()
            
            # Create a complete date range from analysis_start to today
            date_range = pd.date_range(start=analysis_start, end=today, freq='D')
            date_range_dates = [d.date() for d in date_range]
            
            # Create a DataFrame with all dates, filling missing days with 0 hours
            full_daily_data = pd.DataFrame({'date': date_range_dates})
            full_daily_data = full_daily_data.merge(
                daily_data[['date', 'hours']],
                on='date',
                how='left'
            )
            full_daily_data['hours'] = full_daily_data['hours'].fillna(0.0)
            
            # Calculate average over all days in the tracking period (untracked days = 0 hours)
            three_month_average = pd.to_numeric(full_daily_data['hours'], errors='coerce').mean() if not full_daily_data.empty else 0.0
        else:
            three_month_average = 0.0
        
        # Check if we have at least 2 weeks of data
        days_with_data = len(daily_data)
        has_sufficient_data = days_with_data >= 14
        
        hist_time = (time_module.time() - hist_start) * 1000
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'analytics.py:5137',
                    'message': 'get_weekly_hours_history completed',
                    'data': {'time_ms': hist_time, 'days_count': days_with_data},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        return {
            'dates': daily_data['date_str'].tolist(),
            'hours': daily_data['hours'].tolist(),
            'current_value': round(float(current_value), 2),
            'weekly_average': round(float(weekly_average), 2),
            'three_month_average': round(float(three_month_average), 2),
            'has_sufficient_data': has_sufficient_data,
            'days_with_data': days_with_data,
        }

    def get_weekly_relief_history(self) -> Dict[str, any]:
        """Get historical daily relief points data for trend analysis (last 90 days).
        
        Returns:
            Dict with 'dates' (list of date strings), 'relief_points' (list of relief points per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        user_id = self._get_user_id(None)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'relief_points': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Calculate relief × duration score for each task
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        completed['duration_minutes_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce')
        completed['relief_duration_score'] = (
            completed['relief_score_numeric'] * completed['duration_minutes_numeric']
        )
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows with relief score and date
        valid = completed[
            completed['relief_duration_score'].notna() & 
            (completed['relief_duration_score'] != 0) &
            completed['completed_at_dt'].notna()
        ].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'relief_points': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last 90 days
        from datetime import timedelta
        ninety_days_ago = datetime.now() - timedelta(days=90)
        valid = valid[valid['completed_at_dt'] >= ninety_days_ago].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'relief_points': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by day - only include days with data
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_data = valid.groupby('date')['relief_duration_score'].sum().reset_index()
        daily_data['relief_points'] = daily_data['relief_duration_score']
        daily_data = daily_data.sort_values('date')
        
        # Filter to last 90 days (but keep only days with data)
        daily_data = daily_data[daily_data['date'] >= ninety_days_ago.date()].copy()
        
        # Format dates as strings
        daily_data['date_str'] = daily_data['date'].astype(str)
        
        # Get current value (last 7 days total) - this stays as weekly total for the main card
        seven_days_ago = datetime.now() - timedelta(days=7)
        current_week_data = valid[valid['completed_at_dt'] >= seven_days_ago]
        current_value = current_week_data['relief_duration_score'].sum() if not current_week_data.empty else 0.0
        
        # Calculate weekly average (average of daily relief points over last 7 days with data)
        # This is the average daily value, used for chart comparison
        last_7_days = daily_data.tail(7) if len(daily_data) >= 7 else daily_data
        weekly_average = pd.to_numeric(last_7_days['relief_points'], errors='coerce').mean() if not last_7_days.empty else 0.0
        
        # Calculate 3-month average (average of daily relief points over all days with data)
        three_month_average = pd.to_numeric(daily_data['relief_points'], errors='coerce').mean() if not daily_data.empty else 0.0
        
        # Check if we have at least 2 weeks of data
        days_with_data = len(daily_data)
        has_sufficient_data = days_with_data >= 14
        
        return {
            'dates': daily_data['date_str'].tolist(),
            'relief_points': daily_data['relief_points'].tolist(),
            'current_value': round(float(current_value), 2),
            'weekly_average': round(float(weekly_average), 2),
            'three_month_average': round(float(three_month_average), 2),
            'has_sufficient_data': has_sufficient_data,
            'days_with_data': days_with_data,
        }

    def get_weekly_productivity_history(self) -> Dict[str, any]:
        """Get historical daily productivity score data for trend analysis (last 90 days).
        
        Returns:
            Dict with 'dates' (list of date strings), 'productivity_scores' (list of scores per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        import time as time_module
        import traceback
        import json
        # #region agent log
        prod_hist_start = time_module.time()
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                call_stack = ''.join(traceback.format_stack()[-3:-1])
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'C',
                    'location': 'analytics.py:5243',
                    'message': 'get_weekly_productivity_history called',
                    'data': {'caller': call_stack.split('\\n')[-2].strip() if call_stack else 'unknown'},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        user_id = self._get_user_id(None)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'productivity_scores': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Calculate productivity score for each task
        from .task_manager import TaskManager
        task_manager = TaskManager()
        user_id = self._get_user_id(user_id)
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Get self-care tasks per day for productivity score calculation
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'productivity_scores': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Calculate productivity scores
        self_care_tasks_per_day = {}
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            completed_with_type = completed.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
            completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
            
            # Count self-care tasks per day
            self_care_tasks = completed_with_type[
                completed_with_type['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
            ]
            if not self_care_tasks.empty:
                # Use .copy() to avoid SettingWithCopyWarning (per pandas docs)
                self_care_tasks = self_care_tasks.copy()
                self_care_tasks['date'] = self_care_tasks['completed_at_dt'].dt.date
                daily_counts = self_care_tasks.groupby('date').size()
                for date, count in daily_counts.items():
                    self_care_tasks_per_day[str(date)] = int(count)
        
        # Calculate productivity score for each completed task
        weekly_avg_time = 0.0  # Will be calculated if needed
        completed['productivity_score'] = completed.apply(
            lambda row: self.calculate_productivity_score(
                row,
                self_care_tasks_per_day,
                weekly_avg_time
            ),
            axis=1
        )
        
        completed['productivity_score'] = pd.to_numeric(completed['productivity_score'], errors='coerce')
        completed = completed[completed['productivity_score'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'productivity_scores': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last 90 days
        from datetime import timedelta
        ninety_days_ago = datetime.now() - timedelta(days=90)
        valid = completed[completed['completed_at_dt'] >= ninety_days_ago].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'productivity_scores': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by day
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_data = valid.groupby('date')['productivity_score'].sum().reset_index()
        daily_data = daily_data.sort_values('date')
        
        # Filter to last 90 days
        daily_data = daily_data[daily_data['date'] >= ninety_days_ago.date()].copy()
        
        # Format dates as strings
        daily_data['date_str'] = daily_data['date'].astype(str)
        
        # Get current value (last 7 days total)
        seven_days_ago = datetime.now() - timedelta(days=7)
        current_week_data = valid[valid['completed_at_dt'] >= seven_days_ago]
        current_value = current_week_data['productivity_score'].sum() if not current_week_data.empty else 0.0
        
        # Calculate weekly average (average of daily scores over last 7 days with data)
        last_7_days = daily_data.tail(7) if len(daily_data) >= 7 else daily_data
        weekly_average = pd.to_numeric(last_7_days['productivity_score'], errors='coerce').mean() if not last_7_days.empty else 0.0
        
        # Calculate 3-month average
        if not daily_data.empty:
            earliest_date = daily_data['date'].min()
            analysis_start = max(earliest_date, ninety_days_ago.date())
            today = datetime.now().date()
            
            date_range = pd.date_range(start=analysis_start, end=today, freq='D')
            date_range_dates = [d.date() for d in date_range]
            
            full_daily_data = pd.DataFrame({'date': date_range_dates})
            full_daily_data = full_daily_data.merge(
                daily_data[['date', 'productivity_score']],
                on='date',
                how='left'
            )
            full_daily_data['productivity_score'] = full_daily_data['productivity_score'].fillna(0.0)
            
            three_month_average = pd.to_numeric(full_daily_data['productivity_score'], errors='coerce').mean() if not full_daily_data.empty else 0.0
        else:
            three_month_average = 0.0
        
        # Check if we have at least 2 weeks of data
        days_with_data = len(daily_data)
        has_sufficient_data = days_with_data >= 14
        
        prod_hist_time = (time_module.time() - prod_hist_start) * 1000
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'C',
                    'location': 'analytics.py:5393',
                    'message': 'get_weekly_productivity_history completed',
                    'data': {'time_ms': prod_hist_time, 'days_count': days_with_data},
                    'timestamp': int(time_module.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        return {
            'dates': daily_data['date_str'].tolist(),
            'productivity_scores': daily_data['productivity_score'].tolist(),
            'current_value': round(float(current_value), 2),
            'weekly_average': round(float(weekly_average), 2),
            'three_month_average': round(float(three_month_average), 2),
            'has_sufficient_data': has_sufficient_data,
            'days_with_data': days_with_data,
        }

    def calculate_efficiency_score(self, row: pd.Series) -> float:
        """Calculate productivity efficiency score for a task instance.
        
        Formula considers:
        - Time efficiency: completion % relative to time spent vs expected
        - Relief bonus: higher relief increases efficiency
        - Motivation factor: low motivation + high relief + good time ratio = bonus
        
        Returns efficiency score (0-100+ scale, higher is better).
        """
        try:
            # Extract data
            actual_dict = row.get('actual_dict', {})
            predicted_dict = row.get('predicted_dict', {})
            
            if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
                return 0.0
            
            completion_pct = actual_dict.get('completion_percent', 0)
            time_actual = actual_dict.get('time_actual_minutes', 0)
            relief_score = pd.to_numeric(row.get('relief_score', 0), errors='coerce') or 0
            
            time_estimate = predicted_dict.get('time_estimate_minutes', 0)
            motivation = predicted_dict.get('motivation', None)
            
            # Convert to numeric
            completion_pct = float(completion_pct) if completion_pct else 0.0
            time_actual = float(time_actual) if time_actual else 0.0
            time_estimate = float(time_estimate) if time_estimate else 0.0
            relief_score = float(relief_score) if relief_score else 0.0
            motivation = float(motivation) if motivation is not None else None
            
            # Base efficiency: completion percentage
            base_efficiency = completion_pct
            
            # Time efficiency factor
            # If we have both actual and expected time, calculate time ratio
            if time_estimate > 0 and time_actual > 0:
                # Expected time for this completion %: (completion_pct / 100) * time_estimate
                expected_time_for_completion = (completion_pct / 100.0) * time_estimate
                
                if expected_time_for_completion > 0:
                    # Time efficiency: did we complete faster or slower than expected?
                    # Ratio > 1 means we were faster, < 1 means slower
                    time_ratio = expected_time_for_completion / max(time_actual, 0.1)
                    
                    # Time efficiency bonus/penalty: scales with completion %
                    # If 100% done in less time = big bonus
                    # If 25% done in <25% of time = good bonus
                    time_efficiency_factor = time_ratio * (completion_pct / 100.0)
                else:
                    time_efficiency_factor = 1.0
                
                # For 100% completed tasks that took longer: factor in relief to mitigate penalty
                if completion_pct >= 100 and time_actual > time_estimate:
                    # Over time penalty is reduced by relief
                    over_time_penalty = (time_actual / time_estimate) - 1.0
                    # Relief mitigates: high relief (8+) can offset up to 50% of over-time penalty
                    relief_mitigation = min(relief_score / 10.0, 0.5)
                    # Adjust time efficiency factor to account for over-time, mitigated by relief
                    time_efficiency_factor = max(0.5, 1.0 - (over_time_penalty * (1.0 - relief_mitigation)))
            else:
                # No time data, neutral factor
                time_efficiency_factor = 1.0
            
            # Relief bonus: scales with relief score (0-10 -> 0-20 bonus points)
            relief_bonus = relief_score * 2.0
            
            # Motivation factor: if low motivation but high relief and good time ratio
            motivation_bonus = 0.0
            if motivation is not None and motivation < 5 and relief_score >= 6:
                # Low motivation (0-4) + high relief (6+) = bonus
                # Bonus increases if time efficiency is also good
                motivation_bonus = (5 - motivation) * (relief_score / 10.0) * time_efficiency_factor
            
            # Calculate final efficiency score
            efficiency = (base_efficiency * time_efficiency_factor) + relief_bonus + motivation_bonus
            
            return round(float(efficiency), 2)
        except Exception as e:
            # Return 0 if calculation fails
            return 0.0

    def get_efficiency_summary(self) -> Dict[str, any]:
        """Calculate efficiency statistics for completed tasks."""
        user_id = self._get_user_id(None)
        df = self._load_instances(user_id=user_id)
        
        if df.empty:
            return {
                'avg_efficiency': 0.0,
                'high_efficiency_count': 0,
                'low_efficiency_count': 0,
                'efficiency_by_completion': {},
            }
        
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'avg_efficiency': 0.0,
                'high_efficiency_count': 0,
                'low_efficiency_count': 0,
                'efficiency_by_completion': {},
            }
        
        # Calculate efficiency for each completed task
        completed['efficiency_score'] = completed.apply(self.calculate_efficiency_score, axis=1)
        
        # Filter out zero efficiency (likely missing data)
        valid_efficiency = completed[completed['efficiency_score'] > 0]
        
        if valid_efficiency.empty:
            return {
                'avg_efficiency': 0.0,
                'high_efficiency_count': 0,
                'low_efficiency_count': 0,
                'efficiency_by_completion': {},
            }
        
        avg_efficiency = pd.to_numeric(valid_efficiency['efficiency_score'], errors='coerce').mean()
        high_efficiency = valid_efficiency[valid_efficiency['efficiency_score'] >= 80]
        low_efficiency = valid_efficiency[valid_efficiency['efficiency_score'] < 50]
        
        # Group by completion percentage ranges
        def _get_completion_range(row):
            actual_dict = row.get('actual_dict', {})
            completion = actual_dict.get('completion_percent', 0)
            try:
                completion = float(completion)
                if completion >= 100:
                    return '100%'
                elif completion >= 75:
                    return '75-99%'
                elif completion >= 50:
                    return '50-74%'
                elif completion >= 25:
                    return '25-49%'
                else:
                    return '0-24%'
            except:
                return 'unknown'
        
        completed['completion_range'] = completed.apply(_get_completion_range, axis=1)
        efficiency_by_completion = completed.groupby('completion_range')['efficiency_score'].apply(lambda x: pd.to_numeric(x, errors='coerce').mean()).to_dict()
        
        return {
            'avg_efficiency': round(float(avg_efficiency), 2),
            'high_efficiency_count': int(len(high_efficiency)),
            'low_efficiency_count': int(len(low_efficiency)),
            'efficiency_by_completion': {k: round(float(v), 2) for k, v in efficiency_by_completion.items()},
        }

    def get_task_relief_history(self, task_id: Optional[str] = None) -> Dict[str, float]:
        """Get relief history for a specific task or all tasks.
        
        Returns average relief points (actual - expected) per task.
        Negative values indicate tasks that consistently underdeliver on expected relief.
        """
        user_id = self._get_user_id(None)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {}
        
        # Extract expected and actual relief
        def _get_expected_relief(row):
            try:
                pred_dict = row['predicted_dict']
                if isinstance(pred_dict, dict):
                    return pred_dict.get('expected_relief', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
        completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
        completed['actual_relief'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        
        # Filter to rows with both expected and actual
        has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
        relief_data = completed[has_both].copy()
        
        if relief_data.empty:
            return {}
        
        # Calculate relief points per row
        relief_data['relief_points'] = relief_data['actual_relief'] - relief_data['expected_relief']
        
        # Filter by task_id if provided
        if task_id:
            relief_data = relief_data[relief_data['task_id'] == task_id]
        
        if relief_data.empty:
            return {}
        
        # Group by task_id and calculate average relief points
        task_relief = relief_data.groupby('task_id')['relief_points'].agg(['mean', 'count']).to_dict('index')
        
        # Convert to simpler format: {task_id: avg_relief_points}
        result = {}
        for tid, stats in task_relief.items():
            result[tid] = round(float(stats['mean']), 2)
        
        return result

    def get_generic_metric_history(self, metric_key: str, days: int = 90) -> Dict[str, any]:
        """Get historical daily data for a generic metric (e.g., stress_level, net_wellbeing).
        
        Extracts metric values from completed task instances and groups by date.
        
        For stored metrics (stress_level, net_wellbeing, etc.), extracts from actual_dict.
        For calculated metrics (execution_score, grit_score, etc.), returns empty history
        to avoid expensive recalculation during initial load.
        
        Args:
            metric_key: The metric key to extract (e.g., 'stress_level', 'net_wellbeing')
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        import time as time_module
        
        # #region agent log
        try:
            import json as json_module
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'HIST', 'location': 'analytics.py:get_generic_metric_history', 'message': 'get_generic_metric_history called', 'data': {'metric_key': metric_key, 'days': days}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
        except: pass
        # #endregion
        
        # Metrics that have optimized history methods
        # Route to specific methods instead of generic extraction for better performance
        # This avoids expensive JSON parsing for each row and uses direct dataframe column access
        metric_routes = {
            'execution_score': self.get_execution_score_history,
            'grit_score': self.get_grit_score_history,
            'thoroughness_score': self.get_thoroughness_score_history,
            'thoroughness_factor': self.get_thoroughness_factor_history,
            'stress_level': self.get_stress_level_history,
            'net_wellbeing': self.get_net_wellbeing_history,
            'net_wellbeing_normalized': self.get_net_wellbeing_normalized_history,
            'relief_score': self.get_relief_score_history,
            'behavioral_score': self.get_behavioral_score_history,
            'stress_efficiency': self.get_stress_efficiency_history,
            'expected_relief': self.get_expected_relief_history,
            'net_relief': self.get_net_relief_history,
            'serendipity_factor': self.get_serendipity_factor_history,
            'disappointment_factor': self.get_disappointment_factor_history,
            'stress_relief_correlation_score': self.get_stress_relief_correlation_score_history,
            'work_time': self.get_work_time_history,
            'play_time': self.get_play_time_history,
            'duration': self.get_duration_history,
            'time_actual_minutes': self.get_duration_history,  # Alias for duration
            'mental_energy_needed': self.get_mental_energy_needed_history,
            'task_difficulty': self.get_task_difficulty_history,
            'emotional_load': self.get_emotional_load_history,
            'environmental_fit': self.get_environmental_fit_history,
            'environmental_effect': self.get_environmental_fit_history,  # Alias for environmental_fit
        }
        
        if metric_key in metric_routes:
            # Get user_id for routing to specific methods
            user_id = self._get_user_id(None)
            # Route to specific method with user_id if it accepts it
            routed_method = metric_routes[metric_key]
            # Check if method accepts user_id parameter
            import inspect
            sig = inspect.signature(routed_method)
            if 'user_id' in sig.parameters:
                return routed_method(days=days, user_id=user_id)
            else:
                return routed_method(days=days)
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse completed_at dates
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract metric values from actual_dict or predicted_dict
        def _extract_metric_value(row):
            """Extract metric value from instance row."""
            try:
                # Try actual_dict first (for metrics like stress_level, net_wellbeing)
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, str):
                    import json
                    actual_dict = json.loads(actual_dict)
                
                if isinstance(actual_dict, dict):
                    value = actual_dict.get(metric_key)
                    if value is not None:
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            pass
                
                # Try predicted_dict as fallback
                predicted_dict = row.get('predicted_dict', {})
                if isinstance(predicted_dict, str):
                    import json
                    predicted_dict = json.loads(predicted_dict)
                
                if isinstance(predicted_dict, dict):
                    value = predicted_dict.get(metric_key)
                    if value is not None:
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass
            return None
        
        completed = completed.copy()
        completed['metric_value'] = completed.apply(_extract_metric_value, axis=1)
        
        # Filter to valid rows with metric values
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        daily_avg = daily_avg[daily_avg['date'] >= cutoff_date].copy()
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        
        # Weekly average (last 7 days)
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        
        # Three month average (last 90 days)
        three_month_average = sum(values) / len(values) if values else 0.0
        
        # #region agent log
        try:
            import json as json_module
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json_module.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'HIST', 'location': 'analytics.py:get_generic_metric_history', 'message': 'get_generic_metric_history completed', 'data': {'metric_key': metric_key, 'dates_count': len(dates), 'values_count': len(values), 'current_value': current_value}, 'timestamp': int(time_module.time() * 1000)}) + '\n')
        except: pass
        # #endregion
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_task_efficiency_history(self) -> Dict[str, float]:
        """Get average efficiency score per task based on completed instances.
        
        Returns {task_id: avg_efficiency_score}
        Useful for recommending tasks that have historically been efficient.
        """
        user_id = self._get_user_id(None)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {}
        
        # Calculate efficiency for each completed task
        completed['efficiency_score'] = completed.apply(self.calculate_efficiency_score, axis=1)
        
        # Filter to valid efficiency scores
        valid = completed[completed['efficiency_score'] > 0]
        
        if valid.empty:
            return {}
        
        # Group by task_id and calculate average efficiency
        task_efficiency = valid.groupby('task_id')['efficiency_score'].agg(['mean', 'count']).to_dict('index')
        
        # Convert to simpler format: {task_id: avg_efficiency}
        result = {}
        for tid, stats in task_efficiency.items():
            result[tid] = round(float(stats['mean']), 2)
        
        return result

    def get_execution_score_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily execution score data for trend analysis.
        
        Calculates execution_score for each completed instance and groups by date.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation. If None, uses current authenticated user.
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of scores per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        from collections import Counter
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        completed = completed[completed['completed_at_dt'] >= cutoff_date].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Calculate task completion counts for execution_score (optional but can help with difficulty)
        task_completion_counts = Counter(completed['task_id'].tolist())
        task_completion_counts_dict = dict(task_completion_counts)
        
        # Calculate execution_score for each instance
        completed = completed.copy()
        completed['execution_score'] = completed.apply(
            lambda row: self.calculate_execution_score(row, task_completion_counts_dict),
            axis=1
        )
        
        # Filter to valid scores
        valid = completed[completed['execution_score'].notna() & (completed['execution_score'] > 0)].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_avg = valid.groupby('date')['execution_score'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_grit_score_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily grit score data for trend analysis.
        
        Calculates grit_score for each completed instance and groups by date.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of scores per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        from collections import Counter
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        completed = completed[completed['completed_at_dt'] >= cutoff_date].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Calculate task completion counts (required for grit_score)
        task_completion_counts = Counter(completed['task_id'].tolist())
        task_completion_counts_dict = dict(task_completion_counts)
        
        # Calculate grit_score for each instance
        completed = completed.copy()
        completed['grit_score'] = completed.apply(
            lambda row: self.calculate_grit_score(row, task_completion_counts_dict),
            axis=1
        )
        
        # Filter to valid scores
        valid = completed[completed['grit_score'].notna() & (completed['grit_score'] > 0)].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        valid['date'] = valid['completed_at_dt'].dt.date
        daily_avg = valid.groupby('date')['grit_score'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_thoroughness_score_history(self, days: int = 90, window_days: int = 30) -> Dict[str, any]:
        """Get historical weekly thoroughness score data for trend analysis.
        
        Since thoroughness is a user-level metric (not per-instance), we calculate it
        weekly rather than daily to show trends over time.
        
        Args:
            days: Number of days to look back for history (default 90)
            window_days: Rolling window size for thoroughness calculation (default 30)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of scores per week),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        # Calculate current thoroughness_score
        current_score = self.calculate_thoroughness_score(user_id='default', days=window_days)
        
        # For user-level metrics, we return the current value for all dates
        # This shows the trend (the metric changes slowly over time)
        # Generate weekly dates for the period
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        dates = []
        values = []
        
        # Generate weekly data points
        current_date = start_date
        while current_date <= end_date:
            dates.append(str(current_date))
            # Use current value (thoroughness changes slowly, so this is reasonable)
            # In the future, we could calculate this based on data up to each date
            values.append(current_score)
            current_date += timedelta(days=7)  # Weekly intervals
        
        # Ensure we have the most recent date
        if dates and dates[-1] != str(end_date):
            dates.append(str(end_date))
            values.append(current_score)
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-4:] if len(values) >= 4 else values  # Last 4 weeks
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_thoroughness_factor_history(self, days: int = 90, window_days: int = 30) -> Dict[str, any]:
        """Get historical weekly thoroughness factor data for trend analysis.
        
        Since thoroughness is a user-level metric (not per-instance), we calculate it
        weekly rather than daily to show trends over time.
        
        Args:
            days: Number of days to look back for history (default 90)
            window_days: Rolling window size for thoroughness calculation (default 30)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of factors per week),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        # Calculate current thoroughness_factor
        current_factor = self.calculate_thoroughness_factor(user_id='default', days=window_days)
        
        # For user-level metrics, we return the current value for all dates
        # This shows the trend (the metric changes slowly over time)
        # Generate weekly dates for the period
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        dates = []
        values = []
        
        # Generate weekly data points
        current_date = start_date
        while current_date <= end_date:
            dates.append(str(current_date))
            # Use current value (thoroughness changes slowly, so this is reasonable)
            # In the future, we could calculate this based on data up to each date
            values.append(current_factor)
            current_date += timedelta(days=7)  # Weekly intervals
        
        # Ensure we have the most recent date
        if dates and dates[-1] != str(end_date):
            dates.append(str(end_date))
            values.append(current_factor)
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-4:] if len(values) >= 4 else values  # Last 4 weeks
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_stress_level_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily stress_level data for trend analysis.
        
        Optimized method that extracts stress_level directly from dataframe columns
        instead of parsing JSON, providing significant performance improvement.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty or 'stress_level' not in completed.columns:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract stress_level directly from dataframe (already calculated)
        completed['metric_value'] = pd.to_numeric(completed['stress_level'], errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_net_wellbeing_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily net_wellbeing data for trend analysis.
        
        Optimized method that extracts net_wellbeing directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty or 'net_wellbeing' not in completed.columns:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract net_wellbeing directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed['net_wellbeing'], errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_net_wellbeing_normalized_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily net_wellbeing_normalized data for trend analysis.
        
        Optimized method that extracts net_wellbeing_normalized directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty or 'net_wellbeing_normalized' not in completed.columns:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract net_wellbeing_normalized directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed['net_wellbeing_normalized'], errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_relief_score_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily relief_score data for trend analysis.
        
        Optimized method that extracts relief_score directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract relief_score - try relief_score_numeric first (calculated), then relief_score column
        if 'relief_score_numeric' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['relief_score_numeric'], errors='coerce')
        elif 'relief_score' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['relief_score'], errors='coerce')
        else:
            # Fallback: try to extract from actual_dict
            def _extract_relief(row):
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, str):
                        import json
                        actual_dict = json.loads(actual_dict)
                    if isinstance(actual_dict, dict):
                        return actual_dict.get('relief_score') or actual_dict.get('actual_relief')
                except:
                    pass
                return None
            completed['metric_value'] = completed.apply(_extract_relief, axis=1)
            completed['metric_value'] = pd.to_numeric(completed['metric_value'], errors='coerce')
        
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_behavioral_score_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily behavioral_score data for trend analysis.
        
        Optimized method that extracts behavioral_score directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty or 'behavioral_score' not in completed.columns:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract behavioral_score directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed['behavioral_score'], errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_stress_efficiency_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily stress_efficiency data for trend analysis.
        
        Optimized method that extracts stress_efficiency directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty or 'stress_efficiency' not in completed.columns:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract stress_efficiency directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed['stress_efficiency'], errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_expected_relief_history(self, days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get historical daily expected_relief data for trend analysis.
        
        Optimized method that extracts expected_relief directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            user_id: Optional user ID for data isolation
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(user_id)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty or 'expected_relief' not in completed.columns:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract expected_relief directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_net_relief_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily net_relief data for trend analysis.
        
        Optimized method that extracts net_relief directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract net_relief - try column first, then calculate from relief_score and expected_relief
        if 'net_relief' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['net_relief'], errors='coerce')
        else:
            # Calculate from relief_score_numeric and expected_relief
            relief_score = pd.to_numeric(completed.get('relief_score_numeric', completed.get('relief_score', 0)), errors='coerce').fillna(0.0)
            expected_relief = pd.to_numeric(completed.get('expected_relief', 0), errors='coerce').fillna(0.0)
            completed['metric_value'] = relief_score - expected_relief
        
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_serendipity_factor_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily serendipity_factor data for trend analysis.
        
        Optimized method that extracts serendipity_factor directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract serendipity_factor - try column first, then calculate from net_relief
        if 'serendipity_factor' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['serendipity_factor'], errors='coerce')
        else:
            # Calculate from net_relief (positive values only)
            net_relief = pd.to_numeric(completed.get('net_relief', 0), errors='coerce').fillna(0.0)
            completed['metric_value'] = net_relief.apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
        
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_disappointment_factor_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily disappointment_factor data for trend analysis.
        
        Optimized method that extracts disappointment_factor directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract disappointment_factor - try column first, then calculate from net_relief
        if 'disappointment_factor' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['disappointment_factor'], errors='coerce')
        else:
            # Calculate from net_relief (negative values only, made positive)
            net_relief = pd.to_numeric(completed.get('net_relief', 0), errors='coerce').fillna(0.0)
            completed['metric_value'] = net_relief.apply(lambda x: max(0.0, -float(x)) if pd.notna(x) else 0.0)
        
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_stress_relief_correlation_score_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily stress_relief_correlation_score data for trend analysis.
        
        Optimized method that extracts stress_relief_correlation_score directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract stress_relief_correlation_score - try column first, then calculate
        if 'stress_relief_correlation_score' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['stress_relief_correlation_score'], errors='coerce')
        else:
            # Calculate from stress_level and relief_score
            stress_norm = pd.to_numeric(completed.get('stress_level', 50), errors='coerce').fillna(50.0)
            relief_norm = pd.to_numeric(completed.get('relief_score_numeric', completed.get('relief_score', 50)), errors='coerce').fillna(50.0)
            correlation_raw = (relief_norm - stress_norm + 100.0) / 2.0
            completed['metric_value'] = correlation_raw.clip(0.0, 100.0).round(2)
        
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_work_time_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily work_time data for trend analysis.
        
        Calculates work_time by summing time_actual_minutes for Work and Self care tasks.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of minutes per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        user_id = self._get_user_id(user_id)
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Join instances with tasks to get task_type
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            completed_with_type = completed.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
            completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
            # Filter to only Work and Self care tasks (exclude Play)
            completed = completed_with_type[
                completed_with_type['task_type_normalized'].isin(['work', 'self care', 'selfcare', 'self-care'])
            ]
        
        # Extract time_actual_minutes from actual_dict
        def _get_time_actual(row):
            try:
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, str):
                    import json
                    actual_dict = json.loads(actual_dict)
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except:
                pass
            return None
        
        completed = completed.copy()
        completed['time_actual'] = completed.apply(_get_time_actual, axis=1)
        completed['time_actual'] = pd.to_numeric(completed['time_actual'], errors='coerce')
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows
        valid = completed[completed['time_actual'].notna() & completed['completed_at_dt'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and sum work time
        daily_sum = valid.groupby('date')['time_actual'].sum().reset_index()
        daily_sum.columns = ['date', 'total_minutes']
        daily_sum = daily_sum.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_sum['date'].tolist()]
        values = daily_sum['total_minutes'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_play_time_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily play_time data for trend analysis.
        
        Calculates play_time by summing time_actual_minutes for Play tasks.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of minutes per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        user_id = self._get_user_id(user_id)
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Join instances with tasks to get task_type
        if not tasks_df.empty and 'task_type' in tasks_df.columns:
            completed_with_type = completed.merge(
                tasks_df[['task_id', 'task_type']],
                on='task_id',
                how='left'
            )
            completed_with_type['task_type'] = completed_with_type['task_type'].fillna('Work')
            completed_with_type['task_type_normalized'] = completed_with_type['task_type'].astype(str).str.strip().str.lower()
            # Filter to only Play tasks
            completed = completed_with_type[
                completed_with_type['task_type_normalized'] == 'play'
            ]
        
        # Extract time_actual_minutes from actual_dict
        def _get_time_actual(row):
            try:
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, str):
                    import json
                    actual_dict = json.loads(actual_dict)
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except:
                pass
            return None
        
        completed = completed.copy()
        completed['time_actual'] = completed.apply(_get_time_actual, axis=1)
        completed['time_actual'] = pd.to_numeric(completed['time_actual'], errors='coerce')
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows
        valid = completed[completed['time_actual'].notna() & completed['completed_at_dt'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and sum play time
        daily_sum = valid.groupby('date')['time_actual'].sum().reset_index()
        daily_sum.columns = ['date', 'total_minutes']
        daily_sum = daily_sum.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_sum['date'].tolist()]
        values = daily_sum['total_minutes'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_duration_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily duration (time_actual_minutes) data for trend analysis.
        
        Extracts time_actual_minutes from actual_dict for all completed tasks.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of average minutes per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract time_actual_minutes from actual_dict
        def _get_time_actual(row):
            try:
                actual_dict = row.get('actual_dict', {})
                if isinstance(actual_dict, str):
                    import json
                    actual_dict = json.loads(actual_dict)
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except:
                pass
            return None
        
        completed = completed.copy()
        completed['time_actual'] = completed.apply(_get_time_actual, axis=1)
        completed['time_actual'] = pd.to_numeric(completed['time_actual'], errors='coerce')
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Filter to valid rows
        valid = completed[completed['time_actual'].notna() & completed['completed_at_dt'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['time_actual'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_mental_energy_needed_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily mental_energy_needed data for trend analysis.
        
        Optimized method that extracts mental_energy_needed directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract mental_energy_needed directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed.get('mental_energy_needed', completed.get('mental_energy_numeric')), errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_task_difficulty_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily task_difficulty data for trend analysis.
        
        Optimized method that extracts task_difficulty directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract task_difficulty directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed.get('task_difficulty', completed.get('task_difficulty_numeric')), errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_emotional_load_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily emotional_load data for trend analysis.
        
        Optimized method that extracts emotional_load directly from dataframe columns.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract emotional_load directly from dataframe
        completed['metric_value'] = pd.to_numeric(completed.get('emotional_load', completed.get('emotional_load_numeric')), errors='coerce')
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }
    
    def get_environmental_fit_history(self, days: int = 90) -> Dict[str, any]:
        """Get historical daily environmental_fit data for trend analysis.
        
        Optimized method that extracts environmental_fit (or environmental_effect) from dataframe.
        
        Args:
            days: Number of days to look back (default 90)
            
        Returns:
            Dict with 'dates' (list of date strings), 'values' (list of values per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        from datetime import datetime, timedelta
        
        user_id = self._get_user_id(None)
        df = self._load_instances(completed_only=True, user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Parse dates and filter
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()].copy()
        
        if completed.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Extract environmental_fit or environmental_effect from dataframe
        # Try both column names for compatibility
        if 'environmental_fit' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['environmental_fit'], errors='coerce')
        elif 'environmental_effect' in completed.columns:
            completed['metric_value'] = pd.to_numeric(completed['environmental_effect'], errors='coerce')
        else:
            # Try to extract from actual_dict
            def _extract_env_fit(row):
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, str):
                        import json
                        actual_dict = json.loads(actual_dict)
                    if isinstance(actual_dict, dict):
                        return actual_dict.get('environmental_fit') or actual_dict.get('environmental_effect')
                except:
                    pass
                return None
            completed['metric_value'] = completed.apply(_extract_env_fit, axis=1)
            completed['metric_value'] = pd.to_numeric(completed['metric_value'], errors='coerce')
        
        valid = completed[completed['metric_value'].notna()].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now().date() - timedelta(days=days)
        valid['date'] = valid['completed_at_dt'].dt.date
        valid = valid[valid['date'] >= cutoff_date].copy()
        
        if valid.empty:
            return {
                'dates': [],
                'values': [],
                'current_value': 0.0,
                'weekly_average': 0.0,
                'three_month_average': 0.0,
            }
        
        # Group by date and calculate daily averages
        daily_avg = valid.groupby('date')['metric_value'].mean().reset_index()
        daily_avg.columns = ['date', 'avg_value']
        daily_avg = daily_avg.sort_values('date')
        
        # Convert to lists
        dates = [str(d) for d in daily_avg['date'].tolist()]
        values = daily_avg['avg_value'].tolist()
        
        # Calculate averages
        current_value = values[-1] if values else 0.0
        weekly_values = values[-7:] if len(values) >= 7 else values
        weekly_average = sum(weekly_values) / len(weekly_values) if weekly_values else 0.0
        three_month_average = sum(values) / len(values) if values else 0.0
        
        return {
            'dates': dates,
            'values': values,
            'current_value': current_value,
            'weekly_average': weekly_average,
            'three_month_average': three_month_average,
        }

    def get_task_performance_ranking(self, metric: str = 'relief', top_n: int = 5, user_id: Optional[int] = None) -> List[Dict[str, any]]:
        """Get top/bottom performing tasks by various metrics.
        
        Args:
            metric: 'relief', 'stress_efficiency', 'behavioral_score', 'stress_level'
            top_n: Number of top tasks to return
            user_id: User ID for data isolation
        
        Returns:
            List of dicts with task_id, task_name, metric_value, and count
        """
        import time
        import copy
        start = time.perf_counter()
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Check cache (keyed by metric, top_n, and user_id)
        # TODO: Make cache user-specific
        cache_key = (metric, top_n)
        current_time = time.time()
        if (user_id is None and cache_key in self._rankings_cache):
            cached_result, cached_time = self._rankings_cache[cache_key]
            if cached_time is not None and (current_time - cached_time) < self._cache_ttl_seconds:
                duration = (time.perf_counter() - start) * 1000
                print(f"[Analytics] get_task_performance_ranking (cached): {duration:.2f}ms (metric: {metric}, top_n: {top_n})")
                return copy.deepcopy(cached_result)
        df = self._load_instances(user_id=user_id)
        
        # Filter completed instances - check for column existence and use fallback if needed
        if 'completed_at' in df.columns:
            completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        elif 'status' in df.columns:
            completed = df[df['status'] == 'completed'].copy()
        elif 'is_completed' in df.columns:
            completed = df[df['is_completed'] == True].copy()
        else:
            # No way to determine completion - return empty result
            result = []
            self._rankings_cache[cache_key] = (result, time.time())
            return result
        
        if completed.empty:
            result = []
            self._rankings_cache[cache_key] = (result, time.time())
            return result
        
        # Map metric names to columns
        metric_map = {
            'relief': 'relief_score',
            'stress_efficiency': 'stress_efficiency',
            'behavioral_score': 'behavioral_score',
            'stress_level': 'stress_level',
        }
        
        if metric not in metric_map:
            metric = 'relief'
        
        column = metric_map[metric]
        
        # Group by task_id and calculate averages
        task_stats = completed.groupby('task_id').agg({
            column: ['mean', 'count'],
            'task_name': 'first'
        }).reset_index()
        
        task_stats.columns = ['task_id', 'metric_value', 'count', 'task_name']
        
        # Filter out tasks with no valid data
        task_stats = task_stats[task_stats['metric_value'].notna()]
        
        if task_stats.empty:
            result = []
            self._rankings_cache[cache_key] = (result, time.time())
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_task_performance_ranking: {duration:.2f}ms (no data, metric: {metric})")
            return result
        
        # Sort appropriately (higher is better for relief, stress_efficiency, behavioral_score; lower is better for stress_level)
        ascending = (metric == 'stress_level')
        task_stats = task_stats.sort_values('metric_value', ascending=ascending)
        
        # Get top N
        top_tasks = task_stats.head(top_n)
        
        result = []
        for _, row in top_tasks.iterrows():
            result.append({
                'task_id': row['task_id'],
                'task_name': row['task_name'],
                'metric_value': round(float(row['metric_value']), 2),
                'count': int(row['count']),
                'metric': metric,
            })
        
        # Store in cache
        self._rankings_cache[cache_key] = (copy.deepcopy(result), time.time())
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_task_performance_ranking: {duration:.2f}ms (metric: {metric}, top_n: {top_n})")
        return result

    def get_stress_efficiency_leaderboard(self, top_n: int = 10, user_id: Optional[int] = None) -> List[Dict[str, any]]:
        """Get tasks with highest stress efficiency (relief per unit of stress).
        
        Args:
            top_n: Number of top tasks to return
            user_id: Optional user ID for data isolation
        
        Returns:
            List of dicts with task_id, task_name, stress_efficiency, avg_relief, avg_stress, and count
        """
        import time
        start = time.perf_counter()
        
        user_id = self._get_user_id(user_id)
        
        # Check cache (keyed by user_id)
        cache_key = user_id if user_id is not None else "default"
        current_time = time.time()
        if (cache_key in self._leaderboard_cache and 
            cache_key in self._leaderboard_cache_time and
            cache_key in self._leaderboard_cache_top_n and
            self._leaderboard_cache_top_n[cache_key] == top_n and
            (current_time - self._leaderboard_cache_time[cache_key]) < self._cache_ttl_seconds):
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_efficiency_leaderboard (cached): {duration:.2f}ms (top_n: {top_n})")
            return copy.deepcopy(self._leaderboard_cache[cache_key])
        
        df = self._load_instances(user_id=user_id)
        
        # Check if DataFrame is empty or missing required columns
        if df.empty or 'completed_at' not in df.columns:
            result = []
            self._leaderboard_cache[cache_key] = result
            self._leaderboard_cache_time[cache_key] = time.time()
            self._leaderboard_cache_top_n[cache_key] = top_n
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_efficiency_leaderboard: {duration:.2f}ms (no data)")
            return result
        
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            result = []
            self._leaderboard_cache[cache_key] = result
            self._leaderboard_cache_time[cache_key] = time.time()
            self._leaderboard_cache_top_n[cache_key] = top_n
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_efficiency_leaderboard: {duration:.2f}ms (no data)")
            return result
        
        # Filter to tasks with valid stress efficiency
        valid = completed[completed['stress_efficiency'].notna() & (completed['stress_efficiency'] > 0)].copy()
        
        if valid.empty:
            result = []
            self._leaderboard_cache[cache_key] = result
            self._leaderboard_cache_time[cache_key] = time.time()
            self._leaderboard_cache_top_n[cache_key] = top_n
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_efficiency_leaderboard: {duration:.2f}ms (no valid data)")
            return result
        
        # Group by task_id and calculate averages
        task_stats = valid.groupby('task_id').agg({
            'stress_efficiency': 'mean',
            'relief_score': 'mean',
            'stress_level': 'mean',
            'task_name': 'first'
        }).reset_index()
        
        task_stats.columns = ['task_id', 'avg_stress_efficiency', 'avg_relief', 'avg_stress', 'task_name']
        
        # Add count
        task_counts = valid.groupby('task_id').size().reset_index(name='count')
        task_stats = task_stats.merge(task_counts, on='task_id')
        
        # Sort by stress efficiency (descending)
        task_stats = task_stats.sort_values('avg_stress_efficiency', ascending=False)
        
        # Get top N
        top_tasks = task_stats.head(top_n)
        
        result = []
        for _, row in top_tasks.iterrows():
            result.append({
                'task_id': row['task_id'],
                'task_name': row['task_name'],
                'stress_efficiency': round(float(row['avg_stress_efficiency']), 2),
                'avg_relief': round(float(row['avg_relief']), 2),
                'avg_stress': round(float(row['avg_stress']), 2),
                'count': int(row['count']),
            })
        
        # Store in cache
        self._leaderboard_cache[cache_key] = copy.deepcopy(result)
        self._leaderboard_cache_time[cache_key] = time.time()
        self._leaderboard_cache_top_n[cache_key] = top_n
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_stress_efficiency_leaderboard: {duration:.2f}ms (top_n: {top_n})")
        return result

    # ------------------------------------------------------------------
    # Recommendation helpers
    # ------------------------------------------------------------------
    def default_filters(self) -> Dict[str, Optional[float]]:
        return {
            'max_duration': None,
            'min_duration': None,
            'task_type': None,
            'is_recurring': None,
            'categories': None,
        }

    def available_filters(self) -> List[Dict[str, str]]:
        return [
            {'key': 'max_duration', 'label': 'Max Duration (minutes)'},
            {'key': 'min_duration', 'label': 'Min Duration (minutes)'},
            {'key': 'task_type', 'label': 'Task Type'},
            {'key': 'is_recurring', 'label': 'Recurring'},
            {'key': 'categories', 'label': 'Categories'},
        ]

    def recommendations(self, filters: Optional[Dict[str, float]] = None, user_id: Optional[int] = None) -> List[Dict[str, str]]:
        """Generate recommendations based on all task templates, using historical data from completed instances."""
        from .task_manager import TaskManager
        
        filters = {**self.default_filters(), **(filters or {})}
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Load all task templates
        task_manager = TaskManager()
        all_tasks_df = task_manager.get_all(user_id=user_id)
        if all_tasks_df.empty:
            return []
        
        # Load historical instance data to inform recommendations
        instances_df = self._load_instances(user_id=user_id)
        
        # Get historical averages per task from completed instances
        completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy() if not instances_df.empty else pd.DataFrame()
        
        # Calculate historical averages per task_id
        task_stats = {}
        if not completed.empty:
            # Group by task_id and calculate averages
            for task_id in completed['task_id'].unique():
                task_completed = completed[completed['task_id'] == task_id]
                if not task_completed.empty:
                    # Convert columns to numeric before calculating means
                    relief_series = pd.to_numeric(task_completed['relief_score'], errors='coerce')
                    cognitive_series = pd.to_numeric(task_completed['cognitive_load'], errors='coerce')
                    emotional_series = pd.to_numeric(task_completed['emotional_load'], errors='coerce')
                    duration_series = pd.to_numeric(task_completed['duration_minutes'], errors='coerce')
                    
                    task_stats[task_id] = {
                        'avg_relief': relief_series.mean() if relief_series.notna().any() else None,
                        'avg_cognitive_load': cognitive_series.mean() if cognitive_series.notna().any() else None,
                        'avg_emotional_load': emotional_series.mean() if emotional_series.notna().any() else None,
                        'avg_duration': duration_series.mean() if duration_series.notna().any() else None,
                        'count': len(task_completed),
                    }
        
        # Get task efficiency history
        task_efficiency = self.get_task_efficiency_history()
        
        # Build recommendation candidates from all task templates
        candidates = []
        max_duration_filter = None
        if filters.get('max_duration'):
            try:
                max_duration_filter = float(filters['max_duration'])
            except (ValueError, TypeError):
                max_duration_filter = None
        
        for _, task_row in all_tasks_df.iterrows():
            task_id = task_row['task_id']
            task_name = task_row['name']
            default_estimate = task_row.get('default_estimate_minutes', 0)
            
            try:
                default_estimate = float(default_estimate) if default_estimate else 0
            except (ValueError, TypeError):
                default_estimate = 0
            
            # Get historical stats for this task
            stats = task_stats.get(task_id, {})
            avg_relief = stats.get('avg_relief') if stats.get('avg_relief') is not None else None
            avg_cognitive = stats.get('avg_cognitive_load') if stats.get('avg_cognitive_load') is not None else None
            avg_emotional = stats.get('avg_emotional_load') if stats.get('avg_emotional_load') is not None else None
            avg_duration = stats.get('avg_duration') if stats.get('avg_duration') is not None else default_estimate
            historical_efficiency = task_efficiency.get(task_id, 0)
            
            # Use historical data if available, otherwise use defaults
            relief_score = avg_relief if avg_relief is not None else 5.0  # Default neutral
            cognitive_load = avg_cognitive if avg_cognitive is not None else 5.0  # Default neutral
            emotional_load = avg_emotional if avg_emotional is not None else 5.0  # Default neutral
            duration_minutes = avg_duration if avg_duration else default_estimate
            
            # Apply max_duration filter after calculating duration_minutes
            # Use the duration_minutes (which includes historical average if available)
            if max_duration_filter is not None:
                # Filter out tasks that exceed the max duration
                # Note: tasks with 0 duration (unknown) will pass the filter
                if duration_minutes > max_duration_filter:
                    continue
            
            candidates.append({
                'task_id': task_id,
                'task_name': task_name,
                'relief_score': relief_score,
                'cognitive_load': cognitive_load,
                'emotional_load': emotional_load,
                'duration_minutes': duration_minutes,
                'historical_efficiency': historical_efficiency,
                'default_estimate': default_estimate,
            })
        
        if not candidates:
            return []
        
        candidates_df = pd.DataFrame(candidates)
        
        ranked = []
        
        # Always include highest relief pick
        row = candidates_df.sort_values('relief_score', ascending=False).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Highest Relief"))
        
        # Always include shortest task pick
        row = candidates_df.sort_values('duration_minutes', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Shortest Task"))
        
        # Always include lowest cognitive load pick
        row = candidates_df.sort_values('cognitive_load', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Cognitive Load"))
        
        # Always include lowest emotional load pick
        row = candidates_df.sort_values('emotional_load', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Emotional Load"))
        
        # Always include lowest net load pick (cognitive + emotional)
        candidates_df['net_load'] = candidates_df['cognitive_load'] + candidates_df['emotional_load']
        row = candidates_df.sort_values('net_load', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Net Load"))
        
        # Always include net relief picks for variety
        candidates_df['net_relief_proxy'] = candidates_df['relief_score'] - candidates_df['cognitive_load']
        # Highest Net Relief
        row = candidates_df.sort_values('net_relief_proxy', ascending=False).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Highest Net Relief"))
        # Lowest Net Relief (for comparison)
        row = candidates_df.sort_values('net_relief_proxy', ascending=True).head(1)
        if not row.empty:
            ranked.append(self._task_to_recommendation(row.iloc[0], "Lowest Net Relief"))
        
        # Always include efficiency-based pick if we have efficiency data
        high_eff = candidates_df[candidates_df['historical_efficiency'] > 0]
        if not high_eff.empty:
            row = high_eff.sort_values('historical_efficiency', ascending=False).head(1)
            if not row.empty:
                ranked.append(self._task_to_recommendation(row.iloc[0], "High Efficiency Candidate"))
        
        return [r for r in ranked if r]

    def recommendations_by_category(self, metrics: Union[str, List[str]], filters: Optional[Dict[str, float]] = None, limit: int = 3, user_id: Optional[int] = None) -> List[Dict[str, str]]:
        """Generate recommendations ranked by a set of metrics.

        metrics can be a single metric name or a list. Each metric contributes to
        the score; high-is-good metrics add their value, and low-is-good metrics
        add (100 - value) to prioritize lower numbers.
        """
        from .task_manager import TaskManager
        from .recommendation_logger import recommendation_logger
        
        filters = {**self.default_filters(), **(filters or {})}
        
        # Normalize metrics input
        if metrics is None:
            metrics = []
        if isinstance(metrics, str):
            metrics = [metrics]
        metrics = [m for m in metrics if m] or ["relief_score"]
        
        # Which metrics are better when low
        low_is_good = {
            "cognitive_load",
            "emotional_load",
            "net_load",
            "duration_minutes",
            "stress_level",
            "physical_load",
        }
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Load all task templates
        task_manager = TaskManager()
        all_tasks_df = task_manager.get_all(user_id=user_id)
        if all_tasks_df.empty:
            return []
        
        # Load historical instance data to inform recommendations
        instances_df = self._load_instances(user_id=user_id)
        
        # Get historical averages per task from completed instances
        completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy() if not instances_df.empty else pd.DataFrame()
        
        # Calculate historical averages per task_id
        task_stats = {}
        if not completed.empty:
            # Group by task_id and calculate averages
            for task_id in completed['task_id'].unique():
                task_completed = completed[completed['task_id'] == task_id]
                if not task_completed.empty:
                    # Convert columns to numeric before calculating means
                    relief_series = pd.to_numeric(task_completed['relief_score'], errors='coerce')
                    cognitive_series = pd.to_numeric(task_completed['cognitive_load'], errors='coerce')
                    emotional_series = pd.to_numeric(task_completed['emotional_load'], errors='coerce')
                    duration_series = pd.to_numeric(task_completed['duration_minutes'], errors='coerce')
                    
                    task_stats[task_id] = {
                        'avg_relief': relief_series.mean() if relief_series.notna().any() else None,
                        'avg_cognitive_load': cognitive_series.mean() if cognitive_series.notna().any() else None,
                        'avg_emotional_load': emotional_series.mean() if emotional_series.notna().any() else None,
                        'avg_duration': duration_series.mean() if duration_series.notna().any() else None,
                        'avg_stress_level': pd.to_numeric(task_completed['stress_level'], errors='coerce').mean() if 'stress_level' in task_completed and task_completed['stress_level'].notna().any() else None,
                        'avg_behavioral_score': pd.to_numeric(task_completed['behavioral_score'], errors='coerce').mean() if 'behavioral_score' in task_completed and task_completed['behavioral_score'].notna().any() else None,
                        'avg_net_wellbeing': pd.to_numeric(task_completed['net_wellbeing_normalized'], errors='coerce').mean() if 'net_wellbeing_normalized' in task_completed and task_completed['net_wellbeing_normalized'].notna().any() else None,
                        'avg_physical_load': pd.to_numeric(task_completed['physical_load'], errors='coerce').mean() if 'physical_load' in task_completed and task_completed['physical_load'].notna().any() else None,
                        'count': len(task_completed),
                    }
        
        # Get task efficiency history
        task_efficiency = self.get_task_efficiency_history()
        
        # Build recommendation candidates from all task templates
        candidates = []
        
        # Parse filters
        max_duration_filter = None
        if filters.get('max_duration'):
            try:
                max_duration_filter = float(filters['max_duration'])
            except (ValueError, TypeError):
                max_duration_filter = None
        
        min_duration_filter = None
        if filters.get('min_duration'):
            try:
                min_duration_filter = float(filters['min_duration'])
            except (ValueError, TypeError):
                min_duration_filter = None
        
        task_type_filter = filters.get('task_type')
        is_recurring_filter = filters.get('is_recurring')
        categories_filter = filters.get('categories')
        
        for _, task_row in all_tasks_df.iterrows():
            task_id = task_row['task_id']
            task_name = task_row['name']
            default_estimate = task_row.get('default_estimate_minutes', 0)
            task_type = task_row.get('task_type', '')
            is_recurring = task_row.get('is_recurring', 'False')
            categories_str = task_row.get('categories', '[]')
            
            # Apply task_type filter
            if task_type_filter:
                if str(task_type).strip() != str(task_type_filter).strip():
                    continue
            
            # Apply is_recurring filter
            if is_recurring_filter:
                is_recurring_str = str(is_recurring).strip().lower()
                filter_str = str(is_recurring_filter).strip().lower()
                if filter_str == 'true' and is_recurring_str != 'true':
                    continue
                elif filter_str == 'false' and is_recurring_str == 'true':
                    continue
            
            # Apply categories filter (search in categories JSON)
            if categories_filter:
                categories_query = str(categories_filter).strip().lower()
                if categories_query:
                    try:
                        import json
                        categories_list = json.loads(categories_str) if categories_str else []
                        if not isinstance(categories_list, list):
                            categories_list = []
                        # Check if any category matches the search query
                        categories_match = any(
                            categories_query in str(cat).lower() 
                            for cat in categories_list
                        )
                        if not categories_match:
                            continue
                    except (json.JSONDecodeError, Exception):
                        # If categories can't be parsed, skip this filter
                        pass
            
            try:
                default_estimate = float(default_estimate) if default_estimate else 0
            except (ValueError, TypeError):
                default_estimate = 0
            
            # Get historical stats for this task
            stats = task_stats.get(task_id, {})
            avg_relief = stats.get('avg_relief') if stats.get('avg_relief') is not None else None
            avg_cognitive = stats.get('avg_cognitive_load') if stats.get('avg_cognitive_load') is not None else None
            avg_emotional = stats.get('avg_emotional_load') if stats.get('avg_emotional_load') is not None else None
            avg_duration = stats.get('avg_duration') if stats.get('avg_duration') is not None else default_estimate
            historical_efficiency = task_efficiency.get(task_id, 0)
            avg_stress = stats.get('avg_stress_level') if stats.get('avg_stress_level') is not None else None
            avg_behavioral = stats.get('avg_behavioral_score') if stats.get('avg_behavioral_score') is not None else None
            avg_net_wellbeing = stats.get('avg_net_wellbeing') if stats.get('avg_net_wellbeing') is not None else None
            avg_physical = stats.get('avg_physical_load') if stats.get('avg_physical_load') is not None else None
            
            # Use historical data if available, otherwise use defaults
            relief_score = avg_relief if avg_relief is not None else 5.0  # Default neutral
            cognitive_load = avg_cognitive if avg_cognitive is not None else 5.0  # Default neutral
            emotional_load = avg_emotional if avg_emotional is not None else 5.0  # Default neutral
            stress_level = avg_stress if avg_stress is not None else 50.0  # Neutral midpoint
            behavioral_score = avg_behavioral if avg_behavioral is not None else 50.0  # Neutral adherence
            net_wellbeing = avg_net_wellbeing if avg_net_wellbeing is not None else 50.0  # Neutral wellbeing (normalized)
            physical_load = avg_physical if avg_physical is not None else 0.0  # Default minimal physical load
            duration_minutes = avg_duration if avg_duration else default_estimate
            
            # Apply duration filters
            if max_duration_filter is not None:
                if duration_minutes > max_duration_filter:
                    continue
            if min_duration_filter is not None:
                if duration_minutes < min_duration_filter:
                    continue
            
            candidates.append({
                'task_id': task_id,
                'task_name': task_name,
                'relief_score': relief_score,
                'cognitive_load': cognitive_load,
                'emotional_load': emotional_load,
                'duration_minutes': duration_minutes,
                'historical_efficiency': historical_efficiency,
                'default_estimate': default_estimate,
                'stress_level': stress_level,
                'behavioral_score': behavioral_score,
                'net_wellbeing_normalized': net_wellbeing,
                'physical_load': physical_load,
            })
        
        if not candidates:
            return []
        
        candidates_df = pd.DataFrame(candidates)
        
        # Calculate derived metrics
        candidates_df['net_load'] = candidates_df['cognitive_load'] + candidates_df['emotional_load']
        candidates_df['net_relief_proxy'] = candidates_df['relief_score'] - candidates_df['cognitive_load']
        
        # Scoring helper: high-good adds value; low-good adds (100 - value)
        def metric_score(metric_name: str, value: float) -> float:
            try:
                v = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                v = 0.0
            if metric_name in low_is_good:
                return max(0.0, 100.0 - v)
            return v
        
        # Compute score per task
        scores = []
        for _, row in candidates_df.iterrows():
            score_total = 0.0
            for metric in metrics:
                score_total += metric_score(metric, row.get(metric))
            scores.append(score_total)
        candidates_df['score'] = scores
        
        # Normalize scores to 0-100 range
        # Use absolute normalization based on max possible score, not relative to candidates
        # This ensures meaningful scores even with only one candidate
        if len(scores) > 0:
            num_metrics = len(metrics) if metrics else 1
            max_possible_score = num_metrics * 100.0  # Each metric can contribute up to 100
            
            if max_possible_score > 0:
                # Normalize: (score / max_possible) * 100
                candidates_df['score_normalized'] = (candidates_df['score'] / max_possible_score) * 100.0
                # Clamp to 0-100 range
                candidates_df['score_normalized'] = candidates_df['score_normalized'].clip(0.0, 100.0)
            else:
                candidates_df['score_normalized'] = 50.0
        else:
            candidates_df['score_normalized'] = 50.0
        
        # Sort by score descending and take top N
        top_n = candidates_df.sort_values('score', ascending=False).head(limit)
        
        ranked = []
        for idx, (_, row) in enumerate(top_n.iterrows()):
            # Collect only the metrics the user selected
            metric_values = {}
            for metric in metrics:
                try:
                    metric_values[metric] = float(row.get(metric)) if row.get(metric) is not None else None
                except (ValueError, TypeError):
                    metric_values[metric] = None
            
            ranked.append({
                'title': "Recommendation",
                'task_id': row.get('task_id'),
                'task_name': row.get('task_name'),
                'description': row.get('description', '') if 'description' in row else '',
                'score': round(float(row.get('score_normalized', 0.0)), 1),
                'metric_values': metric_values,
                # Include all sub-scores for tooltip
                'sub_scores': {
                    'relief_score': row.get('relief_score'),
                    'cognitive_load': row.get('cognitive_load'),
                    'emotional_load': row.get('emotional_load'),
                    'physical_load': row.get('physical_load'),
                    'stress_level': row.get('stress_level'),
                    'behavioral_score': row.get('behavioral_score'),
                    'net_wellbeing_normalized': row.get('net_wellbeing_normalized'),
                    'net_load': row.get('net_load'),
                    'net_relief_proxy': row.get('net_relief_proxy'),
                    'mental_energy_needed': row.get('mental_energy_needed'),
                    'task_difficulty': row.get('task_difficulty'),
                    'historical_efficiency': row.get('historical_efficiency'),
                    'duration_minutes': row.get('duration_minutes'),
                },
                'duration': row.get('duration_minutes'),
                'relief': row.get('relief_score'),
                'cognitive_load': row.get('cognitive_load'),
                'emotional_load': row.get('emotional_load'),
            })
        
        # Log recommendation generation
        try:
            from .recommendation_logger import recommendation_logger
            metric_list = metrics if isinstance(metrics, list) else [metrics] if metrics else []
            recommendation_logger.log_recommendation_generated(
                mode='templates',
                metrics=metric_list,
                filters=filters,
                recommendations=ranked
            )
        except Exception as e:
            # Don't fail if logging fails
            import warnings
            warnings.warn(f"Failed to log recommendations: {e}")
        
        return ranked

    def recommendations_from_instances(self, metrics: Union[str, List[str]], filters: Optional[Dict[str, float]] = None, limit: int = 3, user_id: Optional[int] = None) -> List[Dict[str, str]]:
        """Generate recommendations from initialized (non-completed) task instances.
        
        Similar to recommendations_by_category but works with active instances instead of templates.
        
        Args:
            metrics: Single metric name or list of metrics to rank by
            filters: Optional filters (min_duration, max_duration, task_type, etc.)
            limit: Maximum number of recommendations to return
            user_id: User ID for data isolation (required)
        
        Returns:
            List of recommendation dicts with instance_id, task_name, score, and metric_values
        """
        from .instance_manager import InstanceManager
        
        filters = {**self.default_filters(), **(filters or {})}
        
        # Normalize metrics input
        if metrics is None:
            metrics = []
        if isinstance(metrics, str):
            metrics = [metrics]
        metrics = [m for m in metrics if m] or ["relief_score"]
        
        # Which metrics are better when low
        low_is_good = {
            "cognitive_load",
            "emotional_load",
            "net_load",
            "duration_minutes",
            "stress_level",
            "physical_load",
        }
        
        # Get user_id if not provided
        if user_id is None:
            user_id = self._get_user_id(user_id)
        
        # Get all active (non-completed) instances
        instance_manager = InstanceManager()
        active_instances = instance_manager.list_active_instances(user_id=user_id)
        
        if not active_instances:
            return []
        
        # Load task templates to get task metadata
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        # Parse filters
        max_duration_filter = None
        if filters.get('max_duration'):
            try:
                max_duration_filter = float(filters['max_duration'])
            except (ValueError, TypeError):
                max_duration_filter = None
        
        min_duration_filter = None
        if filters.get('min_duration'):
            try:
                min_duration_filter = float(filters['min_duration'])
            except (ValueError, TypeError):
                min_duration_filter = None
        
        task_type_filter = filters.get('task_type')
        is_recurring_filter = filters.get('is_recurring')
        categories_filter = filters.get('categories')
        
        # Load historical instance data to get averages for relief_score fallback
        instances_df = self._load_instances(user_id=user_id)
        completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy() if not instances_df.empty else pd.DataFrame()
        
        # Calculate historical averages per task_id (for relief_score fallback)
        task_stats = {}
        if not completed.empty:
            for task_id in completed['task_id'].unique():
                task_completed = completed[completed['task_id'] == task_id]
                if not task_completed.empty:
                    relief_series = pd.to_numeric(task_completed['relief_score'], errors='coerce')
                    task_stats[task_id] = {
                        'avg_relief': relief_series.mean() if relief_series.notna().any() else None,
                    }
        
        # Build recommendation candidates from active instances
        candidates = []
        
        for instance in active_instances:
            instance_id = instance.get('instance_id')
            task_id = instance.get('task_id')
            task_name = instance.get('task_name', '')
            
            # Get task template info for filtering
            task_info = None
            if not tasks_df.empty and task_id:
                task_rows = tasks_df[tasks_df['task_id'] == task_id]
                if not task_rows.empty:
                    task_info = task_rows.iloc[0].to_dict()
            
            # Apply task_type filter
            if task_type_filter and task_info:
                task_type = task_info.get('task_type', '')
                if str(task_type).strip() != str(task_type_filter).strip():
                    continue
            
            # Apply is_recurring filter
            if is_recurring_filter and task_info:
                is_recurring = task_info.get('is_recurring', 'False')
                is_recurring_str = str(is_recurring).strip().lower()
                filter_str = str(is_recurring_filter).strip().lower()
                if filter_str == 'true' and is_recurring_str != 'true':
                    continue
                elif filter_str == 'false' and is_recurring_str == 'true':
                    continue
            
            # Apply categories filter
            if categories_filter and task_info:
                categories_query = str(categories_filter).strip().lower()
                if categories_query:
                    try:
                        import json
                        categories_str = task_info.get('categories', '[]')
                        categories_list = json.loads(categories_str) if categories_str else []
                        if not isinstance(categories_list, list):
                            categories_list = []
                        categories_match = any(
                            categories_query in str(cat).lower() 
                            for cat in categories_list
                        )
                        if not categories_match:
                            continue
                    except (json.JSONDecodeError, Exception):
                        pass
            
            # Extract predicted data from instance (initialization values)
            predicted_str = instance.get('predicted', '{}')
            try:
                import json
                predicted = json.loads(predicted_str) if predicted_str else {}
            except (json.JSONDecodeError, TypeError):
                predicted = {}
            
            # Get task template defaults as backup
            default_estimate = 0.0
            if task_info:
                default_estimate = float(task_info.get('default_estimate_minutes', 0) or 0)
            
            # Helper function to get value with fallback chain: predicted -> task default -> system default
            def get_value(predicted_key, task_default_key=None, system_default=50.0):
                """Get value from predicted, fallback to task default, then system default."""
                # First try predicted field
                if predicted_key in predicted and predicted[predicted_key] is not None:
                    try:
                        return float(predicted[predicted_key])
                    except (ValueError, TypeError):
                        pass
                
                # Then try task template default
                if task_default_key and task_info:
                    task_val = task_info.get(task_default_key)
                    if task_val is not None and task_val != '':
                        try:
                            return float(task_val)
                        except (ValueError, TypeError):
                            pass
                
                # Finally use system default
                return system_default
            
            # Extract values from initialization (predicted field) with fallbacks
            # Duration: time_estimate_minutes from predicted, or task default_estimate_minutes
            duration_minutes = get_value('time_estimate_minutes', 'default_estimate_minutes', 0.0)
            if duration_minutes == 0.0 and default_estimate > 0:
                duration_minutes = default_estimate
            
            # Mental energy and difficulty (used to calculate cognitive_load)
            # First try to get them directly
            expected_mental_energy = get_value('expected_mental_energy', None, None)
            expected_difficulty = get_value('expected_difficulty', None, None)
            
            # If either is missing, try to get from expected_cognitive_load (backward compatibility)
            expected_cognitive_load = get_value('expected_cognitive_load', None, None)
            if expected_cognitive_load is not None:
                # If we have cognitive_load but not the individual components, use it for both
                if expected_mental_energy is None:
                    expected_mental_energy = expected_cognitive_load
                if expected_difficulty is None:
                    expected_difficulty = expected_cognitive_load
            
            # Fallback to defaults if still None
            if expected_mental_energy is None:
                expected_mental_energy = 50.0
            if expected_difficulty is None:
                expected_difficulty = 50.0
            
            # Cognitive load: use expected_cognitive_load if available, otherwise calculate from components
            if expected_cognitive_load is not None:
                cognitive_load = expected_cognitive_load
            else:
                # Calculate from mental_energy and difficulty (average)
                cognitive_load = (expected_mental_energy + expected_difficulty) / 2.0
            
            # Emotional load: from expected_emotional_load
            emotional_load = get_value('expected_emotional_load', None, 50.0)
            
            # Physical load: from expected_physical_load
            physical_load = get_value('expected_physical_load', None, 0.0)
            
            # Relief score: from expected_relief, or use historical average if available
            expected_relief = get_value('expected_relief', None, None)
            if expected_relief is not None:
                relief_score = expected_relief
            else:
                # Try to get historical average for this task from completed instances
                stats = task_stats.get(task_id, {}) if task_id else {}
                avg_relief = stats.get('avg_relief')
                relief_score = avg_relief if avg_relief is not None else 50.0
            
            # Expected aversion (for stress calculation)
            expected_aversion = get_value('expected_aversion', 'default_initial_aversion', 0.0)
            
            # Calculate stress_level from components
            stress_level = (
                (expected_mental_energy * 0.5 + 
                 expected_difficulty * 0.5 + 
                 emotional_load + 
                 physical_load + 
                 expected_aversion * 2.0) / 5.0
            )
            
            # Behavioral score: not typically in predicted, use default
            behavioral_score = 50.0  # Default neutral
            
            # Net wellbeing: calculate from relief and stress
            net_wellbeing = relief_score - stress_level
            # Normalize to 0-100 scale (baseline-relative)
            net_wellbeing_normalized = max(0.0, min(100.0, 50.0 + net_wellbeing))
            
            # Apply duration filters
            if max_duration_filter is not None:
                if duration_minutes > max_duration_filter:
                    continue
            if min_duration_filter is not None:
                if duration_minutes < min_duration_filter:
                    continue
            
            # Calculate derived metrics
            net_load = cognitive_load + emotional_load
            net_relief_proxy = relief_score - cognitive_load
            
            # Get historical efficiency if available
            task_efficiency = self.get_task_efficiency_history()
            historical_efficiency = task_efficiency.get(task_id, 0.0) if task_id else 0.0
            
            # Get initialization notes (description) from predicted field
            description = predicted.get('description', '') or ''
            if not description and task_info:
                description = task_info.get('description', '') or ''
            
            candidates.append({
                'instance_id': instance_id,
                'task_id': task_id,
                'task_name': task_name,
                'description': description,
                'actual': instance.get('actual') or '',
                'relief_score': relief_score,
                'cognitive_load': cognitive_load,
                'emotional_load': emotional_load,
                'duration_minutes': duration_minutes,
                'historical_efficiency': historical_efficiency,
                'stress_level': stress_level,
                'behavioral_score': behavioral_score,
                'net_wellbeing_normalized': net_wellbeing_normalized,
                'physical_load': physical_load,
                'net_load': net_load,
                'net_relief_proxy': net_relief_proxy,
                'mental_energy_needed': expected_mental_energy,
                'task_difficulty': expected_difficulty,
            })
        
        if not candidates:
            return []
        
        candidates_df = pd.DataFrame(candidates)
        
        # Scoring helper: high-good adds value; low-good adds (100 - value)
        def metric_score(metric_name: str, value: float) -> float:
            try:
                v = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                v = 0.0
            if metric_name in low_is_good:
                return max(0.0, 100.0 - v)
            return v
        
        # Compute score per instance
        scores = []
        for _, row in candidates_df.iterrows():
            score_total = 0.0
            for metric in metrics:
                score_total += metric_score(metric, row.get(metric))
            scores.append(score_total)
        candidates_df['score'] = scores
        
        # Normalize scores to 0-100 range
        # Use absolute normalization based on max possible score, not relative to candidates
        # This ensures meaningful scores even with only one candidate
        if len(scores) > 0:
            num_metrics = len(metrics) if metrics else 1
            max_possible_score = num_metrics * 100.0  # Each metric can contribute up to 100
            
            if max_possible_score > 0:
                # Normalize: (score / max_possible) * 100
                candidates_df['score_normalized'] = (candidates_df['score'] / max_possible_score) * 100.0
                # Clamp to 0-100 range
                candidates_df['score_normalized'] = candidates_df['score_normalized'].clip(0.0, 100.0)
            else:
                candidates_df['score_normalized'] = 50.0
        else:
            candidates_df['score_normalized'] = 50.0
        
        # Sort by score descending and take top N
        top_n = candidates_df.sort_values('score', ascending=False).head(limit)
        
        ranked = []
        for idx, (_, row) in enumerate(top_n.iterrows()):
            # Collect only the metrics the user selected
            metric_values = {}
            for metric in metrics:
                try:
                    metric_values[metric] = float(row.get(metric)) if row.get(metric) is not None else None
                except (ValueError, TypeError):
                    metric_values[metric] = None
            
            ranked.append({
                'title': "Recommendation",
                'instance_id': row.get('instance_id'),
                'task_id': row.get('task_id'),
                'task_name': row.get('task_name'),
                'description': row.get('description', ''),
                'actual': row.get('actual') or '',
                'score': round(float(row.get('score_normalized', 0.0)), 1),
                'metric_values': metric_values,
                # Include all sub-scores for tooltip
                'sub_scores': {
                    'relief_score': row.get('relief_score'),
                    'cognitive_load': row.get('cognitive_load'),
                    'emotional_load': row.get('emotional_load'),
                    'physical_load': row.get('physical_load'),
                    'stress_level': row.get('stress_level'),
                    'behavioral_score': row.get('behavioral_score'),
                    'net_wellbeing_normalized': row.get('net_wellbeing_normalized'),
                    'net_load': row.get('net_load'),
                    'net_relief_proxy': row.get('net_relief_proxy'),
                    'mental_energy_needed': row.get('mental_energy_needed'),
                    'task_difficulty': row.get('task_difficulty'),
                    'historical_efficiency': row.get('historical_efficiency'),
                    'duration_minutes': row.get('duration_minutes'),
                },
                'duration': row.get('duration_minutes'),
                'relief': row.get('relief_score'),
                'cognitive_load': row.get('cognitive_load'),
                'emotional_load': row.get('emotional_load'),
            })
        
        # Log recommendation generation
        try:
            from .recommendation_logger import recommendation_logger
            metric_list = metrics if isinstance(metrics, list) else [metrics] if metrics else []
            recommendation_logger.log_recommendation_generated(
                mode='instances',
                metrics=metric_list,
                filters=filters,
                recommendations=ranked
            )
        except Exception as e:
            # Don't fail if logging fails
            import warnings
            warnings.warn(f"Failed to log recommendations: {e}")
        
        return ranked

    def _row_to_recommendation(self, row_df: pd.DataFrame, label: str) -> Optional[Dict[str, str]]:
        """Legacy method for instance-based recommendations."""
        if row_df is None or row_df.empty:
            return None
        row = row_df.iloc[0]
        reason = f"{label}: relief {row.get('relief_score', '—')} / cognitive {row.get('cognitive_load', '—')}."
        return {
            'title': label,
            'instance_id': row.get('instance_id'),
            'task_id': row.get('task_id'),
            'task_name': row.get('task_name'),
            'reason': reason,
            'duration': row.get('duration_minutes'),
            'relief': row.get('relief_score'),
            'cognitive_load': row.get('cognitive_load'),
        }
    
    def _task_to_recommendation(self, task_row: pd.Series, label: str) -> Dict[str, str]:
        """Convert a task template row to a recommendation dict."""
        relief = task_row.get('relief_score', 0)
        cognitive = task_row.get('cognitive_load', 0)
        emotional = task_row.get('emotional_load', 0)
        duration = task_row.get('duration_minutes', task_row.get('default_estimate', 0))
        
        # Format relief and cognitive to 1 decimal place
        try:
            relief_val = float(relief) if relief is not None else 0
            relief_str = f"{relief_val:.1f}" if relief_val > 0 else "—"
        except (ValueError, TypeError):
            relief_str = "—"
        
        try:
            cognitive_val = float(cognitive) if cognitive is not None else 0
            cognitive_str = f"{cognitive_val:.1f}" if cognitive_val > 0 else "—"
        except (ValueError, TypeError):
            cognitive_str = "—"
        
        try:
            emotional_val = float(emotional) if emotional is not None else 0
            emotional_str = f"{emotional_val:.1f}" if emotional_val > 0 else "—"
        except (ValueError, TypeError):
            emotional_str = "—"
        
        try:
            duration_val = float(duration) if duration is not None else 0
            duration_str = f"{duration_val:.0f}" if duration_val > 0 else "—"
        except (ValueError, TypeError):
            duration_str = "—"
        
        # Build reason string - include emotional load if relevant
        if emotional_str != "—" and emotional_val > 0:
            reason = f"{label}: relief {relief_str} / cognitive {cognitive_str} / emotional {emotional_str}."
        else:
            reason = f"{label}: relief {relief_str} / cognitive {cognitive_str}."
        
        return {
            'title': label,
            'task_id': task_row.get('task_id'),
            'task_name': task_row.get('task_name'),
            'reason': reason,
            'duration': duration_str,
            'relief': relief_str,
            'cognitive_load': cognitive_str,
            'emotional_load': emotional_str,
        }

    # ------------------------------------------------------------------
    # Analytics datasets for charts
    # ------------------------------------------------------------------
    def trend_series(self, user_id: Optional[int] = None) -> pd.DataFrame:
        import time
        start = time.perf_counter()
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Check cache (cache is now user-specific, keyed by user_id)
        cache_key = user_id if user_id is not None else "default"
        current_time = time.time()
        if (cache_key in self._trend_series_cache and 
            cache_key in self._trend_series_cache_time and
            (current_time - self._trend_series_cache_time[cache_key]) < self._cache_ttl_seconds):
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] trend_series (cached): {duration:.2f}ms")
            return self._trend_series_cache[cache_key].copy()
        df = self._load_instances(user_id=user_id)
        if df.empty:
            result = pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])
            self._trend_series_cache[cache_key] = result.copy()
            self._trend_series_cache_time[cache_key] = time.time()
            return result
        completed = df[df['completed_at'].astype(str).str.len() > 0]
        if completed.empty:
            result = pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])
            self._trend_series_cache = result.copy()
            self._trend_series_cache_time = time.time()
            return result

        # Ensure datetime and numeric relief
        completed = completed.copy()
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()]
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce').fillna(0.0)

        if completed.empty:
            result = pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])
            self._trend_series_cache = result.copy()
            self._trend_series_cache_time = time.time()
            return result

        # Aggregate relief per day, then compute cumulative total over time
        daily = (
            completed
            .groupby(completed['completed_at_dt'].dt.date)['relief_score_numeric']
            .sum()
            .reset_index()
            .rename(columns={'completed_at_dt': 'completed_at', 'relief_score_numeric': 'daily_relief_score'})
        )

        daily = daily.sort_values('completed_at')
        daily['completed_at'] = pd.to_datetime(daily['completed_at'])
        daily['cumulative_relief_score'] = daily['daily_relief_score'].cumsum()

        result = daily[['completed_at', 'daily_relief_score', 'cumulative_relief_score']].copy()
        
        # Store in cache
        self._trend_series_cache[cache_key] = result.copy()
        self._trend_series_cache_time[cache_key] = time.time()
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] trend_series: {duration:.2f}ms")
        return result

    def attribute_distribution(self, user_id: Optional[int] = None) -> pd.DataFrame:
        import time
        start = time.perf_counter()
        
        user_id = self._get_user_id(user_id)
        
        # Check cache
        # Cache is now user-specific, keyed by user_id
        cache_key = user_id if user_id is not None else "default"
        current_time = time.time()
        if (cache_key in self._attribute_distribution_cache and 
            cache_key in self._attribute_distribution_cache_time and
            (current_time - self._attribute_distribution_cache_time[cache_key]) < self._cache_ttl_seconds):
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] attribute_distribution (cached): {duration:.2f}ms")
            return self._attribute_distribution_cache[cache_key].copy()
        
        df = self._load_instances(user_id=user_id)
        if df.empty:
            result = pd.DataFrame(columns=['attribute', 'value'])
            self._attribute_distribution_cache[cache_key] = result.copy()
            self._attribute_distribution_cache_time[cache_key] = time.time()
            return result
        melted_frames = []
        
        # Attributes to exclude from distribution chart (not actively tracked)
        excluded_attributes = {'environmental_effect'}  # Not collected in UI
        
        for attr in TASK_ATTRIBUTES:
            if attr.dtype != 'numeric':
                continue
            if attr.key in excluded_attributes:
                continue  # Skip excluded attributes
            sub = df[[attr.key]].rename(columns={attr.key: 'value'}).dropna()
            sub['attribute'] = attr.label
            melted_frames.append(sub)
        
        # Include physical load, which is derived from predicted/actual payloads
        if 'physical_load' in df.columns:
            physical_sub = (
                df[['physical_load']]
                .rename(columns={'physical_load': 'value'})
                .dropna()
            )
            physical_sub = physical_sub[physical_sub['value'] > 0]  # omit zeros/missing
            if not physical_sub.empty:
                physical_sub['attribute'] = 'Physical Load'
                melted_frames.append(physical_sub)
        
        # Add calculated metrics: stress_level, net_wellbeing, net_wellbeing_normalized, and stress_efficiency
        if 'stress_level' in df.columns:
            stress_sub = df[['stress_level']].rename(columns={'stress_level': 'value'}).dropna()
            stress_sub['attribute'] = 'Stress Level'
            melted_frames.append(stress_sub)
        
        if 'net_wellbeing' in df.columns:
            wellbeing_sub = df[['net_wellbeing']].rename(columns={'net_wellbeing': 'value'}).dropna()
            wellbeing_sub['attribute'] = 'Net Wellbeing'
            melted_frames.append(wellbeing_sub)
        
        if 'net_wellbeing_normalized' in df.columns:
            wellbeing_norm_sub = df[['net_wellbeing_normalized']].rename(columns={'net_wellbeing_normalized': 'value'}).dropna()
            wellbeing_norm_sub['attribute'] = 'Net Wellbeing (Normalized)'
            melted_frames.append(wellbeing_norm_sub)
        
        if 'stress_efficiency' in df.columns:
            efficiency_sub = df[['stress_efficiency']].rename(columns={'stress_efficiency': 'value'}).dropna()
            efficiency_sub['attribute'] = 'Stress Efficiency'
            melted_frames.append(efficiency_sub)
        
        if not melted_frames:
            result = pd.DataFrame(columns=['attribute', 'value'])
            self._attribute_distribution_cache[cache_key] = result.copy()
            self._attribute_distribution_cache_time[cache_key] = time.time()
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] attribute_distribution: {duration:.2f}ms (no data)")
            return result
        
        result = pd.concat(melted_frames, ignore_index=True).copy()
        
        # Store in cache
        self._attribute_distribution_cache[cache_key] = result.copy()
        self._attribute_distribution_cache_time[cache_key] = time.time()
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] attribute_distribution: {duration:.2f}ms")
        return result

    # ------------------------------------------------------------------
    # Trends and correlation helpers
    # ------------------------------------------------------------------
    def get_attribute_trends(self, attribute_key: str, aggregation: str = 'mean', days: int = 90, user_id: Optional[int] = None) -> Dict[str, any]:
        """Return daily aggregated values for a single attribute."""
        df = self._load_instances(user_id=user_id)
        if df.empty or 'completed_at' not in df.columns:
            return {'dates': [], 'values': [], 'aggregation': aggregation}
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()]
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            completed = completed[completed['completed_at_dt'] >= cutoff]
        if completed.empty:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        # Handle calculated metrics that need to be computed
        if attribute_key == 'productivity_score':
            # Calculate productivity score for trend data
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all(user_id=user_id)
            
            # Merge task_type if needed
            if 'task_type' not in completed.columns and not tasks_df.empty and 'task_type' in tasks_df.columns:
                completed = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed['task_type'] = completed['task_type'].fillna('Work')
            
            # Count self care tasks per day
            self_care_tasks_per_day = {}
            if 'task_type' in completed.columns:
                completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
                self_care_tasks = completed[
                    completed['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
                ].copy()
                if not self_care_tasks.empty:
                    self_care_tasks['date'] = self_care_tasks['completed_at_dt'].dt.date
                    daily_counts = self_care_tasks.groupby('date').size()
                    for date, count in daily_counts.items():
                        self_care_tasks_per_day[date.isoformat()] = int(count)
            
            # Calculate work/play time per day
            work_play_time_per_day = {}
            if 'task_type' in completed.columns:
                def _get_actual_time_for_work_play(row):
                    try:
                        actual_dict = row.get('actual_dict', {})
                        if isinstance(actual_dict, dict):
                            return float(actual_dict.get('time_actual_minutes', 0) or 0)
                    except (KeyError, TypeError, ValueError):
                        pass
                    return 0.0
                
                completed['time_for_work_play'] = completed.apply(_get_actual_time_for_work_play, axis=1)
                completed['time_for_work_play'] = pd.to_numeric(completed['time_for_work_play'], errors='coerce').fillna(0.0)
                valid_for_work_play = completed[completed['completed_at_dt'].notna() & (completed['time_for_work_play'] > 0)].copy()
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

            weekly_work_summary = {}
            if work_play_time_per_day:
                total_work_time = sum(day.get('work_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
                total_play_time = sum(day.get('play_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
                weekly_work_summary = {
                    'total_work_time_minutes': float(total_work_time),
                    'total_play_time_minutes': float(total_play_time),
                    'days_count': int(len(work_play_time_per_day)),
                }
            
            # Calculate weekly average time
            def _get_actual_time_for_avg(row):
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, dict):
                        return actual_dict.get('time_actual_minutes', None)
                except (KeyError, TypeError):
                    pass
                return None
            
            completed['time_actual_for_avg'] = completed.apply(_get_actual_time_for_avg, axis=1)
            completed['time_actual_for_avg'] = pd.to_numeric(completed['time_actual_for_avg'], errors='coerce')
            valid_times = completed[completed['time_actual_for_avg'].notna() & (completed['time_actual_for_avg'] > 0)]
            weekly_avg_time = valid_times['time_actual_for_avg'].mean() if not valid_times.empty else 0.0
            
            # Get goal hours and weekly productive hours for goal-based adjustment
            goal_hours_per_week = None
            weekly_productive_hours = None
            try:
                # Convert user_id to string for UserStateManager (expects str)
                user_id_str = str(user_id) if user_id is not None else "default_user"
                goal_settings = UserStateManager().get_productivity_goal_settings(user_id_str)
                goal_hours_per_week = goal_settings.get('goal_hours_per_week')
                if goal_hours_per_week:
                    goal_hours_per_week = float(goal_hours_per_week)
                    from .productivity_tracker import ProductivityTracker
                    tracker = ProductivityTracker()
                    weekly_data = tracker.calculate_weekly_productivity_hours(user_id_str)
                    weekly_productive_hours = weekly_data.get('total_hours', 0.0)
                    if weekly_productive_hours <= 0:
                        weekly_productive_hours = None
            except Exception as e:
                print(f"[Analytics] Error getting goal hours: {e}")
                goal_hours_per_week = None
                weekly_productive_hours = None
            
            # Calculate productivity score
            completed['productivity_score'] = completed.apply(
                lambda row: self.calculate_productivity_score(
                    row,
                    self_care_tasks_per_day,
                    weekly_avg_time,
                    work_play_time_per_day,
                    productivity_settings=self.productivity_settings,
                    weekly_work_summary=weekly_work_summary,
                    goal_hours_per_week=goal_hours_per_week,
                    weekly_productive_hours=weekly_productive_hours
                ),
                axis=1
            )
            # Invalidate relief_summary cache since productivity_score calculation may have changed
            # This ensures monitored metrics get fresh data when viewing trends
            Analytics._invalidate_relief_summary_cache()
        elif attribute_key == 'grit_score':
            # Calculate grit score for trend data
            # Count how many times each task has been completed
            task_completion_counts = {}
            if 'task_id' in completed.columns:
                task_counts = completed.groupby('task_id').size()
                for task_id, count in task_counts.items():
                    task_completion_counts[task_id] = int(count)
            
            # Calculate grit score
            completed['grit_score'] = completed.apply(
                lambda row: self.calculate_grit_score(row, task_completion_counts),
                axis=1
            )
        elif attribute_key == 'relief_duration_score':
            # Calculate relief_duration_score if not already present
            if 'relief_duration_score' not in completed.columns:
                # Calculate relief multiplier
                def _calculate_relief_multiplier(row):
                    task_type = row.get('task_type', 'Work')
                    type_mult = self.get_task_type_multiplier(task_type)
                    initial_av = row.get('initial_aversion')
                    expected_av = row.get('expected_aversion')
                    aversion_mult = self.calculate_aversion_multiplier(initial_av, expected_av)
                    return type_mult * aversion_mult
                
                if 'relief_multiplier' not in completed.columns:
                    completed['relief_multiplier'] = completed.apply(_calculate_relief_multiplier, axis=1)
                
                completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce')
                completed['duration_minutes_numeric'] = pd.to_numeric(completed['duration_minutes'], errors='coerce')
                completed['relief_duration_score'] = (
                    completed['relief_score_numeric'] * 
                    completed['duration_minutes_numeric'] * 
                    completed['relief_multiplier']
                ) / 60.0  # Divide by 60 to normalize (convert minutes to hours scale)
        elif attribute_key == 'daily_productivity_score_idle_refresh':
            # #region agent log
            import json
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'E',
                        'location': 'analytics.py:10050',
                        'message': 'get_attribute_trends: daily_productivity_score_idle_refresh entry',
                        'data': {
                            'days': days,
                            'aggregation': aggregation,
                            'completed_count': len(completed)
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            # Calculate daily productivity score with midnight refresh
            # Get all unique dates in the range
            now = datetime.now()
            if days:
                cutoff = now - timedelta(days=days)
                date_range = pd.date_range(start=cutoff, end=now, freq='D')
            else:
                if completed.empty:
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'analytics.py:10057',
                                'message': 'Early return: completed empty',
                                'data': {},
                                'timestamp': int(datetime.now().timestamp() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    return {'dates': [], 'values': [], 'aggregation': aggregation}
                min_date = completed['completed_at_dt'].min().date()
                max_date = completed['completed_at_dt'].max().date()
                date_range = pd.date_range(start=pd.Timestamp(min_date), end=pd.Timestamp(max_date), freq='D')
            
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'E',
                        'location': 'analytics.py:10065',
                        'message': 'Date range calculated',
                        'data': {
                            'date_range_length': len(date_range),
                            'first_date': str(date_range[0].date()) if len(date_range) > 0 else None,
                            'last_date': str(date_range[-1].date()) if len(date_range) > 0 else None
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            daily_scores = []
            daily_dates = []
            
            for date_ts in date_range:
                date_obj = date_ts.date()
                is_today = date_obj == now.date()
                
                try:
                    # For today, pass None to use rolling calculation
                    # For historical dates, pass the specific date
                    target_date = None if is_today else datetime.combine(date_obj, datetime.min.time())
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'analytics.py:10075',
                                'message': 'Calling calculate_daily_productivity_score_with_idle_refresh',
                                'data': {
                                    'date_obj': str(date_obj),
                                    'is_today': is_today,
                                    'target_date': str(target_date) if target_date else None
                                },
                                'timestamp': int(datetime.now().timestamp() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    
                    score_data = self.calculate_daily_productivity_score_with_idle_refresh(
                        target_date=target_date,
                        idle_refresh_hours=8.0,
                        user_id=user_id
                    )
                    daily_score = score_data.get('daily_score', 0.0)
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'analytics.py:10090',
                                'message': 'Score calculated for date',
                                'data': {
                                    'date_obj': str(date_obj),
                                    'daily_score': daily_score,
                                    'total_tasks': score_data.get('total_tasks', 0)
                                },
                                'timestamp': int(datetime.now().timestamp() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    
                    daily_scores.append(float(daily_score))
                    daily_dates.append(str(date_obj))
                except Exception as e:
                    # If calculation fails for a date, use 0.0
                    print(f"[Analytics] Error calculating idle refresh score for {date_obj}: {e}")
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'analytics.py:10100',
                                'message': 'Exception calculating score',
                                'data': {
                                    'date_obj': str(date_obj),
                                    'error': str(e)
                                },
                                'timestamp': int(datetime.now().timestamp() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    daily_scores.append(0.0)
                    daily_dates.append(str(date_obj))
            
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'E',
                        'location': 'analytics.py:10110',
                        'message': 'Returning trend data',
                        'data': {
                            'dates_count': len(daily_dates),
                            'scores_count': len(daily_scores),
                            'total_score': sum(daily_scores)
                        },
                        'timestamp': int(datetime.now().timestamp() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            return {
                'dates': daily_dates,
                'values': daily_scores,
                'aggregation': 'sum',  # Sum is appropriate since it's a daily total
            }
        elif attribute_key == 'daily_self_care_tasks':
            # Calculate daily self care tasks count
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all(user_id=user_id)
            
            # Merge task_type if needed
            if 'task_type' not in completed.columns and not tasks_df.empty and 'task_type' in tasks_df.columns:
                completed = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
                completed['task_type'] = completed['task_type'].fillna('Work')
            
            # Filter to self care tasks and count per day
            if 'task_type' in completed.columns:
                completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
                self_care_tasks = completed[
                    completed['task_type_normalized'].isin(['self care', 'selfcare', 'self-care'])
                ].copy()
                
                if not self_care_tasks.empty:
                    self_care_tasks['date'] = self_care_tasks['completed_at_dt'].dt.date
                    # Count self care tasks per day
                    daily_counts = self_care_tasks.groupby('date').size().reset_index(name='count')
                    daily_counts = daily_counts.sort_values('date')
                    
                    # Create a complete date range and fill missing days with 0
                    if days:
                        cutoff = datetime.now() - timedelta(days=days)
                        date_range = pd.date_range(start=cutoff, end=datetime.now(), freq='D')
                    else:
                        min_date = daily_counts['date'].min()
                        max_date = daily_counts['date'].max()
                        date_range = pd.date_range(start=pd.Timestamp(min_date), end=pd.Timestamp(max_date), freq='D')
                    
                    date_df = pd.DataFrame({'date': [d.date() for d in date_range]})
                    daily_counts = date_df.merge(daily_counts, on='date', how='left')
                    daily_counts['count'] = daily_counts['count'].fillna(0).astype(int)
                    
                    return {
                        'dates': daily_counts['date'].astype(str).tolist(),
                        'values': daily_counts['count'].tolist(),
                        'aggregation': 'count',
                    }
            
            # If no self care tasks or no task_type, return empty
            return {'dates': [], 'values': [], 'aggregation': 'count'}
        
        # Ensure calculated metrics are available by calling _load_instances if needed
        # This ensures stress_level, net_wellbeing, stress_efficiency, etc. are calculated
        if attribute_key in ['stress_level', 'net_wellbeing', 'net_wellbeing_normalized', 
                              'stress_efficiency', 'stress_relief_correlation_score', 'relief_score',
                              'expected_relief', 'net_relief', 'serendipity_factor', 'disappointment_factor']:
            # These metrics should already be calculated in _load_instances
            # But ensure they exist by checking the dataframe
            if attribute_key not in completed.columns:
                # Recalculate if missing (shouldn't happen, but safety check)
                completed = self._load_instances(user_id=user_id)
                completed = completed[completed['completed_at'].astype(str).str.len() > 0].copy()
                completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                completed = completed[completed['completed_at_dt'].notna()]
                if days:
                    cutoff = datetime.now() - timedelta(days=days)
                    completed = completed[completed['completed_at_dt'] >= cutoff]
        
        if attribute_key not in completed.columns:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        # Convert to numeric where possible
        completed['value_numeric'] = pd.to_numeric(completed[attribute_key], errors='coerce')
        # Group by date
        completed['date'] = completed['completed_at_dt'].dt.date

        agg_map = {
            'mean': 'mean',
            'sum': 'sum',
            'median': 'median',
            'min': 'min',
            'max': 'max',
            'count': 'count',
            'std': 'std',
            'var': 'var',
        }
        agg = agg_map.get(str(aggregation).lower(), 'mean')

        if agg == 'count':
            daily = completed.groupby('date')['value_numeric'].count().reset_index(name='value')
        else:
            daily = completed.groupby('date')['value_numeric'].agg(agg).reset_index(name='value')

        if daily.empty:
            return {'dates': [], 'values': [], 'aggregation': aggregation}

        daily = daily.sort_values('date')
        return {
            'dates': daily['date'].astype(str).tolist(),
            'values': daily['value'].fillna(0).astype(float).tolist(),
            'aggregation': agg,
        }

    def get_multi_attribute_trends(
        self,
        attribute_keys: List[str],
        aggregation: str = 'mean',
        days: int = 90,
        normalize: bool = False,
        user_id: Optional[int] = None,
    ) -> Dict[str, Dict[str, any]]:
        """Return trends for multiple attributes; optionally normalize each series (min-max)."""
        import time
        start = time.perf_counter()
        trends = {}
        attribute_keys = attribute_keys or []
        for key in attribute_keys:
            data = self.get_attribute_trends(key, aggregation, days, user_id=user_id)
            values = data.get('values') or []
            if normalize and values:
                v_min = min(values)
                v_max = max(values)
                if v_max != v_min:
                    normalized = [(v - v_min) / (v_max - v_min) for v in values]
                else:
                    normalized = [0.0 for _ in values]
                data['values'] = normalized
                data['original_min'] = v_min
                data['original_max'] = v_max
            trends[key] = data
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_multi_attribute_trends: {duration:.2f}ms (attributes: {len(attribute_keys)})")
        return trends

    def get_stress_dimension_data(self, user_id: Optional[int] = None) -> Dict[str, Dict[str, float]]:
        """
        Calculate stress dimension values for cognitive, emotional, and physical stress.
        Returns dictionary with totals, 7-day averages, and daily values for each dimension.
        
        Args:
            user_id: Optional user ID for data isolation
        """
        import time
        start = time.perf_counter()
        
        user_id = self._get_user_id(user_id)
        
        # Check cache (cache is now user-specific, keyed by user_id)
        cache_key = user_id if user_id is not None else "default"
        current_time = time.time()
        if (cache_key in self._stress_dimension_cache and 
            cache_key in self._stress_dimension_cache_time and
            (current_time - self._stress_dimension_cache_time[cache_key]) < self._cache_ttl_seconds):
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_dimension_data (cached): {duration:.2f}ms")
            # Deep copy to prevent mutation
            return copy.deepcopy(self._stress_dimension_cache[cache_key])
        
        df = self._load_instances(user_id=user_id)
        
        # Check if DataFrame is empty or missing required column
        if df.empty or 'completed_at' not in df.columns:
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_dimension_data: {duration:.2f}ms (no data or missing column)")
            result = {
                'cognitive': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'emotional': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'physical': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
            }
            self._stress_dimension_cache[cache_key] = copy.deepcopy(result)
            self._stress_dimension_cache_time[cache_key] = time.time()
            return result
        
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            result = {
                'cognitive': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'emotional': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'physical': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
            }
            self._stress_dimension_cache[cache_key] = copy.deepcopy(result)
            self._stress_dimension_cache_time[cache_key] = time.time()
            return result
        
        # Convert to numeric and calculate dimensions
        completed['mental_energy_numeric'] = pd.to_numeric(completed['mental_energy_needed'], errors='coerce').fillna(50.0)
        completed['task_difficulty_numeric'] = pd.to_numeric(completed['task_difficulty'], errors='coerce').fillna(50.0)
        completed['emotional_load_numeric'] = pd.to_numeric(completed['emotional_load'], errors='coerce').fillna(0.0)
        completed['physical_load_numeric'] = pd.to_numeric(completed['physical_load'], errors='coerce').fillna(0.0)
        
        # Calculate stress dimensions
        # Cognitive = (mental_energy * 0.5 + task_difficulty * 0.5)
        completed['cognitive_stress'] = (completed['mental_energy_numeric'] * 0.5 + completed['task_difficulty_numeric'] * 0.5)
        completed['emotional_stress'] = completed['emotional_load_numeric']
        completed['physical_stress'] = completed['physical_load_numeric']
        
        # Parse dates
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()]
        
        if completed.empty:
            duration = (time.perf_counter() - start) * 1000
            print(f"[Analytics] get_stress_dimension_data: {duration:.2f}ms (no data)")
            return {
                'cognitive': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'emotional': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'physical': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
            }
        
        # Calculate totals
        cognitive_total = float(completed['cognitive_stress'].sum())
        emotional_total = float(completed['emotional_stress'].sum())
        physical_total = float(completed['physical_stress'].sum())
        
        # Calculate 7-day average
        cutoff_7d = datetime.now() - timedelta(days=7)
        recent_7d = completed[completed['completed_at_dt'] >= cutoff_7d]
        
        cognitive_avg_7d = float(recent_7d['cognitive_stress'].mean()) if not recent_7d.empty else 0.0
        emotional_avg_7d = float(recent_7d['emotional_stress'].mean()) if not recent_7d.empty else 0.0
        physical_avg_7d = float(recent_7d['physical_stress'].mean()) if not recent_7d.empty else 0.0
        
        # Calculate daily values
        completed['date'] = completed['completed_at_dt'].dt.date
        daily_cognitive = completed.groupby('date')['cognitive_stress'].mean().reset_index()
        daily_emotional = completed.groupby('date')['emotional_stress'].mean().reset_index()
        daily_physical = completed.groupby('date')['physical_stress'].mean().reset_index()
        
        daily_cognitive = daily_cognitive.sort_values('date')
        daily_emotional = daily_emotional.sort_values('date')
        daily_physical = daily_physical.sort_values('date')
        
        cognitive_daily = [{'date': str(row['date']), 'value': float(row['cognitive_stress'])} for _, row in daily_cognitive.iterrows()]
        emotional_daily = [{'date': str(row['date']), 'value': float(row['emotional_stress'])} for _, row in daily_emotional.iterrows()]
        physical_daily = [{'date': str(row['date']), 'value': float(row['physical_stress'])} for _, row in daily_physical.iterrows()]
        
        result = {
            'cognitive': {
                'total': cognitive_total,
                'avg_7d': cognitive_avg_7d,
                'daily': cognitive_daily,
            },
            'emotional': {
                'total': emotional_total,
                'avg_7d': emotional_avg_7d,
                'daily': emotional_daily,
            },
            'physical': {
                'total': physical_total,
                'avg_7d': physical_avg_7d,
                'daily': physical_daily,
            },
        }
        
        # Store in cache (deep copy to prevent mutation)
        self._stress_dimension_cache[cache_key] = copy.deepcopy(result)
        self._stress_dimension_cache_time[cache_key] = time.time()
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_stress_dimension_data: {duration:.2f}ms")
        return result

    def calculate_correlation(self, attribute_x: str, attribute_y: str, method: str = 'pearson', user_id: Optional[int] = None) -> Dict[str, any]:
        """Calculate correlation between two attributes with metadata for tooltips.
        
        Args:
            attribute_x: Name of first attribute
            attribute_y: Name of second attribute
            method: Correlation method ('pearson', 'spearman', etc.)
            user_id: User ID for data isolation (required for database mode)
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty or attribute_x not in completed.columns or attribute_y not in completed.columns:
            return {'correlation': None, 'p_value': None, 'r_squared': None, 'n': 0}

        completed['x_val'] = pd.to_numeric(completed[attribute_x], errors='coerce')
        completed['y_val'] = pd.to_numeric(completed[attribute_y], errors='coerce')
        clean = completed[['x_val', 'y_val']].dropna()
        if clean.empty or len(clean) < 2:
            return {'correlation': None, 'p_value': None, 'r_squared': None, 'n': len(clean)}

        method = (method or 'pearson').lower()
        meta = {
            'pearson': {
                'name': 'Pearson Correlation',
                'description': 'Measures linear relationship strength between two variables. Range -1..1.',
                'statistician': 'Karl Pearson',
                'search_term': 'Pearson correlation coefficient',
            },
            'spearman': {
                'name': 'Spearman Rank Correlation',
                'description': 'Non-parametric measure of monotonic relationship using ranked data. Range -1..1.',
                'statistician': 'Charles Spearman',
                'search_term': 'Spearman rank correlation',
            },
        }

        correlation = None
        p_value = None
        try:
            if method == 'spearman':
                correlation, p_value = stats.spearmanr(clean['x_val'], clean['y_val'])
            else:
                correlation, p_value = stats.pearsonr(clean['x_val'], clean['y_val'])
        except Exception:
            correlation, p_value = None, None

        r_squared = correlation ** 2 if correlation is not None else None
        return {
            'correlation': correlation,
            'p_value': p_value,
            'r_squared': r_squared,
            'n': len(clean),
            'method': method,
            'meta': meta.get(method, {}),
        }

    def find_threshold_relationships(self, dependent_var: str, independent_var: str, bins: int = 10, user_id: Optional[int] = None) -> Dict[str, any]:
        """Bin independent variable and summarize dependent averages to surface threshold ranges."""
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty or dependent_var not in completed.columns or independent_var not in completed.columns:
            return {'bins': [], 'best_max': None, 'best_min': None}

        completed['x_val'] = pd.to_numeric(completed[independent_var], errors='coerce')
        completed['y_val'] = pd.to_numeric(completed[dependent_var], errors='coerce')
        clean = completed[['x_val', 'y_val']].dropna()
        if clean.empty or len(clean) < 2:
            return {'bins': [], 'best_max': None, 'best_min': None}

        unique_x = clean['x_val'].nunique()
        bin_count = max(1, min(bins, unique_x))

        try:
            clean['bin'] = pd.cut(clean['x_val'], bins=bin_count, duplicates='drop')
        except Exception:
            return {'bins': [], 'best_max': None, 'best_min': None}

        grouped = clean.groupby('bin')['y_val'].agg(['mean', 'count']).reset_index()
        if grouped.empty:
            return {'bins': [], 'best_max': None, 'best_min': None}

        bins_list = []
        for _, row in grouped.iterrows():
            interval = row['bin']
            bins_list.append({
                'range': str(interval),
                'dependent_avg': round(float(row['mean']), 4) if pd.notna(row['mean']) else None,
                'count': int(row['count']),
            })

        best_max = grouped.loc[grouped['mean'].idxmax()] if grouped['mean'].notna().any() else None
        best_min = grouped.loc[grouped['mean'].idxmin()] if grouped['mean'].notna().any() else None

        def _format_best(row):
            if row is None or pd.isna(row['mean']):
                return None
            return {
                'range': str(row['bin']),
                'dependent_avg': round(float(row['mean']), 4),
                'count': int(row['count']),
            }

        return {
            'bins': bins_list,
            'best_max': _format_best(best_max),
            'best_min': _format_best(best_min),
        }

    def get_scatter_data(self, attribute_x: str, attribute_y: str, user_id: Optional[int] = None) -> Dict[str, any]:
        """Return paired scatter values for two attributes.
        
        Supports calculated metrics like productivity_score and grit_score by computing them on-the-fly.
        
        Args:
            attribute_x: Name of first attribute
            attribute_y: Name of second attribute
            user_id: User ID for data isolation (required for database mode)
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        
        # Check if DataFrame is empty or missing required column
        if df.empty or 'completed_at' not in df.columns:
            return {'x': [], 'y': [], 'n': 0}
        
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            return {'x': [], 'y': [], 'n': 0}
        
        # Ensure actual_dict and predicted_dict exist (they should from _load_instances, but check)
        if 'actual_dict' not in completed.columns:
            def _safe_json(cell):
                if isinstance(cell, dict):
                    return cell
                cell = cell or '{}'
                try:
                    import json
                    return json.loads(cell)
                except (ValueError, TypeError, json.JSONDecodeError):
                    return {}
            completed['actual_dict'] = completed['actual'].apply(_safe_json) if 'actual' in completed.columns else pd.Series([{}] * len(completed))
        
        if 'predicted_dict' not in completed.columns:
            def _safe_json(cell):
                if isinstance(cell, dict):
                    return cell
                cell = cell or '{}'
                try:
                    import json
                    return json.loads(cell)
                except (ValueError, TypeError, json.JSONDecodeError):
                    return {}
            completed['predicted_dict'] = completed['predicted'].apply(_safe_json) if 'predicted' in completed.columns else pd.Series([{}] * len(completed))
        
        # Calculate productivity_score if needed
        if attribute_x == 'productivity_score' or attribute_y == 'productivity_score':
            from datetime import datetime
            # Get self-care tasks per day
            self_care_tasks_per_day = {}
            if 'task_type' in completed.columns and 'completed_at' in completed.columns:
                for _, row in completed.iterrows():
                    task_type = str(row.get('task_type', '')).strip().lower()
                    completed_at = row.get('completed_at', '')
                    if task_type in ['self care', 'selfcare', 'self-care'] and completed_at:
                        try:
                            completed_date = pd.to_datetime(completed_at).date()
                            date_str = completed_date.isoformat()
                            self_care_tasks_per_day[date_str] = self_care_tasks_per_day.get(date_str, 0) + 1
                        except (ValueError, TypeError):
                            pass
            
            # Calculate work/play time per day
            work_play_time_per_day = {}
            if 'task_type' in completed.columns and 'completed_at' in completed.columns:
                # Ensure completed_at_dt exists
                if 'completed_at_dt' not in completed.columns:
                    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                
                def _get_actual_time_for_work_play(row):
                    try:
                        actual_dict = row.get('actual_dict', {})
                        if isinstance(actual_dict, dict):
                            return float(actual_dict.get('time_actual_minutes', 0) or 0)
                    except (KeyError, TypeError, ValueError):
                        pass
                    return 0.0
                
                completed['time_for_work_play'] = completed.apply(_get_actual_time_for_work_play, axis=1)
                completed['time_for_work_play'] = pd.to_numeric(completed['time_for_work_play'], errors='coerce').fillna(0.0)
                completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
                valid_for_work_play = completed[completed['completed_at_dt'].notna() & (completed['time_for_work_play'] > 0)].copy()
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

            weekly_work_summary = {}
            if work_play_time_per_day:
                total_work_time = sum(day.get('work_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
                total_play_time = sum(day.get('play_time', 0.0) or 0.0 for day in work_play_time_per_day.values())
                weekly_work_summary = {
                    'total_work_time_minutes': float(total_work_time),
                    'total_play_time_minutes': float(total_play_time),
                    'days_count': int(len(work_play_time_per_day)),
                }
            
            # Calculate weekly average time
            def _get_actual_time_for_avg(row):
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, dict):
                        return float(actual_dict.get('time_actual_minutes', 0) or 0)
                except (ValueError, TypeError, AttributeError):
                    return None
            
            completed['time_actual_for_avg'] = completed.apply(_get_actual_time_for_avg, axis=1)
            completed['time_actual_for_avg'] = pd.to_numeric(completed['time_actual_for_avg'], errors='coerce')
            valid_times = completed[completed['time_actual_for_avg'].notna() & (completed['time_actual_for_avg'] > 0)]
            weekly_avg_time = valid_times['time_actual_for_avg'].mean() if not valid_times.empty else 0.0
            
            # Get goal hours and weekly productive hours for goal-based adjustment
            goal_hours_per_week = None
            weekly_productive_hours = None
            try:
                # Convert user_id to string for UserStateManager (expects str)
                user_id_str = str(user_id) if user_id is not None else "default_user"
                goal_settings = UserStateManager().get_productivity_goal_settings(user_id_str)
                goal_hours_per_week = goal_settings.get('goal_hours_per_week')
                if goal_hours_per_week:
                    goal_hours_per_week = float(goal_hours_per_week)
                    from .productivity_tracker import ProductivityTracker
                    tracker = ProductivityTracker()
                    weekly_data = tracker.calculate_weekly_productivity_hours(user_id_str)
                    weekly_productive_hours = weekly_data.get('total_hours', 0.0)
                    if weekly_productive_hours <= 0:
                        weekly_productive_hours = None
            except Exception as e:
                print(f"[Analytics] Error getting goal hours: {e}")
                goal_hours_per_week = None
                weekly_productive_hours = None
            
            # Calculate productivity score
            completed['productivity_score'] = completed.apply(
                lambda row: self.calculate_productivity_score(
                    row,
                    self_care_tasks_per_day,
                    weekly_avg_time,
                    work_play_time_per_day,
                    productivity_settings=self.productivity_settings,
                    weekly_work_summary=weekly_work_summary,
                    goal_hours_per_week=goal_hours_per_week,
                    weekly_productive_hours=weekly_productive_hours
                ),
                axis=1
            )
        
        # Calculate grit_score if needed
        if attribute_x == 'grit_score' or attribute_y == 'grit_score':
            # Count how many times each task has been completed
            task_completion_counts = {}
            if 'task_id' in completed.columns:
                task_counts = completed.groupby('task_id').size()
                for task_id, count in task_counts.items():
                    task_completion_counts[task_id] = int(count)
            
            # Calculate grit score
            completed['grit_score'] = completed.apply(
                lambda row: self.calculate_grit_score(row, task_completion_counts),
                axis=1
            )
        
        # Calculate work_time and play_time if needed
        if attribute_x == 'work_time' or attribute_y == 'work_time' or attribute_x == 'play_time' or attribute_y == 'play_time':
            # Load tasks to get task_type
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all(user_id=user_id)
            
            if not tasks_df.empty and 'task_type' in tasks_df.columns:
                # Merge to get task_type
                completed = completed.merge(
                    tasks_df[['task_id', 'task_type']],
                    on='task_id',
                    how='left'
                )
            
            # Normalize task_type
            completed['task_type'] = completed['task_type'].fillna('Work')
            completed['task_type_normalized'] = completed['task_type'].astype(str).str.strip().str.lower()
            
            # Get duration in minutes
            def _get_duration_for_work_play(row):
                """Get duration from actual_dict or duration_minutes."""
                try:
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, dict):
                        time_actual = actual_dict.get('time_actual_minutes', None)
                        if time_actual is not None:
                            return float(time_actual)
                except (ValueError, TypeError, AttributeError):
                    pass
                # Fallback to duration_minutes
                try:
                    duration = pd.to_numeric(row.get('duration_minutes', 0), errors='coerce')
                    return float(duration) if pd.notna(duration) else 0.0
                except (ValueError, TypeError):
                    return 0.0
            
            completed['duration_for_work_play'] = completed.apply(_get_duration_for_work_play, axis=1)
            
            # Calculate work_time and play_time per instance
            # For each instance, if it's a work task, work_time = duration, play_time = 0
            # If it's a play task, play_time = duration, work_time = 0
            # Otherwise, both are 0
            def _get_work_time(row):
                if row.get('task_type_normalized') == 'work':
                    return row.get('duration_for_work_play', 0.0)
                return 0.0
            
            def _get_play_time(row):
                if row.get('task_type_normalized') == 'play':
                    return row.get('duration_for_work_play', 0.0)
                return 0.0
            
            completed['work_time'] = completed.apply(_get_work_time, axis=1)
            completed['play_time'] = completed.apply(_get_play_time, axis=1)
        
        # Check if attributes exist (either in columns or calculated)
        if attribute_x not in completed.columns or attribute_y not in completed.columns:
            return {'x': [], 'y': [], 'n': 0}

        completed['x_val'] = pd.to_numeric(completed[attribute_x], errors='coerce')
        completed['y_val'] = pd.to_numeric(completed[attribute_y], errors='coerce')
        clean = completed[['x_val', 'y_val']].dropna()
        
        # Include time estimates for efficiency calculations if needed
        time_data = None
        if ('duration_minutes' in [attribute_x, attribute_y] and 'productivity_score' in [attribute_x, attribute_y]):
            # Extract time_estimate and time_actual for time efficiency calculation
            # Use the same rows that passed the dropna() filter
            time_estimates = []
            time_actuals = []
            
            for idx in clean.index:
                # Get time estimate
                time_est = None
                try:
                    row = completed.loc[idx]
                    predicted_dict = row.get('predicted_dict', {})
                    if isinstance(predicted_dict, dict):
                        val = predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0
                        if val:
                            time_est = float(val)
                except (ValueError, TypeError, AttributeError, KeyError):
                    pass
                time_estimates.append(time_est)
                
                # Get time actual
                time_act = None
                try:
                    row = completed.loc[idx]
                    actual_dict = row.get('actual_dict', {})
                    if isinstance(actual_dict, dict):
                        val = actual_dict.get('time_actual_minutes', 0) or 0
                        if val:
                            time_act = float(val)
                except (ValueError, TypeError, AttributeError, KeyError):
                    pass
                time_actuals.append(time_act)
            
            time_data = {
                'time_estimate': time_estimates,
                'time_actual': time_actuals,
            }
        
        result = {
            'x': clean['x_val'].astype(float).tolist(),
            'y': clean['y_val'].astype(float).tolist(),
            'n': len(clean),
        }
        if time_data:
            result['time_data'] = time_data
        return result

    def get_emotional_flow_data(self, user_id: Optional[int] = None) -> Dict[str, any]:
        """Get comprehensive emotional flow data for analytics.
        
        Args:
            user_id: User ID for data isolation
        
        Returns:
            Dictionary containing:
            - avg_emotional_load: Average emotional load across all tasks
            - avg_relief: Average relief score
            - spike_count: Number of emotional spikes detected
            - emotion_relief_ratio: Ratio of relief to emotional load
            - transitions: List of emotion transitions (initial -> final)
            - load_relief_scatter: Data for emotional load vs relief scatter plot
            - expected_actual_comparison: Expected vs actual emotional load data
            - emotion_trends: Time series data for each emotion
            - spikes: List of tasks with emotional spikes
            - correlations: Correlation data for emotions with other metrics
        """
        user_id = self._get_user_id(user_id)
        df = self._load_instances(user_id=user_id)
        if df.empty:
            return {
                'avg_emotional_load': 0,
                'avg_relief': 0,
                'spike_count': 0,
                'emotion_relief_ratio': 0,
                'transitions': [],
                'load_relief_scatter': {},
                'expected_actual_comparison': {},
                'emotion_trends': {},
                'spikes': [],
                'correlations': {}
            }
        
        # Filter to completed instances only
        completed = df[df['status'] == 'completed'].copy()
        if completed.empty:
            return {
                'avg_emotional_load': 0,
                'avg_relief': 0,
                'spike_count': 0,
                'emotion_relief_ratio': 0,
                'transitions': [],
                'load_relief_scatter': {},
                'expected_actual_comparison': {},
                'emotion_trends': {},
                'spikes': [],
                'correlations': {}
            }
        
        # Extract emotion data
        transitions = []
        load_relief_x = []
        load_relief_y = []
        load_relief_tasks = []
        expected_actual_expected = []
        expected_actual_actual = []
        expected_actual_tasks = []
        emotion_trends = {}
        spikes = []
        
        def _parse_json_safe(json_data):
            """Safely parse JSON, return empty dict on error."""
            if isinstance(json_data, dict):
                return json_data
            if not json_data or not isinstance(json_data, str):
                return {}
            try:
                return json.loads(json_data)
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}
        
        for _, row in completed.iterrows():
            # Parse JSON data
            predicted_dict = _parse_json_safe(row.get('predicted_dict', {}))
            actual_dict = _parse_json_safe(row.get('actual_dict', {}))
            
            # Emotion transitions (initial vs final emotion_values)
            initial_emotions = predicted_dict.get('emotion_values', {})
            final_emotions = actual_dict.get('emotion_values', {})
            
            # Handle string JSON if needed
            if isinstance(initial_emotions, str):
                try:
                    initial_emotions = json.loads(initial_emotions)
                except (json.JSONDecodeError, TypeError):
                    initial_emotions = {}
            if isinstance(final_emotions, str):
                try:
                    final_emotions = json.loads(final_emotions)
                except (json.JSONDecodeError, TypeError):
                    final_emotions = {}
            
            # Ensure dicts
            if not isinstance(initial_emotions, dict):
                initial_emotions = {}
            if not isinstance(final_emotions, dict):
                final_emotions = {}
            
            # Track transitions for each emotion
            all_emotions = set(list(initial_emotions.keys()) + list(final_emotions.keys()))
            for emotion in all_emotions:
                initial_val = initial_emotions.get(emotion) if isinstance(initial_emotions, dict) else None
                final_val = final_emotions.get(emotion) if isinstance(final_emotions, dict) else None
                
                # Convert to numeric if needed
                try:
                    if initial_val is not None:
                        initial_val = float(initial_val)
                except (ValueError, TypeError):
                    initial_val = None
                try:
                    if final_val is not None:
                        final_val = float(final_val)
                except (ValueError, TypeError):
                    final_val = None
                
                if initial_val is not None or final_val is not None:
                    transitions.append({
                        'emotion': emotion,
                        'initial_value': initial_val,
                        'final_value': final_val,
                        'task_name': str(row.get('task_name', 'Unknown')),
                        'completed_at': str(row.get('completed_at', ''))
                    })
            
            # Emotional load vs relief
            emotional_load = actual_dict.get('actual_emotional')
            if emotional_load is None:
                emotional_load = pd.to_numeric(row.get('emotional_load'), errors='coerce')
            
            relief = actual_dict.get('actual_relief')
            if relief is None:
                relief = pd.to_numeric(row.get('relief_score'), errors='coerce')
            
            if emotional_load is not None and not pd.isna(emotional_load) and relief is not None and not pd.isna(relief):
                load_relief_x.append(float(emotional_load))
                load_relief_y.append(float(relief))
                load_relief_tasks.append(str(row.get('task_name', 'Unknown')))
            
            # Expected vs actual
            expected = predicted_dict.get('expected_emotional_load')
            if expected is None:
                expected = pd.to_numeric(row.get('emotional_load'), errors='coerce')
            
            actual = actual_dict.get('actual_emotional')
            if actual is None:
                actual = pd.to_numeric(row.get('emotional_load'), errors='coerce')
            
            if expected is not None and not pd.isna(expected) and actual is not None and not pd.isna(actual):
                expected_actual_expected.append(float(expected))
                expected_actual_actual.append(float(actual))
                expected_actual_tasks.append(str(row.get('task_name', 'Unknown')))
                
                # Check for spikes (actual > expected + 30)
                if actual > expected + 30:
                    spikes.append({
                        'task_name': str(row.get('task_name', 'Unknown')),
                        'expected': float(expected),
                        'actual': float(actual),
                        'spike_amount': float(actual - expected),
                        'completed_at': str(row.get('completed_at', ''))
                    })
            
            # Emotion trends (time series)
            if final_emotions and isinstance(final_emotions, dict):
                completed_at = row.get('completed_at')
                if completed_at:
                    for emotion, value in final_emotions.items():
                        try:
                            value_float = float(value)
                            if emotion not in emotion_trends:
                                emotion_trends[emotion] = {'dates': [], 'values': []}
                            emotion_trends[emotion]['dates'].append(str(completed_at))
                            emotion_trends[emotion]['values'].append(value_float)
                        except (ValueError, TypeError):
                            pass
        
        # Calculate correlations (simplified - could be enhanced)
        correlations = {}
        if transitions:
            # Group by emotion and calculate basic stats
            emotion_groups = {}
            for trans in transitions:
                emotion = trans['emotion']
                if emotion not in emotion_groups:
                    emotion_groups[emotion] = {'final_values': [], 'relief_values': []}
                if trans['final_value'] is not None:
                    emotion_groups[emotion]['final_values'].append(trans['final_value'])
            
            # Match with relief values for correlation
            for emotion in emotion_groups.keys():
                # Simple placeholder correlation - could be enhanced with proper correlation calculation
                correlations[emotion] = {
                    'relief': 0.0,  # Placeholder
                    'difficulty': 0.0  # Placeholder
                }
        
        # Calculate summary metrics
        avg_emotional_load = sum(expected_actual_actual) / len(expected_actual_actual) if expected_actual_actual else 0
        avg_relief = sum(load_relief_y) / len(load_relief_y) if load_relief_y else 0
        emotion_relief_ratio = avg_relief / avg_emotional_load if avg_emotional_load > 0 else 0
        
        return {
            'avg_emotional_load': avg_emotional_load,
            'avg_relief': avg_relief,
            'spike_count': len(spikes),
            'emotion_relief_ratio': emotion_relief_ratio,
            'transitions': transitions,
            'load_relief_scatter': {
                'x': load_relief_x,
                'y': load_relief_y,
                'task_names': load_relief_tasks
            },
            'expected_actual_comparison': {
                'expected': expected_actual_expected,
                'actual': expected_actual_actual,
                'task_names': expected_actual_tasks
            },
            'emotion_trends': emotion_trends,
            'spikes': sorted(spikes, key=lambda x: x['spike_amount'], reverse=True),
            'correlations': correlations
        }

    # ------------------------------------------------------------------
    # Batched methods for performance optimization (Phase 2)
    # ------------------------------------------------------------------
    
    def get_analytics_page_data(self, days: int = 7, user_id: Optional[int] = None) -> Dict[str, any]:
        """Batched method to get all main analytics page data in one call.
        
        Combines:
        - get_dashboard_metrics()
        - get_relief_summary()
        - calculate_time_tracking_consistency_score()
        
        This reduces multiple sequential calls to a single batched call.
        
        Args:
            days: Number of days for time tracking consistency (default 7)
            user_id: User ID for data isolation
        
        Returns:
            Dict with keys: 'dashboard_metrics', 'relief_summary', 'time_tracking'
        """
        import time
        start = time.perf_counter()
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Get all three datasets (they may use caching internally)
        dashboard_metrics = self.get_dashboard_metrics(user_id=user_id)
        relief_summary = self.get_relief_summary(user_id=user_id)
        time_tracking = self.calculate_time_tracking_consistency_score(days=days, user_id=user_id)
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_analytics_page_data (batched): {duration:.2f}ms")
        
        return {
            'dashboard_metrics': dashboard_metrics,
            'relief_summary': relief_summary,
            'time_tracking': time_tracking,
        }
    
    def get_chart_data(self, user_id: Optional[int] = None) -> Dict[str, any]:
        """Batched method to get all chart data in one call.
        
        Combines:
        - trend_series()
        - attribute_distribution()
        - get_stress_dimension_data()
        
        This reduces multiple sequential calls to a single batched call.
        
        Args:
            user_id: User ID for data isolation
        
        Returns:
            Dict with keys: 'trend_series', 'attribute_distribution', 'stress_dimension_data'
        """
        import time
        start = time.perf_counter()
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Get all three chart datasets
        trend_series_df = self.trend_series(user_id=user_id)
        attribute_dist_df = self.attribute_distribution(user_id=user_id)
        stress_dimension = self.get_stress_dimension_data(user_id=user_id)
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_chart_data (batched): {duration:.2f}ms")
        
        return {
            'trend_series': trend_series_df,
            'attribute_distribution': attribute_dist_df,
            'stress_dimension_data': stress_dimension,
        }
    
    def get_rankings_data(self, top_n: int = 5, leaderboard_n: int = 10, user_id: Optional[int] = None) -> Dict[str, List[Dict[str, any]]]:
        """Batched method to get all task ranking data in one call.
        
        Combines:
        - get_task_performance_ranking() for multiple metrics
        - get_stress_efficiency_leaderboard()
        
        This reduces multiple sequential calls to a single batched call.
        
        Args:
            top_n: Number of top tasks for each ranking (default 5)
            leaderboard_n: Number of tasks for stress efficiency leaderboard (default 10)
            user_id: User ID for data isolation
        
        Returns:
            Dict with keys:
            - 'relief_ranking'
            - 'stress_efficiency_ranking'
            - 'behavioral_score_ranking'
            - 'stress_level_ranking'
            - 'stress_efficiency_leaderboard'
        """
        import time
        start = time.perf_counter()
        
        # Get user_id if not provided
        user_id = self._get_user_id(user_id)
        
        # Get all rankings in one batch
        relief_ranking = self.get_task_performance_ranking('relief', top_n=top_n, user_id=user_id)
        stress_efficiency_ranking = self.get_task_performance_ranking('stress_efficiency', top_n=top_n, user_id=user_id)
        behavioral_ranking = self.get_task_performance_ranking('behavioral_score', top_n=top_n, user_id=user_id)
        stress_level_ranking = self.get_task_performance_ranking('stress_level', top_n=top_n, user_id=user_id)
        leaderboard = self.get_stress_efficiency_leaderboard(top_n=leaderboard_n, user_id=user_id)
        
        duration = (time.perf_counter() - start) * 1000
        print(f"[Analytics] get_rankings_data (batched): {duration:.2f}ms")
        
        return {
            'relief_ranking': relief_ranking,
            'stress_efficiency_ranking': stress_efficiency_ranking,
            'behavioral_score_ranking': behavioral_ranking,
            'stress_level_ranking': stress_level_ranking,
            'stress_efficiency_leaderboard': leaderboard,
        }

    # ------------------------------------------------------------------
    # Priority heuristics (used for legacy views)
    # ------------------------------------------------------------------
    def compute_priority_score(self, instance_row: dict):
        try:
            p = float(instance_row.get('procrastination_score') or 0)
            predicted = instance_row.get('predicted') or '{}'
            pred = json.loads(predicted)
            tmin = float(pred.get('time_estimate_minutes') or pred.get('estimate') or 0)
            proact = float(instance_row.get('proactive_score') or 0)
            score = p * 1.5 + (tmin / 60.0) - (proact * 0.5)
            return round(score, 3)
        except Exception:
            return 0.0


# Library references for documentation / UI hints
SUGGESTED_ANALYTICS_LIBRARIES = [
    "Plotly Express (interactive, declarative)",
    "Altair / Vega-Lite (grammar of graphics, good for small datasets)",
    "Pandas Profiling (automatic data summaries)",
]

SUGGESTED_ML_LIBRARIES = [
    "scikit-learn (baselines, pipelines)",
    "PyTorch (deep recommenders, embeddings)",
    "LightFM (hybrid recommendation systems)",
]
