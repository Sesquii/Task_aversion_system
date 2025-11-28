from nicegui import ui
from datetime import datetime

from fastapi import Request

def initialize_task_page(task_manager, emotion_manager):

    @ui.page('/initialize-task')
    def page(request: Request):
        params = request.query_params  # ✅

        task_id = params.get("task_id")

        if not task_id:
            ui.notify("Error: no task_id provided", color='negative')
            ui.navigate.to('/')
            return

        task = task_manager.get_task(task_id)
        task_description = task.get('description', '') if task else ''

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

            def save():
                emotion_list = emotions.value or []

                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "task": task_id,
                    "emotions": ",".join(emotion_list),
                    "expected_cognitive_load": cog_load.value,
                    "physical_context": (
                        custom_physical.value if physical_context.value == "Custom..." else physical_context.value
                    ),
                    "motivation": motivation.value,
                    "description": description_field.value or '',
                    "initialized": True,
                    "completed": False,
                }

                task_manager.save_initialization_entry(entry)
                ui.notify("Task initialized!", color='positive')

            ui.button("Save Initialization", on_click=save).classes("mt-4")
