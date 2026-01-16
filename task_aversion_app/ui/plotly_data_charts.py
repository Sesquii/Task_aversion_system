"""
Plotly chart generators for data-driven visualizations.
These generate interactive charts dynamically with fresh user data.
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import json
import math
import pandas as pd
from typing import Optional, Dict, List, Tuple


def get_user_instances(limit=100):
    """Get user's task instances for visualization."""
    try:
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.normpath(os.path.join(script_dir, '..'))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from backend.instance_manager import InstanceManager
        from backend.analytics import Analytics
        from backend.auth import get_current_user
        
        instance_manager = InstanceManager()
        analytics = Analytics()
        
        # Get current user for data isolation
        current_user_id = get_current_user()
        
        instances = instance_manager.list_recent_completed(limit=limit, user_id=current_user_id)
        return instances, analytics
    except Exception as e:
        print(f"[PlotlyCharts] Error loading instances: {e}")
        return [], None


def calculate_weekly_multiplier(time_percentage_diff, curve_type='flattened_square', strength=1.0):
    """Calculate weekly average multiplier."""
    if curve_type == 'flattened_square':
        effect = math.copysign((abs(time_percentage_diff) ** 2) / 100.0, time_percentage_diff)
        multiplier = 1.0 - (0.01 * strength * effect)
    else:  # linear
        multiplier = 1.0 - (0.01 * strength * time_percentage_diff)
    return max(0.5, min(1.5, multiplier))


def calculate_goal_multiplier(goal_achievement_ratio):
    """Calculate goal-based multiplier."""
    if goal_achievement_ratio >= 1.2:
        return 1.2
    elif goal_achievement_ratio >= 1.0:
        return 1.0 + (goal_achievement_ratio - 1.0) * 1.0
    elif goal_achievement_ratio >= 0.8:
        return 0.9 + (goal_achievement_ratio - 0.8) * 0.5
    else:
        multiplier = 0.8 + (goal_achievement_ratio / 0.8) * 0.1
        return max(0.8, multiplier)


