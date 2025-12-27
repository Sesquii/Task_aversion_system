# ui/analytics_glossary.py
from nicegui import ui
from typing import Dict, List, Optional
import os
from ui.plotly_data_charts import PLOTLY_DATA_CHARTS

# Module definitions for the analytics glossary
ANALYTICS_MODULES = {
    'execution_score': {
        'title': 'Execution Score',
        'version': '1.0',
        'description': 'Rewards efficient execution of difficult tasks by combining difficulty, speed, start speed, and completion quality.',
        'icon': 'rocket_launch',
        'color': 'blue',
        'components': [
            {
                'name': 'Difficulty Factor',
                'version': '1.0',
                'description': 'Measures how difficult the task was (high aversion + high cognitive load). Uses exponential scaling to reward completing challenging tasks.',
                'formula': 'difficulty_factor = calculate_difficulty_bonus(aversion, stress_level, mental_energy, task_difficulty)',
                'range': '0.0 - 1.0',
                'graphic_script': 'execution_score_difficulty_factor.py'
            },
            {
                'name': 'Speed Factor',
                'version': '1.0',
                'description': 'Measures execution efficiency relative to time estimate. Rewards fast completion (2x speed or faster gets max bonus), penalizes slow completion.',
                'formula': 'speed_factor = f(time_actual / time_estimate)',
                'range': '0.0 - 1.0',
                'graphic_script': 'execution_score_speed_factor.py'
            },
            {
                'name': 'Start Speed Factor',
                'version': '1.0',
                'description': 'Measures procrastination resistance - how quickly you started the task after initialization. Rewards fast starts (within 5 minutes = perfect).',
                'formula': 'start_speed_factor = f((started_at - initialized_at) / minutes)',
                'range': '0.0 - 1.0',
                'graphic_script': 'execution_score_start_speed_factor.py'
            },
            {
                'name': 'Completion Factor',
                'version': '1.0',
                'description': 'Measures quality of completion. Full completion (100%) gets max score, partial completion gets proportional penalty.',
                'formula': 'completion_factor = f(completion_percent)',
                'range': '0.0 - 1.0',
                'graphic_script': 'execution_score_completion_factor.py'
            }
        ],
        'formula': 'execution_score = 50 * (1.0 + difficulty_factor) * (0.5 + speed_factor * 0.5) * (0.5 + start_speed_factor * 0.5) * completion_factor',
        'range': '0 - 100',
        'use_cases': [
            'Rewards fast completion of difficult tasks',
            'Recognizes overcoming procrastination (fast starts)',
            'Complements productivity score (which ignores difficulty)',
            'Complements grit score (which rewards persistence, not speed)'
        ]
    },
    'grit_score': {
        'title': 'Grit Score',
        'description': 'Rewards persistence and taking on difficult tasks. Includes difficulty bonus and time bonus (for tasks taking longer than estimated).',
        'icon': 'fitness_center',
        'color': 'purple',
        'components': [],
        'formula': 'grit_score = difficulty_bonus * time_bonus',
        'range': '0 - 100+',
        'use_cases': [
            'Rewards completing difficult tasks',
            'Rewards persistence (taking longer than estimated)',
            'Opposite of execution score (which rewards speed)'
        ]
    },
    'difficulty_bonus': {
        'title': 'Difficulty Bonus',
        'description': 'Calculates bonus for completing difficult tasks based on aversion and cognitive load. Uses exponential scaling.',
        'icon': 'trending_up',
        'color': 'orange',
        'components': [],
        'formula': 'bonus = 1.0 * (1 - exp(-(0.7 * aversion + 0.3 * load) / 50))',
        'range': '0.0 - 1.0',
        'use_cases': [
            'Used as component in execution score and grit score',
            'Rewards high aversion + high cognitive load',
            'Exponential scaling for smooth curve'
        ]
    },
    'composite_score': {
        'title': 'Composite Score',
        'description': 'Combines multiple scores, bonuses, and penalties into a single normalized score (0-100) with customizable weights.',
        'icon': 'dashboard',
        'color': 'indigo',
        'components': [],
        'formula': 'composite_score = Σ(component_score * normalized_weight)',
        'range': '0 - 100',
        'use_cases': [
            'Holistic view of overall performance',
            'Customizable component weights',
            'Includes execution score, productivity, grit, and more'
        ]
    },
    'productivity_score': {
        'title': 'Productivity Score',
        'version': '1.0',
        'description': 'Measures productive output based on task completion and type. Prioritizes baseline formula with optional enhancements for weekly averages, goal achievement, and burnout prevention.',
        'icon': 'trending_up',
        'color': 'green',
        'components': [
            {
                'name': 'Baseline Formula',
                'version': '1.0',
                'description': 'Core productivity calculation: completion percentage multiplied by task type multiplier. This is the foundation that all enhancements build upon.',
                'formula': 'baseline_score = completion_pct × task_type_multiplier',
                'range': '0 - 500+ (depends on task type)',
                'graphic_script': 'productivity_score_baseline_completion.py',
                'details': {
                    'completion_pct': 'Percentage of task completed (0-100). Base score multiplier.',
                    'task_type_multiplier': {
                        'work': '3.0x-5.0x based on completion/time ratio (efficient = higher multiplier)',
                        'self_care': 'Multiplier = number of self care tasks completed that day',
                        'play': '1.0x (neutral) or penalty if play exceeds work by 2x threshold'
                    }
                }
            },
            {
                'name': 'Work Task Multiplier',
                'version': '1.0',
                'description': 'Work tasks use a multiplier that scales from 3.0x to 5.0x based on completion/time ratio. More efficient completion (higher ratio) = higher multiplier.',
                'formula': 'If ratio ≤ 1.0: 3.0x | If ratio ≥ 1.5: 5.0x | Else: smooth transition 3.0-5.0x',
                'range': '3.0x - 5.0x',
                'graphic_script': 'productivity_score_work_multiplier.py',
            },
            {
                'name': 'Efficiency Bonus/Penalty',
                'version': '1.0',
                'description': 'Adjusts score based on efficiency: compares actual time and completion percentage to task estimate. Accounts for both time and completion - if you take 2x longer but complete 200%, efficiency ratio = 1.0 (no penalty).',
                'formula': 'efficiency_ratio = (completion_pct × time_estimate) / (100 × time_actual); multiplier = 1.0 - (0.01 × strength × effect) where effect depends on curve type',
                'range': '0.5 - 1.5x (approximate, penalty capped at 50% reduction)',
                'graphic_script': 'productivity_score_weekly_avg_bonus.py',
                'parameters': {
                    'time_estimate': 'Estimated time for the task (minutes)',
                    'time_actual': 'Actual time taken (minutes)',
                    'completion_percentage': 'Percentage of task completed (%)',
                    'weekly_curve': 'Response curve type: linear or flattened_square',
                    'weekly_curve_strength': 'Strength of adjustment (0.0-2.0)'
                }
            },
            {
                'name': 'Goal-Based Adjustment',
                'version': '1.0',
                'description': 'Optional enhancement that adjusts score based on weekly goal achievement. Provides bonus for exceeding goals, penalty for falling short.',
                'formula': 'multiplier = 0.8-1.2 based on goal achievement ratio',
                'range': '0.8 - 1.2x',
                'graphic_script': 'productivity_score_goal_adjustment.py',
                'parameters': {
                    'goal_hours_per_week': 'Target productive hours per week',
                    'weekly_productive_hours': 'Actual productive hours completed this week'
                },
                'details': {
                    '100% goal': '1.0x (no change)',
                    '120%+ goal': '1.2x (20% bonus)',
                    '80-100% goal': '0.9-1.0x (linear interpolation)',
                    '<80% goal': '0.8-0.9x (penalty)'
                }
            },
            {
                'name': 'Burnout Penalty',
                'version': '1.0',
                'description': 'Optional enhancement that penalizes excessive work hours. Only applies when weekly total exceeds threshold AND daily work exceeds daily cap.',
                'formula': 'penalty_factor = 1.0 - exp(-excess_week / 300.0), capped at 50% reduction',
                'range': '0.5 - 1.0x (penalty reduces score)',
                'parameters': {
                    'weekly_burnout_threshold_hours': 'Weekly work hours threshold (default: 42)',
                    'daily_burnout_cap_multiplier': 'Daily cap = (weekly_total / days) × multiplier (default: 2.0)'
                }
            }
        ],
        'formula': 'Baseline: score = completion_pct × task_type_multiplier\nWith enhancements: score = baseline × weekly_multiplier × goal_multiplier × burnout_multiplier',
        'range': '0 - 500+ (can be negative for play penalty)',
        'use_cases': [
            'Measures productive output (Work and Self Care tasks)',
            'Rewards efficient completion (work tasks)',
            'Encourages self-care consistency (self care tasks)',
            'Penalizes excessive play time (play tasks)',
            'Optional enhancements provide context-aware adjustments'
        ],
        'interactive_module': '/productivity-module'
    }
}

