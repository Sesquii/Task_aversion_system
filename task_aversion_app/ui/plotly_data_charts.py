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
        
        instance_manager = InstanceManager()
        analytics = Analytics()
        
        instances = instance_manager.list_recent_completed(limit=limit)
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
        
        user_state = UserStateManager()
        tracker = ProductivityTracker()
        DEFAULT_USER_ID = "default_user"
        
        goal_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
        goal_hours = goal_settings.get('goal_hours_per_week', 40.0)
        
        # Get weekly history data
        history = tracker.get_productivity_history(DEFAULT_USER_ID, weeks=12)
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


# Mapping of chart generators
PLOTLY_DATA_CHARTS = {
    'productivity_score_baseline_completion': generate_baseline_completion_plotly,
    'productivity_score_work_multiplier': generate_work_multiplier_plotly,
    'productivity_score_weekly_avg_bonus': generate_weekly_avg_bonus_plotly,
    'productivity_score_goal_adjustment': generate_goal_adjustment_plotly,
}