def generate_baseline_completion_plotly() -> Optional[go.Figure]:
    """Generate baseline completion Plotly chart with actual user data."""
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Extract completion and score data
    completion_percentages = []
    baseline_scores = []
    task_types = []
    
    for instance in instances:
        try:
            # Parse JSON strings
            predicted_raw = instance.get('predicted', '{}') if hasattr(instance, 'get') else (instance.get('predicted', '{}') if 'predicted' in instance else '{}')
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            
            if isinstance(predicted_raw, str):
                predicted = json.loads(predicted_raw) if predicted_raw.strip() else {}
            else:
                predicted = predicted_raw if isinstance(predicted_raw, dict) else {}
            
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            completion_pct = float(actual.get('completion_percent', 100) or 100)
            
            # Get task type
            task_type = instance.get('task_type', 'Work') if hasattr(instance, 'get') else (instance.get('task_type', 'Work') if 'task_type' in instance else 'Work')
            task_type_lower = str(task_type).strip().lower()
            
            # Calculate baseline score using same logic as backend
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted.get('time_estimate_minutes', 0) or predicted.get('estimate', 0) or 0)
            
            if time_estimate > 0 and time_actual > 0:
                completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
            else:
                completion_time_ratio = 1.0
            
            if task_type_lower == 'work':
                if completion_time_ratio <= 1.0:
                    multiplier = 3.0
                elif completion_time_ratio >= 1.5:
                    multiplier = 5.0
                else:
                    smooth_factor = (completion_time_ratio - 1.0) / 0.5
                    multiplier = 3.0 + (2.0 * smooth_factor)
                baseline_score = completion_pct * multiplier
            elif task_type_lower in ['self care', 'selfcare', 'self-care']:
                multiplier = 1.0
                baseline_score = completion_pct * multiplier
            else:
                multiplier = 1.0
                baseline_score = completion_pct * multiplier
            
            completion_percentages.append(completion_pct)
            baseline_scores.append(baseline_score)
            task_types.append(task_type_lower)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not completion_percentages:
        return None
    
    # Create subplots
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=(
            'Your Data: Completion % vs Baseline Score',
            f'Distribution of Completion Percentages ({len(completion_percentages)} tasks)',
            f'Distribution of Baseline Scores ({len(baseline_scores)} tasks)'
        ),
        specs=[[{"secondary_y": False}, {"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Plot 1: Scatter with theoretical curves
    work_completion = np.linspace(0, 100, 200)
    work_scores = [cp * 3.0 for cp in work_completion]
    self_care_scores = [cp * 1.0 for cp in work_completion]
    play_scores = [cp * 1.0 for cp in work_completion]
    
    # Theoretical curves
    fig.add_trace(go.Scatter(x=work_completion, y=work_scores, mode='lines', name='Work Theoretical (×3.0)',
                            line=dict(dash='dash', color='blue', width=2), opacity=0.5), row=1, col=1)
    fig.add_trace(go.Scatter(x=work_completion, y=self_care_scores, mode='lines', name='Self Care Theoretical (×1.0)',
                            line=dict(dash='dash', color='green', width=2), opacity=0.5), row=1, col=1)
    fig.add_trace(go.Scatter(x=work_completion, y=play_scores, mode='lines', name='Play Theoretical (×1.0)',
                            line=dict(dash='dash', color='orange', width=2), opacity=0.5), row=1, col=1)
    
    # User data by task type
    work_data = [(cp, score) for cp, score, tt in zip(completion_percentages, baseline_scores, task_types) if tt == 'work']
    self_care_data = [(cp, score) for cp, score, tt in zip(completion_percentages, baseline_scores, task_types) if tt in ['self care', 'selfcare', 'self-care']]
    play_data = [(cp, score) for cp, score, tt in zip(completion_percentages, baseline_scores, task_types) if tt == 'play']
    
    if work_data:
        work_cp, work_sc = zip(*work_data)
        fig.add_trace(go.Scatter(x=list(work_cp), y=list(work_sc), mode='markers', name='Work Data',
                                marker=dict(color='blue', size=8, opacity=0.6, line=dict(width=0.5, color='black'))), row=1, col=1)
    if self_care_data:
        sc_cp, sc_sc = zip(*self_care_data)
        fig.add_trace(go.Scatter(x=list(sc_cp), y=list(sc_sc), mode='markers', name='Self Care Data',
                                marker=dict(color='green', size=8, opacity=0.6, line=dict(width=0.5, color='black'))), row=1, col=1)
    if play_data:
        p_cp, p_sc = zip(*play_data)
        fig.add_trace(go.Scatter(x=list(p_cp), y=list(p_sc), mode='markers', name='Play Data',
                                marker=dict(color='orange', size=8, opacity=0.6, line=dict(width=0.5, color='black'))), row=1, col=1)
    
    # Plot 2: Histogram of completion percentages
    fig.add_trace(go.Histogram(x=completion_percentages, nbinsx=20, name='Completion %',
                              marker_color='blue', opacity=0.7), row=1, col=2)
    fig.add_vline(x=100, line_dash="dash", line_color="green", annotation_text="Full (100%)", row=1, col=2)
    mean_cp = np.mean(completion_percentages)
    fig.add_vline(x=mean_cp, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_cp:.1f}%", row=1, col=2)
    
    # Plot 3: Histogram of baseline scores
    fig.add_trace(go.Histogram(x=baseline_scores, nbinsx=20, name='Baseline Score',
                              marker_color='purple', opacity=0.7), row=1, col=3)
    mean_bs = np.mean(baseline_scores)
    fig.add_vline(x=mean_bs, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_bs:.1f}", row=1, col=3)
    
    # Update axes
    fig.update_xaxes(title_text="Completion Percentage (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="Baseline Score", range=[0, 350], row=1, col=1)
    fig.update_xaxes(title_text="Completion Percentage (%)", range=[0, 100], row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=1, col=2)
    fig.update_xaxes(title_text="Baseline Score", range=[0, 550], row=1, col=3)
    fig.update_yaxes(title_text="Frequency", row=1, col=3)
    
    fig.update_layout(
        title_text="Productivity Score: Baseline Completion - Your Data",
        height=500,
        showlegend=True,
        hovermode='closest'
    )
    
    return fig


def generate_work_multiplier_plotly() -> Optional[go.Figure]:
    """Generate work multiplier Plotly chart with actual user data."""
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Extract work task data
    completion_time_ratios = []
    multipliers = []
    
    for instance in instances:
        try:
            # Parse JSON strings
            predicted_raw = instance.get('predicted', '{}') if hasattr(instance, 'get') else (instance.get('predicted', '{}') if 'predicted' in instance else '{}')
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            
            if isinstance(predicted_raw, str):
                predicted = json.loads(predicted_raw) if predicted_raw.strip() else {}
            else:
                predicted = predicted_raw if isinstance(predicted_raw, dict) else {}
            
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            task_type = instance.get('task_type', 'Work') if hasattr(instance, 'get') else (instance.get('task_type', 'Work') if 'task_type' in instance else 'Work')
            task_type_lower = str(task_type).strip().lower()
            
            if task_type_lower != 'work':
                continue
            
            completion_pct = float(actual.get('completion_percent', 100) or 100)
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted.get('time_estimate_minutes', 0) or predicted.get('estimate', 0) or 0)
            
            if time_estimate > 0 and time_actual > 0:
                ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
                
                # Calculate multiplier
                if ratio <= 1.0:
                    multiplier = 3.0
                elif ratio >= 1.5:
                    multiplier = 5.0
                else:
                    smooth_factor = (ratio - 1.0) / 0.5
                    multiplier = 3.0 + (2.0 * smooth_factor)
                
                completion_time_ratios.append(ratio)
                multipliers.append(multiplier)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not completion_time_ratios:
        return None
    
    # Create subplots
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=(
            'Your Data: Ratio vs Work Multiplier',
            f'Distribution of Ratios ({len(completion_time_ratios)} work tasks)',
            f'Distribution of Multipliers ({len(multipliers)} work tasks)'
        )
    )
    
    # Plot 1: Scatter with theoretical curve
    ratio_range = np.linspace(0.5, 2.0, 200)
    theoretical_multipliers = []
    for r in ratio_range:
        if r <= 1.0:
            theoretical_multipliers.append(3.0)
        elif r >= 1.5:
            theoretical_multipliers.append(5.0)
        else:
            smooth_factor = (r - 1.0) / 0.5
            theoretical_multipliers.append(3.0 + (2.0 * smooth_factor))
    
    fig.add_trace(go.Scatter(x=ratio_range, y=theoretical_multipliers, mode='lines', name='Theoretical',
                            line=dict(dash='dash', color='red', width=2), opacity=0.5), row=1, col=1)
    fig.add_trace(go.Scatter(x=completion_time_ratios, y=multipliers, mode='markers', name='Your Data',
                            marker=dict(color='blue', size=8, opacity=0.6, line=dict(width=0.5, color='black'))), row=1, col=1)
    fig.add_vline(x=1.0, line_dash="dash", line_color="red", opacity=0.3, row=1, col=1)
    fig.add_vline(x=1.5, line_dash="dash", line_color="orange", opacity=0.3, row=1, col=1)
    
    # Plot 2: Histogram of ratios
    fig.add_trace(go.Histogram(x=completion_time_ratios, nbinsx=20, name='Ratios',
                              marker_color='green', opacity=0.7), row=1, col=2)
    fig.add_vline(x=1.0, line_dash="dash", line_color="orange", annotation_text="Efficient (1.0)", row=1, col=2)
    mean_ratio = np.mean(completion_time_ratios)
    fig.add_vline(x=mean_ratio, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_ratio:.2f}", row=1, col=2)
    
    # Plot 3: Histogram of multipliers
    fig.add_trace(go.Histogram(x=multipliers, nbinsx=20, name='Multipliers',
                              marker_color='purple', opacity=0.7), row=1, col=3)
    fig.add_vline(x=3.0, line_dash="dash", line_color="blue", annotation_text="Base (3.0x)", row=1, col=3)
    fig.add_vline(x=5.0, line_dash="dash", line_color="green", annotation_text="Max (5.0x)", row=1, col=3)
    mean_mult = np.mean(multipliers)
    fig.add_vline(x=mean_mult, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_mult:.2f}x", row=1, col=3)
    
    # Update axes
    fig.update_xaxes(title_text="Completion/Time Ratio", range=[0.5, 2.0], row=1, col=1)
    fig.update_yaxes(title_text="Work Multiplier", range=[2.5, 5.5], row=1, col=1)
    fig.update_xaxes(title_text="Completion/Time Ratio", range=[0.5, 2.0], row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=1, col=2)
    fig.update_xaxes(title_text="Work Multiplier", range=[2.5, 5.5], row=1, col=3)
    fig.update_yaxes(title_text="Frequency", row=1, col=3)
    
    fig.update_layout(
        title_text="Productivity Score: Work Multiplier - Your Data",
        height=500,
        showlegend=True,
        hovermode='closest'
    )
    
    return fig


def generate_weekly_avg_bonus_plotly() -> Optional[go.Figure]:
    """Generate weekly average bonus Plotly chart with actual user data."""
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Calculate weekly average from instances
    time_values = []
    for instance in instances:
        try:
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            if time_actual > 0:
                time_values.append(time_actual)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if len(time_values) < 3:
        return None
    
    weekly_avg = np.mean(time_values)
    
    # Extract deviation data
    deviations = []
    multipliers = []
    
    for instance in instances:
        try:
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            if time_actual > 0 and weekly_avg > 0:
                deviation = ((time_actual - weekly_avg) / weekly_avg) * 100.0
                multiplier = calculate_weekly_multiplier(deviation, 'flattened_square', 1.0)
                
                deviations.append(deviation)
                multipliers.append(multiplier)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not deviations:
        return None
    
    # Create subplots
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=(
            'Your Data: Deviation vs Weekly Multiplier',
            f'Distribution of Deviations ({len(deviations)} tasks)',
            f'Distribution of Multipliers ({len(multipliers)} tasks)'
        )
    )
    
    # Plot 1: Scatter with theoretical curve
    deviation_range = np.linspace(-100, 100, 200)
    theoretical_multipliers = [calculate_weekly_multiplier(d, 'flattened_square', 1.0) for d in deviation_range]
    
    fig.add_trace(go.Scatter(x=deviation_range, y=theoretical_multipliers, mode='lines', name='Theoretical',
                            line=dict(dash='dash', color='red', width=2), opacity=0.5), row=1, col=1)
    fig.add_trace(go.Scatter(x=deviations, y=multipliers, mode='markers', name='Your Data',
                            marker=dict(color='blue', size=8, opacity=0.6, line=dict(width=0.5, color='black'))), row=1, col=1)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.3, row=1, col=1)
    fig.add_hline(y=1.0, line_dash="dash", line_color="green", opacity=0.3, row=1, col=1)
    
    # Plot 2: Histogram of deviations
    fig.add_trace(go.Histogram(x=deviations, nbinsx=20, name='Deviations',
                              marker_color='green', opacity=0.7), row=1, col=2)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", annotation_text="Average (0%)", row=1, col=2)
    mean_dev = np.mean(deviations)
    fig.add_vline(x=mean_dev, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_dev:.1f}%", row=1, col=2)
    
    # Plot 3: Histogram of multipliers
    fig.add_trace(go.Histogram(x=multipliers, nbinsx=20, name='Multipliers',
                              marker_color='purple', opacity=0.7), row=1, col=3)
    fig.add_vline(x=1.0, line_dash="dash", line_color="green", annotation_text="No Change (1.0x)", row=1, col=3)
    mean_mult = np.mean(multipliers)
    fig.add_vline(x=mean_mult, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_mult:.3f}x", row=1, col=3)
    
    # Update axes
    fig.update_xaxes(title_text="Percentage Deviation from Weekly Average (%)", range=[-100, 100], row=1, col=1)
    fig.update_yaxes(title_text="Weekly Multiplier", range=[0.5, 1.5], row=1, col=1)
    fig.update_xaxes(title_text="Percentage Deviation (%)", range=[-100, 100], row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=1, col=2)
    fig.update_xaxes(title_text="Weekly Multiplier", range=[0.5, 1.5], row=1, col=3)
    fig.update_yaxes(title_text="Frequency", row=1, col=3)
    
    fig.update_layout(
        title_text="Productivity Score: Weekly Average Bonus - Your Data",
        height=500,
        showlegend=True,
        hovermode='closest'
    )
    
    return fig