# Get absolute path to scripts directory
_glossary_file_dir = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.normpath(os.path.join(_glossary_file_dir, '..', 'scripts', 'graphic_aids'))
# Images directory for generated graphics (web-accessible)
_images_dir = os.path.normpath(os.path.join(_glossary_file_dir, '..', 'assets', 'graphic_aids'))
# Ensure directories exist
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(_images_dir, exist_ok=True)


def register_analytics_glossary():
    """Register the analytics glossary page."""
    @ui.page('/analytics/glossary')
    def analytics_glossary_page():
        build_analytics_glossary()
    
    @ui.page('/analytics/glossary/{module_id}')
    def analytics_glossary_module_page(module_id: str):
        build_module_page(module_id)


def build_analytics_glossary():
    """Build the main analytics glossary page."""
    ui.label("Analytics Glossary").classes("text-3xl font-bold mb-2")
    ui.label("Learn about the metrics and scores used in the analytics system.").classes(
        "text-gray-500 mb-6"
    )
    
    # Module grid
    with ui.grid(columns=3).classes("gap-4 w-full"):
        for module_id, module_info in ANALYTICS_MODULES.items():
            with ui.card().classes("p-4 cursor-pointer hover:bg-gray-50").on(
                'click', lambda mid=module_id: ui.navigate.to(f'/analytics/glossary/{mid}')
            ):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.icon(module_info['icon']).classes(f"text-{module_info['color']}-500 text-2xl")
                    ui.label(module_info['title']).classes("text-lg font-semibold")
                
                ui.label(module_info['description']).classes("text-sm text-gray-600 mb-2")
                
                if module_info.get('components'):
                    ui.label(f"{len(module_info['components'])} components").classes(
                        "text-xs text-gray-500"
                    )
                
                ui.button("View Details", 
                         on_click=lambda mid=module_id: ui.navigate.to(f'/analytics/glossary/{mid}')).classes(
                    f"bg-{module_info['color']}-500 text-white mt-2"
                )


