"""Productivity Module - Interactive parameter control and formula explanation.

Allows manual parameter selection with tooltips explaining each parameter's effect.
Prioritizes baseline formula with optional enhancements.

⚠️ FLAGGED FOR REMOVAL AFTER REVIEW ⚠️
This page appears to be redundant/useless. Review and remove if confirmed.
"""
from nicegui import ui
from backend.productivity_tracker import ProductivityTracker
from backend.analytics import Analytics
from backend.user_state import UserStateManager
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from datetime import date, timedelta
import pandas as pd
import json

DEFAULT_USER_ID = "default_user"
tracker = ProductivityTracker()
analytics = Analytics()
user_state = UserStateManager()
task_manager = TaskManager()
instance_manager = InstanceManager()


# Formula parameter explanations
PARAMETER_EXPLANATIONS = {
    'baseline_formula': {
        'title': 'Baseline Productivity Formula',
        'description': 'The core productivity score calculation without optional adjustments.',
        'formula': 'score = completion_pct × task_type_multiplier',
        'components': {
            'completion_pct': {
                'name': 'Completion Percentage',
                'description': 'Percentage of task completed (0-100). Base score multiplier.',
                'range': '0-100',
                'default': 100,
                'effect': 'Directly multiplies the final score. 100% = full credit, 50% = half credit.'
            },
            'task_type_multiplier': {
                'name': 'Task Type Multiplier',
                'description': 'Multiplier based on task type (Work, Self Care, Play).',
                'work': {
                    'value': '3.0-5.0x',
                    'description': 'Work tasks: 3.0x base (efficient) to 5.0x (very efficient). Scales with completion/time ratio.',
                    'formula': 'If ratio ≤ 1.0: 3.0x | If ratio ≥ 1.5: 5.0x | Else: smooth transition 3.0-5.0x'
                },
                'self_care': {
                    'value': 'count_per_day',
                    'description': 'Self Care tasks: multiplier = number of self care tasks completed that day.',
                    'formula': 'multiplier = self_care_tasks_completed_today'
                },
                'play': {
                    'value': 'neutral or penalty',
                    'description': 'Play tasks: neutral (completion_pct) if play/work ratio ≤ 2.0, else penalty.',
                    'formula': 'If play_time/work_time > 2.0: score = completion_pct × (-0.003 × time_percentage)'
                }
            }
        }
    },
    'optional_enhancements': {
        'title': 'Optional Enhancements',
        'description': 'Additional adjustments that can be applied to the baseline formula.',
        'enhancements': {
            'weekly_avg_bonus': {
                'name': 'Weekly Average Bonus/Penalty',
                'description': 'Adjusts score based on how task time compares to weekly average.',
                'enabled': False,
                'parameters': {
                    'weekly_avg_time': {
                        'name': 'Weekly Average Time (minutes)',
                        'description': 'Average productive time per task this week. Used to calculate deviation.',
                        'default': 0,
                        'effect': 'Tasks faster than average get bonus, slower get penalty.'
                    },
                    'weekly_curve': {
                        'name': 'Weekly Curve Type',
                        'description': 'Response curve type: linear or flattened_square.',
                        'options': ['linear', 'flattened_square'],
                        'default': 'flattened_square',
                        'effect': 'Linear: proportional adjustment. Flattened square: larger deviations grow faster but scaled down.'
                    },
                    'weekly_curve_strength': {
                        'name': 'Weekly Curve Strength',
                        'description': 'Strength of weekly adjustment (0.0-2.0).',
                        'range': '0.0-2.0',
                        'default': 1.0,
                        'effect': 'Higher values = stronger bonus/penalty for deviations from average.'
                    }
                },
                'formula': 'multiplier = 1.0 - (0.01 × strength × effect) where effect depends on curve type'
            },
            'goal_adjustment': {
                'name': 'Goal-Based Adjustment',
                'description': 'Adjusts score based on weekly goal achievement.',
                'enabled': False,
                'parameters': {
                    'goal_hours_per_week': {
                        'name': 'Goal Hours Per Week',
                        'description': 'Target productive hours per week.',
                        'default': 40.0,
                        'effect': 'Used to calculate goal achievement ratio.'
                    },
                    'weekly_productive_hours': {
                        'name': 'Weekly Productive Hours',
                        'description': 'Actual productive hours completed this week.',
                        'default': 0.0,
                        'effect': 'Compared to goal to determine achievement ratio.'
                    }
                },
                'formula': 'multiplier = 0.8-1.2 based on goal achievement ratio (80% goal = 0.9x, 100% = 1.0x, 120%+ = 1.2x)'
            },
            'burnout_penalty': {
                'name': 'Burnout Penalty',
                'description': 'Penalty for excessive work hours (weekly + daily cap).',
                'enabled': False,
                'parameters': {
                    'weekly_burnout_threshold_hours': {
                        'name': 'Weekly Burnout Threshold (hours)',
                        'description': 'Weekly work hours threshold before burnout penalty applies.',
                        'default': 42.0,
                        'effect': 'Only applies when weekly total exceeds this AND daily work exceeds daily cap.'
                    },
                    'daily_burnout_cap_multiplier': {
                        'name': 'Daily Cap Multiplier',
                        'description': 'Daily work cap = (weekly_total / days) × this multiplier.',
                        'default': 2.0,
                        'effect': 'Daily work must exceed this cap for penalty to apply.'
                    }
                },
                'formula': 'penalty_factor = 1.0 - exp(-excess_week / 300.0), capped at 50% reduction'
            }
        }
    }
}