def generate_goal_adjustment_plotly() -> Optional[go.Figure]:
    """Generate goal adjustment Plotly chart with actual user data."""
    # Get goal data from user state
    try:
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.normpath(os.path.join(script_dir, '..'))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from backend.user_state import UserStateManager
        from backend.productivity_tracker import ProductivityTracker
        from backend.auth import get_current_user
        
        # Get current user for data isolation
        current_user_id = get_current_user()
        user_id_str = str(current_user_id) if current_user_id is not None else "default_user"
        
        user_state = UserStateManager()
        tracker = ProductivityTracker()
        
        goal_settings = user_state.get_productivity_goal_settings(user_id_str)
        goal_hours = goal_settings.get('goal_hours_per_week', 40.0)
        
        # Get weekly history data
        history = tracker.get_productivity_history(user_id_str, weeks=12)
        if not history:
            return None
        
        # Extract goal ratios
        goal_ratios = []
        multipliers = []
        
        for week_entry in history:
            if isinstance(week_entry, dict):
                actual_hours = week_entry.get('actual_hours', 0.0)
                if goal_hours > 0:
                    ratio = actual_hours / goal_hours
                    multiplier = calculate_goal_multiplier(ratio)
                    goal_ratios.append(ratio)
                    multipliers.append(multiplier)
    except Exception as e:
        print(f"[PlotlyCharts] Error loading goal data: {e}")
        return None
    
    if not goal_ratios:
        return None
    
    # Create subplots
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=(
            'Your Data: Goal Ratio vs Multiplier',
            f'Distribution of Goal Ratios ({len(goal_ratios)} weeks)',
            f'Distribution of Multipliers ({len(multipliers)} weeks)'
        )
    )
    
    # Plot 1: Scatter with theoretical curve
    ratio_range = np.linspace(0, 1.5, 300)
    theoretical_multipliers = [calculate_goal_multiplier(r) for r in ratio_range]
    
    fig.add_trace(go.Scatter(x=ratio_range, y=theoretical_multipliers, mode='lines', name='Theoretical',
                            line=dict(dash='dash', color='red', width=2), opacity=0.5), row=1, col=1)
    fig.add_trace(go.Scatter(x=goal_ratios, y=multipliers, mode='markers', name='Your Data',
                            marker=dict(color='blue', size=8, opacity=0.6, line=dict(width=0.5, color='black'))), row=1, col=1)
    fig.add_vline(x=1.0, line_dash="dash", line_color="green", opacity=0.3, row=1, col=1)
    
    # Plot 2: Histogram of goal ratios
    fig.add_trace(go.Histogram(x=goal_ratios, nbinsx=20, name='Goal Ratios',
                              marker_color='green', opacity=0.7), row=1, col=2)
    fig.add_vline(x=1.0, line_dash="dash", line_color="green", annotation_text="100% Goal", row=1, col=2)
    mean_ratio = np.mean(goal_ratios)
    fig.add_vline(x=mean_ratio, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_ratio:.2f}", row=1, col=2)
    
    # Plot 3: Histogram of multipliers
    fig.add_trace(go.Histogram(x=multipliers, nbinsx=20, name='Multipliers',
                              marker_color='purple', opacity=0.7), row=1, col=3)
    fig.add_vline(x=1.0, line_dash="dash", line_color="green", annotation_text="No Change (1.0x)", row=1, col=3)
    mean_mult = np.mean(multipliers)
    fig.add_vline(x=mean_mult, line_dash="dash", line_color="red", annotation_text=f"Mean: {mean_mult:.3f}x", row=1, col=3)
    
    # Update axes
    fig.update_xaxes(title_text="Goal Achievement Ratio (actual / goal)", range=[0, 1.5], row=1, col=1)
    fig.update_yaxes(title_text="Goal Multiplier", range=[0.75, 1.25], row=1, col=1)
    fig.update_xaxes(title_text="Goal Achievement Ratio", range=[0, 1.5], row=1, col=2)
    fig.update_yaxes(title_text="Frequency", row=1, col=2)
    fig.update_xaxes(title_text="Goal Multiplier", range=[0.75, 1.25], row=1, col=3)
    fig.update_yaxes(title_text="Frequency", row=1, col=3)
    
    fig.update_layout(
        title_text="Productivity Score: Goal Adjustment - Your Data",
        height=500,
        showlegend=True,
        hovermode='closest'
    )
    
    return fig