def build_module_page(module_id: str):
    """Build a detailed page for a specific analytics module."""
    if module_id not in ANALYTICS_MODULES:
        ui.label("Module not found").classes("text-red-500")
        ui.button("Back to Glossary", on_click=lambda: ui.navigate.to('/analytics/glossary'))
        return
    
    module_info = ANALYTICS_MODULES[module_id]
    
    # Header
    with ui.row().classes("items-center gap-3 mb-4"):
        ui.button("← Back", on_click=lambda: ui.navigate.to('/analytics/glossary')).classes(
            "bg-gray-500 text-white"
        )
        ui.icon(module_info['icon']).classes(f"text-{module_info['color']}-500 text-3xl")
        ui.label(module_info['title']).classes("text-3xl font-bold")
        if module_info.get('version'):
            ui.badge(f"v{module_info['version']}").classes("bg-blue-500 text-white")
    
    # Description
    ui.label(module_info['description']).classes("text-lg text-gray-700 mb-6")
    
    # Formula
    with ui.card().classes("p-4 mb-4 bg-gray-50"):
        with ui.row().classes("items-center gap-2 mb-2"):
            ui.label("Formula").classes("text-lg font-semibold")
            if module_info.get('version'):
                ui.badge(f"v{module_info['version']}").classes("bg-gray-600 text-white text-xs")
        ui.code(module_info['formula']).classes("text-sm")
        ui.label(f"Range: {module_info['range']}").classes("text-sm text-gray-600 mt-2")
    
    # Components (if any)
    if module_info.get('components'):
        ui.label("Components").classes("text-2xl font-semibold mb-4")
        
        for i, component in enumerate(module_info['components'], 1):
            with ui.card().classes("p-4 mb-4"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label(f"{i}. {component['name']}").classes("text-xl font-semibold")
                    if component.get('version'):
                        ui.badge(f"v{component['version']}").classes("bg-blue-500 text-white text-xs")
                
                ui.label(component['description']).classes("text-gray-700 mb-2")
                
                with ui.expansion("Formula", icon="functions").classes("w-full mb-2"):
                    with ui.row().classes("items-center gap-2 mb-1"):
                        ui.code(component['formula']).classes("text-sm")
                        if component.get('version'):
                            ui.badge(f"v{component['version']}").classes("bg-gray-600 text-white text-xs")
                    ui.label(f"Range: {component['range']}").classes("text-sm text-gray-600 mt-2")
                
                # Show details if available
                if component.get('details'):
                    with ui.expansion("Details", icon="info").classes("w-full mb-2"):
                        if isinstance(component['details'], dict):
                            for key, value in component['details'].items():
                                if isinstance(value, dict):
                                    ui.label(f"{key}:").classes("font-semibold text-sm mt-2")
                                    for sub_key, sub_value in value.items():
                                        ui.label(f"  • {sub_key}: {sub_value}").classes("text-xs text-gray-600 ml-4")
                                else:
                                    ui.label(f"• {key}: {value}").classes("text-xs text-gray-600")
                
                # Show parameters if available
                if component.get('parameters'):
                    with ui.expansion("Parameters", icon="tune").classes("w-full mb-2"):
                        for param_name, param_desc in component['parameters'].items():
                            ui.label(f"• {param_name}: {param_desc}").classes("text-xs text-gray-600")
                
                # Graphic aid display - show both theoretical and data-driven
                if component.get('graphic_script'):
                    script_name = component['graphic_script']
                    image_name = script_name.replace('.py', '.png')
                    data_image_name = script_name.replace('.py', '_data.png')
                    
                    theoretical_image_path = os.path.normpath(os.path.join(_images_dir, image_name))
                    data_image_path = os.path.normpath(os.path.join(_images_dir, data_image_name))
                    
                    theoretical_web_path = f'/static/graphic_aids/{image_name}'
                    data_web_path = f'/static/graphic_aids/{data_image_name}'
                    
                    # Display graphic aids automatically (no button needed)
                    ui.label("Visualizations").classes("text-lg font-semibold mt-4 mb-2")
                    
                    # Theoretical visualization
                    with ui.expansion("Theoretical Formula", icon="functions", value=False).classes("w-full mb-2"):
                        if _ensure_graphic_image(script_name, theoretical_image_path):
                            ui.image(theoretical_web_path).classes("w-full max-w-4xl")
                            ui.label("Theoretical visualization showing how the formula works").classes(
                                "text-sm text-gray-600 mt-2"
                            )
                        else:
                            ui.label("Unable to generate theoretical visualization.").classes(
                                "text-sm text-red-500"
                            )
                    
                    # Data-driven visualization (your actual data) - use Plotly for live charts
                    with ui.expansion("Your Data", icon="bar_chart", value=True).classes("w-full"):
                        chart_key = _get_plotly_chart_key(component['name'], script_name)
                        if chart_key and chart_key in PLOTLY_DATA_CHARTS:
                            try:
                                chart_func = PLOTLY_DATA_CHARTS[chart_key]
                                fig = chart_func()
                                if fig:
                                    ui.plotly(fig).classes("w-full")
                                    ui.label(f"Your actual task data for {component['name']} (live, updates with new data)").classes(
                                        "text-sm text-gray-600 mt-2"
                                    )
                                else:
                                    ui.label("Insufficient data to generate visualization. Complete more tasks to see your patterns.").classes(
                                        "text-sm text-gray-500 italic"
                                    )
                            except Exception as e:
                                print(f"[AnalyticsGlossary] Error generating Plotly chart: {e}")
                                ui.label("Error generating chart. Please try again later.").classes(
                                    "text-sm text-red-500"
                                )
                        else:
                            # Fallback to PNG if no Plotly chart available
                            if _ensure_data_graphic_image(data_image_name, data_image_path):
                                ui.image(data_web_path).classes("w-full max-w-4xl")
                                ui.label(f"Your actual task data for {component['name']}").classes(
                                    "text-sm text-gray-600 mt-2"
                                )
                            else:
                                ui.label("Insufficient data to generate visualization. Complete more tasks to see your patterns.").classes(
                                    "text-sm text-gray-500 italic"
                                )
    
    # Interactive Module Link
    if module_info.get('interactive_module'):
        ui.separator().classes("my-6")
        with ui.card().classes("p-4 bg-blue-50 border-2 border-blue-200"):
            ui.label("Interactive Module").classes("text-xl font-semibold mb-2")
            ui.label("Try adjusting parameters and see how they affect the formula in real-time.").classes("text-sm text-gray-700 mb-3")
            ui.button("Open Interactive Module", 
                     on_click=lambda: ui.navigate.to(module_info['interactive_module'])).classes(
                "bg-blue-500 text-white"
            )
    
    # Use Cases
    if module_info.get('use_cases'):
        ui.label("Use Cases").classes("text-2xl font-semibold mb-4")
        with ui.card().classes("p-4"):
            with ui.column().classes("gap-2"):
                for use_case in module_info['use_cases']:
                    with ui.row().classes("items-start gap-2"):
                        ui.icon("check_circle").classes("text-green-500 mt-1")
                        ui.label(use_case).classes("text-gray-700")


def _get_plotly_chart_key(component_name: str, script_name: str) -> Optional[str]:
    """Get the Plotly chart key for a component."""
    # Map component names to Plotly chart keys
    name_mapping = {
        'Baseline Completion': 'productivity_score_baseline_completion',
        'Work Multiplier': 'productivity_score_work_multiplier',
        'Weekly Average Bonus/Penalty': 'productivity_score_weekly_avg_bonus',
        'Goal-Based Adjustment': 'productivity_score_goal_adjustment',
    }
    
    # Try direct name match first
    if component_name in name_mapping:
        return name_mapping[component_name]
    
    # Try script name pattern matching
    if 'baseline_completion' in script_name.lower():
        return 'productivity_score_baseline_completion'
    elif 'work_multiplier' in script_name.lower():
        return 'productivity_score_work_multiplier'
    elif 'weekly_avg' in script_name.lower() or 'weekly_average' in script_name.lower():
        return 'productivity_score_weekly_avg_bonus'
    elif 'goal' in script_name.lower() and 'adjustment' in script_name.lower():
        return 'productivity_score_goal_adjustment'
    
    return None


def _ensure_data_graphic_image(image_name: str, image_path: str) -> bool:
    """Ensure data-driven graphic aid image exists, generating it if needed."""
    # Check if image already exists
    if os.path.exists(image_path):
        return True
    
    # Try to generate the image using the data-driven generator module
    try:
        import sys
        scripts_parent = os.path.normpath(os.path.join(_glossary_file_dir, '..'))
        if scripts_parent not in sys.path:
            sys.path.insert(0, scripts_parent)
        
        from scripts.graphic_aids.generate_data_driven import DATA_DRIVEN_GENERATORS
        
        # image_name should match the key in DATA_DRIVEN_GENERATORS
        if image_name in DATA_DRIVEN_GENERATORS:
            generator_func = DATA_DRIVEN_GENERATORS[image_name]
            generated_path = generator_func(image_path)
            return os.path.exists(generated_path) if generated_path else False
        else:
            # Try to find by partial match (in case naming differs slightly)
            for key, func in DATA_DRIVEN_GENERATORS.items():
                if image_name in key or key in image_name:
                    generated_path = func(image_path)
                    return os.path.exists(generated_path) if generated_path else False
    except ImportError as e:
        print(f"[AnalyticsGlossary] Import error for data graphic {image_name}: {e}")
    except Exception as e:
        print(f"[AnalyticsGlossary] Error generating data image for {image_name}: {e}")
    
    return False


def _ensure_graphic_image(script_name: str, image_path: str) -> bool:
    """Ensure graphic aid image exists, generating it if needed."""
    # Check if image already exists
    if os.path.exists(image_path):
        return True
    
    # Try to generate the image using the generator module
    try:
        # Add scripts directory to path for import
        import sys
        scripts_parent = os.path.normpath(os.path.join(_glossary_file_dir, '..'))
        if scripts_parent not in sys.path:
            sys.path.insert(0, scripts_parent)
        
        from scripts.graphic_aids.generate_all import GRAPHIC_AID_GENERATORS
        
        if script_name in GRAPHIC_AID_GENERATORS:
            generator_func = GRAPHIC_AID_GENERATORS[script_name]
            generated_path = generator_func(image_path)
            return os.path.exists(generated_path) if generated_path else False
    except ImportError as e:
        print(f"[AnalyticsGlossary] Import error for {script_name}: {e}")
        # Fallback: try to import and run the script directly
        try:
            script_path = os.path.normpath(os.path.join(SCRIPTS_DIR, script_name))
            if os.path.exists(script_path):
                # Import the script module and look for a generate function
                import importlib.util
                spec = importlib.util.spec_from_file_location("graphic_script", script_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # Try to call a generate function if it exists
                    if hasattr(module, 'generate_image'):
                        module.generate_image(image_path)
                        return os.path.exists(image_path)
        except Exception as e2:
            print(f"[AnalyticsGlossary] Error generating image for {script_name}: {e2}")
    except Exception as e:
        print(f"[AnalyticsGlossary] Error generating image for {script_name}: {e}")
    
    return False