def create_tooltip_button(text: str, tooltip_content: str, icon: str = "ℹ️"):
    """Create a button with tooltip that shows on hover."""
    with ui.button(icon=icon).props("flat dense round").classes("text-gray-400 hover:text-blue-600"):
        ui.tooltip(tooltip_content).style("max-width: 400px; white-space: normal;")


def create_parameter_control(param_name: str, param_info: dict, value_callback=None):
    """Create a UI control for a parameter with explanation."""
    with ui.card().classes("p-3 mb-2 border border-gray-200"):
        with ui.row().classes("items-center gap-2 w-full"):
            ui.label(param_info['name']).classes("font-semibold flex-1")
            if 'description' in param_info:
                create_tooltip_button("", param_info['description'])
        
        # Show description
        if 'description' in param_info:
            ui.label(param_info['description']).classes("text-sm text-gray-600 mb-2")
        
        # Create appropriate input control
        if 'options' in param_info:
            # Select dropdown
            control = ui.select(
                options={opt: opt for opt in param_info['options']},
                value=param_info.get('default', param_info['options'][0]),
                label=param_info['name']
            ).props("dense outlined").classes("w-full")
        elif 'range' in param_info:
            # Number input with range
            min_val, max_val = map(float, param_info['range'].split('-'))
            control = ui.number(
                label=param_info['name'],
                value=float(param_info.get('default', 0)),
                min=min_val,
                max=max_val,
                step=0.1 if max_val <= 10 else 1.0,
                format="%.2f" if max_val <= 10 else "%.1f"
            ).props("dense outlined").classes("w-full")
        else:
            # Regular number input
            control = ui.number(
                label=param_info['name'],
                value=float(param_info.get('default', 0)),
                min=0,
                step=0.1,
                format="%.2f"
            ).props("dense outlined").classes("w-full")
        
        # Show effect explanation
        if 'effect' in param_info:
            with ui.row().classes("mt-2 text-xs text-gray-500"):
                ui.icon("info", size="xs")
                ui.label(param_info['effect']).classes("ml-1")
        
        # Show formula if available
        if 'formula' in param_info:
            with ui.card().classes("mt-2 p-2 bg-gray-50 border border-gray-300"):
                ui.label("Formula:").classes("text-xs font-semibold text-gray-700")
                ui.label(param_info['formula']).classes("text-xs font-mono text-gray-600")
        
        if value_callback:
            control.on('update:model-value', lambda e, name=param_name: value_callback(name, e.args if hasattr(e, 'args') else e))
        
        return control