def generate_thoroughness_note_coverage_plotly(user_id: Optional[int] = None) -> Optional[go.Figure]:
    """Generate note coverage visualization showing percentage of tasks with notes."""
    try:
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.normpath(os.path.join(script_dir, '..'))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from backend.task_manager import TaskManager
        from backend.analytics import Analytics
        from backend.auth import get_current_user
        
        # Get user_id if not provided
        if user_id is None:
            user_id = get_current_user()
        
        task_manager = TaskManager()
        analytics = Analytics()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        if tasks_df.empty:
            return None
        
        # Filter out test tasks
        if 'name' in tasks_df.columns:
            tasks_df = tasks_df[~tasks_df['name'].apply(
                lambda x: Analytics._is_test_task(x) if pd.notna(x) else False
            )]
        
        if tasks_df.empty:
            return None
        
        # Calculate note coverage
        tasks_with_notes = 0
        tasks_without_notes = 0
        
        for _, task in tasks_df.iterrows():
            has_notes = False
            description = str(task.get('description', '') or '').strip()
            notes = str(task.get('notes', '') or '').strip()
            
            if description or notes:
                has_notes = True
                tasks_with_notes += 1
            else:
                tasks_without_notes += 1
        
        total_tasks = len(tasks_df)
        note_coverage = (tasks_with_notes / total_tasks * 100) if total_tasks > 0 else 0.0
        
        # Create pie chart
        fig = go.Figure(data=[go.Pie(
            labels=['Tasks with Notes', 'Tasks without Notes'],
            values=[tasks_with_notes, tasks_without_notes],
            hole=0.4,
            marker_colors=['#14b8a6', '#94a3b8'],
            textinfo='label+percent+value',
            texttemplate='%{label}<br>%{value} tasks<br>(%{percent})',
        )])
        
        fig.update_layout(
            title=f"Note Coverage: {note_coverage:.1f}% of tasks have notes",
            margin=dict(l=20, r=20, t=60, b=20),
            annotations=[dict(
                text=f'{note_coverage:.1f}%<br>Coverage',
                x=0.5, y=0.5, font_size=16, showarrow=False
            )]
        )
        
        return fig
    except Exception as e:
        print(f"[PlotlyCharts] Error generating note coverage chart: {e}")
        return None


