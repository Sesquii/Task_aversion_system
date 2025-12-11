from nicegui import ui
import json

def create_task_page(task_manager, emotion_manager):

    @ui.page('/create_task')
    def page():

        ui.label("Create Task Template").classes("text-xl font-bold")

        with ui.column().classes('w-full max-w-2xl gap-4'):

            name = ui.input(label="Task Name")
            desc = ui.textarea(label="Description (optional)")
            ttype = ui.select(['one-time','recurring','routine','project'], label='Type', value='one-time')
            est = ui.number(label='Default estimate minutes', value=0)

            def save_task():
                if not name.value.strip():
                    ui.notify("Task name required", color='negative')
                    return

                tid = task_manager.create_task(
                    name.value.strip(),
                    description=desc.value or '',
                    ttype=ttype.value,
                    is_recurring=(ttype.value != 'one-time'),
                    categories=json.dumps([]),
                    default_estimate_minutes=int(est.value or 0)
                )

                ui.notify(f"Task created: {tid}", color='positive')
                ui.navigate.to('/')

            ui.button("Create Task", on_click=save_task)
