# ui/complete_task.py
from nicegui import ui, app
from backend.instance_manager import InstanceManager
from fastapi import Request
im = InstanceManager()

def complete_task_page(task_manager, emotion_manager):



    @ui.page('/complete_task')
    def page():

        ui.label("Complete Task").classes("text-xl font-bold")

        # Access Starlette request directly from NiceGUI
        req = app.request
        params = dict(req.query_params)
        instance_id = params.get("instance_id")

        inst_input = ui.input(
            label='Instance ID (or leave blank to choose)',
            value=instance_id or ''
        )

        # If no instance_id provided, show selector UI
        if not instance_id:
            active = im.list_active_instances()
            inst_select = ui.select(
                options=[f"{r['instance_id']} | {r['task_name']}" for r in active],
                label='Pick active instance'
            )

            def on_choose(e):
                val = e.args[0] if isinstance(e.args, list) and e.args else None
                if val:
                    iid = val.split('|', 1)[0]
                    inst_input.set_value(iid)

            inst_select.on('update:model-value', on_choose)

        # ----- Actual Values -----

        ui.label("Actual Relief")
        actual_relief = ui.slider(min=0, max=10, value=5)

        ui.label("Actual Cognitive Demand")
        actual_cognitive = ui.slider(min=0, max=10, value=5)

        ui.label("Actual Emotional Demand")
        actual_emotional = ui.slider(min=0, max=10, value=5)

        ui.label("Completion %")
        completion_pct = ui.slider(min=0, max=100, step=5, value=100)

        ui.label("Actual Time (minutes)")
        actual_time = ui.number(value=0)

        notes = ui.textarea(label='Notes (optional)')

        def submit_completion():
            iid = (inst_input.value or "").strip()
            if not iid:
                ui.notify("Instance ID required", color='negative')
                return

            actual = {
                'actual_relief': int(actual_relief.value),
                'actual_cognitive': int(actual_cognitive.value),
                'actual_emotional': int(actual_emotional.value),
                'completion_percent': int(completion_pct.value),
                'time_actual_minutes': int(actual_time.value or 0),
                'notes': notes.value or ""
            }

            im.complete_instance(iid, actual)
            ui.notify("Instance completed", color='positive')
            ui.navigate.to('/')

        ui.button("Submit Completion", on_click=submit_completion)