def generate_thoroughness_note_length_plotly(user_id: Optional[int] = None) -> Optional[go.Figure]:
    """Generate note length distribution visualization."""
    try:
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.normpath(os.path.join(script_dir, '..'))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from backend.task_manager import TaskManager
        from backend.analytics import Analytics
        from backend.auth import get_current_user
        
        # Get user_id if not provided
        if user_id is None:
            user_id = get_current_user()
        
        task_manager = TaskManager()
        analytics = Analytics()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        if tasks_df.empty:
            return None
        
        # Filter out test tasks
        if 'name' in tasks_df.columns:
            tasks_df = tasks_df[~tasks_df['name'].apply(
                lambda x: Analytics._is_test_task(x) if pd.notna(x) else False
            )]
        
        # Calculate note lengths
        note_lengths = []
        task_names = []
        
        for _, task in tasks_df.iterrows():
            description = str(task.get('description', '') or '').strip()
            notes = str(task.get('notes', '') or '').strip()
            total_length = len(description) + len(notes)
            
            if total_length > 0:
                note_lengths.append(total_length)
                task_name = str(task.get('name', 'Unknown'))
                task_names.append(task_name)
        
        if not note_lengths:
            return None
        
        avg_length = sum(note_lengths) / len(note_lengths)
        
        # Create histogram
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=note_lengths,
            nbinsx=20,
            name='Note Length Distribution',
            marker_color='#14b8a6',
            opacity=0.7
        ))
        
        # Add average line
        fig.add_vline(
            x=avg_length,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Average: {avg_length:.0f} chars",
            annotation_position="top"
        )
        
        # Add target line (500 chars for max bonus)
        fig.add_vline(
            x=500,
            line_dash="dot",
            line_color="green",
            annotation_text="Target: 500 chars (max bonus)",
            annotation_position="top"
        )
        
        fig.update_layout(
            title=f"Note Length Distribution (Average: {avg_length:.0f} characters)",
            xaxis_title="Note Length (characters)",
            yaxis_title="Number of Tasks",
            margin=dict(l=20, r=20, t=60, b=20),
            showlegend=False
        )
        
        return fig
    except Exception as e:
        print(f"[PlotlyCharts] Error generating note length chart: {e}")
        return None


