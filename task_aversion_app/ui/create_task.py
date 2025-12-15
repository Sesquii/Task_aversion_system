from nicegui import ui
import json

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

            def save_task():
                if not name.value.strip():
                    ui.notify("Task name required", color='negative')
                    return

                # If checkbox is checked, set default aversion to 50, otherwise None
                default_aversion = 50 if aversion_checkbox.value else None

                tid = task_manager.create_task(
                    name.value.strip(),
                    description=desc.value or '',
                    categories=json.dumps([]),
                    default_estimate_minutes=int(est.value or 0),
                    task_type=task_type.value,
                    default_initial_aversion=default_aversion
                )

                ui.notify(f"Task created: {tid}", color='positive')
                ui.navigate.to('/')

            ui.button("Create Task", on_click=save_task)
