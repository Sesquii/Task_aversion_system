"""
Formula Baseline Charts System

Generates theoretical charts (6 per variable) and correlation charts for all score/points systems.
Includes notes system with CSV storage for formula refinement analysis.
"""
from nicegui import ui
from typing import Dict, List, Optional, Tuple
import os
import csv
import json
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import math
from ui.formula_chart_generators import (
    generate_6_charts_for_variable,
    generate_correlation_charts,
    SCORE_CALCULATORS
)

# Score/Points system definitions
SCORE_SYSTEMS = {
    'execution_score': {
        'title': 'Execution Score',
        'description': 'Rewards efficient execution of difficult tasks',
        'components': [
            {'name': 'difficulty_factor', 'range': (0, 1), 'description': 'Difficulty bonus (0-1)'},
            {'name': 'speed_factor', 'range': (0, 1), 'description': 'Speed efficiency (0-1)'},
            {'name': 'start_speed_factor', 'range': (0, 1), 'description': 'Start speed (0-1)'},
            {'name': 'completion_factor', 'range': (0, 1), 'description': 'Completion quality (0-1)'},
        ],
        'formula': 'execution_score = 50 * (1.0 + difficulty_factor) * (0.5 + speed_factor * 0.5) * (0.5 + start_speed_factor * 0.5) * completion_factor',
        'range': '0-100',
        'has_points': False,
        'weights': {'difficulty_factor': 1.0, 'speed_factor': 0.5, 'start_speed_factor': 0.5, 'completion_factor': 1.0}
    },
    'grit_score': {
        'title': 'Grit Score',
        'description': 'Rewards persistence and taking on difficult tasks',
        'components': [
            {'name': 'difficulty_bonus', 'range': (0, 1), 'description': 'Difficulty bonus (0-1)'},
            {'name': 'time_bonus', 'range': (0, 2), 'description': 'Time bonus (0-2)'},
            {'name': 'passion_factor', 'range': (0.5, 1.5), 'description': 'Passion factor (0.5-1.5)'},
        ],
        'formula': 'grit_score = completion_pct * persistence_multiplier * time_bonus * passion_factor',
        'range': '0-100+',
        'has_points': False,
        'weights': {'difficulty_bonus': 1.0, 'time_bonus': 1.0, 'passion_factor': 1.0}
    },
    'productivity_score': {
        'title': 'Productivity Score',
        'description': 'Measures productive task completion',
        'components': [
            {'name': 'completion_pct', 'range': (0, 100), 'description': 'Completion percentage (0-100)'},
            {'name': 'task_type_multiplier', 'range': (1, 5), 'description': 'Task type multiplier (1-5)'},
            {'name': 'weekly_avg_multiplier', 'range': (0.5, 1.5), 'description': 'Weekly average multiplier (0.5-1.5)'},
            {'name': 'goal_multiplier', 'range': (0.8, 1.2), 'description': 'Goal achievement multiplier (0.8-1.2)'},
        ],
        'formula': 'productivity_score = completion_pct * task_type_multiplier * weekly_avg_multiplier * goal_multiplier',
        'range': '0-550+',
        'has_points': True,
        'weights': {'completion_pct': 1.0, 'task_type_multiplier': 1.0, 'weekly_avg_multiplier': 1.0, 'goal_multiplier': 1.0}
    },
    'obstacles_score': {
        'title': 'Obstacles Score',
        'description': 'Rewards overcoming spontaneous aversion spikes',
        'components': [
            {'name': 'spike_amount', 'range': (0, 100), 'description': 'Spike amount (0-100)'},
            {'name': 'relief_score', 'range': (0, 100), 'description': 'Relief score (0-100)'},
        ],
        'formula': 'obstacles_score = (spike_amount * multiplier) / 50.0',
        'range': '0-100+',
        'has_points': False,
        'weights': {'spike_amount': 1.0, 'relief_score': 1.0}
    },
    'difficulty_bonus': {
        'title': 'Difficulty Bonus',
        'description': 'Bonus for completing difficult tasks',
        'components': [
            {'name': 'aversion', 'range': (0, 100), 'description': 'Aversion level (0-100)'},
            {'name': 'mental_energy', 'range': (0, 100), 'description': 'Mental energy needed (0-100)'},
            {'name': 'task_difficulty', 'range': (0, 100), 'description': 'Task difficulty (0-100)'},
        ],
        'formula': 'bonus = 1.0 * (1 - exp(-(0.7 * aversion + 0.3 * load) / 50))',
        'range': '0.0-1.0',
        'has_points': False,
        'weights': {'aversion': 0.7, 'mental_energy': 0.3, 'task_difficulty': 0.0}
    },
    'composite_score': {
        'title': 'Composite Score',
        'description': 'Combines multiple scores with weights',
        'components': [
            {'name': 'tracking_consistency', 'range': (0, 100), 'description': 'Tracking consistency (0-100)'},
            {'name': 'execution_score', 'range': (0, 100), 'description': 'Execution score (0-100)'},
            {'name': 'productivity_score', 'range': (0, 100), 'description': 'Productivity score (0-100)'},
            {'name': 'grit_score', 'range': (0, 100), 'description': 'Grit score (0-100)'},
        ],
        'formula': 'composite_score = Σ(component_score * normalized_weight)',
        'range': '0-100',
        'has_points': False,
        'weights': {'tracking_consistency': 1.0, 'execution_score': 1.0, 'productivity_score': 1.0, 'grit_score': 1.0}
    },
    'time_tracking_consistency_score': {
        'title': 'Time Tracking Consistency Score',
        'description': 'Measures how well time is tracked',
        'components': [
            {'name': 'tracking_coverage', 'range': (0, 1), 'description': 'Tracking coverage ratio (0-1)'},
        ],
        'formula': 'score = 100 × (1 - exp(-tracking_coverage × 2.0))',
        'range': '0-100',
        'has_points': False,
        'weights': {'tracking_coverage': 1.0}
    },
    'efficiency_score': {
        'title': 'Efficiency Score',
        'description': 'Measures task execution efficiency',
        'components': [
            {'name': 'time_actual', 'range': (0, 300), 'description': 'Actual time (minutes)'},
            {'name': 'time_estimate', 'range': (0, 300), 'description': 'Estimated time (minutes)'},
            {'name': 'completion_pct', 'range': (0, 100), 'description': 'Completion percentage (0-100)'},
        ],
        'formula': 'efficiency_score = f(time_actual, time_estimate, completion_pct)',
        'range': '0-100',
        'has_points': False,
        'weights': {'time_actual': 1.0, 'time_estimate': 1.0, 'completion_pct': 1.0}
    },
    'productivity_potential': {
        'title': 'Productivity Potential',
        'description': 'Estimates potential productivity based on efficiency',
        'components': [
            {'name': 'avg_efficiency_score', 'range': (0, 100), 'description': 'Average efficiency (0-100)'},
            {'name': 'avg_daily_work_time', 'range': (0, 16), 'description': 'Average daily work time (hours)'},
        ],
        'formula': 'potential = f(efficiency_score, daily_work_time)',
        'range': '0-100',
        'has_points': False,
        'weights': {'avg_efficiency_score': 1.0, 'avg_daily_work_time': 1.0}
    },
    'composite_productivity_score': {
        'title': 'Composite Productivity Score',
        'description': 'Combines efficiency and volume',
        'components': [
            {'name': 'efficiency_score', 'range': (0, 100), 'description': 'Efficiency score (0-100)'},
            {'name': 'volume_score', 'range': (0, 100), 'description': 'Volume score (0-100)'},
        ],
        'formula': 'composite_productivity = f(efficiency_score, volume_score)',
        'range': '0-100',
        'has_points': False,
        'weights': {'efficiency_score': 1.0, 'volume_score': 1.0}
    },
    'productivity_points': {
        'title': 'Productivity Points',
        'description': 'Productivity points (score × time)',
        'components': [
            {'name': 'productivity_score', 'range': (0, 550), 'description': 'Productivity score (0-550)'},
            {'name': 'time_hours', 'range': (0, 16), 'description': 'Time in hours (0-16)'},
        ],
        'formula': 'productivity_points = productivity_score * time_hours',
        'range': '0-8800+',
        'has_points': True,
        'weights': {'productivity_score': 1.0, 'time_hours': 1.0}
    },
    'relief_points': {
        'title': 'Relief Points',
        'description': 'Points based on actual vs expected relief',
        'components': [
            {'name': 'actual_relief', 'range': (0, 100), 'description': 'Actual relief (0-100)'},
            {'name': 'expected_relief', 'range': (0, 100), 'description': 'Expected relief (0-100)'},
            {'name': 'aversion_multiplier', 'range': (0.5, 2.0), 'description': 'Aversion multiplier (0.5-2.0)'},
        ],
        'formula': 'relief_points = (actual_relief - expected_relief) * aversion_multiplier',
        'range': '-200 to +200',
        'has_points': True,
        'weights': {'actual_relief': 1.0, 'expected_relief': 1.0, 'aversion_multiplier': 1.0}
    },
    'execution_points': {
        'title': 'Execution Points',
        'description': 'Execution points (score × time)',
        'components': [
            {'name': 'execution_score', 'range': (0, 100), 'description': 'Execution score (0-100)'},
            {'name': 'time_hours', 'range': (0, 16), 'description': 'Time in hours (0-16)'},
        ],
        'formula': 'execution_points = execution_score * time_hours',
        'range': '0-1600+',
        'has_points': True,
        'weights': {'execution_score': 1.0, 'time_hours': 1.0}
    },
    'grit_points': {
        'title': 'Grit Points',
        'description': 'Grit points (score × time)',
        'components': [
            {'name': 'grit_score', 'range': (0, 200), 'description': 'Grit score (0-200+)'},
            {'name': 'time_hours', 'range': (0, 16), 'description': 'Time in hours (0-16)'},
        ],
        'formula': 'grit_points = grit_score * time_hours',
        'range': '0-3200+',
        'has_points': True,
        'weights': {'grit_score': 1.0, 'time_hours': 1.0}
    },
    'obstacles_points': {
        'title': 'Obstacles Points',
        'description': 'Points for overcoming obstacles',
        'components': [
            {'name': 'obstacles_score', 'range': (0, 200), 'description': 'Obstacles score (0-200+)'},
            {'name': 'time_hours', 'range': (0, 16), 'description': 'Time in hours (0-16)'},
        ],
        'formula': 'obstacles_points = obstacles_score * time_hours',
        'range': '0-3200+',
        'has_points': True,
        'weights': {'obstacles_score': 1.0, 'time_hours': 1.0}
    },
    'composite_points': {
        'title': 'Composite Points',
        'description': 'Composite points (score × time)',
        'components': [
            {'name': 'composite_score', 'range': (0, 100), 'description': 'Composite score (0-100)'},
            {'name': 'time_hours', 'range': (0, 16), 'description': 'Time in hours (0-16)'},
        ],
        'formula': 'composite_points = composite_score * time_hours',
        'range': '0-1600+',
        'has_points': True,
        'weights': {'composite_score': 1.0, 'time_hours': 1.0}
    },
    'relief_score': {
        'title': 'Relief Score',
        'description': 'Normalized score based on actual relief, expectations, duration, and aversion (prototype formula)',
        'components': [
            {'name': 'actual_relief', 'range': (0, 100), 'description': 'Actual relief experienced (0-100)'},
            {'name': 'expected_relief', 'range': (0, 100), 'description': 'Expected relief (0-100)'},
            {'name': 'duration_minutes', 'range': (0, 300), 'description': 'Task duration (minutes)'},
            {'name': 'aversion_multiplier', 'range': (0.5, 2.0), 'description': 'Aversion multiplier (0.5-2.0)'},
        ],
        'formula': 'relief_score = (actual_relief + (actual - expected) * 0.5) * log(duration/30 + 1) / log(2) * aversion_mult',
        'range': '0-200+',
        'has_points': False,
        'weights': {'actual_relief': 1.0, 'expected_relief': 0.5, 'duration_minutes': 0.3, 'aversion_multiplier': 0.7}
    }
}