def generate_thoroughness_popup_penalty_plotly() -> Optional[go.Figure]:
    """Generate popup penalty visualization showing frequency of no-slider popups."""
    try:
        import sys
        import os
        from datetime import datetime, timedelta
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.normpath(os.path.join(script_dir, '..'))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from backend.database import get_session, PopupResponse
        from backend.auth import get_current_user
        
        # Get current user for data isolation
        current_user_id = get_current_user()
        if current_user_id is None:
            # Fallback to default_user for backward compatibility
            user_id_str = 'default'
        else:
            user_id_str = str(current_user_id)
        
        # Get popup data for last 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        with get_session() as session:
            popups = session.query(PopupResponse).filter(
                PopupResponse.trigger_id == '7.1',
                PopupResponse.user_id == user_id_str,
                PopupResponse.created_at >= cutoff_date
            ).order_by(PopupResponse.created_at).all()
        
        if not popups:
            # Show empty state with message
            fig = go.Figure()
            fig.add_annotation(
                text="No popup data yet. Popups appear when you complete/initialize tasks without adjusting sliders.",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                title="No Slider Adjustment Popups (Last 30 Days)",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False),
                margin=dict(l=20, r=20, t=60, b=20)
            )
            return fig
        
        # Group by date
        from collections import defaultdict
        daily_counts = defaultdict(int)
        
        for popup in popups:
            date = popup.created_at.date() if hasattr(popup.created_at, 'date') else datetime.fromisoformat(str(popup.created_at)).date()
            daily_counts[date] += 1
        
        # Sort by date
        sorted_dates = sorted(daily_counts.keys())
        dates = [str(d) for d in sorted_dates]
        counts = [daily_counts[d] for d in sorted_dates]
        
        total_popups = len(popups)
        avg_per_day = total_popups / 30.0 if total_popups > 0 else 0.0
        
        # Create bar chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=dates,
            y=counts,
            name='No-Slider Popups',
            marker_color='#ef4444',
            text=counts,
            textposition='outside'
        ))
        
        # Add average line
        if avg_per_day > 0:
            fig.add_hline(
                y=avg_per_day,
                line_dash="dash",
                line_color="orange",
                annotation_text=f"Average: {avg_per_day:.2f} per day",
                annotation_position="right"
            )
        
        # Add penalty threshold line (10 popups = max penalty)
        fig.add_hline(
            y=10,
            line_dash="dot",
            line_color="red",
            annotation_text="Max penalty threshold (10 popups)",
            annotation_position="right"
        )
        
        fig.update_layout(
            title=f"No-Slider Popups Over Time (Total: {total_popups}, Last 30 Days)",
            xaxis_title="Date",
            yaxis_title="Number of Popups",
            margin=dict(l=20, r=20, t=60, b=20),
            xaxis=dict(tickangle=-45),
            showlegend=False
        )
        
        return fig
    except Exception as e:
        print(f"[PlotlyCharts] Error generating popup penalty chart: {e}")
        return None


