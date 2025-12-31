# ui/productivity_settings_page.py
from nicegui import ui
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
from backend.user_state import UserStateManager
from backend.task_manager import TaskManager
from backend.analytics import Analytics

user_state = UserStateManager()
task_manager = TaskManager()
analytics = Analytics()
DEFAULT_USER_ID = "default_user"

# Productivity score components that can be weighted
PRODUCTIVITY_COMPONENTS = {
    'base_completion': 'Base Completion Percentage',
    'work_multiplier': 'Work Task Multiplier',
    'efficiency_bonus': 'Efficiency Bonus',
    'weekly_bonus': 'Weekly Bonus',
    'burnout_penalty': 'Burnout Penalty',
    'primary_task_bonus': 'Primary Task Bonus',
}

# Curve weight options
CURVE_WEIGHTS = {
    'weekly_curve_strength': 'Weekly Curve Strength',
    'efficiency_curve_strength': 'Efficiency Curve Strength',
    'burnout_curve_strength': 'Burnout Curve Strength',
}


@ui.page("/settings/productivity-settings")
def productivity_settings_page():
    """Productivity score settings page with basic and advanced configuration options."""
    
    ui.label("Productivity Score Settings").classes("text-2xl font-bold mb-2")
    ui.label("Configure how productivity scores are calculated and displayed.").classes(
        "text-gray-500 mb-4"
    )
    
    # Load existing settings
    existing_settings = user_state.get_productivity_settings(DEFAULT_USER_ID) or {}
    
    # Basic Settings Section
    with ui.card().classes("w-full max-w-4xl p-6 mb-4"):
        ui.label("Basic Settings").classes("text-xl font-semibold mb-4")
        
        # Weekly curve setting
        weekly_curve = existing_settings.get("weekly_curve", "flattened_square")
        weekly_curve_select = ui.select(
            {
                "linear": "Linear (legacy)",
                "flattened_square": "Softened square (default)",
            },
            value=weekly_curve,
            label="Weekly bonus/penalty curve",
        ).props("dense outlined").classes("w-full max-w-md mb-4")
        
        # Target productivity hours
        with ui.row().classes("gap-4 w-full mb-4"):
            target_mode = existing_settings.get("target_mode", "weekly")
            target_mode_select = ui.select(
                {"daily": "Daily", "weekly": "Weekly"},
                value=target_mode,
                label="Target mode",
            ).props("dense outlined").classes("w-full max-w-xs")
            
            target_hours = float(existing_settings.get("target_hours", 40.0) or 40.0)
            target_hours_input = ui.number(
                label="Target productivity hours",
                value=target_hours,
                min=1.0,
                max=168.0,
                step=0.5,
            ).props("dense outlined").classes("w-full max-w-xs")
        
        # Burnout thresholds
        ui.label("Burnout Thresholds").classes("text-lg font-semibold mt-4 mb-2")
        
        with ui.row().classes("gap-4 w-full mb-4"):
            weekly_burnout_threshold_hours = float(existing_settings.get("weekly_burnout_threshold_hours", 42.0) or 42.0)
            burnout_weekly_input = ui.number(
                label="Weekly burnout threshold (hours/week)",
                value=weekly_burnout_threshold_hours,
                min=10,
                max=100,
                step=1,
            ).props("dense outlined").classes("w-full max-w-xs")
            
            daily_burnout_threshold_hours = float(existing_settings.get("daily_burnout_threshold_hours", 8.0) or 8.0)
            burnout_daily_input = ui.number(
                label="Daily burnout threshold (hours/day)",
                value=daily_burnout_threshold_hours,
                min=2,
                max=16,
                step=0.5,
            ).props("dense outlined").classes("w-full max-w-xs")
        
        daily_burnout_cap_multiplier = float(existing_settings.get("daily_burnout_cap_multiplier", 2.0) or 2.0)
        burnout_daily_cap_input = ui.number(
            label="Daily burnout cap (x daily average)",
            value=daily_burnout_cap_multiplier,
            min=1.0,
            max=4.0,
            step=0.1,
        ).props("dense outlined").classes("w-full max-w-md mb-4")
        
        # Primary productivity task
        ui.label("Primary Productivity Task").classes("text-lg font-semibold mt-4 mb-2")
        ui.label("Select a task that gives bonus productivity points when completed.").classes(
            "text-sm text-gray-600 mb-2"
        )
        
        # Get all tasks for selection
        all_tasks_df = task_manager.get_all()
        task_options = {}
        if not all_tasks_df.empty:
            for _, task in all_tasks_df.iterrows():
                task_id = task.get('task_id', '')
                task_name = task.get('name', 'Unknown')
                if task_id:
                    task_options[task_id] = task_name
        task_options[''] = 'None (no bonus)'
        
        primary_task_id = existing_settings.get("primary_productivity_task_id", "")
        primary_task_select = ui.select(
            task_options,
            value=primary_task_id if primary_task_id in task_options else '',
            label="Primary productivity task",
        ).props("dense outlined").classes("w-full max-w-md mb-2")
        
        primary_task_bonus_multiplier = float(existing_settings.get("primary_task_bonus_multiplier", 1.2) or 1.2)
        primary_task_bonus_input = ui.number(
            label="Primary task bonus multiplier",
            value=primary_task_bonus_multiplier,
            min=1.0,
            max=3.0,
            step=0.1,
        ).props("dense outlined").classes("w-full max-w-md mb-4")
        ui.label("Multiplier applied to productivity score when primary task is completed.").classes(
            "text-xs text-gray-500 mb-4"
        )
        
        # Note about future settings
        with ui.card().classes("p-3 bg-blue-50 border border-blue-200 mb-4"):
            ui.label("Note").classes("text-sm font-semibold text-blue-700 mb-1")
            ui.label(
                "More productivity settings may be introduced in the future. "
                "This page will be updated as new features are added."
            ).classes("text-sm text-blue-600")
        
        def save_basic_settings():
            settings = {
                "weekly_curve": weekly_curve_select.value or "flattened_square",
                "target_mode": target_mode_select.value or "weekly",
                "target_hours": float(target_hours_input.value or 40.0),
                "weekly_burnout_threshold_hours": float(burnout_weekly_input.value or 42.0),
                "daily_burnout_threshold_hours": float(burnout_daily_input.value or 8.0),
                "daily_burnout_cap_multiplier": float(burnout_daily_cap_input.value or 2.0),
                "primary_productivity_task_id": primary_task_select.value or "",
                "primary_task_bonus_multiplier": float(primary_task_bonus_input.value or 1.2),
            }
            # Merge with existing settings to preserve advanced settings
            current_settings = user_state.get_productivity_settings(DEFAULT_USER_ID) or {}
            current_settings.update(settings)
            user_state.set_productivity_settings(DEFAULT_USER_ID, current_settings)
            ui.notify("Productivity settings saved. Refresh analytics to apply.", color="positive")
        
        ui.button("Save Basic Settings", on_click=save_basic_settings).classes("bg-blue-500 text-white mt-2")
    
    # Advanced Settings Section (Toggleable)
    with ui.expansion("Advanced Settings", icon="tune", value=False).classes("w-full max-w-4xl mb-4"):
        with ui.card().classes("w-full p-6"):
            ui.label("Advanced Configuration").classes("text-xl font-semibold mb-4")
            ui.label(
                "Configure component weights and curve strengths. "
                "You can save multiple weight configurations and compare them to optimize the formula."
            ).classes("text-sm text-gray-600 mb-4")
            
            # Load weight configurations
            weight_configs = load_weight_configurations()
            config_names = list(weight_configs.keys())
            
            # Configuration selector
            with ui.row().classes("gap-4 w-full mb-4"):
                config_select = ui.select(
                    {name: name for name in config_names},
                    value=config_names[0] if config_names else None,
                    label="Weight Configuration",
                ).props("dense outlined").classes("w-full max-w-md")
                
                new_config_name_input = ui.input(
                    label="New configuration name",
                    placeholder="Enter name...",
                ).props("dense outlined").classes("w-full max-w-md")
            
            # Component weights
            ui.label("Component Weights").classes("text-lg font-semibold mt-4 mb-2")
            component_weight_inputs = {}
            
            current_config = weight_configs.get(config_select.value, {}) if config_select.value else {}
            component_weights = current_config.get('component_weights', {})
            curve_weights_config = current_config.get('curve_weights', {})
            
            with ui.grid(columns=2).classes("gap-4 w-full mb-4"):
                for component_key, component_label in PRODUCTIVITY_COMPONENTS.items():
                    default_weight = component_weights.get(component_key, 1.0)
                    component_weight_inputs[component_key] = ui.number(
                        label=component_label,
                        value=default_weight,
                        min=0.0,
                        max=10.0,
                        step=0.1,
                    ).props("dense outlined")
            
            # Curve weights
            ui.label("Curve Weights").classes("text-lg font-semibold mt-4 mb-2")
            curve_weight_inputs = {}
            
            with ui.grid(columns=2).classes("gap-4 w-full mb-4"):
                for curve_key, curve_label in CURVE_WEIGHTS.items():
                    default_weight = curve_weights_config.get(curve_key, 1.0)
                    curve_weight_inputs[curve_key] = ui.number(
                        label=curve_label,
                        value=default_weight,
                        min=0.0,
                        max=10.0,
                        step=0.1,
                    ).props("dense outlined")
            
            # Save/Load configuration buttons
            with ui.row().classes("gap-2 mb-4"):
                def save_weight_config():
                    config_name = config_select.value
                    if not config_name:
                        ui.notify("Please select or create a configuration", color="warning")
                        return
                    
                    component_weights = {key: float(input.value or 1.0) for key, input in component_weight_inputs.items()}
                    curve_weights = {key: float(input.value or 1.0) for key, input in curve_weight_inputs.items()}
                    
                    config = {
                        'component_weights': component_weights,
                        'curve_weights': curve_weights,
                        'updated_at': datetime.now().isoformat(),
                    }
                    
                    save_weight_configuration(config_name, config)
                    ui.notify(f"Configuration '{config_name}' saved", color="positive")
                
                def create_new_config():
                    new_name = new_config_name_input.value.strip()
                    if not new_name:
                        ui.notify("Please enter a configuration name", color="warning")
                        return
                    
                    if new_name in weight_configs:
                        ui.notify("Configuration name already exists", color="warning")
                        return
                    
                    # Create new config with default weights
                    new_config = {
                        'component_weights': {key: 1.0 for key in PRODUCTIVITY_COMPONENTS.keys()},
                        'curve_weights': {key: 1.0 for key in CURVE_WEIGHTS.keys()},
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat(),
                    }
                    
                    save_weight_configuration(new_name, new_config)
                    ui.notify(f"Configuration '{new_name}' created", color="positive")
                    ui.navigate.reload()
                
                def load_config():
                    config_name = config_select.value
                    if not config_name or config_name not in weight_configs:
                        return
                    
                    config = weight_configs[config_name]
                    component_weights = config.get('component_weights', {})
                    curve_weights = config.get('curve_weights', {})
                    
                    # Update inputs
                    for key, input_widget in component_weight_inputs.items():
                        input_widget.value = component_weights.get(key, 1.0)
                    
                    for key, input_widget in curve_weight_inputs.items():
                        input_widget.value = curve_weights.get(key, 1.0)
                    
                    ui.notify(f"Configuration '{config_name}' loaded", color="positive")
                
                ui.button("Save Configuration", on_click=save_weight_config).classes("bg-green-500 text-white")
                ui.button("Create New", on_click=create_new_config).classes("bg-blue-500 text-white")
                ui.button("Load Selected", on_click=load_config).classes("bg-gray-500 text-white")
            
            # Productivity Score Over Time Chart
            ui.label("Productivity Score Over Time").classes("text-lg font-semibold mt-4 mb-2")
            chart_container = ui.column().classes("w-full")
            
            def update_chart():
                chart_container.clear()
                
                # Get productivity scores over time
                try:
                    df = analytics._load_instances(completed_only=True)
                    if df.empty:
                        with chart_container:
                            ui.label("No completed tasks yet. Complete some tasks to see productivity trends.").classes(
                                "text-sm text-gray-500"
                            )
                        return
                    
                    # Filter to completed tasks with productivity scores
                    completed = df[df['completed_at'].astype(str).str.len() > 0].copy()
                    if completed.empty:
                        with chart_container:
                            ui.label("No completed tasks found.").classes("text-sm text-gray-500")
                        return
                    
                    # Calculate productivity scores (simplified - using work tasks only)
                    completed['completed_at'] = pd.to_datetime(completed['completed_at'], errors='coerce')
                    completed = completed.dropna(subset=['completed_at'])
                    completed = completed[completed['task_type'].str.lower() == 'work']
                    
                    if completed.empty:
                        with chart_container:
                            ui.label("No work tasks completed yet.").classes("text-sm text-gray-500")
                        return
                    
                    # Group by date and calculate average productivity
                    completed['date'] = completed['completed_at'].dt.date
                    daily_scores = completed.groupby('date').size().reset_index(name='task_count')
                    daily_scores['date'] = pd.to_datetime(daily_scores['date'])
                    daily_scores = daily_scores.sort_values('date')
                    
                    # Create line chart
                    fig = px.line(
                        daily_scores,
                        x='date',
                        y='task_count',
                        title="Daily Work Task Completion Count",
                        labels={'task_count': 'Tasks Completed', 'date': 'Date'},
                    )
                    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
                    
                    with chart_container:
                        ui.plotly(fig)
                        ui.label(
                            "Note: This shows work task completion count. "
                            "Full productivity score calculation requires all components."
                        ).classes("text-xs text-gray-500 mt-2")
                        
                except Exception as e:
                    with chart_container:
                        ui.label(f"Error loading chart: {str(e)}").classes("text-sm text-red-500")
            
            # Load chart when expansion opens
            config_select.on('update:model-value', lambda e: update_chart())
            update_chart()
    
    # Link to Productivity Module
    ui.separator().classes("my-4")
    with ui.card().classes("w-full max-w-4xl p-4 bg-gray-50 border border-gray-200"):
        ui.label("Related Resources").classes("text-lg font-semibold mb-2")
        ui.button(
            "📚 Productivity Module",
            on_click=lambda: ui.navigate.to("/productivity-module"),
            icon="science"
        ).classes("bg-purple-500 text-white")
        ui.label(
            "Explore the interactive productivity module to understand how productivity scores are calculated "
            "and experiment with different parameter values."
        ).classes("text-sm text-gray-600 mt-2")


