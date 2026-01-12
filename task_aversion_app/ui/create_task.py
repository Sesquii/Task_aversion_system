from nicegui import ui
import json
from backend.security_utils import ValidationError
from backend.auth import get_current_user
from ui.error_reporting import handle_error_with_ui

def create_task_page(task_manager, emotion_manager):

    @ui.page('/create_task')
    def page():

        ui.label("Create Task Template").classes("text-xl font-bold")

        with ui.column().classes('w-full max-w-2xl gap-4'):

            name = ui.input(label="Task Name")
            desc = ui.textarea(label="Description (optional)")
            task_type = ui.select(['Work', 'Play', 'Self care'], label='Task Type', value='Work')
            est = ui.number(label='Default estimate minutes', value=0)
            
            # Simple checkbox for aversion - if checked, sets default to 50
            aversion_checkbox = ui.checkbox("Check if you are averse to starting this task")

            # Routine scheduling section
            ui.label("Routine Scheduling (Optional)").classes("text-lg font-semibold mt-4")
            
            routine_frequency = ui.select(
                ['none', 'daily', 'weekly'],
                label='Routine Frequency',
                value='none'
            )
            
            # Day of week selection (for daily and weekly)
            day_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_checkboxes = {}
            day_container = ui.column().classes("gap-2")
            
            def update_day_visibility():
                """Show/hide day selection based on frequency"""
                day_container.set_visibility(routine_frequency.value in ['daily', 'weekly'])
            
            routine_frequency.on('update:model-value', lambda: update_day_visibility())
            
            with day_container:
                ui.label("Select days of week (leave all unchecked for daily to run every day):").classes("text-sm")
                for i, day in enumerate(day_labels):
                    day_checkboxes[i] = ui.checkbox(day)
            
            day_container.set_visibility(False)  # Hidden by default
            
            # Time picker (using input with time type)
            routine_time = ui.input(
                label='Routine Time (HH:MM, 24-hour format)',
                value='00:00',
                placeholder='00:00'
            ).classes("max-w-xs")
            
            # Completion window (hours and days)
            ui.label("Completion Window (Optional)").classes("text-sm font-semibold")
            ui.label("Time to complete task after initialization without penalty").classes("text-xs text-gray-500")
            with ui.row().classes("gap-4"):
                completion_window_hours = ui.number(
                    label='Hours',
                    value=None,
                    placeholder='Hours',
                    min=0
                ).classes("flex-1")
                completion_window_days = ui.number(
                    label='Days',
                    value=None,
                    placeholder='Days',
                    min=0
                ).classes("flex-1")

            def save_task():
                if not name.value.strip():
                    ui.notify("Task name required", color='negative')
                    return

                # Validate time format
                time_str = routine_time.value.strip() or '00:00'
                try:
                    # Basic validation: should be HH:MM format
                    parts = time_str.split(':')
                    if len(parts) != 2:
                        raise ValueError("Invalid time format")
                    hour = int(parts[0])
                    minute = int(parts[1])
                    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                        raise ValueError("Invalid time values")
                    # Normalize format
                    time_str = f"{hour:02d}:{minute:02d}"
                except (ValueError, IndexError):
                    ui.notify("Invalid time format. Use HH:MM (24-hour format, e.g., 09:30)", color='negative')
                    return

                # If checkbox is checked, set default aversion to 50, otherwise 0
                default_aversion = 50 if aversion_checkbox.value else 0

                # Get selected days for daily or weekly routine
                selected_days = []
                if routine_frequency.value in ['daily', 'weekly']:
                    selected_days = [i for i, cb in day_checkboxes.items() if cb.value]
                    if routine_frequency.value == 'weekly' and not selected_days:
                        ui.notify("Please select at least one day for weekly routine", color='negative')
                        return
                    # For daily, if no days selected, it means every day (empty list)
                    # If days are selected, it means only on those days

                # Get completion window values (None if empty)
                completion_window_hours_val = None
                if completion_window_hours.value is not None and completion_window_hours.value > 0:
                    completion_window_hours_val = int(completion_window_hours.value)
                
                completion_window_days_val = None
                if completion_window_days.value is not None and completion_window_days.value > 0:
                    completion_window_days_val = int(completion_window_days.value)

                try:
                    user_id = get_current_user()
                    tid = task_manager.create_task(
                        name.value.strip(),
                        description=desc.value or '',
                        categories=json.dumps([]),
                        default_estimate_minutes=int(est.value or 0),
                        task_type=task_type.value,
                        default_initial_aversion=default_aversion,
                        routine_frequency=routine_frequency.value,
                        routine_days_of_week=selected_days,
                        routine_time=time_str,
                        completion_window_hours=completion_window_hours_val,
                        completion_window_days=completion_window_days_val,
                        user_id=user_id
                    )

                    ui.notify(f"Task created: {tid}", color='positive')
                    
                    # Signal dashboard to refresh templates
                    from nicegui import app
                    app.storage.general['refresh_templates'] = True
                    
                    ui.navigate.to('/')
                except ValidationError as e:
                    # Validation errors (e.g., name too long) - show user-friendly message
                    ui.notify(str(e), color='negative')
                except Exception as e:
                    # Other errors - use error ID system
                    handle_error_with_ui(
                        'create_task',
                        e,
                        user_id=get_current_user(),
                        context={
                            'task_name': name.value[:50] if name.value else None,
                            'task_type': task_type.value
                        }
                    )

            ui.button("Create Task", on_click=save_task)