def generate_thoroughness_factor_overview_plotly(user_id: Optional[int] = None) -> Optional[go.Figure]:
    """Generate overview chart showing all thoroughness components."""
    try:
        import sys
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.normpath(os.path.join(script_dir, '..'))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from backend.analytics import Analytics
        from backend.auth import get_current_user
        
        # Get user_id if not provided
        if user_id is None:
            user_id = get_current_user()
        
        analytics = Analytics()
        
        # Calculate current thoroughness factor and components
        thoroughness_factor = analytics.calculate_thoroughness_factor(user_id='default', days=30)
        thoroughness_score = analytics.calculate_thoroughness_score(user_id='default', days=30)
        
        # Get component breakdown (we'll need to extract this from the calculation)
        # For now, create a visual representation
        from backend.task_manager import TaskManager
        from backend.database import get_session, PopupResponse
        from datetime import datetime, timedelta
        
        task_manager = TaskManager()
        tasks_df = task_manager.get_all(user_id=user_id)
        
        if tasks_df.empty:
            return None
        
        # Calculate components
        total_tasks = len(tasks_df)
        tasks_with_notes = 0
        total_note_length = 0
        note_count = 0
        
        for _, task in tasks_df.iterrows():
            has_notes = False
            note_length = 0
            description = str(task.get('description', '') or '').strip()
            notes = str(task.get('notes', '') or '').strip()
            
            if description:
                has_notes = True
                note_length += len(description)
            if notes:
                has_notes = True
                note_length += len(notes)
            
            if has_notes:
                tasks_with_notes += 1
                total_note_length += note_length
                note_count += 1
        
        note_coverage = (tasks_with_notes / total_tasks) if total_tasks > 0 else 0.0
        base_factor = 0.5 + (note_coverage * 0.5)
        
        avg_note_length = (total_note_length / note_count) if note_count > 0 else 0.0
        if avg_note_length > 0:
            length_ratio = min(1.0, avg_note_length / 500.0)
            length_bonus = 0.3 * (1.0 - math.exp(-length_ratio * 2.0))
        else:
            length_bonus = 0.0
        
        # Get popup count
        popup_penalty = 0.0
        try:
            with get_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                popup_count = session.query(PopupResponse).filter(
                    PopupResponse.trigger_id == '7.1',
                    PopupResponse.user_id == 'default',
                    PopupResponse.created_at >= cutoff_date
                ).count()
                
                if popup_count > 0:
                    popup_ratio = min(1.0, popup_count / 10.0)
                    popup_penalty = -0.2 * (1.0 - math.exp(-popup_ratio * 2.0))
        except Exception:
            pass
        
        # Create component breakdown chart
        components = ['Base Factor\n(Note Coverage)', 'Length Bonus', 'Popup Penalty', 'Total Factor']
        values = [base_factor, length_bonus, popup_penalty, thoroughness_factor]
        colors = ['#14b8a6', '#10b981', '#ef4444', '#3b82f6']
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=components,
            y=values,
            marker_color=colors,
            text=[f'{v:.3f}' for v in values],
            textposition='outside',
            name='Component Value'
        ))
        
        # Add baseline line at 1.0
        fig.add_hline(
            y=1.0,
            line_dash="dash",
            line_color="gray",
            annotation_text="Baseline (1.0)",
            annotation_position="right"
        )
        
        fig.update_layout(
            title=f"Thoroughness Factor Breakdown (Score: {thoroughness_score:.1f})",
            xaxis_title="Component",
            yaxis_title="Factor Value",
            margin=dict(l=20, r=20, t=60, b=20),
            showlegend=False,
            yaxis=dict(range=[-0.3, 1.4])
        )
        
        return fig
    except Exception as e:
        print(f"[PlotlyCharts] Error generating thoroughness overview chart: {e}")
        return None


