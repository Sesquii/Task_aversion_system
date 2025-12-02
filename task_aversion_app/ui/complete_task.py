# ui/complete_task.py
from nicegui import ui
from fastapi import Request
from backend.instance_manager import InstanceManager
import json

im = InstanceManager()

def complete_task_page(task_manager, emotion_manager):

    @ui.page('/complete_task')
    def page(request: Request):   # <-- Request injected here (IMPORTANT)

        print("[complete_task] Entered /complete_task page")
        print("[complete_task] Request headers:", request.headers)
        print("[complete_task] Query params:", request.query_params)

        ui.label("Complete Task").classes("text-xl font-bold")

        params = dict(request.query_params)
        instance_id = params.get("instance_id")
        print("[complete_task] instance_id from URL:", instance_id)

        # Get instance and previous values if instance_id is available
        instance = None
        previous_averages = {}
        current_actual_data = {}
        task_id = None
        
        if instance_id:
            instance = im.get_instance(instance_id)
            if instance:
                task_id = instance.get('task_id')
                # Get previous actual averages for this task
                if task_id:
                    previous_averages = im.get_previous_actual_averages(task_id)
                
                # Check if current instance already has actual values
                actual_raw = instance.get('actual') or '{}'
                try:
                    current_actual_data = json.loads(actual_raw) if actual_raw else {}
                except json.JSONDecodeError:
                    current_actual_data = {}

        inst_input = ui.input(
            label='Instance ID (or leave blank to choose)',
            value=instance_id or ''
        )

        # If no instance_id provided, show selector UI
        if not instance_id:
            active = im.list_active_instances()
            print("[complete_task] active instances:", active)

            inst_select = ui.select(
                options=[f"{r['instance_id']} | {r['task_name']}" for r in active],
                label='Pick active instance'
            )

            def on_choose(e):
                print("[complete_task] dropdown event:", e.args)
                if e.args:
                    iid = e.args[0].split('|', 1)[0]
                    print("[complete_task] picked instance_id:", iid)
                    inst_input.set_value(iid)

            inst_select.on('update:model-value', on_choose)

        # Helper to get default value, scaling from 0-10 to 0-100 if needed
        def get_default_value(key, default=50):
            # First check if current instance has a value
            val = current_actual_data.get(key)
            if val is not None:
                try:
                    num_val = float(val)
                    # Scale from 0-10 to 0-100 if value is <= 10
                    if num_val <= 10 and num_val >= 0:
                        num_val = num_val * 10
                    return int(round(num_val))
                except (ValueError, TypeError):
                    pass
            # Then check previous averages
            if key in previous_averages:
                return previous_averages[key]
            return default
        
        default_relief = get_default_value('actual_relief', 50)
        default_cognitive = get_default_value('actual_cognitive', 50)
        default_physical = get_default_value('actual_physical', 50)
        default_emotional = get_default_value('actual_emotional', 50)

        # ----- Actual values -----

        ui.label("Actual Relief")
        actual_relief = ui.slider(min=0, max=100, step=1, value=default_relief)
        if 'actual_relief' in previous_averages:
            prev_val = previous_averages['actual_relief']
            if prev_val != default_relief:
                ui.label(f"Previous average: {prev_val} (current: {default_relief})").classes("text-xs text-gray-500")
            else:
                ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

        ui.label("Actual Cognitive Demand")
        actual_cognitive = ui.slider(min=0, max=100, step=1, value=default_cognitive)
        if 'actual_cognitive' in previous_averages:
            prev_val = previous_averages['actual_cognitive']
            if prev_val != default_cognitive:
                ui.label(f"Previous average: {prev_val} (current: {default_cognitive})").classes("text-xs text-gray-500")
            else:
                ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

        ui.label("Actual Emotional Demand")
        actual_emotional = ui.slider(min=0, max=100, step=1, value=default_emotional)
        if 'actual_emotional' in previous_averages:
            prev_val = previous_averages['actual_emotional']
            if prev_val != default_emotional:
                ui.label(f"Previous average: {prev_val} (current: {default_emotional})").classes("text-xs text-gray-500")
            else:
                ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

        ui.label("Actual Physical Demand")
        actual_physical = ui.slider(min=0, max=100, step=1, value=default_physical)
        if 'actual_physical' in previous_averages:
            prev_val = previous_averages['actual_physical']
            if prev_val != default_physical:
                ui.label(f"Previous average: {prev_val} (current: {default_physical})").classes("text-xs text-gray-500")
            else:
                ui.label(f"Previous average: {prev_val}").classes("text-xs text-gray-500")

        ui.label("Completion %")
        completion_pct = ui.slider(min=0, max=100, step=5, value=100)

        # Calculate default duration based on whether task was started
        default_duration = 0
        if instance:
            started_at = instance.get('started_at', '')
            if started_at:
                # Calculate duration from start time to now
                from datetime import datetime
                import pandas as pd
                try:
                    started = pd.to_datetime(started_at)
                    now = datetime.now()
                    default_duration = (now - started).total_seconds() / 60.0
                except Exception:
                    pass
            else:
                # Default to expected duration from predicted data
                predicted_raw = instance.get('predicted') or '{}'
                try:
                    predicted_data = json.loads(predicted_raw) if predicted_raw else {}
                    default_duration = float(predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0)
                except (ValueError, TypeError, json.JSONDecodeError):
                    pass

        ui.label("Actual Time (minutes)")
        actual_time = ui.number(value=int(default_duration) if default_duration > 0 else 0)

        notes = ui.textarea(label='Notes (optional)')

        def submit_completion():
            print("[complete_task] submit clicked")
            iid = (inst_input.value or "").strip()
            print("[complete_task] iid:", iid)

            if not iid:
                ui.notify("Instance ID required", color='negative')
                return

            actual = {
                'actual_relief': int(actual_relief.value),
                'actual_cognitive': int(actual_cognitive.value),
                'actual_emotional': int(actual_emotional.value),
                'actual_physical': int(actual_physical.value),
                'completion_percent': int(completion_pct.value),
                'time_actual_minutes': int(actual_time.value or 0),
                'notes': notes.value or ""
            }

            print("[complete_task] actual payload:", actual)

            try:
                result = im.complete_instance(iid, actual)
                print("[complete_task] complete_instance result:", result)
            except Exception as e:
                print("[complete_task] ERROR:", e)
                ui.notify(str(e), color='negative')
                return

            ui.notify("Instance completed", color='positive')
            ui.navigate.to('/')

        ui.button("Submit Completion", on_click=submit_completion)
