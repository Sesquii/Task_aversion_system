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

        with ui.column().classes("w-full max-w-xl gap-4"):

            ui.label("Emotional Context")

            emotions = ui.select(
                ["Excitement", "Anxiety", "Confusion", "Overwhelm", "Dread", "Neutral", "Custom..."],
                multiple=True
            )

            custom_emotion_field = ui.input(placeholder="Custom Emotion")
            custom_emotion_field.set_visibility(False)

            def emotion_changed(e):
                custom_emotion_field.set_visibility(
                    "Custom..." in (e.args or [])
                )

            emotions.on("update:model-value", emotion_changed)

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
                if "Custom..." in emotion_list and custom_emotion_field.value:
                    emotion_list.remove("Custom...")
                    emotion_list.append(custom_emotion_field.value)

                entry = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "task": task_id,
                    "emotions": ",".join(emotion_list),
                    "expected_cognitive_load": cog_load.value,
                    "physical_context": (
                        custom_physical.value if physical_context.value == "Custom..." else physical_context.value
                    ),
                    "motivation": motivation.value,
                    "initialized": True,
                    "completed": False,
                }

                task_manager.save_initialization_entry(entry)
                ui.notify("Task initialized!", color='positive')

            ui.button("Save Initialization", on_click=save).classes("mt-4")
