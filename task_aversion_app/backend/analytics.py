# backend/analytics.py
from __future__ import annotations

import json
import math
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from scipy import stats

from .task_schema import TASK_ATTRIBUTES, attribute_defaults
from .gap_detector import GapDetector
from .user_state import UserStateManager

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# Execution Score Formula Version
EXECUTION_SCORE_VERSION = '1.0'

# Productivity Score Formula Version
PRODUCTIVITY_SCORE_VERSION = '1.1'


class Analytics:
    """Central analytics + lightweight recommendation helper."""
    
    # Note: All inputs now use 0-100 scale natively.
    # Old data may have 0-10 scale values, but we use them as-is (no scaling).
    # This is acceptable since old 0-10 data was only used for a short time.
    
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
        completed_instances: Optional[pd.DataFrame] = None
    ) -> float:
        """Calculate overall improvement ratio from a task instance row.
        
        Helper method that extracts data from a task instance and calculates
        the overall improvement ratio using calculate_overall_improvement_ratio().
        
        Args:
            row: Task instance row with task_type, relief_score, completed_at, etc.
            avg_self_care_per_day: Average self-care tasks per day (baseline)
            avg_relief_score: Average relief score (baseline, 0-100)
            completed_instances: Optional DataFrame of all completed instances for metric calculation
        
        Returns:
            Overall improvement ratio (0.0 to 1.0)
        """
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
                    tasks_df = task_manager.get_all()
                    
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
        - Persistence component (sqrt→log growth, familiarity decay after very high counts)
        - Time bonus that weights difficulty, uses diminishing returns, and fades after many repetitions
        - Passion factor (relief vs emotional load) multiplied with persistence score
        
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
            
            # Base persistence score (before passion factor)
            persistence_score = completion_pct * persistence_multiplier * time_bonus
            grit_score = persistence_score * passion_factor
            
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
        - Popup penalty: -0.0 to -0.2 based on frequency of no-slider popups
        
        Args:
            user_id: User identifier (default: 'default')
            days: Number of days to look back for popup data (default: 30)
        
        Returns:
            Thoroughness factor (0.5 to 1.3), where 1.0 = baseline thoroughness
        """
        try:
            from .task_manager import TaskManager
            from .database import get_session, PopupTrigger
            
            task_manager = TaskManager()
            tasks_df = task_manager.get_all()
            
            if tasks_df.empty:
                return 1.0  # Default neutral factor if no tasks
            
            # Filter out test tasks
            if 'name' in tasks_df.columns:
                tasks_df = tasks_df[~tasks_df['name'].apply(lambda x: Analytics._is_test_task(x) if pd.notna(x) else False)]
            
            if tasks_df.empty:
                return 1.0
            
            total_tasks = len(tasks_df)
            
            # 1. Calculate percentage of tasks with notes
            tasks_with_notes = 0
            total_note_length = 0
            note_count = 0
            
            for _, task in tasks_df.iterrows():
                has_notes = False
                note_length = 0
                
                # Check description field
                description = str(task.get('description', '') or '').strip()
                if description:
                    has_notes = True
                    note_length += len(description)
                
                # Check notes field
                notes = str(task.get('notes', '') or '').strip()
                if notes:
                    has_notes = True
                    note_length += len(notes)
                
                if has_notes:
                    tasks_with_notes += 1
                    total_note_length += note_length
                    note_count += 1
            
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
                    
                    # Normalize penalty: 0 popups = 0.0, 10+ popups = -0.2 penalty
                    # Using exponential decay for diminishing penalty
                    if popup_count > 0:
                        # Scale: 0-10 popups maps to 0.0 to -0.2 penalty
                        popup_ratio = min(1.0, popup_count / 10.0)
                        popup_penalty = -0.2 * (1.0 - math.exp(-popup_ratio * 2.0))  # Exponential decay
            except Exception as e:
                # If database access fails, skip popup penalty
                print(f"[Analytics] Could not access popup data for thoroughness factor: {e}")
                popup_penalty = 0.0
            
            # Combine factors
            thoroughness_factor = base_factor + length_bonus + popup_penalty
            
            # Clamp to reasonable range (0.5 to 1.3)
            thoroughness_factor = max(0.5, min(1.3, thoroughness_factor))
            
            return float(thoroughness_factor)
        
        except Exception as e:
            print(f"[Analytics] Error calculating thoroughness factor: {e}")
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
    
    def _load_instances(self) -> pd.DataFrame:
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
            try:
                from backend.database import get_session, TaskInstance
                session = get_session()
                try:
                    instances = session.query(TaskInstance).all()
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
                    stress_norm = pd.to_numeric(df['stress_level'], errors='coerce').fillna(50.0)
                    relief_norm = pd.to_numeric(df['relief_score_numeric'], errors='coerce').fillna(50.0)
                    correlation_raw = (relief_norm - stress_norm + 100.0) / 2.0
                    df['stress_relief_correlation_score'] = correlation_raw.clip(0.0, 100.0).round(2)
                    
                    # Calculate behavioral_score (simplified version - full version is in CSV path)
                    def _calculate_behavioral_score(row):
                        try:
                            behavioral = row.get('behavioral_score')
                            if behavioral and str(behavioral).strip():
                                return pd.to_numeric(behavioral, errors='coerce')
                            return pd.NA
                        except (KeyError, TypeError, ValueError):
                            return pd.NA
                    
                    df['behavioral_score'] = df.apply(_calculate_behavioral_score, axis=1)
                    
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
        return df

    # ------------------------------------------------------------------
    # Dashboard summaries
    # ------------------------------------------------------------------
    def active_summary(self) -> Dict[str, Optional[str]]:
        df = self._load_instances()
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

    def get_dashboard_metrics(self) -> Dict[str, Dict[str, Optional[float]]]:
        df = self._load_instances()
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
        completed = df[df['completed_at'].astype(str).str.len() > 0]
        completed_7d = completed[
            pd.to_datetime(completed['completed_at']) >= datetime.now() - pd.Timedelta(days=7)
        ]

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
        
        # Calculate life balance
        life_balance = self.get_life_balance()
        
        # Calculate daily work volume metrics
        work_volume_metrics = self.get_daily_work_volume_metrics(days=30)
        avg_daily_work_time = work_volume_metrics.get('avg_daily_work_time', 0.0)
        work_volume_score = work_volume_metrics.get('work_volume_score', 0.0)
        work_consistency_score = work_volume_metrics.get('work_consistency_score', 50.0)
        
        # Calculate average efficiency score for productivity potential
        efficiency_summary = self.get_efficiency_summary()
        avg_efficiency_score = efficiency_summary.get('avg_efficiency', 0.0)
        
        # Calculate productivity potential (target: 6 hours/day = 360 minutes)
        productivity_potential = self.calculate_productivity_potential(
            avg_efficiency_score=avg_efficiency_score,
            avg_daily_work_time=avg_daily_work_time,
            target_hours_per_day=360.0
        )
        
        # Calculate composite productivity score
        composite_productivity = self.calculate_composite_productivity_score(
            efficiency_score=avg_efficiency_score,
            volume_score=work_volume_score,
            consistency_score=work_consistency_score
        )
        
        # Calculate thoroughness/notetaking score
        thoroughness_score = self.calculate_thoroughness_score(user_id='default', days=30)
        thoroughness_factor = self.calculate_thoroughness_factor(user_id='default', days=30)
        
        # Calculate daily self care tasks metrics
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all()
        
        daily_self_care_tasks = 0
        avg_daily_self_care_tasks = 0.0
        
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
        
        metrics = {
            'counts': {
                'active': int(len(active)),
                'completed_7d': int(len(completed_7d)),
                'total_created': int(total_created),
                'total_completed': int(total_completed),
                'completion_rate': round(completion_rate, 1),
                'daily_self_care_tasks': daily_self_care_tasks,
                'avg_daily_self_care_tasks': avg_daily_self_care_tasks,
            },
            'quality': {
                'avg_relief': _avg(df['relief_score']),
                'avg_cognitive_load': _avg(df['cognitive_load']),
                'avg_stress_level': _avg(df['stress_level']),
                'avg_net_wellbeing': _avg(df['net_wellbeing']),
                'avg_net_wellbeing_normalized': _avg(df['net_wellbeing_normalized']),
                'avg_stress_efficiency': _avg(df['stress_efficiency']),
                'avg_aversion': round(avg_aversion_completed, 1),
                'adjusted_wellbeing': round(adjusted_wellbeing, 2),
                'adjusted_wellbeing_normalized': round(adjusted_wellbeing_normalized, 2),
                'thoroughness_score': round(thoroughness_score, 1),
                'thoroughness_factor': round(thoroughness_factor, 3),
            },
            'time': {
                'median_duration': _median(df['duration_minutes']),
                'avg_delay': _avg(df['delay_minutes']),
                'estimation_accuracy': round(time_accuracy, 2),
            },
            'life_balance': life_balance,
            'aversion': {
                'general_aversion_score': round(general_aversion_score, 1),
            },
            'productivity_volume': {
                'avg_daily_work_time': round(avg_daily_work_time, 1),
                'work_volume_score': round(work_volume_score, 1),
                'work_consistency_score': round(work_consistency_score, 1),
                'productivity_potential_score': round(productivity_potential.get('potential_score', 0.0), 1),
                'work_volume_gap': round(productivity_potential.get('gap_hours', 0.0), 1),
                'composite_productivity_score': round(composite_productivity, 1),
            },
        }
        return metrics

    def get_life_balance(self) -> Dict[str, any]:
        """Calculate life balance metric comparing work and play task amounts.
        
        Returns:
            Dict with work_count, play_count, work_time_minutes, play_time_minutes,
            balance_score (0-100, where 50 = balanced), and ratio
        """
        df = self._load_instances()
        
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
        tasks_df = task_manager.get_all()
        
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

    def get_daily_work_volume_metrics(self, days: int = 30) -> Dict[str, any]:
        """Calculate daily work volume metrics including average work time, volume score, and consistency.
        
        Args:
            days: Number of days to analyze (default 30)
            
        Returns:
            Dict with avg_daily_work_time, work_volume_score (0-100), work_consistency_score (0-100),
            daily_work_times (list of daily work times), and work_days_count
        """
        df = self._load_instances()
        
        if df.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'work_days_count': 0,
            }
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all()
        
        if tasks_df.empty or 'task_type' not in tasks_df.columns:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'work_days_count': 0,
            }
        
        # Join instances with tasks to get task_type
        merged = df.merge(
            tasks_df[['task_id', 'task_type']],
            on='task_id',
            how='left'
        )
        
        # Filter to completed work tasks only
        completed = merged[merged['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'work_days_count': 0,
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
                'work_days_count': 0,
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
                'work_days_count': 0,
            }
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_work = work_tasks[work_tasks['completed_at_dt'] >= cutoff_date].copy()
        
        if recent_work.empty:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'work_days_count': 0,
            }
        
        # Group by date and sum work time per day
        recent_work['date'] = recent_work['completed_at_dt'].dt.date
        daily_work = recent_work.groupby('date')['duration_numeric'].sum()
        
        daily_work_times = [float(time) for time in daily_work.values if time > 0]
        work_days_count = len(daily_work_times)
        
        if work_days_count == 0:
            return {
                'avg_daily_work_time': 0.0,
                'work_volume_score': 0.0,
                'work_consistency_score': 50.0,
                'daily_work_times': [],
                'work_days_count': 0,
            }
        
        # Calculate average daily work time
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
        # Lower variance = higher consistency score
        if len(daily_work_times) > 1:
            variance = np.var(daily_work_times)
            # Normalize variance: assume max reasonable variance is 4 hours (240 min) squared
            # Lower variance = higher score
            max_variance = 240.0 ** 2
            consistency_score = max(0.0, min(100.0, 100.0 * (1.0 - min(1.0, variance / max_variance))))
        else:
            # Single day = perfect consistency
            consistency_score = 100.0
        
        return {
            'avg_daily_work_time': round(float(avg_daily_work_time), 1),
            'work_volume_score': round(float(work_volume_score), 1),
            'work_consistency_score': round(float(consistency_score), 1),
            'daily_work_times': daily_work_times,
            'work_days_count': work_days_count,
        }

    def calculate_productivity_potential(self, avg_efficiency_score: float, avg_daily_work_time: float, 
                                         target_hours_per_day: float = 360.0) -> Dict[str, any]:
        """Calculate productivity potential based on current efficiency and target work time.
        
        Args:
            avg_efficiency_score: Average efficiency score from completed tasks
            avg_daily_work_time: Current average daily work time in minutes
            target_hours_per_day: Target work hours per day in minutes (default 360 = 6 hours)
            
        Returns:
            Dict with potential_score, current_score, multiplier, and gap_hours
        """
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
        target_sleep_hours: float = 8.0
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
            
        Returns:
            Dict with:
            - tracking_consistency_score (0-100): Overall score
            - avg_tracked_time_minutes: Average tracked time per day
            - avg_untracked_time_minutes: Average untracked time per day
            - avg_sleep_time_minutes: Average sleep time per day
            - tracking_coverage: Proportion of day tracked (0-1)
            - daily_scores: List of daily scores
        """
        df = self._load_instances()
        
        if df.empty:
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
        tasks_df = task_manager.get_all()
        
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
        
        return {
            'tracking_consistency_score': round(float(overall_score), 1),
            'avg_tracked_time_minutes': round(float(avg_tracked), 1),
            'avg_untracked_time_minutes': round(float(avg_untracked), 1),
            'avg_sleep_time_minutes': round(float(avg_sleep), 1),
            'tracking_coverage': round(float(avg_coverage), 3),
            'daily_scores': [round(float(s), 1) for s in daily_scores],
        }

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

    def calculate_composite_productivity_score(self, efficiency_score: float, volume_score: float, 
                                                consistency_score: float) -> float:
        """Calculate composite productivity score combining efficiency, volume, and consistency.
        
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

    def get_all_scores_for_composite(self, days: int = 7) -> Dict[str, float]:
        """Get all available scores, bonuses, and penalties for composite score calculation.
        
        Returns a dictionary of component_name -> score_value that can be used
        with calculate_composite_score().
        
        Args:
            days: Number of days to analyze for time-based metrics
            
        Returns:
            Dict with component_name -> score_value (0-100 range where applicable)
        """
        scores = {}
        
        # Get dashboard metrics
        metrics = self.get_dashboard_metrics()
        
        # Quality scores (0-100 range)
        quality = metrics.get('quality', {})
        scores['avg_stress_level'] = 100.0 - float(quality.get('avg_stress_level', 50.0))  # Invert: lower stress = higher score
        scores['avg_net_wellbeing'] = float(quality.get('avg_net_wellbeing_normalized', 50.0))
        scores['avg_stress_efficiency'] = float(quality.get('avg_stress_efficiency', 50.0)) if quality.get('avg_stress_efficiency') is not None else 50.0
        scores['avg_relief'] = float(quality.get('avg_relief', 50.0))
        
        # Productivity scores
        productivity_volume = metrics.get('productivity_volume', {})
        scores['work_volume_score'] = float(productivity_volume.get('work_volume_score', 0.0))
        scores['work_consistency_score'] = float(productivity_volume.get('work_consistency_score', 50.0))
        
        # Life balance
        life_balance = metrics.get('life_balance', {})
        scores['life_balance_score'] = float(life_balance.get('balance_score', 50.0))
        
        # Relief summary
        relief_summary = self.get_relief_summary()
        # Normalize weekly relief to 0-100 (assuming typical range 0-1000)
        weekly_relief = float(relief_summary.get('weekly_relief_score_with_bonus_robust', 0.0))
        scores['weekly_relief_score'] = min(100.0, weekly_relief / 10.0)  # Scale down if needed
        
        # Time tracking consistency score
        tracking_data = self.calculate_time_tracking_consistency_score(days=days)
        scores['tracking_consistency_score'] = float(tracking_data.get('tracking_consistency_score', 0.0))
        
        # Counts (normalize to 0-100)
        counts = metrics.get('counts', {})
        completion_rate = float(counts.get('completion_rate', 0.0))
        scores['completion_rate'] = completion_rate  # Already 0-100
        
        # Self-care frequency (normalize: assume 0-5 tasks/day = 0-100)
        avg_self_care = float(counts.get('avg_daily_self_care_tasks', 0.0))
        scores['self_care_frequency'] = min(100.0, avg_self_care * 20.0)  # 5 tasks = 100 score
        
        # Execution score (average of recent completed instances)
        try:
            from .instance_manager import InstanceManager
            instance_manager = InstanceManager()
            recent_instances = instance_manager.list_recent_completed(limit=100)
            execution_scores = []
            
            for instance in recent_instances:
                execution_score = self.calculate_execution_score(instance)
                if execution_score is not None:
                    execution_scores.append(execution_score)
            
            avg_execution_score = sum(execution_scores) / len(execution_scores) if execution_scores else 50.0
            scores['execution_score'] = avg_execution_score
        except Exception as e:
            # If execution score calculation fails, use neutral score
            print(f"[Analytics] Error calculating execution score: {e}")
            scores['execution_score'] = 50.0
        
        return scores

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

    def calculate_execution_score(
        self,
        row: Union[pd.Series, Dict],
        task_completion_counts: Optional[Dict[str, int]] = None
    ) -> float:
        """Calculate execution score (0-100) for efficient execution of difficult tasks.
        
        **Formula Version: 1.0**
        
        Combines four component factors:
        1. Difficulty factor: High aversion + high load
        2. Speed factor: Fast execution relative to estimate
        3. Start speed factor: Fast start after initialization (procrastination resistance)
        4. Completion factor: Full completion (100% or close)
        
        Formula: execution_score = base_score * (1.0 + difficulty_factor) * 
                                   (0.5 + speed_factor * 0.5) * 
                                   (0.5 + start_speed_factor * 0.5) * 
                                   completion_factor
        
        See: docs/execution_module_v1.0.md for complete formula documentation.
        
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
        
        # Combined Formula
        # Base score: 50 points (neutral)
        base_score = 50.0
        
        # Apply factors multiplicatively (all must be high for high score)
        execution_score = base_score * (
            (1.0 + difficulty_factor) *      # 1.0-2.0 range (difficulty boost)
            (0.5 + speed_factor * 0.5) *     # 0.5-1.0 range (speed boost)
            (0.5 + start_speed_factor * 0.5) *  # 0.5-1.0 range (start speed boost)
            completion_factor                # 0.0-1.0 range (completion quality)
        )
        
        # Normalize to 0-100 range
        execution_score = max(0.0, min(100.0, execution_score))
        
        return execution_score

    def get_relief_summary(self) -> Dict[str, any]:
        """Calculate relief points, productivity time, and relief statistics."""
        df = self._load_instances()
        
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
        
        # Extract expected relief from predicted_dict
        # predicted_dict is a Series, so we need to access it properly
        def _get_expected_relief(row):
            try:
                pred_dict = row['predicted_dict']
                if isinstance(pred_dict, dict):
                    return pred_dict.get('expected_relief', None)
            except (KeyError, TypeError):
                pass
            return None
        
        def _get_initial_aversion(row):
            """Get initial aversion from predicted_dict."""
            try:
                pred_dict = row['predicted_dict']
                if isinstance(pred_dict, dict):
                    return pred_dict.get('initial_aversion', None)
            except (KeyError, TypeError):
                pass
            return None
        
        def _get_expected_aversion(row):
            """Get expected aversion from predicted_dict."""
            try:
                pred_dict = row['predicted_dict']
                if isinstance(pred_dict, dict):
                    return pred_dict.get('expected_aversion', None)
            except (KeyError, TypeError):
                pass
            return None
        
        completed['expected_relief'] = completed.apply(_get_expected_relief, axis=1)
        completed['expected_relief'] = pd.to_numeric(completed['expected_relief'], errors='coerce')
        
        # Get initial and expected aversion
        completed['initial_aversion'] = completed.apply(_get_initial_aversion, axis=1)
        completed['initial_aversion'] = pd.to_numeric(completed['initial_aversion'], errors='coerce')
        completed['expected_aversion'] = completed.apply(_get_expected_aversion, axis=1)
        completed['expected_aversion'] = pd.to_numeric(completed['expected_aversion'], errors='coerce')
        
        # Get actual relief from actual_dict (from completion page), not from relief_score column
        # This ensures we get the actual value even if CSV column was previously overwritten
        def _get_actual_relief(row):
            try:
                actual_dict = row['actual_dict']
                if isinstance(actual_dict, dict):
                    return actual_dict.get('actual_relief', None)
            except (KeyError, TypeError):
                pass
            # Fallback to relief_score column if actual_dict doesn't have it
            try:
                return row.get('relief_score')
            except (KeyError, TypeError):
                pass
            return None
        
        completed['actual_relief'] = completed.apply(_get_actual_relief, axis=1)
        completed['actual_relief'] = pd.to_numeric(completed['actual_relief'], errors='coerce')
        
        # Filter to rows where we have both expected and actual relief
        has_both = completed['expected_relief'].notna() & completed['actual_relief'].notna()
        relief_data = completed[has_both].copy()
        
        # Calculate default relief points (actual - expected, can be negative)
        relief_data['default_relief_points'] = relief_data['actual_relief'] - relief_data['expected_relief']
        
        # Apply aversion multipliers to relief points
        def _apply_aversion_multiplier(row):
            """Apply aversion-based multiplier to relief points."""
            initial_av = row.get('initial_aversion')
            expected_av = row.get('expected_aversion')
            # Use expected_aversion as current_aversion (what was set during initialization)
            aversion_mult = self.calculate_aversion_multiplier(initial_av, expected_av)
            return row['default_relief_points'] * aversion_mult
        
        relief_data['default_relief_points'] = relief_data.apply(_apply_aversion_multiplier, axis=1)
        
        # Calculate net relief points (calibrated):
        # - 0 for negative net relief (when actual < expected)
        # - actual - expected for positive (when actual >= expected)
        # - For negative cases, store the negative value separately
        relief_data['net_relief_points'] = relief_data.apply(
            lambda row: max(0.0, row['default_relief_points']), axis=1
        )
        relief_data['negative_relief_points'] = relief_data.apply(
            lambda row: min(0.0, row['default_relief_points']), axis=1
        )
        
        # Calculate productivity time (sum of actual time from actual_dict) - LAST 7 DAYS ONLY
        # Productivity includes only Work and Self care tasks, not Play tasks
        from datetime import timedelta
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # Prepare completed tasks with date for later use (includes ALL tasks for relief score)
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        
        # Load tasks to get task_type
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all()
        
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
        
        # Apply task type multipliers to relief points
        def _apply_task_type_multiplier(row):
            """Apply task type multiplier to relief points."""
            task_type = row.get('task_type')
            type_mult = self.get_task_type_multiplier(task_type)
            return row['default_relief_points'] * type_mult
        
        relief_data['default_relief_points'] = relief_data.apply(_apply_task_type_multiplier, axis=1)
        
        def _get_actual_time(row):
            try:
                actual_dict = row['actual_dict']
                if isinstance(actual_dict, dict):
                    return actual_dict.get('time_actual_minutes', None)
            except (KeyError, TypeError):
                pass
            return None
        
        productivity_tasks['time_actual'] = productivity_tasks.apply(_get_actual_time, axis=1)
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
        
        # Get efficiency summary
        efficiency_summary = self.get_efficiency_summary()
        
        # Filter out test/dev tasks from obstacles calculation
        # Keep all tasks for relief calculations, but exclude test tasks from obstacles
        if 'task_name' in relief_data.columns:
            relief_data_for_obstacles = relief_data[
                ~relief_data['task_name'].apply(self._is_test_task)
            ].copy()
        else:
            relief_data_for_obstacles = relief_data.copy()
        
        # Calculate obstacles overcome scores
        from .instance_manager import InstanceManager
        im = InstanceManager()
        
        # Add baseline aversion (both robust and sensitive) to relief_data_for_obstacles
        def _get_baseline_aversion_robust(row):
            task_id = row.get('task_id')
            if task_id:
                try:
                    return im.get_baseline_aversion_robust(task_id)
                except Exception as e:
                    print(f"[Analytics] Error getting baseline_aversion_robust for task {task_id}: {e}")
                    return None
            return None
        
        def _get_baseline_aversion_sensitive(row):
            task_id = row.get('task_id')
            if task_id:
                try:
                    return im.get_baseline_aversion_sensitive(task_id)
                except Exception as e:
                    print(f"[Analytics] Error getting baseline_aversion_sensitive for task {task_id}: {e}")
                    return None
            return None
        
        try:
            relief_data_for_obstacles['baseline_aversion_robust'] = relief_data_for_obstacles.apply(_get_baseline_aversion_robust, axis=1)
            relief_data_for_obstacles['baseline_aversion_sensitive'] = relief_data_for_obstacles.apply(_get_baseline_aversion_sensitive, axis=1)
        except Exception as e:
            print(f"[Analytics] Error calculating baseline aversion: {e}")
            # Set default values if calculation fails
            relief_data_for_obstacles['baseline_aversion_robust'] = None
            relief_data_for_obstacles['baseline_aversion_sensitive'] = None
        
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
        
        # Extract individual scores for backward compatibility and new analytics
        score_variants = ['expected_only', 'actual_only', 'minimum', 'average', 'net_penalty', 'net_bonus', 'net_weighted']
        for variant in score_variants:
            relief_data_for_obstacles[f'obstacles_score_{variant}_robust'] = relief_data_for_obstacles['obstacles_scores_robust'].apply(
                lambda x: x.get(variant, 0.0) if isinstance(x, dict) else 0.0
            )
            relief_data_for_obstacles[f'obstacles_score_{variant}_sensitive'] = relief_data_for_obstacles['obstacles_scores_sensitive'].apply(
                lambda x: x.get(variant, 0.0) if isinstance(x, dict) else 0.0
            )
        
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
            relief_data_last_7d['spike_amount_robust'] = relief_data_last_7d.apply(_get_max_spike_robust, axis=1)
            relief_data_last_7d['spike_amount_sensitive'] = relief_data_last_7d.apply(_get_max_spike_sensitive, axis=1)
            max_spike_robust = relief_data_last_7d['spike_amount_robust'].max() if 'spike_amount_robust' in relief_data_last_7d.columns else 0.0
            max_spike_sensitive = relief_data_last_7d['spike_amount_sensitive'].max() if 'spike_amount_sensitive' in relief_data_last_7d.columns else 0.0
        else:
            max_spike_robust = 0.0
            max_spike_sensitive = 0.0
        
        # Calculate weekly bonus multipliers
        weekly_bonus_multiplier_robust = self.calculate_obstacles_bonus_multiplier(max_spike_robust)
        weekly_bonus_multiplier_sensitive = self.calculate_obstacles_bonus_multiplier(max_spike_sensitive)
        
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
        
        # Calculate multipliers for each task
        def _calculate_relief_multiplier(row):
            """Calculate combined aversion and task type multiplier for relief."""
            initial_av = row.get('initial_aversion')
            expected_av = row.get('expected_aversion')
            task_type = row.get('task_type')
            
            aversion_mult = self.calculate_aversion_multiplier(initial_av, expected_av)
            type_mult = self.get_task_type_multiplier(task_type)
            
            return aversion_mult * type_mult
        
        completed['relief_multiplier'] = completed.apply(_calculate_relief_multiplier, axis=1)
        
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
        weekly_relief_score_robust = weekly_relief_score_base * weekly_bonus_multiplier_robust
        weekly_relief_score_sensitive = weekly_relief_score_base * weekly_bonus_multiplier_sensitive
        
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
        
        def _calculate_productivity_multiplier(row):
            """Calculate productivity multiplier (work: 2.0, self care: 1.0)."""
            task_type = row.get('task_type', 'Work')
            task_type_lower = str(task_type).strip().lower()
            
            if task_type_lower == 'work':
                return 2.0
            elif task_type_lower in ['self care', 'selfcare', 'self-care']:
                return 1.0
            else:
                return 1.0
        
        if not productivity_relief_data.empty:
            productivity_relief_data['productivity_multiplier'] = productivity_relief_data.apply(_calculate_productivity_multiplier, axis=1)
            # Productivity points: we need to undo the relief task_type_multiplier and apply productivity multiplier instead
            # default_relief_points already has: (actual - expected) × aversion_mult × relief_task_type_mult
            # We want: (actual - expected) × aversion_mult × productivity_mult
            # So: productivity_points = default_relief_points / relief_task_type_mult × productivity_mult
            def _get_relief_task_type_mult(row):
                """Get the relief task type multiplier that was already applied."""
                task_type = row.get('task_type')
                return self.get_task_type_multiplier(task_type)
            
            productivity_relief_data['relief_task_type_mult'] = productivity_relief_data.apply(_get_relief_task_type_mult, axis=1)
            # Calculate base points without task type multiplier
            # Avoid division by zero - if relief_task_type_mult is 0 or very small, use default_relief_points directly
            productivity_relief_data['base_relief_points'] = productivity_relief_data.apply(
                lambda row: (
                    row['default_relief_points'] / row['relief_task_type_mult'] 
                    if row['relief_task_type_mult'] > 0.01 
                    else row['default_relief_points']
                ),
                axis=1
            )
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
            weekly_productivity_points_robust = weekly_productivity_points_base * weekly_bonus_multiplier_robust
            weekly_productivity_points_sensitive = weekly_productivity_points_base * weekly_bonus_multiplier_sensitive
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
                tasks_df = task_manager.get_all()
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
            goal_settings = UserStateManager().get_productivity_goal_settings("default_user")
            goal_hours_per_week = goal_settings.get('goal_hours_per_week')
            if goal_hours_per_week:
                goal_hours_per_week = float(goal_hours_per_week)
                # Calculate weekly productive hours (Work + Self Care only)
                from .productivity_tracker import ProductivityTracker
                tracker = ProductivityTracker()
                weekly_data = tracker.calculate_weekly_productivity_hours("default_user")
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
        
        return {
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
            'weekly_obstacles_bonus_multiplier_robust': round(float(weekly_bonus_multiplier_robust), 3),
            'weekly_obstacles_bonus_multiplier_sensitive': round(float(weekly_bonus_multiplier_sensitive), 3),
            'max_obstacle_spike_robust': round(float(max_spike_robust), 1),
            'max_obstacle_spike_sensitive': round(float(max_spike_sensitive), 1),
            # Aversion analytics: all score variants for comparison
            **{k: round(float(v), 2) for k, v in obstacles_totals.items()},
        }

    def get_weekly_hours_history(self) -> Dict[str, any]:
        """Get historical daily productivity hours data for trend analysis (last 90 days).
        
        Productivity includes only Work and Self care tasks, not Play tasks.
        
        Returns:
            Dict with 'dates' (list of date strings), 'hours' (list of hours per day),
            'current_value' (float), 'weekly_average' (float), 'three_month_average' (float)
        """
        df = self._load_instances()
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
        tasks_df = task_manager.get_all()
        
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
        df = self._load_instances()
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
        df = self._load_instances()
        
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
        df = self._load_instances()
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

    def get_task_efficiency_history(self) -> Dict[str, float]:
        """Get average efficiency score per task based on completed instances.
        
        Returns {task_id: avg_efficiency_score}
        Useful for recommending tasks that have historically been efficient.
        """
        df = self._load_instances()
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

    def get_task_performance_ranking(self, metric: str = 'relief', top_n: int = 5) -> List[Dict[str, any]]:
        """Get top/bottom performing tasks by various metrics.
        
        Args:
            metric: 'relief', 'stress_efficiency', 'behavioral_score', 'stress_level'
            top_n: Number of top tasks to return
        
        Returns:
            List of dicts with task_id, task_name, metric_value, and count
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return []
        
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
            return []
        
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
        
        return result

    def get_stress_efficiency_leaderboard(self, top_n: int = 10) -> List[Dict[str, any]]:
        """Get tasks with highest stress efficiency (relief per unit of stress).
        
        Args:
            top_n: Number of top tasks to return
        
        Returns:
            List of dicts with task_id, task_name, stress_efficiency, avg_relief, avg_stress, and count
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return []
        
        # Filter to tasks with valid stress efficiency
        valid = completed[completed['stress_efficiency'].notna() & (completed['stress_efficiency'] > 0)].copy()
        
        if valid.empty:
            return []
        
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

    def recommendations(self, filters: Optional[Dict[str, float]] = None) -> List[Dict[str, str]]:
        """Generate recommendations based on all task templates, using historical data from completed instances."""
        from .task_manager import TaskManager
        
        filters = {**self.default_filters(), **(filters or {})}
        print(f"[Analytics] recommendations called with filters: {filters}")
        
        # Load all task templates
        task_manager = TaskManager()
        all_tasks_df = task_manager.get_all()
        if all_tasks_df.empty:
            return []
        
        # Load historical instance data to inform recommendations
        instances_df = self._load_instances()
        
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

    def recommendations_by_category(self, metrics: Union[str, List[str]], filters: Optional[Dict[str, float]] = None, limit: int = 3) -> List[Dict[str, str]]:
        """Generate recommendations ranked by a set of metrics.

        metrics can be a single metric name or a list. Each metric contributes to
        the score; high-is-good metrics add their value, and low-is-good metrics
        add (100 - value) to prioritize lower numbers.
        """
        from .task_manager import TaskManager
        
        filters = {**self.default_filters(), **(filters or {})}
        print(f"[Analytics] recommendations_by_category called with metrics: {metrics}, limit: {limit}, filters: {filters}")
        
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
        
        # Load all task templates
        task_manager = TaskManager()
        all_tasks_df = task_manager.get_all()
        if all_tasks_df.empty:
            return []
        
        # Load historical instance data to inform recommendations
        instances_df = self._load_instances()
        
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
        print(f"[Analytics] recommendations_by_category: {len(candidates)} candidates, taking top {len(top_n)} after sorting")
        if len(top_n) > 0:
            print(f"[Analytics] Top recommendation scores: {top_n['score'].tolist()}")
            print(f"[Analytics] Top recommendation normalized scores: {top_n['score_normalized'].tolist()}")
        
        ranked = []
        for idx, (_, row) in enumerate(top_n.iterrows()):
            print(f"[Analytics] Processing recommendation {idx + 1}: {row.get('task_name')} (score: {row.get('score')}, normalized: {row.get('score_normalized')})")
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
            print(f"[Analytics] Added recommendation {idx + 1} to ranked list: {row.get('task_name')}")
        
        print(f"[Analytics] recommendations_by_category: Returning {len(ranked)} ranked recommendations")
        return ranked

    def recommendations_from_instances(self, metrics: Union[str, List[str]], filters: Optional[Dict[str, float]] = None, limit: int = 3) -> List[Dict[str, str]]:
        """Generate recommendations from initialized (non-completed) task instances.
        
        Similar to recommendations_by_category but works with active instances instead of templates.
        
        Args:
            metrics: Single metric name or list of metrics to rank by
            filters: Optional filters (min_duration, max_duration, task_type, etc.)
            limit: Maximum number of recommendations to return
        
        Returns:
            List of recommendation dicts with instance_id, task_name, score, and metric_values
        """
        from .instance_manager import InstanceManager
        
        filters = {**self.default_filters(), **(filters or {})}
        print(f"[Analytics] recommendations_from_instances called with metrics: {metrics}, limit: {limit}, filters: {filters}")
        
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
        
        # Get all active (non-completed) instances
        instance_manager = InstanceManager()
        active_instances = instance_manager.list_active_instances()
        
        if not active_instances:
            return []
        
        # Load task templates to get task metadata
        from .task_manager import TaskManager
        task_manager = TaskManager()
        tasks_df = task_manager.get_all()
        
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
        instances_df = self._load_instances()
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
            print(f"[Analytics] Processing recommendation {idx + 1}: {row.get('task_name')} (score: {row.get('score')}, normalized: {row.get('score_normalized')})")
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
            print(f"[Analytics] Added recommendation {len(ranked)} to ranked list: {row.get('task_name')}")
        
        print(f"[Analytics] recommendations_from_instances: Returning {len(ranked)} ranked recommendations")
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
    def trend_series(self) -> pd.DataFrame:
        df = self._load_instances()
        if df.empty:
            return pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])
        completed = df[df['completed_at'].astype(str).str.len() > 0]
        if completed.empty:
            return pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])

        # Ensure datetime and numeric relief
        completed = completed.copy()
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed[completed['completed_at_dt'].notna()]
        completed['relief_score_numeric'] = pd.to_numeric(completed['relief_score'], errors='coerce').fillna(0.0)

        if completed.empty:
            return pd.DataFrame(columns=['completed_at', 'daily_relief_score', 'cumulative_relief_score'])

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

        return daily[['completed_at', 'daily_relief_score', 'cumulative_relief_score']]

    def attribute_distribution(self) -> pd.DataFrame:
        df = self._load_instances()
        if df.empty:
            return pd.DataFrame(columns=['attribute', 'value'])
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
            return pd.DataFrame(columns=['attribute', 'value'])
        return pd.concat(melted_frames, ignore_index=True)

    # ------------------------------------------------------------------
    # Trends and correlation helpers
    # ------------------------------------------------------------------
    def get_attribute_trends(self, attribute_key: str, aggregation: str = 'mean', days: int = 90) -> Dict[str, any]:
        """Return daily aggregated values for a single attribute."""
        df = self._load_instances()
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
            tasks_df = task_manager.get_all()
            
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
                goal_settings = UserStateManager().get_productivity_goal_settings("default_user")
                goal_hours_per_week = goal_settings.get('goal_hours_per_week')
                if goal_hours_per_week:
                    goal_hours_per_week = float(goal_hours_per_week)
                    from .productivity_tracker import ProductivityTracker
                    tracker = ProductivityTracker()
                    weekly_data = tracker.calculate_weekly_productivity_hours("default_user")
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
        elif attribute_key == 'daily_self_care_tasks':
            # Calculate daily self care tasks count
            from .task_manager import TaskManager
            task_manager = TaskManager()
            tasks_df = task_manager.get_all()
            
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
                completed = self._load_instances()
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
    ) -> Dict[str, Dict[str, any]]:
        """Return trends for multiple attributes; optionally normalize each series (min-max)."""
        trends = {}
        attribute_keys = attribute_keys or []
        for key in attribute_keys:
            data = self.get_attribute_trends(key, aggregation, days)
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
        return trends

    def get_stress_dimension_data(self) -> Dict[str, Dict[str, float]]:
        """
        Calculate stress dimension values for cognitive, emotional, and physical stress.
        Returns dictionary with totals, 7-day averages, and daily values for each dimension.
        """
        df = self._load_instances()
        completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
        
        if completed.empty:
            return {
                'cognitive': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'emotional': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
                'physical': {'total': 0.0, 'avg_7d': 0.0, 'daily': []},
            }
        
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
        
        return {
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

    def calculate_correlation(self, attribute_x: str, attribute_y: str, method: str = 'pearson') -> Dict[str, any]:
        """Calculate correlation between two attributes with metadata for tooltips."""
        df = self._load_instances()
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

    def find_threshold_relationships(self, dependent_var: str, independent_var: str, bins: int = 10) -> Dict[str, any]:
        """Bin independent variable and summarize dependent averages to surface threshold ranges."""
        df = self._load_instances()
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

    def get_scatter_data(self, attribute_x: str, attribute_y: str) -> Dict[str, any]:
        """Return paired scatter values for two attributes.
        
        Supports calculated metrics like productivity_score and grit_score by computing them on-the-fly.
        """
        
        df = self._load_instances()
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
                goal_settings = UserStateManager().get_productivity_goal_settings("default_user")
                goal_hours_per_week = goal_settings.get('goal_hours_per_week')
                if goal_hours_per_week:
                    goal_hours_per_week = float(goal_hours_per_week)
                    from .productivity_tracker import ProductivityTracker
                    tracker = ProductivityTracker()
                    weekly_data = tracker.calculate_weekly_productivity_hours("default_user")
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
            tasks_df = task_manager.get_all()
            
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

    def get_emotional_flow_data(self) -> Dict[str, any]:
        """Get comprehensive emotional flow data for analytics.
        
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
        df = self._load_instances()
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