@ui.page("/productivity-module")
def productivity_module_page():
    """Interactive productivity module with parameter controls.
    
    ⚠️ FLAGGED FOR REMOVAL AFTER REVIEW ⚠️
    This page appears to be redundant/useless. Review and remove if confirmed.
    """
    
    ui.add_head_html("""
    <style>
        .formula-display {
            font-family: 'Courier New', monospace;
            background: #f5f5f5;
            padding: 12px;
            border-radius: 6px;
            border: 1px solid #ddd;
            margin: 8px 0;
        }
        .parameter-section {
            border-left: 3px solid #3b82f6;
            padding-left: 12px;
            margin: 16px 0;
        }
        .enhancement-toggle {
            cursor: pointer;
            user-select: none;
        }
    </style>
    """)
    
    ui.label("Productivity Module - Interactive Formula Control").classes("text-3xl font-bold mb-4")
    ui.label("Adjust parameters and see how they affect the productivity score calculation.").classes("text-gray-600 mb-6")
    
    # State for current parameters
    current_params = {
        'baseline': {
            'completion_pct': 100.0,
            'task_type': 'work',
            'time_actual': 60.0,
            'time_estimate': 60.0,
        },
        'enhancements': {
            'weekly_avg_bonus': {'enabled': False, 'weekly_avg_time': 0.0, 'weekly_curve': 'flattened_square', 'weekly_curve_strength': 1.0},
            'goal_adjustment': {'enabled': False, 'goal_hours_per_week': 40.0, 'weekly_productive_hours': 0.0},
            'burnout_penalty': {'enabled': False, 'weekly_burnout_threshold_hours': 42.0, 'daily_burnout_cap_multiplier': 2.0}
        }
    }
    
    # Result display area
    result_card = ui.card().classes("w-full p-4 mb-4 bg-blue-50 border-2 border-blue-200")
    result_display = ui.column().classes("w-full")
    
    # Store input references for later use
    input_refs = {}
    
    def calculate_and_display():
        """Calculate productivity score with current parameters and display result."""
        result_display.clear()
        
        with result_display:
            # Get baseline parameters
            completion_pct = current_params['baseline']['completion_pct']
            task_type = current_params['baseline']['task_type']
            time_actual = current_params['baseline']['time_actual']
            time_estimate = current_params['baseline']['time_estimate']
            
            # Calculate baseline score using backend method
            baseline_result = tracker.calculate_baseline_productivity_score(
                completion_pct=completion_pct,
                task_type=task_type,
                time_actual_minutes=time_actual,
                time_estimate_minutes=time_estimate,
                self_care_tasks_today=1  # Default for demo
            )
            
            baseline_score = baseline_result['baseline_score']
            multiplier = baseline_result['multiplier']
            
            # Apply enhancements using backend method
            enhancement_params = {}
            if current_params['enhancements']['weekly_avg_bonus']['enabled']:
                enhancement_params['weekly_avg_time_minutes'] = current_params['enhancements']['weekly_avg_bonus']['weekly_avg_time']
                enhancement_params['time_actual_minutes'] = time_actual
                enhancement_params['weekly_curve'] = current_params['enhancements']['weekly_avg_bonus']['weekly_curve']
                enhancement_params['weekly_curve_strength'] = current_params['enhancements']['weekly_avg_bonus']['weekly_curve_strength']
            
            if current_params['enhancements']['goal_adjustment']['enabled']:
                enhancement_params['goal_hours_per_week'] = current_params['enhancements']['goal_adjustment']['goal_hours_per_week']
                enhancement_params['weekly_productive_hours'] = current_params['enhancements']['goal_adjustment']['weekly_productive_hours']
            
            if enhancement_params:
                enhancement_result = tracker.calculate_productivity_score_with_enhancements(
                    baseline_score=baseline_score,
                    **enhancement_params
                )
                final_score = enhancement_result['final_score']
                enhancement_details = list(enhancement_result['enhancement_details'].values())
            else:
                final_score = baseline_score
                enhancement_details = []
            
            # Display results
            ui.label("Calculation Result").classes("text-xl font-bold mb-3")
            
            with ui.row().classes("w-full gap-4 mb-3"):
                with ui.column().classes("flex-1"):
                    ui.label("Baseline Score").classes("text-sm text-gray-600")
                    ui.label(f"{baseline_score:.2f}").classes("text-2xl font-bold text-blue-600")
                    ui.label(f"({completion_pct:.0f}% × {multiplier:.2f}x)").classes("text-xs text-gray-500")
                
                with ui.column().classes("flex-1"):
                    ui.label("Final Score").classes("text-sm text-gray-600")
                    ui.label(f"{final_score:.2f}").classes("text-3xl font-bold text-green-600")
            
            if enhancement_details:
                ui.separator().classes("my-3")
                ui.label("Applied Enhancements:").classes("text-sm font-semibold mb-2")
                for detail in enhancement_details:
                    ui.label(f"• {detail.get('description', str(detail))}").classes("text-xs text-gray-600")
            
            # Show formula breakdown
            ui.separator().classes("my-3")
            ui.label("Formula Breakdown:").classes("text-sm font-semibold mb-2")
            ui.label(baseline_result['formula_breakdown']).classes("text-xs font-mono bg-gray-100 p-2 rounded mb-2")
            if enhancement_details:
                formula_text = f"Baseline: {baseline_score:.2f}"
                for detail in enhancement_details:
                    mult = detail.get('multiplier', 1.0)
                    formula_text += f" × {mult:.3f}"
                formula_text += f" = {final_score:.2f}"
                ui.label(formula_text).classes("text-xs font-mono bg-gray-100 p-2 rounded")
    
    # Baseline Formula Section
    with ui.card().classes("w-full p-4 mb-4"):
        ui.label("Baseline Formula Parameters").classes("text-xl font-semibold mb-4")
        ui.label(PARAMETER_EXPLANATIONS['baseline_formula']['description']).classes("text-sm text-gray-600 mb-4")
        
        with ui.row().classes("w-full gap-4 mb-4"):
            # Completion percentage
            completion_input = ui.number(
                label="Completion Percentage",
                value=100.0,
                min=0,
                max=100,
                step=1,
                format="%.0f"
            ).props("dense outlined").classes("flex-1")
            completion_input.on('update:model-value', lambda e: current_params['baseline'].update({'completion_pct': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
            create_tooltip_button("", PARAMETER_EXPLANATIONS['baseline_formula']['components']['completion_pct']['description'])
            
            # Task type
            task_type_input = ui.select(
                options={'work': 'Work', 'self_care': 'Self Care', 'play': 'Play'},
                value='work',
                label="Task Type"
            ).props("dense outlined").classes("flex-1")
            task_type_input.on('update:model-value', lambda e: current_params['baseline'].update({'task_type': e.args if hasattr(e, 'args') else e}) or calculate_and_display())
            
            # Time actual
            time_actual_input = ui.number(
                label="Actual Time (minutes)",
                value=60.0,
                min=0,
                step=1,
                format="%.0f"
            ).props("dense outlined").classes("flex-1")
            time_actual_input.on('update:model-value', lambda e: current_params['baseline'].update({'time_actual': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
            
            # Time estimate
            time_estimate_input = ui.number(
                label="Estimated Time (minutes)",
                value=60.0,
                min=0,
                step=1,
                format="%.0f"
            ).props("dense outlined").classes("flex-1")
            time_estimate_input.on('update:model-value', lambda e: current_params['baseline'].update({'time_estimate': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
        
        # Show baseline formula
        with ui.card().classes("p-3 bg-gray-50 border border-gray-300"):
            ui.label("Baseline Formula:").classes("text-sm font-semibold mb-1")
            ui.label("score = completion_pct × task_type_multiplier").classes("text-sm font-mono")
            ui.label("Where task_type_multiplier depends on task type and completion/time ratio").classes("text-xs text-gray-600 mt-1")
    
    # Optional Enhancements Section
    with ui.card().classes("w-full p-4 mb-4"):
        ui.label("Optional Enhancements").classes("text-xl font-semibold mb-4")
        ui.label("Enable optional adjustments to see how they modify the baseline score.").classes("text-sm text-gray-600 mb-4")
        
        # Weekly Average Bonus
        with ui.card().classes("p-3 mb-3 border border-gray-200"):
            weekly_avg_enabled = ui.checkbox("Enable Weekly Average Bonus/Penalty").bind_value(current_params['enhancements']['weekly_avg_bonus'], 'enabled')
            weekly_avg_enabled.on('update:model-value', lambda: calculate_and_display())
            
            weekly_avg_container = ui.column().classes("ml-6 mt-2")
            with weekly_avg_container:
                input_refs['weekly_avg_time_input'] = ui.number(
                    label="Weekly Average Time (minutes)",
                    value=0.0,
                    min=0,
                    step=1,
                    format="%.0f"
                ).props("dense outlined").classes("w-full mb-2")
                input_refs['weekly_avg_time_input'].on('update:model-value', lambda e: current_params['enhancements']['weekly_avg_bonus'].update({'weekly_avg_time': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
                create_tooltip_button("", "Average productive time per task this week. Tasks faster than average get bonus, slower get penalty.")
                
                weekly_curve_input = ui.select(
                    options={'linear': 'Linear', 'flattened_square': 'Flattened Square'},
                    value='flattened_square',
                    label="Weekly Curve Type"
                ).props("dense outlined").classes("w-full mb-2")
                weekly_curve_input.on('update:model-value', lambda e: current_params['enhancements']['weekly_avg_bonus'].update({'weekly_curve': e.args if hasattr(e, 'args') else e}) or calculate_and_display())
                
                weekly_strength_input = ui.number(
                    label="Weekly Curve Strength",
                    value=1.0,
                    min=0,
                    max=2.0,
                    step=0.1,
                    format="%.1f"
                ).props("dense outlined").classes("w-full")
                weekly_strength_input.on('update:model-value', lambda e: current_params['enhancements']['weekly_avg_bonus'].update({'weekly_curve_strength': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
        
        # Goal Adjustment
        with ui.card().classes("p-3 mb-3 border border-gray-200"):
            goal_enabled = ui.checkbox("Enable Goal-Based Adjustment").bind_value(current_params['enhancements']['goal_adjustment'], 'enabled')
            goal_enabled.on('update:model-value', lambda: calculate_and_display())
            
            goal_inputs_container = ui.column().classes("ml-6 mt-2")
            with goal_inputs_container:
                input_refs['goal_hours_input'] = ui.number(
                    label="Goal Hours Per Week",
                    value=40.0,
                    min=0,
                    step=0.5,
                    format="%.1f"
                ).props("dense outlined").classes("w-full mb-2")
                input_refs['goal_hours_input'].on('update:model-value', lambda e: current_params['enhancements']['goal_adjustment'].update({'goal_hours_per_week': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
                
                input_refs['weekly_hours_input'] = ui.number(
                    label="Weekly Productive Hours",
                    value=0.0,
                    min=0,
                    step=0.5,
                    format="%.1f"
                ).props("dense outlined").classes("w-full")
                input_refs['weekly_hours_input'].on('update:model-value', lambda e: current_params['enhancements']['goal_adjustment'].update({'weekly_productive_hours': float(e.args) if hasattr(e, 'args') else float(e)}) or calculate_and_display())
    
    # Result display
    with result_card:
        calculate_and_display()
    
    # Manual Data Update Section
    with ui.card().classes("w-full p-4 mb-4"):
        ui.label("Manual Data Update").classes("text-xl font-semibold mb-4")
        ui.label("Update productivity tracking data manually or load from current week.").classes("text-sm text-gray-600 mb-4")
        
        # Current week data display
        data_display = ui.column().classes("w-full mb-4")
        
        def load_and_display_current_week():
            """Load and display current week's data."""
            data_display.clear()
            weekly_data = tracker.calculate_weekly_productivity_hours(DEFAULT_USER_ID)
            comparison = tracker.compare_to_goal(DEFAULT_USER_ID)
            
            with data_display:
                ui.label("Current Week Data").classes("text-lg font-semibold mb-2")
                with ui.row().classes("w-full gap-4 mb-2"):
                    with ui.column().classes("flex-1"):
                        ui.label("Total Hours").classes("text-sm text-gray-600")
                        ui.label(f"{weekly_data.get('total_hours', 0):.1f}").classes("text-xl font-bold")
                    with ui.column().classes("flex-1"):
                        ui.label("Goal Hours").classes("text-sm text-gray-600")
                        ui.label(f"{comparison.get('goal_hours', 0):.1f}").classes("text-xl font-bold")
                    with ui.column().classes("flex-1"):
                        ui.label("Percentage").classes("text-sm text-gray-600")
                        pct = comparison.get('percentage_of_goal', 0)
                        color = "text-green-600" if pct >= 100 else "text-yellow-600" if pct >= 85 else "text-red-600"
                        ui.label(f"{pct:.1f}%").classes(f"text-xl font-bold {color}")
                
                # Update enhancement parameters with loaded data
                if comparison.get('goal_hours', 0) > 0 and 'goal_hours_input' in input_refs:
                    input_refs['goal_hours_input'].set_value(comparison.get('goal_hours', 40.0))
                    current_params['enhancements']['goal_adjustment']['goal_hours_per_week'] = comparison.get('goal_hours', 40.0)
                
                if weekly_data.get('total_hours', 0) > 0 and 'weekly_hours_input' in input_refs:
                    input_refs['weekly_hours_input'].set_value(weekly_data.get('total_hours', 0.0))
                    current_params['enhancements']['goal_adjustment']['weekly_productive_hours'] = weekly_data.get('total_hours', 0.0)
                
                # Calculate weekly average if we have daily data
                if weekly_data.get('daily_averages') and 'weekly_avg_time_input' in input_refs:
                    total_minutes = sum(day['minutes'] for day in weekly_data['daily_averages'])
                    count = len(weekly_data['daily_averages'])
                    if count > 0:
                        avg_minutes = total_minutes / count
                        input_refs['weekly_avg_time_input'].set_value(avg_minutes)
                        current_params['enhancements']['weekly_avg_bonus']['weekly_avg_time'] = avg_minutes
                
                calculate_and_display()
                ui.notify("Current week data loaded!", color="positive")
        
        def record_snapshot_and_notify():
            """Record snapshot and notify."""
            result = tracker.record_weekly_snapshot(DEFAULT_USER_ID)
            ui.notify(
                f"Recorded: {result.get('actual_hours', 0):.1f}h, "
                f"{result.get('productivity_score', 0):.1f} points",
                color="positive"
            )
        
        with ui.row().classes("w-full gap-4 mb-4"):
            ui.button("Load Current Week Data", on_click=load_and_display_current_week).classes("bg-blue-500 text-white")
            ui.button("Record Weekly Snapshot", on_click=record_snapshot_and_notify).classes("bg-green-500 text-white")
            ui.button("Refresh Calculations", on_click=calculate_and_display).classes("bg-gray-500 text-white")
        
        with data_display:
            ui.label("Click 'Load Current Week Data' to load your actual productivity data.").classes("text-sm text-gray-500 italic")
    
    ui.separator().classes("my-4")
    with ui.card().classes("w-full p-4 bg-gray-50 border border-gray-200"):
        ui.label("Related Resources").classes("text-lg font-semibold mb-2")
        ui.button(
            "⚙️ Productivity Settings",
            on_click=lambda: ui.navigate.to("/settings/productivity-settings"),
            icon="settings"
        ).classes("bg-blue-500 text-white")
        ui.label(
            "Configure productivity scoring settings, target hours, burnout thresholds, and advanced weight configurations."
        ).classes("text-sm text-gray-600 mt-2")
    
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4")


def load_current_week_data():
    """Load current week's productivity data."""
    weekly_data = tracker.calculate_weekly_productivity_hours(DEFAULT_USER_ID)
    comparison = tracker.compare_to_goal(DEFAULT_USER_ID)
    
    ui.notify(f"Loaded: {weekly_data.get('total_hours', 0):.1f} hours, {comparison.get('percentage_of_goal', 0):.1f}% of goal", color="info")


def record_snapshot():
    """Record current week's snapshot."""
    result = tracker.record_weekly_snapshot(DEFAULT_USER_ID)
    ui.notify(f"Recorded snapshot: {result.get('actual_hours', 0):.1f} hours, {result.get('productivity_score', 0):.1f} points", color="positive")


def register_productivity_module():
    """Register the productivity module page."""
    pass  # Page is registered via decorator