def generate_work_volume_score_plotly() -> Optional[go.Figure]:
    """Generate work volume score Plotly chart with actual user data."""
    try:
        _, analytics = get_user_instances()
        if not analytics:
            return None
        
        # Get current user for data isolation
        from backend.auth import get_current_user
        current_user_id = get_current_user()
        
        # Get work volume metrics
        volume_metrics = analytics.get_daily_work_volume_metrics(days=30, user_id=current_user_id)
        avg_daily_work_time = volume_metrics.get('avg_daily_work_time', 0.0)
        work_volume_score = volume_metrics.get('work_volume_score', 0.0)
        work_consistency_score = volume_metrics.get('work_consistency_score', 50.0)
        variance = volume_metrics.get('variance', 0.0)
        daily_work_times = volume_metrics.get('daily_work_times', [])  # Only days with work
        daily_work_times_history = volume_metrics.get('daily_work_times_history', [])  # All days including zeros
        total_days = volume_metrics.get('total_days', 0)
        days_with_work = volume_metrics.get('days_with_work', 0)
        
        if not daily_work_times_history:
            return None
        
        # Create subplots
        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=(
                f'Your Daily Work Times (Avg: {avg_daily_work_time:.1f} min, Score: {work_volume_score:.1f})',
                f'Work Time Distribution ({days_with_work} work days of {total_days} total)',
                f'Consistency: {work_consistency_score:.1f} (Variance: {variance:.0f})'
            ),
            specs=[[{"secondary_y": False}, {"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Plot 1: Daily work times over time (using history to show all days)
        dates = list(range(len(daily_work_times_history)))
        fig.add_trace(go.Scatter(
            x=dates, y=daily_work_times_history,
            mode='lines+markers',
            name='Daily Work Time',
            line=dict(color='blue', width=2),
            marker=dict(size=4),
            hovertemplate='Day %{x}<br>%{y:.1f} min<extra></extra>'
        ), row=1, col=1)
        
        # Add average line
        fig.add_hline(
            y=avg_daily_work_time,
            line_dash="dash",
            line_color="green",
            annotation_text=f"Avg: {avg_daily_work_time:.1f} min",
            annotation_position="right",
            row=1, col=1
        )
        
        # Add tier thresholds
        fig.add_hline(y=120, line_dash="dot", line_color="orange", row=1, col=1, annotation_text="2h")
        fig.add_hline(y=240, line_dash="dot", line_color="yellow", row=1, col=1, annotation_text="4h")
        fig.add_hline(y=360, line_dash="dot", line_color="green", row=1, col=1, annotation_text="6h")
        
        # Plot 2: Histogram of daily work times (only days with work)
        fig.add_trace(go.Histogram(
            x=daily_work_times,
            nbinsx=20,
            name='Frequency',
            marker_color='blue',
            opacity=0.7
        ), row=1, col=2)
        
        # Plot 3: Consistency visualization - show variance
        # Create a bar chart showing consistency score and variance
        fig.add_trace(go.Bar(
            x=['Consistency Score', 'Variance'],
            y=[work_consistency_score, min(100.0, variance / 10.0)],  # Scale variance for display
            marker_color=['green', 'red'],
            name='Metrics',
            text=[f'{work_consistency_score:.1f}', f'{variance:.0f}'],
            textposition='outside'
        ), row=1, col=3)
        
        fig.update_xaxes(title_text="Day Index", row=1, col=1)
        fig.update_xaxes(title_text="Daily Work Time (minutes)", row=1, col=2)
        fig.update_xaxes(title_text="Metric", row=1, col=3)
        fig.update_yaxes(title_text="Work Time (minutes)", row=1, col=1)
        fig.update_yaxes(title_text="Frequency", row=1, col=2)
        fig.update_yaxes(title_text="Score / Scaled Variance", row=1, col=3)
        
        fig.update_layout(
            title=f"Productivity Volume: Work Volume & Consistency - Your Data<br>Consistency: {work_consistency_score:.1f}/100 (Variance: {variance:.0f}, {days_with_work}/{total_days} days with work)",
            height=400,
            showlegend=False
        )
        
        return fig
    except Exception as e:
        print(f"[PlotlyCharts] Error generating work volume score chart: {e}")
        return None


def generate_volumetric_productivity_plotly() -> Optional[go.Figure]:
    """Generate volumetric productivity Plotly chart with actual user data."""
    try:
        instances, analytics = get_user_instances()
        if not instances or not analytics:
            return None
        
        # Get current user for data isolation
        from backend.auth import get_current_user
        current_user_id = get_current_user()
        if current_user_id is None:
            # Fallback to default_user for backward compatibility
            current_user_id = None
        
        # Get target hours from settings
        from backend.user_state import UserStateManager
        user_state = UserStateManager()
        user_id_str = str(current_user_id) if current_user_id is not None else "default_user"
        goal_settings = user_state.get_productivity_goal_settings(user_id_str)
        goal_hours_per_week = goal_settings.get('goal_hours_per_week', 30.0)
        target_hours_per_day = goal_hours_per_week / 5.0  # Assume 5 work days
        
        # Get metrics
        metrics = analytics.get_dashboard_metrics(user_id=current_user_id)
        productivity_volume = metrics.get('productivity_volume', {})
        
        base_productivity = productivity_volume.get('avg_base_productivity', 0.0)
        volumetric_productivity = productivity_volume.get('volumetric_productivity_score', 0.0)
        volumetric_potential = productivity_volume.get('volumetric_potential_score', 0.0)
        work_volume_score = productivity_volume.get('work_volume_score', 0.0)
        
        if base_productivity == 0:
            return None
        
        # Calculate volume multiplier
        volume_multiplier = 0.5 + (work_volume_score / 100.0) * 1.0
        
        # Create comparison chart
        fig = go.Figure()
        
        categories = ['Base\nProductivity', 'Volume\nMultiplier', 'Volumetric\nProductivity', 'Volumetric\nPotential']
        values = [base_productivity, volume_multiplier * 100, volumetric_productivity, volumetric_potential]
        colors = ['lightblue', 'orange', 'green', 'blue']
        
        fig.add_trace(go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f'{v:.1f}' for v in values],
            textposition='outside',
            name='Score'
        ))
        
        # Add formula annotation
        fig.add_annotation(
            x=1, y=max(values) * 0.8,
            text=f"Formula:<br>volumetric = base × multiplier<br>Multiplier: {volume_multiplier:.2f}x",
            showarrow=False,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black",
            borderwidth=1
        )
        
        fig.update_layout(
            title=f"Volumetric Productivity Score Breakdown<br>Base: {base_productivity:.1f}, Volume Score: {work_volume_score:.1f}<br>Goal: {goal_hours_per_week:.1f}h/week ({target_hours_per_day:.1f}h/day)",
            xaxis_title="Metric",
            yaxis_title="Score",
            height=500,
            showlegend=False
        )
        
        return fig
    except Exception as e:
        print(f"[PlotlyCharts] Error generating volumetric productivity chart: {e}")
        return None


# Mapping of chart generators
PLOTLY_DATA_CHARTS = {
    'productivity_score_baseline_completion': generate_baseline_completion_plotly,
    'productivity_score_work_multiplier': generate_work_multiplier_plotly,
    'productivity_score_weekly_avg_bonus': generate_weekly_avg_bonus_plotly,
    'productivity_score_goal_adjustment': generate_goal_adjustment_plotly,
    'thoroughness_note_coverage': generate_thoroughness_note_coverage_plotly,
    'thoroughness_note_length': generate_thoroughness_note_length_plotly,
    'thoroughness_popup_penalty': generate_thoroughness_popup_penalty_plotly,
    'thoroughness_factor_overview': generate_thoroughness_factor_overview_plotly,
    'productivity_volume_work_volume_score': generate_work_volume_score_plotly,
    'volumetric_productivity_calculation': generate_volumetric_productivity_plotly,
}
