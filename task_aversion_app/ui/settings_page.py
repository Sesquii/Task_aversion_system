from nicegui import ui
from backend.user_state import UserStateManager
from backend.instance_manager import InstanceManager
from backend.analytics import Analytics
import json
import re

analytics = Analytics()

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"
im = InstanceManager()

# Default cancellation categories
DEFAULT_CANCELLATION_CATEGORIES = {
    'did_while_another_active': 'Did task while another task was active',
    'deferred_to_plan': 'Deferred to plan instead of executing',
    'development_test': 'Development/test task',
    'accidental_initialization': 'Accidentally initialized',
    'failed_to_complete': 'Failed to complete task',
    'other': 'Other reason'
}


def get_all_cancellation_categories():
    """Get all cancellation categories (default + custom)."""
    custom_categories = user_state.get_cancellation_categories(DEFAULT_USER_ID)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


def sanitize_category_key(key: str) -> str:
    """Convert a label to a valid category key (lowercase, underscores, no spaces)."""
    # Convert to lowercase and replace spaces/special chars with underscores
    key = re.sub(r'[^a-z0-9_]', '_', key.lower())
    # Remove multiple underscores
    key = re.sub(r'_+', '_', key)
    # Remove leading/trailing underscores
    key = key.strip('_')
    return key or 'custom_category'


