"""Experimental Formula Control System.

Allows dynamic adjustment of formula parameters with CSV persistence and Plotly visualizations.
Each formula has its own page: /experimental/formula-control-system/{formula-name}
"""
from nicegui import ui
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import math
import plotly.graph_objects as go
import plotly.express as px
from backend.user_state import UserStateManager

# Data directory for formula settings
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
FORMULA_SETTINGS_FILE = os.path.join(DATA_DIR, 'formula_settings.csv')


def ensure_data_dir():
    """Ensure data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_formula_settings(formula_name: str) -> Dict[str, Any]:
    """Load current formula settings from CSV, or return defaults."""
    ensure_data_dir()
    
    defaults = get_formula_defaults(formula_name)
    
    if not os.path.exists(FORMULA_SETTINGS_FILE):
        return defaults
    
    try:
        df = pd.read_csv(FORMULA_SETTINGS_FILE)
        # Get most recent settings for this formula
        formula_rows = df[df['formula_name'] == formula_name]
        if not formula_rows.empty:
            # Get the most recent entry (by timestamp)
            latest = formula_rows.sort_values('timestamp', ascending=False).iloc[0]
            # Convert to dict, excluding metadata columns
            settings = {}
            for col in df.columns:
                if col not in ['formula_name', 'timestamp', 'user_id']:
                    value = latest[col]
                    # Try to convert to appropriate type
                    if pd.notna(value):
                        try:
                            # Try float first
                            settings[col] = float(value)
                        except (ValueError, TypeError):
                            # Fall back to string
                            settings[col] = str(value)
                    else:
                        # Use default if NaN
                        settings[col] = defaults.get(col, 0.0)
            return {**defaults, **settings}
    except Exception as e:
        print(f"[FormulaControl] Error loading settings: {e}")
    
    return defaults


def save_formula_settings(formula_name: str, settings: Dict[str, Any], user_id: str = "default_user"):
    """Save formula settings to CSV."""
    ensure_data_dir()
    
    # Prepare row data
    row_data = {
        'formula_name': formula_name,
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        **settings
    }
    
    # Load existing data or create new DataFrame
    if os.path.exists(FORMULA_SETTINGS_FILE):
        try:
            df = pd.read_csv(FORMULA_SETTINGS_FILE)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    
    # Append new row
    new_row = pd.DataFrame([row_data])
    df = pd.concat([df, new_row], ignore_index=True)
    
    # Save to CSV
    df.to_csv(FORMULA_SETTINGS_FILE, index=False)
    print(f"[FormulaControl] Saved settings for {formula_name}: {settings}")


def get_formula_defaults(formula_name: str) -> Dict[str, Any]:
    """Get default values for a formula."""
    if formula_name == 'productivity-score':
        return {
            'weekly_curve': 'flattened_square',
            'weekly_curve_strength': 1.5,
            'weekly_burnout_threshold_hours': 42.0,
            'daily_burnout_cap_multiplier': 2.0,
            'goal_hours_per_week': 40.0,
            'goal_adjustment_enabled': False,
            'weekly_avg_bonus_enabled': True,
            'burnout_penalty_enabled': False,
            'work_multiplier_min': 3.0,
            'work_multiplier_max': 5.0,
            'work_ratio_threshold_low': 1.0,
            'work_ratio_threshold_high': 1.5,
            'self_care_base_multiplier': 1.0,
            'play_penalty_threshold': 2.0,
            'play_penalty_multiplier': -0.003,
        }
    elif formula_name == 'execution-score':
        return {
            'base_score': 50.0,
            'difficulty_factor_weight': 1.0,
            'speed_factor_weight': 0.5,
            'start_speed_factor_weight': 0.5,
            'completion_factor_enabled': True,
            'speed_very_fast_threshold': 0.5,
            'speed_fast_threshold': 1.0,
            'start_speed_instant_threshold': 5.0,
            'start_speed_fast_threshold': 30.0,
            'start_speed_moderate_threshold': 120.0,
            'start_speed_decay_constant': 240.0,
            'completion_full_threshold': 100.0,
            'completion_near_threshold': 90.0,
            'completion_partial_threshold': 50.0,
        }
    elif formula_name == 'grit-score':
        return {
            'persistence_growth_rate': 0.02,
            'persistence_power': 1.13,
            'persistence_max_multiplier': 5.0,
            'persistence_decay_start': 100.0,
            'persistence_decay_rate': 200.0,
            'time_bonus_linear_rate': 0.5,
            'time_bonus_diminishing_rate': 0.2,
            'time_bonus_max': 3.0,
            'time_bonus_excess_threshold': 1.0,
            'difficulty_weight_min': 0.5,
            'difficulty_weight_max': 1.0,
            'time_bonus_fade_start': 10.0,
            'time_bonus_fade_rate': 40.0,
            'passion_weight': 0.5,
            'passion_min': 0.5,
            'passion_max': 1.5,
            'passion_incomplete_penalty': 0.9,
        }
    return {}


# Navigation page
@ui.page("/experimental/formula-control-system")
def formula_control_system_navigation():
    """Navigation page for formula control system."""
    ui.label("Formula Control System").classes("text-3xl font-bold mb-4")
    ui.label("Adjust formula parameters dynamically with real-time visualizations and CSV persistence.").classes("text-gray-600 mb-6")
    
    with ui.card().classes("w-full max-w-6xl p-6"):
        ui.label("Available Formulas").classes("text-xl font-semibold mb-4")
        
        formulas = [
            {
                'name': 'productivity-score',
                'title': 'Productivity Score',
                'description': 'Controls how productivity scores are calculated based on task completion, efficiency, and goals. Includes work multipliers, weekly bonuses, and burnout penalties.',
                'path': '/experimental/formula-control-system/productivity-score'
            },
            {
                'name': 'execution-score',
                'title': 'Execution Score',
                'description': 'Controls execution score calculation for efficient execution of difficult tasks. Includes difficulty factor, speed factor, start speed, and completion quality.',
                'path': '/experimental/formula-control-system/execution-score'
            },
            {
                'name': 'grit-score',
                'title': 'Grit Score',
                'description': 'Controls grit score calculation that rewards persistence and taking longer. Includes persistence multipliers, time bonuses, and passion factors.',
                'path': '/experimental/formula-control-system/grit-score'
            }
        ]
        
        for formula in formulas:
            with ui.card().classes("p-4 mb-4 border border-gray-300"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("flex-1 gap-2"):
                        ui.label(formula['title']).classes("text-lg font-semibold")
                        ui.label(formula['description']).classes("text-sm text-gray-700")
                    ui.button(
                        "Open",
                        on_click=lambda path=formula['path']: ui.navigate.to(path)
                    ).classes("bg-blue-500 text-white ml-4")
    
    ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-2")


# Visualization functions
def generate_productivity_visualizations(settings: Dict[str, Any], comparison_settings: Optional[List[Dict[str, Any]]] = None) -> List[go.Figure]:
    """Generate Plotly visualizations for productivity score formula."""
    figures = []
    
    # 1. Weekly curve strength effect
    weekly_avg_times = [30, 45, 60, 75, 90]  # minutes
    time_actuals = list(range(15, 120, 5))  # minutes
    
    fig1 = go.Figure()
    
    curve_strength = settings.get('weekly_curve_strength', 1.5)
    curve_type = settings.get('weekly_curve', 'flattened_square')
    
    for weekly_avg in weekly_avg_times:
        multipliers = []
        for time_actual in time_actuals:
            time_percentage_diff = ((time_actual - weekly_avg) / weekly_avg) * 100.0
            if curve_type == 'flattened_square':
                effect = math.copysign((abs(time_percentage_diff) ** 2) / 100.0, time_percentage_diff)
                multiplier = 1.0 - (0.01 * curve_strength * effect)
            else:
                multiplier = 1.0 - (0.01 * curve_strength * time_percentage_diff)
            multipliers.append(multiplier)
        
        fig1.add_trace(go.Scatter(
            x=time_actuals,
            y=multipliers,
            mode='lines',
            name=f'Weekly Avg: {weekly_avg}min',
            line=dict(width=2)
        ))
    
    # Add comparison lines if provided
    if comparison_settings:
        for idx, comp_settings in enumerate(comparison_settings):
            comp_strength = comp_settings.get('weekly_curve_strength', 1.5)
            comp_curve = comp_settings.get('weekly_curve', 'flattened_square')
            for weekly_avg in weekly_avg_times[:1]:  # Just show one line for comparison
                multipliers = []
                for time_actual in time_actuals:
                    time_percentage_diff = ((time_actual - weekly_avg) / weekly_avg) * 100.0
                    if comp_curve == 'flattened_square':
                        effect = math.copysign((abs(time_percentage_diff) ** 2) / 100.0, time_percentage_diff)
                        multiplier = 1.0 - (0.01 * comp_strength * effect)
                    else:
                        multiplier = 1.0 - (0.01 * comp_strength * time_percentage_diff)
                    multipliers.append(multiplier)
                
                fig1.add_trace(go.Scatter(
                    x=time_actuals,
                    y=multipliers,
                    mode='lines',
                    name=f'Comparison {idx+1} (avg {weekly_avg}min)',
                    line=dict(width=2, dash='dash', color='gray')
                ))
    
    fig1.update_layout(
        title='Weekly Efficiency Bonus/Penalty Multiplier',
        xaxis_title='Actual Time (minutes)',
        yaxis_title='Multiplier',
        height=400,
        font=dict(size=10),
        title_font=dict(size=12),
        legend=dict(font=dict(size=9))
    )
    figures.append(fig1)
    
    # 2. Work multiplier transition
    ratios = [x / 100.0 for x in range(50, 250, 2)]  # 0.5 to 2.5
    multipliers = []
    
    min_mult = settings.get('work_multiplier_min', 3.0)
    max_mult = settings.get('work_multiplier_max', 5.0)
    threshold_low = settings.get('work_ratio_threshold_low', 1.0)
    threshold_high = settings.get('work_ratio_threshold_high', 1.5)
    
    fig2 = go.Figure()
    
    for ratio in ratios:
        if ratio <= threshold_low:
            mult = min_mult
        elif ratio >= threshold_high:
            mult = max_mult
        else:
            smooth_factor = (ratio - threshold_low) / (threshold_high - threshold_low)
            mult = min_mult + (max_mult - min_mult) * smooth_factor
        multipliers.append(mult)
    
    fig2.add_trace(go.Scatter(
        x=ratios,
        y=multipliers,
        mode='lines',
        name='Work Multiplier',
        line=dict(width=2, color='blue')
    ))
    
    fig2.update_layout(
        title='Work Task Multiplier vs Completion/Time Ratio',
        xaxis_title='Completion/Time Ratio',
        yaxis_title='Multiplier',
        height=400,
        font=dict(size=10),
        title_font=dict(size=12)
    )
    figures.append(fig2)
    
    return figures


def generate_execution_visualizations(settings: Dict[str, Any], comparison_settings: Optional[List[Dict[str, Any]]] = None) -> List[go.Figure]:
    """Generate Plotly visualizations for execution score formula."""
    figures = []
    
    # 1. Speed factor
    time_ratios = [x / 100.0 for x in range(10, 400, 2)]  # 0.1 to 4.0
    speed_factors = []
    
    very_fast_threshold = settings.get('speed_very_fast_threshold', 0.5)
    fast_threshold = settings.get('speed_fast_threshold', 1.0)
    
    fig1 = go.Figure()
    
    for ratio in time_ratios:
        if ratio <= very_fast_threshold:
            speed_factor = 1.0
        elif ratio <= fast_threshold:
            speed_factor = 1.0 - (ratio - very_fast_threshold) * 1.0
        else:
            speed_factor = 0.5 * (1.0 / ratio)
        speed_factors.append(speed_factor)
    
    fig1.add_trace(go.Scatter(
        x=time_ratios,
        y=speed_factors,
        mode='lines',
        name='Speed Factor',
        line=dict(width=2, color='green')
    ))
    
    fig1.update_layout(
        title='Speed Factor vs Time Ratio (actual/estimate)',
        xaxis_title='Time Ratio',
        yaxis_title='Speed Factor',
        height=400,
        font=dict(size=10),
        title_font=dict(size=12)
    )
    figures.append(fig1)
    
    # 2. Start speed factor
    delays = list(range(0, 480, 5))  # 0 to 480 minutes
    start_factors = []
    
    instant_threshold = settings.get('start_speed_instant_threshold', 5.0)
    fast_threshold = settings.get('start_speed_fast_threshold', 30.0)
    moderate_threshold = settings.get('start_speed_moderate_threshold', 120.0)
    decay_constant = settings.get('start_speed_decay_constant', 240.0)
    
    for delay in delays:
        if delay <= instant_threshold:
            factor = 1.0
        elif delay <= fast_threshold:
            factor = 1.0 - ((delay - instant_threshold) / (fast_threshold - instant_threshold)) * 0.2
        elif delay <= moderate_threshold:
            factor = 0.8 - ((delay - fast_threshold) / (moderate_threshold - fast_threshold)) * 0.3
        else:
            excess = delay - moderate_threshold
            factor = 0.5 * math.exp(-excess / decay_constant)
        start_factors.append(factor)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=delays,
        y=start_factors,
        mode='lines',
        name='Start Speed Factor',
        line=dict(width=2, color='orange')
    ))
    
    fig2.update_layout(
        title='Start Speed Factor vs Delay (minutes)',
        xaxis_title='Start Delay (minutes)',
        yaxis_title='Start Speed Factor',
        height=400,
        font=dict(size=10),
        title_font=dict(size=12)
    )
    figures.append(fig2)
    
    # 3. Overall execution score with varying difficulty
    base_score = settings.get('base_score', 50.0)
    difficulty_levels = [x for x in range(0, 101, 5)]  # 0 to 100
    execution_scores = []
    
    # Assume speed_factor = 1.0, start_speed_factor = 1.0, completion = 100%
    speed_factor = 1.0
    start_speed_factor = 1.0
    completion_factor = 1.0
    
    for difficulty in difficulty_levels:
        difficulty_factor = max(0.0, min(1.0, difficulty / 100.0))
        score = base_score * (
            (1.0 + difficulty_factor) *
            (0.5 + speed_factor * 0.5) *
            (0.5 + start_speed_factor * 0.5) *
            completion_factor
        )
        execution_scores.append(min(100.0, score))
    
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=difficulty_levels,
        y=execution_scores,
        mode='lines',
        name='Execution Score',
        line=dict(width=2, color='purple')
    ))
    
    fig3.update_layout(
        title='Execution Score vs Task Difficulty (optimal speed)',
        xaxis_title='Task Difficulty (0-100)',
        yaxis_title='Execution Score',
        height=400,
        font=dict(size=10),
        title_font=dict(size=12)
    )
    figures.append(fig3)
    
    return figures


def generate_grit_visualizations(settings: Dict[str, Any], comparison_settings: Optional[List[Dict[str, Any]]] = None) -> List[go.Figure]:
    """Generate Plotly visualizations for grit score formula."""
    figures = []
    
    # 1. Persistence multiplier
    completion_counts = list(range(1, 200, 2))
    persistence_multipliers = []
    
    growth_rate = settings.get('persistence_growth_rate', 0.02)
    power = settings.get('persistence_power', 1.13)
    max_mult = settings.get('persistence_max_multiplier', 5.0)
    decay_start = settings.get('persistence_decay_start', 100.0)
    decay_rate = settings.get('persistence_decay_rate', 200.0)
    
    fig1 = go.Figure()
    
    for count in completion_counts:
        raw_multiplier = 1.0 + growth_rate * max(0, count - 1) ** power
        if count > decay_start:
            decay = 1.0 / (1.0 + (count - decay_start) / decay_rate)
        else:
            decay = 1.0
        multiplier = max(1.0, min(max_mult, raw_multiplier * decay))
        persistence_multipliers.append(multiplier)
    
    fig1.add_trace(go.Scatter(
        x=completion_counts,
        y=persistence_multipliers,
        mode='lines',
        name='Persistence Multiplier',
        line=dict(width=2, color='brown')
    ))
    
    fig1.update_layout(
        title='Persistence Multiplier vs Completion Count',
        xaxis_title='Task Completion Count',
        yaxis_title='Persistence Multiplier',
        height=400,
        font=dict(size=10),
        title_font=dict(size=12)
    )
    figures.append(fig1)
    
    # 2. Time bonus
    time_ratios = [x / 100.0 for x in range(50, 500, 2)]  # 0.5 to 5.0
    time_bonuses = []
    
    linear_rate = settings.get('time_bonus_linear_rate', 0.5)
    diminishing_rate = settings.get('time_bonus_diminishing_rate', 0.2)
    max_bonus = settings.get('time_bonus_max', 3.0)
    excess_threshold = settings.get('time_bonus_excess_threshold', 1.0)
    difficulty_weight_min = settings.get('difficulty_weight_min', 0.5)
    difficulty_weight_max = settings.get('difficulty_weight_max', 1.0)
    fade_start = settings.get('time_bonus_fade_start', 10.0)
    fade_rate = settings.get('time_bonus_fade_rate', 40.0)
    
    # Show for different completion counts and difficulty levels
    for completion_count in [1, 10, 50]:
        for difficulty in [0, 50, 100]:
            bonuses = []
            difficulty_factor = max(0.0, min(1.0, difficulty / 100.0))
            fade = 1.0 / (1.0 + max(0, completion_count - fade_start) / fade_rate)
            
            for ratio in time_ratios:
                if ratio > 1.0:
                    excess = ratio - 1.0
                    if excess <= excess_threshold:
                        base_bonus = 1.0 + (excess * linear_rate)
                    else:
                        base_bonus = 1.0 + (excess_threshold * linear_rate) + ((excess - excess_threshold) * diminishing_rate)
                    base_bonus = min(max_bonus, base_bonus)
                    
                    weighted_bonus = 1.0 + (base_bonus - 1.0) * (difficulty_weight_min + (difficulty_weight_max - difficulty_weight_min) * difficulty_factor)
                    time_bonus = 1.0 + (weighted_bonus - 1.0) * fade
                else:
                    time_bonus = 1.0
                bonuses.append(time_bonus)
            
            fig1_name = f'Count {completion_count}, Difficulty {difficulty}'
            if completion_count == 1 and difficulty == 50:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=time_ratios,
                    y=bonuses,
                    mode='lines',
                    name=fig1_name,
                    line=dict(width=2)
                ))
    
    if 'fig2' in locals():
        fig2.update_layout(
            title='Time Bonus vs Time Ratio (example: count=1, difficulty=50)',
            xaxis_title='Time Ratio (actual/estimate)',
            yaxis_title='Time Bonus',
            height=400,
            font=dict(size=10),
            title_font=dict(size=12)
        )
        figures.append(fig2)
    
    return figures


# Continue with the rest of the file - I'll add the page creation functions next
# Due to length, I'll create a helper function to generate formula pages

def create_formula_control_page(formula_name: str, metadata_func, visualization_func):
    """Create a formula control page with parameters, visualizations, and comparison."""
    
    @ui.page(f"/experimental/formula-control-system/{formula_name}")
    def formula_page():
        metadata = metadata_func(formula_name)
        current_settings = load_formula_settings(formula_name)
        
        ui.label(metadata['title']).classes("text-3xl font-bold mb-2")
        ui.label(metadata['description']).classes("text-gray-600 mb-6")
        
        # Settings form
        with ui.card().classes("w-full max-w-7xl p-4 mb-4"):
            ui.label("Formula Parameters").classes("text-xl font-semibold mb-4")
            
            input_refs = {}
            settings_state = current_settings.copy()
            comparison_sets = []  # Store comparison parameter sets
            
            def create_parameter_control(param_key: str, param_meta: Dict[str, Any]):
                """Create a UI control for a parameter."""
                param_name = param_meta.get('name', param_key)
                param_desc = param_meta.get('description', '')
                param_type = param_meta.get('type', 'number')
                default_value = current_settings.get(param_key, param_meta.get('default', 0))
                
                with ui.card().classes("p-3 mb-3 border border-gray-200"):
                    with ui.row().classes("items-center gap-2 w-full mb-2"):
                        ui.label(param_name).classes("font-semibold flex-1")
                        if param_desc:
                            ui.tooltip(param_desc).style("max-width: 400px; white-space: normal;")
                    
                    if param_type == 'select':
                        options = param_meta.get('options', [])
                        control = ui.select(
                            options={opt: opt.replace('_', ' ').title() for opt in options},
                            value=default_value,
                            label=param_name
                        ).props("dense outlined").classes("w-full")
                        control.on('update:model-value', lambda e, key=param_key: settings_state.update({key: e.args if hasattr(e, 'args') else e}) or update_visualizations())
                        input_refs[param_key] = control
                        
                    elif param_type == 'checkbox':
                        control = ui.checkbox(param_name, value=bool(default_value))
                        control.on('update:model-value', lambda e, key=param_key: settings_state.update({key: bool(e.args if hasattr(e, 'args') else e)}) or update_visualizations())
                        input_refs[param_key] = control
                        
                    else:  # number
                        min_val = param_meta.get('min', 0.0)
                        max_val = param_meta.get('max', 100.0)
                        step = param_meta.get('step', 0.1)
                        
                        control = ui.number(
                            label=param_name,
                            value=float(default_value),
                            min=min_val,
                            max=max_val,
                            step=step,
                            format="%.2f" if step < 1.0 else "%.1f"
                        ).props("dense outlined").classes("w-full")
                        control.on('update:model-value', lambda e, key=param_key: settings_state.update({key: float(e.args if hasattr(e, 'args') else e)}) or update_visualizations())
                        input_refs[param_key] = control
                    
                    if param_meta.get('note'):
                        ui.label(param_meta['note']).classes("text-xs text-blue-600 mt-1 italic")
            
            # Create controls for each parameter
            for param_key, param_meta in metadata['parameters'].items():
                create_parameter_control(param_key, param_meta)
            
            # Comparison section
            with ui.card().classes("p-3 mb-3 border border-blue-300 bg-blue-50"):
                ui.label("Parameter Comparison").classes("text-lg font-semibold mb-2")
                ui.label("Save current settings as a comparison set to overlay on visualizations.").classes("text-sm text-gray-700 mb-2")
                
                comparison_display = ui.column().classes("w-full mb-2")
                
                def add_comparison():
                    comparison_sets.append(settings_state.copy())
                    update_comparison_display()
                    update_visualizations()
                    ui.notify(f"Added comparison set {len(comparison_sets)}", color="info")
                
                def clear_comparisons():
                    comparison_sets.clear()
                    update_comparison_display()
                    update_visualizations()
                    ui.notify("Cleared all comparisons", color="info")
                
                def update_comparison_display():
                    comparison_display.clear()
                    with comparison_display:
                        if comparison_sets:
                            for idx, comp_set in enumerate(comparison_sets):
                                ui.label(f"Comparison {idx+1}").classes("text-sm font-mono bg-white px-2 py-1 rounded mb-1")
                        else:
                            ui.label("No comparison sets added").classes("text-xs text-gray-500")
                
                ui.button("Add Current as Comparison", on_click=add_comparison).classes("bg-blue-500 text-white")
                ui.button("Clear Comparisons", on_click=clear_comparisons).classes("bg-gray-500 text-white ml-2")
                update_comparison_display()
            
            # Save and reset buttons
            def save_settings():
                save_formula_settings(formula_name, settings_state)
                if formula_name == 'productivity-score':
                    user_state = UserStateManager()
                    user_id = "default_user"
                    productivity_settings = {
                        'weekly_curve': settings_state.get('weekly_curve', 'flattened_square'),
                        'weekly_curve_strength': settings_state.get('weekly_curve_strength', 1.5),
                        'weekly_burnout_threshold_hours': settings_state.get('weekly_burnout_threshold_hours', 42.0),
                        'daily_burnout_cap_multiplier': settings_state.get('daily_burnout_cap_multiplier', 2.0),
                    }
                    user_state.set_productivity_settings(user_id, productivity_settings)
                ui.notify("Settings saved!", color="positive")
            
            def reset_to_defaults():
                defaults = get_formula_defaults(formula_name)
                settings_state.clear()
                settings_state.update(defaults)
                for key, control in input_refs.items():
                    if key in defaults:
                        if hasattr(control, 'set_value'):
                            control.set_value(defaults[key])
                update_visualizations()
                ui.notify("Reset to defaults", color="info")
            
            with ui.row().classes("mt-4 gap-2"):
                ui.button("Save Settings", on_click=save_settings).classes("bg-green-500 text-white")
                ui.button("Reset to Defaults", on_click=reset_to_defaults).classes("bg-gray-500 text-white")
        
        # Visualization section
        visualization_container = ui.column().classes("w-full max-w-7xl")
        
        def update_visualizations():
            visualization_container.clear()
            with visualization_container:
                ui.label("Formula Visualizations").classes("text-xl font-semibold mb-4")
                try:
                    figures = visualization_func(settings_state, comparison_sets if comparison_sets else None)
                    for fig in figures:
                        ui.plotly(fig).classes("w-full mb-6")
                except Exception as e:
                    ui.label(f"Error generating visualizations: {e}").classes("text-red-500")
                    import traceback
                    ui.code(traceback.format_exc()).classes("text-xs")
        
        with visualization_container:
            update_visualizations()
        
        ui.button("Back to Formula Control", on_click=lambda: ui.navigate.to("/experimental/formula-control-system")).classes("mt-4")
        ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-2")
    
    return formula_page


# Get formula metadata function (needs to be completed)
def get_formula_metadata(formula_name: str) -> Dict[str, Any]:
    """Get metadata (descriptions, ranges, etc.) for formula parameters."""
    if formula_name == 'productivity-score':
        return {
            'title': 'Productivity Score Formula',
            'description': 'Controls how productivity scores are calculated based on task completion, efficiency, and goals.',
            'parameters': {
                'weekly_curve': {
                    'name': 'Weekly Curve Type',
                    'description': 'Response curve for weekly average bonus/penalty',
                    'type': 'select',
                    'options': ['linear', 'flattened_square'],
                    'default': 'flattened_square'
                },
                'weekly_curve_strength': {
                    'name': 'Weekly Curve Strength',
                    'description': 'Strength of weekly efficiency adjustment (0.0-2.0)',
                    'type': 'number',
                    'min': 0.0,
                    'max': 2.0,
                    'step': 0.1,
                    'default': 1.5,
                    'note': 'Note: This affects per-task efficiency bonuses.'
                },
                'work_multiplier_min': {
                    'name': 'Work Multiplier Minimum',
                    'description': 'Minimum multiplier for work tasks',
                    'type': 'number',
                    'min': 1.0,
                    'max': 10.0,
                    'step': 0.1,
                    'default': 3.0
                },
                'work_multiplier_max': {
                    'name': 'Work Multiplier Maximum',
                    'description': 'Maximum multiplier for work tasks',
                    'type': 'number',
                    'min': 1.0,
                    'max': 10.0,
                    'step': 0.1,
                    'default': 5.0
                },
                'work_ratio_threshold_low': {
                    'name': 'Work Ratio Threshold Low',
                    'description': 'Completion/time ratio below which minimum multiplier applies',
                    'type': 'number',
                    'min': 0.1,
                    'max': 2.0,
                    'step': 0.1,
                    'default': 1.0
                },
                'work_ratio_threshold_high': {
                    'name': 'Work Ratio Threshold High',
                    'description': 'Completion/time ratio above which maximum multiplier applies',
                    'type': 'number',
                    'min': 0.1,
                    'max': 3.0,
                    'step': 0.1,
                    'default': 1.5
                },
            }
        }
    elif formula_name == 'execution-score':
        return {
            'title': 'Execution Score Formula',
            'description': 'Controls execution score calculation for efficient execution of difficult tasks.',
            'parameters': {
                'base_score': {
                    'name': 'Base Score',
                    'description': 'Base execution score (neutral starting point)',
                    'type': 'number',
                    'min': 0.0,
                    'max': 100.0,
                    'step': 1.0,
                    'default': 50.0
                },
                'speed_very_fast_threshold': {
                    'name': 'Very Fast Threshold',
                    'description': 'Time ratio below which max speed bonus applies',
                    'type': 'number',
                    'min': 0.1,
                    'max': 1.0,
                    'step': 0.1,
                    'default': 0.5
                },
                'speed_fast_threshold': {
                    'name': 'Fast Threshold',
                    'description': 'Time ratio below which linear speed bonus applies',
                    'type': 'number',
                    'min': 0.1,
                    'max': 2.0,
                    'step': 0.1,
                    'default': 1.0
                },
            }
        }
    elif formula_name == 'grit-score':
        return {
            'title': 'Grit Score Formula',
            'description': 'Controls grit score calculation that rewards persistence and taking longer.',
            'parameters': {
                'persistence_growth_rate': {
                    'name': 'Persistence Growth Rate',
                    'description': 'Rate at which persistence multiplier grows',
                    'type': 'number',
                    'min': 0.0,
                    'max': 0.1,
                    'step': 0.001,
                    'default': 0.02
                },
                'persistence_power': {
                    'name': 'Persistence Power',
                    'description': 'Power curve exponent for persistence growth',
                    'type': 'number',
                    'min': 0.5,
                    'max': 2.0,
                    'step': 0.01,
                    'default': 1.13
                },
                'time_bonus_linear_rate': {
                    'name': 'Time Bonus Linear Rate',
                    'description': 'Linear rate for time bonus when taking longer',
                    'type': 'number',
                    'min': 0.0,
                    'max': 1.0,
                    'step': 0.1,
                    'default': 0.5
                },
            }
        }
    return {'title': 'Unknown Formula', 'description': '', 'parameters': {}}


# Create pages for each formula
productivity_score_formula_control = create_formula_control_page(
    'productivity-score',
    get_formula_metadata,
    generate_productivity_visualizations
)

execution_score_formula_control = create_formula_control_page(
    'execution-score',
    get_formula_metadata,
    generate_execution_visualizations
)

grit_score_formula_control = create_formula_control_page(
    'grit-score',
    get_formula_metadata,
    generate_grit_visualizations
)


def register_formula_control_system():
    """Register all formula control pages."""
    # Pages are registered via decorators
    pass
