from nicegui import ui
from datetime import datetime
import json

from fastapi import Request
from backend.instance_manager import InstanceManager

im = InstanceManager()


def initialize_task_page(task_manager, emotion_manager):

    @ui.page('/initialize-task')
    def page(request: Request):
        params = request.query_params  # ✅

        instance_id = params.get("instance_id")

        if not instance_id:
            ui.notify("Error: no instance_id provided", color='negative')
            ui.navigate.to('/')
            return

        instance = im.get_instance(instance_id)
        if not instance:
            ui.notify("Instance not found", color='negative')
            ui.navigate.to('/')
            return

        task = task_manager.get_task(instance.get('task_id'))
        task_description = task.get('description', '') if task else ''
        predicted_raw = instance.get('predicted') or '{}'
        try:
            predicted_data = json.loads(predicted_raw) if predicted_raw else {}
        except json.JSONDecodeError:
            predicted_data = {}
        default_estimate = predicted_data.get('time_estimate_minutes') \
            or predicted_data.get('estimate') \
            or (task.get('default_estimate_minutes') if task else 0) \
            or 0
        try:
            default_estimate = int(default_estimate)
        except (TypeError, ValueError):
            default_estimate = 0

        with ui.column().classes("w-full max-w-xl gap-4"):

            description_field = ui.textarea(
                label="Task Description (optional)",
                value=task_description,
            )

            ui.label("Emotional Context")

            default_emotions = ["Excitement", "Anxiety", "Confusion", "Overwhelm", "Dread", "Neutral"]
            stored_emotions = emotion_manager.list_emotions()
            emotion_options = default_emotions + [e for e in stored_emotions if e not in default_emotions]

            emotions = ui.select(
                emotion_options,
                multiple=True
            )

            new_em = ui.input(label="Add custom emotion")

            def add_emotion():
                val = (new_em.value or '').strip()
                if not val:
                    ui.notify("Enter an emotion", color='negative')
                    return
                added = emotion_manager.add_emotion(val)
                if added:
                    ui.notify(f"Added emotion: {val}", color='positive')
                else:
                    ui.notify("Emotion already exists", color='warning')
                latest = default_emotions + [e for e in emotion_manager.list_emotions() if e not in default_emotions]
                emotions.options = latest
                current = set(emotions.value or [])
                current.add(val)
                emotions.value = list(current)
                new_em.set_value('')

            ui.button("Add Emotion", on_click=add_emotion)

            # Cognitive load slider (NiceGUI 1.x → no label)
            ui.label("Expected Cognitive Load")
            cog_load = ui.slider(min=0, max=10, step=1, value=5)

            ui.label("Expected Physical Load")
            physical_load = ui.slider(min=0, max=10, step=1, value=5)

            ui.label("Expected Emotional Load")
            emotional_load = ui.slider(min=0, max=10, step=1, value=5)

            ui.label("Physical Context")
            physical_context = ui.select(
                ["None", "Home", "Work", "Gym", "Outdoors", "Errands", "Custom..."]
            )

            custom_physical = ui.input(placeholder="Custom Physical Context")
            custom_physical.set_visibility(False)

            def physical_changed(e):
                custom_physical.set_visibility(e.args == "Custom...")

            physical_context.on("update:model-value", physical_changed)

            ui.label("Motivation Level")
            motivation = ui.slider(min=0, max=10, value=5)

            estimate_input = ui.number(
                label="Estimated Time to Complete (minutes)",
                value=default_estimate,
                min=0
            )

            def save():
                emotion_list = emotions.value or []
                physical_value = (
                    custom_physical.value if physical_context.value == "Custom..." else physical_context.value
                ) or "None"
                try:
                    estimate_val = int(estimate_input.value or 0)
                except (TypeError, ValueError):
                    estimate_val = 0

                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "instance_id": instance_id,
                    "task": instance.get('task_id'),
                    "emotions": ",".join(emotion_list),
                    "expected_cognitive_load": cog_load.value,
                    "expected_physical_load": physical_load.value,
                    "expected_emotional_load": emotional_load.value,
                    "physical_context": physical_value,
                    "motivation": motivation.value,
                    "description": description_field.value or '',
                    "estimate_minutes": estimate_val,
                    "initialized": True,
                    "completed": False,
                }

                predicted_payload = {
                    "time_estimate_minutes": estimate_val,
                    "emotions": emotion_list,
                    "expected_cognitive_load": cog_load.value,
                    "expected_physical_load": physical_load.value,
                    "expected_emotional_load": emotional_load.value,
                    "physical_context": physical_value,
                    "motivation": motivation.value,
                    "description": description_field.value or ''
                }

                try:
                    im.add_prediction_to_instance(instance_id, predicted_payload)
                except Exception as exc:
                    ui.notify(f"Failed to save instance: {exc}", color='negative')
                    return

                task_manager.save_initialization_entry(entry)
                ui.notify("Task initialized!", color='positive')
                ui.navigate.to('/')

            ui.button("Save Initialization", on_click=save).classes("mt-4")
