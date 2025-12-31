from nicegui import ui
from backend.user_state import UserStateManager
from backend.instance_manager import InstanceManager
from backend.analytics import Analytics
import json

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


@ui.page("/settings")
def settings_page():
    def go_survey():
        ui.navigate.to("/survey")
    
    # def go_data_guide():
    #     ui.navigate.to("/data-guide")

    ui.label("Settings").classes("text-2xl font-bold mb-2")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Surveys").classes("text-lg font-semibold")
        ui.button("Take Mental Health Survey", on_click=go_survey)
        ui.separator()
        ui.label("Scores & Analytics").classes("text-lg font-semibold")
        
        # Composite Score Weights
        ui.button("⚖️ Composite Score Weights", on_click=lambda: ui.navigate.to("/settings/composite-score-weights")).classes("bg-indigo-500 text-white w-full")
        ui.label("Adjust component weights for composite score calculation.").classes("text-xs text-gray-500 mb-2")
        
        # Productivity Settings Link
        ui.button("⚙️ Productivity Settings", on_click=lambda: ui.navigate.to("/settings/productivity-settings")).classes("bg-blue-500 text-white w-full")
        ui.label("Configure productivity scoring, targets, burnout thresholds, and advanced weight settings.").classes("text-xs text-gray-500")
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
    
    # Task Editing Management Section
    ui.separator().classes("my-4")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Task Editing").classes("text-lg font-semibold")
        ui.button("✏️ Task Editing Manager", on_click=lambda: ui.navigate.to("/task-editing-manager")).classes("bg-blue-500 text-white w-full")
        ui.label("Edit completed and cancelled task instances. Navigate between initialization and completion pages for completed tasks.").classes("text-sm text-gray-600 mt-2")
        
        ui.button("⚠️ Cancellation Penalty Weights", on_click=lambda: ui.navigate.to("/settings/cancellation-penalties")).classes("bg-orange-500 text-white w-full mt-2")
        ui.label("Configure productivity penalties for different cancellation reasons.").classes("text-xs text-gray-500")