# Notes storage file
NOTES_FILE = os.path.join('data', 'formula_baseline_notes.csv')


def ensure_notes_file():
    """Ensure notes CSV file exists with proper headers."""
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'score_system', 'chart_id', 'notes'])


def save_note(score_system: str, chart_id: str, notes: str):
    """Save notes for a specific chart."""
    ensure_notes_file()
    with open(NOTES_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(), score_system, chart_id, notes])


def load_notes(score_system: str, chart_id: str) -> str:
    """Load notes for a specific chart."""
    ensure_notes_file()
    if not os.path.exists(NOTES_FILE):
        return ''
    
    notes_list = []
    with open(NOTES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('score_system') == score_system and row.get('chart_id') == chart_id:
                notes_list.append(row.get('notes', ''))
    
    # Return most recent note
    return notes_list[-1] if notes_list else ''


def generate_theoretical_charts(score_system: str, variable: str) -> List[go.Figure]:
    """Generate 6 theoretical charts for a variable in a score system."""
    system = SCORE_SYSTEMS.get(score_system)
    if not system:
        return []
    
    # Use the chart generator
    calculate_func = SCORE_CALCULATORS.get(score_system)
    if not calculate_func:
        return []
    
    # Find the variable definition
    var_def = None
    all_vars = []
    for comp in system.get('components', []):
        if isinstance(comp, dict):
            all_vars.append(comp)
            if comp.get('name') == variable:
                var_def = comp
        else:
            # String format - convert to dict
            comp_dict = {'name': comp, 'range': (0, 100), 'description': comp}
            all_vars.append(comp_dict)
            if comp == variable:
                var_def = comp_dict
    
    if not var_def:
        # Create a default variable definition
        var_def = {'name': variable, 'range': (0, 100), 'description': variable}
    
    # Convert system to format expected by generator
    system_info = {
        'variables': all_vars,
        'weights': system.get('weights', {c if isinstance(c, str) else c['name']: 1.0 for c in system['components']})
    }
    
    charts = generate_6_charts_for_variable(score_system, var_def, system_info, calculate_func)
    return charts


def generate_correlation_charts_for_system(score_system: str, weights: Dict[str, float]) -> List[go.Figure]:
    """Generate correlation charts for a score system with given weights."""
    system = SCORE_SYSTEMS.get(score_system)
    if not system:
        return []
    
    calculate_func = SCORE_CALCULATORS.get(score_system)
    if not calculate_func:
        return []
    
    # Convert components to variables format expected by generator
    variables = []
    for comp in system['components']:
        if isinstance(comp, dict):
            variables.append(comp)
        else:
            # String format - convert to dict
            variables.append({'name': comp, 'range': (0, 100), 'description': comp})
    
    system_info = {
        'variables': variables,
        'weights': weights
    }
    
    charts = generate_correlation_charts(score_system, system_info, calculate_func)
    return charts


def build_formula_baseline_page(score_system: str):
    """Build the formula baseline charts page for a specific score system."""
    system = SCORE_SYSTEMS.get(score_system)
    if not system:
        ui.label(f"Score system '{score_system}' not found").classes("text-red-500")
        return
    
    # Header
    with ui.row().classes("items-center gap-3 mb-4"):
        ui.button("← Back", on_click=lambda: ui.navigate.to('/experimental/formula-baseline-charts')).classes(
            "bg-gray-500 text-white"
        )
        ui.label(system['title']).classes("text-3xl font-bold")
        ui.label(f"({system['range']})").classes("text-lg text-gray-600")
    
    ui.label(system['description']).classes("text-lg text-gray-700 mb-2")
    ui.code(system['formula']).classes("text-sm mb-6")
    
    # Generate charts for each component
    for component in system['components']:
        # Handle both string and dict formats
        if isinstance(component, str):
            var_name = component
            var_def = {'name': component, 'range': (0, 100), 'description': component}
        else:
            var_name = component['name']
            var_def = component
        
        with ui.card().classes("p-4 mb-6"):
            ui.label(f"Variable: {var_name}").classes("text-xl font-semibold mb-4")
            if isinstance(component, dict):
                ui.label(component.get('description', '')).classes("text-gray-600 mb-2")
                ui.label(f"Range: {component.get('range', 'N/A')}").classes("text-sm text-gray-500 mb-4")
            
            # Generate 6 theoretical charts
            charts = generate_theoretical_charts(score_system, var_name)
            
            if charts:
                with ui.grid(columns=2).classes("gap-4 mb-4"):
                    for i, chart in enumerate(charts[:4]):  # First 4 in grid
                        ui.plotly(chart).classes("w-full")
                
                with ui.row().classes("gap-4 mb-4"):
                    for chart in charts[4:]:  # Last 2 in row
                        ui.plotly(chart).classes("flex-1")
            else:
                ui.label("Charts coming soon...").classes("text-gray-500 italic")
            
            # Notes section
            chart_id = f"{score_system}_{var_name}"
            notes_textarea = ui.textarea(
                label="Notes",
                placeholder="Add your analysis and observations here...",
                value=load_notes(score_system, chart_id)
            ).classes("w-full mb-2")
            
            def save_notes_callback(sys=score_system, cid=chart_id, textarea=notes_textarea):
                save_note(sys, cid, textarea.value)
                ui.notify("Notes saved!", color='green')
            
            ui.button("Save Notes", on_click=save_notes_callback).classes("bg-blue-500 text-white")
    
    # Correlation charts section
    ui.separator().classes("my-6")
    ui.label("Weight Calibration").classes("text-2xl font-semibold mb-4")
    ui.label("Explore how different weights affect the correlation between variables and total score.").classes("text-gray-600 mb-4")
    
    # Weight controls
    weight_inputs = {}
    with ui.card().classes("p-4 mb-4"):
        ui.label("Adjust Weights").classes("text-lg font-semibold mb-2")
        for component in system['components']:
            comp_name = component if isinstance(component, str) else component['name']
            default_weight = system.get('weights', {}).get(comp_name, 1.0)
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.label(f"{comp_name}:").classes("w-48")
                weight_inputs[comp_name] = ui.number(
                    label="Weight",
                    value=default_weight,
                    min=0.0,
                    max=10.0,
                    step=0.1
                ).classes("flex-1")
    
    # Generate correlation chart
    def update_correlation_chart():
        comp_names = [comp if isinstance(comp, str) else comp['name'] for comp in system['components']]
        weights = {comp: weight_inputs[comp].value for comp in comp_names}
        
        correlation_area.clear()
        with correlation_area:
            charts = generate_correlation_charts_for_system(score_system, weights)
            for fig in charts:
                ui.plotly(fig).classes("w-full mb-4")
    
    correlation_area = ui.column().classes("w-full")
    ui.button("Generate Correlation Charts", on_click=update_correlation_chart).classes("bg-green-500 text-white mb-4")
    
    # Initial generation
    update_correlation_chart()


def build_formula_baseline_landing():
    """Build the landing page for formula baseline charts."""
    ui.label("Formula Baseline Charts").classes("text-3xl font-bold mb-4")
    ui.label(
        "Theoretical charts for refining formulas. Each score system has 6 charts per variable "
        "plus correlation charts for weight calibration. Add notes to track your analysis."
    ).classes("text-gray-600 mb-6")
    
    # Score systems grid
    with ui.grid(columns=3).classes("gap-4 w-full"):
        for system_id, system in SCORE_SYSTEMS.items():
            with ui.card().classes("p-4 cursor-pointer hover:bg-gray-50").on(
                'click', lambda sid=system_id: ui.navigate.to(f'/experimental/formula-baseline-charts/{sid}')
            ):
                ui.label(system['title']).classes("text-lg font-semibold mb-2")
                ui.label(system['description']).classes("text-sm text-gray-600 mb-2")
                ui.label(f"Range: {system['range']}").classes("text-xs text-gray-500 mb-2")
                ui.label(f"Components: {len(system['components'])}").classes("text-xs text-gray-500")
                if system.get('has_points'):
                    ui.badge("Has Points").classes("bg-green-500 text-white text-xs mt-2")
                else:
                    ui.badge("Needs Points").classes("bg-yellow-500 text-white text-xs mt-2")
                
                ui.button(
                    "View Charts",
                    on_click=lambda sid=system_id: ui.navigate.to(f'/experimental/formula-baseline-charts/{sid}')
                ).classes("bg-blue-500 text-white mt-2 w-full")


def register_formula_baseline_charts():
    """Register all formula baseline chart pages."""
    @ui.page('/experimental/formula-baseline-charts')
    def formula_baseline_landing():
        build_formula_baseline_landing()
    
    # Register individual pages for each score system
    for system_id in SCORE_SYSTEMS.keys():
        # Create closure-safe function
        def make_page_handler(sid: str):
            @ui.page(f'/experimental/formula-baseline-charts/{sid}')
            def formula_baseline_page():
                build_formula_baseline_page(sid)
            return formula_baseline_page
        make_page_handler(system_id)
