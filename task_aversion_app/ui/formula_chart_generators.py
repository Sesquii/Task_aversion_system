"""
Chart generators for formula baseline charts.
Generates 6 charts per variable plus correlation charts for weight calibration.
"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import math
from typing import List, Dict, Optional, Tuple


def generate_6_charts_for_variable(
    system_id: str,
    variable: Dict,
    system_info: Dict,
    calculate_score_func
) -> List[go.Figure]:
    """Generate 6 theoretical charts for a single variable.
    
    Charts:
    1. Variable vs Score (single variable, others at default)
    2. Variable vs Score (with different other variable values)
    3. Score distribution histogram
    4. Variable sensitivity (derivative/rate of change)
    5. Score heatmap (if 2+ variables)
    6. Score vs variable with different weights
    """
    var_name = variable['name']
    var_range = variable['range']
    charts = []
    
    # Generate data range
    if isinstance(var_range, tuple):
        x_min, x_max = var_range
    else:
        x_min, x_max = 0, 100
    
    x_values = np.linspace(x_min, x_max, 200)
    
    # Get default values for other variables
    defaults = {}
    for v in system_info['variables']:
        if v['name'] != var_name:
            if isinstance(v['range'], tuple):
                defaults[v['name']] = (v['range'][0] + v['range'][1]) / 2
            else:
                defaults[v['name']] = 50.0
    
    # Chart 1: Variable vs Score (single variable, others at default)
    scores_1 = [calculate_score_func({**defaults, var_name: x}) for x in x_values]
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=x_values, y=scores_1, mode='lines', name='Score',
                             line=dict(width=2, color='blue')))
    fig1.update_layout(
        title=f'{var_name} vs Score (others at default)',
        xaxis_title=var_name,
        yaxis_title='Score',
        height=400
    )
    charts.append(fig1)
    
    # Chart 2: Variable vs Score with different other variable values
    if len(system_info['variables']) > 1:
        fig2 = go.Figure()
        other_var = [v for v in system_info['variables'] if v['name'] != var_name][0]
        other_name = other_var['name']
        if isinstance(other_var['range'], tuple):
            other_min, other_max = other_var['range']
        else:
            other_min, other_max = 0, 100
        
        for other_val in [other_min, (other_min + other_max) / 2, other_max]:
            scores_2 = [calculate_score_func({**defaults, var_name: x, other_name: other_val}) 
                        for x in x_values]
            fig2.add_trace(go.Scatter(
                x=x_values, y=scores_2, mode='lines',
                name=f'{other_name}={other_val:.1f}',
                line=dict(width=2)
            ))
        fig2.update_layout(
            title=f'{var_name} vs Score (varying {other_name})',
            xaxis_title=var_name,
            yaxis_title='Score',
            height=400
        )
        charts.append(fig2)
    else:
        # Single variable system - duplicate chart 1
        charts.append(fig1)
    
    # Chart 3: Score distribution histogram
    scores_3 = [calculate_score_func({**defaults, var_name: x}) for x in x_values]
    fig3 = go.Figure()
    fig3.add_trace(go.Histogram(x=scores_3, nbinsx=30, name='Score Distribution',
                                marker_color='purple', opacity=0.7))
    fig3.update_layout(
        title=f'Score Distribution (varying {var_name})',
        xaxis_title='Score',
        yaxis_title='Frequency',
        height=400
    )
    charts.append(fig3)
    
    # Chart 4: Variable sensitivity (derivative/rate of change)
    scores_4 = [calculate_score_func({**defaults, var_name: x}) for x in x_values]
    # Calculate derivative (rate of change)
    derivatives = np.diff(scores_4) / np.diff(x_values)
    x_deriv = (x_values[:-1] + x_values[1:]) / 2
    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=x_deriv, y=derivatives, mode='lines', name='Sensitivity',
                             line=dict(width=2, color='red')))
    fig4.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig4.update_layout(
        title=f'{var_name} Sensitivity (Rate of Change)',
        xaxis_title=var_name,
        yaxis_title='dScore/dVariable',
        height=400
    )
    charts.append(fig4)
    
    # Chart 5: Score heatmap (if 2+ variables)
    if len(system_info['variables']) >= 2:
        other_var = [v for v in system_info['variables'] if v['name'] != var_name][0]
        other_name = other_var['name']
        if isinstance(other_var['range'], tuple):
            other_min, other_max = other_var['range']
        else:
            other_min, other_max = 0, 100
        
        y_values = np.linspace(other_min, other_max, 50)
        z_data = []
        for y in y_values:
            row = [calculate_score_func({**defaults, var_name: x, other_name: y}) for x in x_values]
            z_data.append(row)
        
        fig5 = go.Figure(data=go.Heatmap(
            z=z_data,
            x=x_values,
            y=y_values,
            colorscale='Viridis'
        ))
        fig5.update_layout(
            title=f'Score Heatmap: {var_name} vs {other_name}',
            xaxis_title=var_name,
            yaxis_title=other_name,
            height=500
        )
        charts.append(fig5)
    else:
        # Single variable - create a 2D view of score vs variable
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(
            x=x_values, y=scores_1, mode='lines+markers',
            name='Score', line=dict(width=2, color='blue'),
            marker=dict(size=4)
        ))
        fig5.update_layout(
            title=f'{var_name} vs Score (2D View)',
            xaxis_title=var_name,
            yaxis_title='Score',
            height=400
        )
        charts.append(fig5)
    
    # Chart 6: Score vs variable with different weights (if applicable)
    weights = system_info.get('weights', {})
    if var_name in weights and len(system_info['variables']) > 1:
        fig6 = go.Figure()
        base_weight = weights[var_name]
        for weight_mult in [0.5, 1.0, 1.5, 2.0]:
            # Adjust weight and recalculate
            adjusted_weights = weights.copy()
            adjusted_weights[var_name] = base_weight * weight_mult
            # Normalize weights
            total = sum(adjusted_weights.values())
            normalized_weights = {k: v/total for k, v in adjusted_weights.items()}
            
            # Recalculate scores with adjusted weights
            scores_6 = []
            for x in x_values:
                # This is a simplified version - actual implementation depends on formula
                score = calculate_score_func({**defaults, var_name: x})
                scores_6.append(score * normalized_weights[var_name] / weights[var_name])
            
            fig6.add_trace(go.Scatter(
                x=x_values, y=scores_6, mode='lines',
                name=f'Weight={weight_mult:.1f}x',
                line=dict(width=2)
            ))
        fig6.update_layout(
            title=f'{var_name} vs Score (Different Weights)',
            xaxis_title=var_name,
            yaxis_title='Score',
            height=400
        )
        charts.append(fig6)
    else:
        # No weight variation - duplicate chart 1
        charts.append(fig1)
    
    return charts


def generate_correlation_charts(system_id: str, system_info: Dict, calculate_score_func) -> List[go.Figure]:
    """Generate correlation charts for weight calibration."""
    charts = []
    variables = system_info['variables']
    weights = system_info.get('weights', {})
    
    if len(variables) < 2:
        return charts  # Need at least 2 variables for correlation
    
    # Create correlation matrix showing how each variable correlates with total score
    # at different weight combinations
    
    # Chart 1: Correlation matrix heatmap
    # Extract variable names safely
    var_names = []
    for v in variables:
        if isinstance(v, dict) and 'name' in v:
            var_names.append(str(v['name']))
        else:
            var_names.append(str(v))
    
    n_vars = len(var_names)
    correlation_matrix = np.zeros((n_vars, n_vars))
    
    # Generate sample data points
    n_samples = 100
    for i, var1 in enumerate(variables):
        var1_name = var1['name'] if isinstance(var1, dict) and 'name' in var1 else str(var1)
        var1_range = var1.get('range', (0, 100)) if isinstance(var1, dict) else (0, 100)
        
        for j, var2 in enumerate(variables):
            var2_name = var2['name'] if isinstance(var2, dict) and 'name' in var2 else str(var2)
            var2_range = var2.get('range', (0, 100)) if isinstance(var2, dict) else (0, 100)
            
            if i == j:
                correlation_matrix[i, j] = 1.0
            else:
                # Calculate correlation between var1 and score when var2 varies
                if isinstance(var1_range, tuple):
                    v1_min, v1_max = var1_range
                else:
                    v1_min, v1_max = 0, 100
                
                if isinstance(var2_range, tuple):
                    v2_min, v2_max = var2_range
                else:
                    v2_min, v2_max = 0, 100
                
                v1_values = np.linspace(v1_min, v1_max, n_samples)
                v2_values = np.linspace(v2_min, v2_max, n_samples)
                
                # Calculate scores
                defaults = {}
                for v in variables:
                    var_name = v['name'] if isinstance(v, dict) and 'name' in v else str(v)
                    if var_name not in [var1_name, var2_name]:
                        v_range = v.get('range', (0, 100)) if isinstance(v, dict) else (0, 100)
                        if isinstance(v_range, tuple):
                            defaults[var_name] = (v_range[0] + v_range[1]) / 2
                        else:
                            defaults[var_name] = 50.0
                
                scores = []
                for v1, v2 in zip(v1_values, v2_values):
                    params = {**defaults, var1_name: v1, var2_name: v2}
                    scores.append(calculate_score_func(params))
                
                # Calculate correlation
                if len(scores) > 1 and np.std(scores) > 0:
                    correlation = np.corrcoef(v1_values, scores)[0, 1]
                    correlation_matrix[i, j] = correlation if not np.isnan(correlation) else 0.0
    
    fig1 = go.Figure(data=go.Heatmap(
        z=correlation_matrix,
        x=var_names,
        y=var_names,
        colorscale='RdBu',
        zmid=0,
        text=[[f'{val:.2f}' for val in row] for row in correlation_matrix],
        texttemplate='%{text}',
        textfont={"size": 10}
    ))
    fig1.update_layout(
        title='Variable Correlation Matrix',
        height=500
    )
    charts.append(fig1)
    
    # Chart 2: Weight sensitivity analysis
    if weights:
        fig2 = go.Figure()
        base_weights = weights.copy()
        
        for var_name in var_names:
            if var_name in base_weights:
                weight_variations = np.linspace(0.1, 2.0, 20)
                score_impacts = []
                
                for w_mult in weight_variations:
                    # Adjust weight
                    adjusted = base_weights.copy()
                    adjusted[var_name] = base_weights[var_name] * w_mult
                    # Normalize
                    total = sum(adjusted.values())
                    normalized = {k: v/total for k, v in adjusted.items()}
                    
                    # Calculate impact (simplified)
                    impact = normalized[var_name] / base_weights[var_name] if base_weights[var_name] > 0 else 0
                    score_impacts.append(impact)
                
                fig2.add_trace(go.Scatter(
                    x=weight_variations,
                    y=score_impacts,
                    mode='lines',
                    name=var_name,
                    line=dict(width=2)
                ))
        
        fig2.update_layout(
            title='Weight Sensitivity Analysis',
            xaxis_title='Weight Multiplier',
            yaxis_title='Score Impact',
            height=400
        )
        charts.append(fig2)
    
    return charts


# System-specific score calculation functions
def calculate_execution_score(params: Dict) -> float:
    """Calculate execution score from parameters."""
    difficulty = params.get('difficulty_factor', 0.5)
    speed = params.get('speed_factor', 0.5)
    start_speed = params.get('start_speed_factor', 0.5)
    completion = params.get('completion_factor', 1.0)
    
    return 50 * (1.0 + difficulty) * (0.5 + speed * 0.5) * (0.5 + start_speed * 0.5) * completion


def calculate_grit_score(params: Dict) -> float:
    """Calculate grit score from parameters."""
    difficulty = params.get('difficulty_bonus', 0.5)
    time = params.get('time_bonus', 1.0)
    
    return difficulty * time * 50  # Scale to 0-100 range


def calculate_productivity_score(params: Dict) -> float:
    """Calculate productivity score from parameters."""
    completion = params.get('completion_pct', 50) / 100.0
    task_type = params.get('task_type_multiplier', 3.0)
    weekly_avg = params.get('weekly_avg_multiplier', 1.0)
    goal = params.get('goal_multiplier', 1.0)
    
    return completion * 100 * task_type * weekly_avg * goal


def calculate_difficulty_bonus(params: Dict) -> float:
    """Calculate difficulty bonus from parameters."""
    aversion = params.get('aversion', 50)
    load = params.get('load', 50)
    
    combined = 0.7 * aversion + 0.3 * load
    return 1.0 * (1.0 - math.exp(-combined / 50.0))


def calculate_obstacles_score(params: Dict) -> float:
    """Calculate obstacles score from parameters."""
    spike = params.get('spike_amount', 0)
    relief = params.get('relief_score', 50)
    
    # Simplified formula
    return (spike * relief) / 50.0


def calculate_composite_score(params: Dict) -> float:
    """Calculate composite score from parameters."""
    execution = params.get('execution_score', 50)
    productivity = params.get('productivity_score', 50)
    grit = params.get('grit_score', 50)
    tracking = params.get('tracking_consistency', 50)
    
    # Equal weights, normalized
    return (execution + productivity + grit + tracking) / 4.0


def calculate_time_tracking_consistency(params: Dict) -> float:
    """Calculate time tracking consistency score from parameters."""
    coverage = params.get('tracking_coverage', 0.5)
    
    return 100 * (1.0 - math.exp(-coverage * 2.0))


def calculate_efficiency_score(params: Dict) -> float:
    """Calculate efficiency score from parameters."""
    time_actual = params.get('time_actual', 60)
    time_estimate = params.get('time_estimate', 60)
    completion = params.get('completion_pct', 100) / 100.0
    
    if time_estimate > 0:
        time_ratio = time_actual / time_estimate
        efficiency = completion / max(time_ratio, 0.1)
        return min(100, efficiency * 100)
    return 0.0


def calculate_productivity_potential(params: Dict) -> float:
    """Calculate productivity potential from parameters."""
    efficiency = params.get('avg_efficiency_score', 50)
    work_time = params.get('avg_daily_work_time', 4)
    
    # Simplified: efficiency * normalized work time
    normalized_time = min(work_time / 8.0, 1.0)  # Cap at 8 hours
    return efficiency * normalized_time


def calculate_composite_productivity_score(params: Dict) -> float:
    """Calculate composite productivity score from parameters."""
    efficiency = params.get('efficiency_score', 50)
    volume = params.get('volume_score', 50)
    
    # Equal weights
    return (efficiency + volume) / 2.0


def calculate_productivity_points(params: Dict) -> float:
    """Calculate productivity points from parameters."""
    score = params.get('productivity_score', 50)
    hours = params.get('time_hours', 1.0)
    
    return score * hours


def calculate_relief_points(params: Dict) -> float:
    """Calculate relief points from parameters."""
    actual = params.get('actual_relief', 50)
    expected = params.get('expected_relief', 50)
    aversion_mult = params.get('aversion_multiplier', 1.0)
    
    return (actual - expected) * aversion_mult


def calculate_execution_points(params: Dict) -> float:
    """Calculate execution points from parameters."""
    score = params.get('execution_score', 50)
    hours = params.get('time_hours', 1.0)
    
    return score * hours


def calculate_grit_points(params: Dict) -> float:
    """Calculate grit points from parameters."""
    score = params.get('grit_score', 50)
    hours = params.get('time_hours', 1.0)
    
    return score * hours


def calculate_obstacles_points(params: Dict) -> float:
    """Calculate obstacles points from parameters."""
    score = params.get('obstacles_score', 0)
    hours = params.get('time_hours', 1.0)
    
    return score * hours


def calculate_composite_points(params: Dict) -> float:
    """Calculate composite points from parameters."""
    score = params.get('composite_score', 50)
    hours = params.get('time_hours', 1.0)
    
    return score * hours


def calculate_relief_score(params: Dict) -> float:
    """Calculate relief score from parameters.
    
    Prototype formula:
    - Base: actual_relief (0-100)
    - Expectation bonus: (actual - expected) * 0.5 (can be negative)
    - Duration factor: log(duration_minutes / 30 + 1) / log(2) (normalized to 0-1.5 range)
    - Aversion multiplier: applies to final score
    
    Formula: relief_score = (actual_relief + expectation_bonus) * duration_factor * aversion_multiplier
    """
    actual = params.get('actual_relief', 50)
    expected = params.get('expected_relief', 50)
    duration = params.get('duration_minutes', 30)
    aversion_mult = params.get('aversion_multiplier', 1.0)
    
    # Expectation bonus: positive if actual > expected, negative if actual < expected
    expectation_bonus = (actual - expected) * 0.5
    
    # Duration factor: logarithmic scaling
    # 30 min = 1.0, 60 min = 1.3, 120 min = 1.5, 300 min = 1.7
    duration_factor = math.log(duration / 30.0 + 1.0) / math.log(2.0)
    duration_factor = min(1.5, duration_factor)  # Cap at 1.5
    
    # Base score with expectation bonus
    base_score = actual + expectation_bonus
    base_score = max(0.0, min(100.0, base_score))  # Clamp to 0-100
    
    # Apply duration factor and aversion multiplier
    relief_score = base_score * duration_factor * aversion_mult
    
    return max(0.0, relief_score)


# Map system IDs to calculation functions
SCORE_CALCULATORS = {
    'execution_score': calculate_execution_score,
    'grit_score': calculate_grit_score,
    'productivity_score': calculate_productivity_score,
    'difficulty_bonus': calculate_difficulty_bonus,
    'obstacles_score': calculate_obstacles_score,
    'composite_score': calculate_composite_score,
    'time_tracking_consistency_score': calculate_time_tracking_consistency,
    'efficiency_score': calculate_efficiency_score,
    'productivity_potential': calculate_productivity_potential,
    'composite_productivity_score': calculate_composite_productivity_score,
    'productivity_points': calculate_productivity_points,
    'relief_points': calculate_relief_points,
    'execution_points': calculate_execution_points,
    'grit_points': calculate_grit_points,
    'obstacles_points': calculate_obstacles_points,
    'composite_points': calculate_composite_points,
    'relief_score': calculate_relief_score,
}