def load_weight_configurations() -> dict:
    """Load weight configurations from CSV file."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    config_file = os.path.join(data_dir, 'productivity_weight_configs.csv')
    
    if not os.path.exists(config_file):
        # Create default configuration
        default_config = {
            'default': {
                'component_weights': {key: 1.0 for key in PRODUCTIVITY_COMPONENTS.keys()},
                'curve_weights': {key: 1.0 for key in CURVE_WEIGHTS.keys()},
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
            }
        }
        save_weight_configurations(default_config)
        return default_config
    
    try:
        df = pd.read_csv(config_file)
        configs = {}
        for _, row in df.iterrows():
            config_name = row['config_name']
            try:
                component_weights = json.loads(row.get('component_weights', '{}'))
                curve_weights = json.loads(row.get('curve_weights', '{}'))
                configs[config_name] = {
                    'component_weights': component_weights,
                    'curve_weights': curve_weights,
                    'created_at': row.get('created_at', ''),
                    'updated_at': row.get('updated_at', ''),
                }
            except (json.JSONDecodeError, KeyError):
                continue
        return configs if configs else {'default': {
            'component_weights': {key: 1.0 for key in PRODUCTIVITY_COMPONENTS.keys()},
            'curve_weights': {key: 1.0 for key in CURVE_WEIGHTS.keys()},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }}
    except Exception as e:
        print(f"[ProductivitySettings] Error loading configs: {e}")
        return {'default': {
            'component_weights': {key: 1.0 for key in PRODUCTIVITY_COMPONENTS.keys()},
            'curve_weights': {key: 1.0 for key in CURVE_WEIGHTS.keys()},
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }}


def save_weight_configuration(config_name: str, config: dict):
    """Save a single weight configuration to CSV."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    config_file = os.path.join(data_dir, 'productivity_weight_configs.csv')
    
    # Load existing configs
    all_configs = load_weight_configurations()
    all_configs[config_name] = config
    
    # Save to CSV
    rows = []
    for name, cfg in all_configs.items():
        rows.append({
            'config_name': name,
            'component_weights': json.dumps(cfg.get('component_weights', {})),
            'curve_weights': json.dumps(cfg.get('curve_weights', {})),
            'created_at': cfg.get('created_at', ''),
            'updated_at': cfg.get('updated_at', ''),
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(config_file, index=False)


def save_weight_configurations(configs: dict):
    """Save all weight configurations to CSV."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    config_file = os.path.join(data_dir, 'productivity_weight_configs.csv')
    
    rows = []
    for name, config in configs.items():
        rows.append({
            'config_name': name,
            'component_weights': json.dumps(config.get('component_weights', {})),
            'curve_weights': json.dumps(config.get('curve_weights', {})),
            'created_at': config.get('created_at', ''),
            'updated_at': config.get('updated_at', ''),
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(config_file, index=False)