@ui.page("/settings")
def settings_page():
    def go_survey():
        ui.navigate.to("/survey")
    
    # def go_data_guide():
    #     ui.navigate.to("/data-guide")

    def go_composite_score():
        ui.navigate.to("/composite-score")
    
    ui.label("Settings").classes("text-2xl font-bold mb-2")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Surveys").classes("text-lg font-semibold")
        ui.button("Take Mental Health Survey", on_click=go_survey)
        ui.separator()
        ui.label("Scores & Analytics").classes("text-lg font-semibold")
        ui.button("📊 Composite Score Dashboard", on_click=go_composite_score).classes("bg-purple-500 text-white")
        ui.label("View your overall performance score and component breakdown.").classes("text-sm text-gray-600 mt-2")
        
        ui.separator()
        ui.label("Productivity Scoring").classes("text-lg font-semibold")
        ui.label("Adjust productivity weekly curve and burnout thresholds.").classes("text-sm text-gray-600 mb-2")

        # Load existing settings
        existing_settings = user_state.get_productivity_settings(DEFAULT_USER_ID) or {}
        weekly_curve = existing_settings.get("weekly_curve", "flattened_square")
        weekly_burnout_threshold_hours = float(existing_settings.get("weekly_burnout_threshold_hours", 42.0) or 42.0)
        daily_burnout_cap_multiplier = float(existing_settings.get("daily_burnout_cap_multiplier", 2.0) or 2.0)

        weekly_curve_select = ui.select(
            {
                "linear": "Linear (legacy)",
                "flattened_square": "Softened square (default)",
            },
            value=weekly_curve,
            label="Weekly bonus/penalty curve",
        ).props("dense outlined")

        burnout_weekly_input = ui.number(
            label="Weekly burnout threshold (hours/week)",
            value=weekly_burnout_threshold_hours,
            min=10,
            max=100,
            step=1,
        ).props("dense outlined").classes("w-full max-w-sm")

        burnout_daily_cap_input = ui.number(
            label="Daily burnout cap (x daily average)",
            value=daily_burnout_cap_multiplier,
            min=1.0,
            max=4.0,
            step=0.1,
        ).props("dense outlined").classes("w-full max-w-sm")

        def save_productivity_settings():
            settings = {
                "weekly_curve": weekly_curve_select.value or "flattened_square",
                "weekly_burnout_threshold_hours": float(burnout_weekly_input.value or 42.0),
                "daily_burnout_cap_multiplier": float(burnout_daily_cap_input.value or 2.0),
            }
            user_state.set_productivity_settings(DEFAULT_USER_ID, settings)
            ui.notify("Productivity settings saved. Refresh analytics to apply.", color="positive")

        ui.button("Save Productivity Settings", on_click=save_productivity_settings).classes("bg-blue-500 text-white mt-2")
        ui.separator()
        ui.label("Data & Export").classes("text-lg font-semibold")
        
        def export_csv():
            """Export database data to CSV files."""
            import os
            import sys
            
            try:
                # Import here to avoid circular imports
                from backend.database import get_session, Task, TaskInstance, Emotion
                import pandas as pd
                from nicegui import app
                
                session = get_session()
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
                os.makedirs(data_dir, exist_ok=True)
                
                try:
                    # Export tasks
                    tasks = session.query(Task).all()
                    if tasks:
                        tasks_data = [task.to_dict() for task in tasks]
                        tasks_df = pd.DataFrame(tasks_data)
                        tasks_file = os.path.join(data_dir, 'tasks.csv')
                        tasks_df.to_csv(tasks_file, index=False)
                    
                    # Export instances
                    instances = session.query(TaskInstance).all()
                    if instances:
                        instances_data = [instance.to_dict() for instance in instances]
                        instances_df = pd.DataFrame(instances_data)
                        instances_file = os.path.join(data_dir, 'task_instances.csv')
                        instances_df.to_csv(instances_file, index=False)
                    
                    # Export emotions
                    emotions = session.query(Emotion).all()
                    if emotions:
                        emotions_data = [emotion.to_dict() for emotion in emotions]
                        emotions_df = pd.DataFrame(emotions_data)
                        emotions_file = os.path.join(data_dir, 'emotions.csv')
                        emotions_df.to_csv(emotions_file, index=False)
                    
                    ui.notify(f"Data exported successfully! Files saved to: {data_dir}", color="positive")
                finally:
                    session.close()
            except Exception as e:
                import traceback
                error_msg = str(e)
                ui.notify(f"Error exporting data: {error_msg}", color="negative")
                print(f"[Settings] Export error: {traceback.format_exc()}")
        
        ui.button("📥 Export Data to CSV", on_click=export_csv).classes("bg-green-500 text-white mt-2")
        ui.label("Export all database data (tasks, instances, emotions) to CSV files in the data/ folder.").classes("text-sm text-gray-600 mt-2")
        ui.markdown("- **Data Guide**: Currently missing - documentation for local setup, data backup, and troubleshooting is planned but not yet implemented").classes("text-sm text-gray-600 mt-2")
    
    # Score & Penalty Configuration Links
    ui.separator().classes("my-4")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Score & Penalty Configuration").classes("text-lg font-semibold")
        ui.label("Configure multipliers and weights for scoring systems.").classes("text-sm text-gray-600 mb-3")
        
        with ui.column().classes("w-full gap-2"):
            ui.button("⚖️ Composite Score Weights", on_click=lambda: ui.navigate.to("/settings/composite-score-weights")).classes("bg-indigo-500 text-white w-full")
            ui.label("Adjust component weights for composite score calculation.").classes("text-xs text-gray-500")
            
            ui.button("⚠️ Cancellation Penalties", on_click=lambda: ui.navigate.to("/settings/cancellation-penalties")).classes("bg-orange-500 text-white w-full")
            ui.label("Configure productivity penalties for different cancellation reasons.").classes("text-xs text-gray-500")
    
    # Cancelled Tasks Management Section
    ui.separator().classes("my-4")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Cancelled Tasks").classes("text-lg font-semibold")
        ui.button("📋 Manage Cancelled Tasks", on_click=lambda: ui.navigate.to("/cancelled-tasks")).classes("bg-orange-500 text-white")
        ui.label("View, filter, and manage all cancelled task instances. Configure cancellation penalties.").classes("text-sm text-gray-600 mt-2")
    
    # Cancellation Categories Management Section
    ui.separator().classes("my-4")
    with ui.card().classes("w-full max-w-4xl p-4 gap-3"):
        ui.label("Cancellation Categories").classes("text-lg font-semibold")
        ui.label("Manage custom cancellation categories. Default categories cannot be deleted.").classes("text-sm text-gray-600 mb-3")
        
        def refresh_categories_list():
            categories_list_container.clear()
            with categories_list_container:
                all_categories = get_all_cancellation_categories()
                custom_categories = user_state.get_cancellation_categories(DEFAULT_USER_ID)
                
                if not all_categories:
                    ui.label("No categories found.").classes("text-gray-500 p-4")
                else:
                    with ui.column().classes("w-full gap-2"):
                        for cat_key, cat_label in sorted(all_categories.items()):
                            is_default = cat_key in DEFAULT_CANCELLATION_CATEGORIES
                            with ui.card().classes("w-full p-3 border border-gray-200"):
                                with ui.row().classes("w-full items-center justify-between gap-3"):
                                    with ui.column().classes("flex-1 gap-1"):
                                        ui.label(cat_label).classes("text-base font-semibold")
                                        ui.label(f"Key: {cat_key}").classes("text-xs text-gray-500")
                                        if is_default:
                                            ui.label("Default category").classes("text-xs text-blue-600")
                                    
                                    if not is_default:
                                        def delete_category(key=cat_key):
                                            user_state.remove_cancellation_category(key, DEFAULT_USER_ID)
                                            refresh_categories_list()
                                            ui.notify("Category deleted", color="positive")
                                        
                                        ui.button("Delete", on_click=delete_category, color="negative").classes("text-xs")
                        
                        # Add new category form
                        ui.separator().classes("my-2")
                        with ui.card().classes("w-full p-3 bg-gray-50 border border-gray-300"):
                            ui.label("Add New Category").classes("text-sm font-semibold mb-2")
                            with ui.row().classes("w-full gap-2 items-end"):
                                new_category_label_input = ui.input(
                                    label="Category Label",
                                    placeholder="e.g., Changed my mind"
                                ).classes("flex-1")
                                
                                def add_category():
                                    label = new_category_label_input.value.strip()
                                    if not label:
                                        ui.notify("Please enter a category label", color="negative")
                                        return
                                    
                                    # Generate key from label
                                    key = sanitize_category_key(label)
                                    
                                    # Check if key already exists
                                    all_cats = get_all_cancellation_categories()
                                    if key in all_cats:
                                        # Make it unique
                                        counter = 1
                                        original_key = key
                                        while key in all_cats:
                                            key = f"{original_key}_{counter}"
                                            counter += 1
                                    
                                    user_state.add_cancellation_category(key, label, DEFAULT_USER_ID)
                                    new_category_label_input.set_value("")
                                    refresh_categories_list()
                                    ui.notify("Category added", color="positive")
                                
                                ui.button("Add", on_click=add_category, color="positive").classes("bg-green-500 text-white")
        
        categories_list_container = ui.column().classes("w-full mt-3")
        refresh_categories_list()
