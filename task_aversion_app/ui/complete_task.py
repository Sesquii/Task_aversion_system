# ui/complete_task.py
from nicegui import ui
from backend.instance_manager import InstanceManager
import json

im = InstanceManager()

def complete_task_page(task_manager, emotion_manager):
    @ui.page('/complete_task')
    def page():
        ui.label("Complete Task").classes("text-xl font-bold")
        params = ui.get_query()
        instance_id = params.get('instance_id') if params else None

        inst_input = ui.input(label='Instance ID (or leave blank to choose)', value=instance_id or '')
        if not instance_id:
            # populate a list for quick select
            active = im.list_active_instances()
            inst_select = ui.select(options=[f"{r['instance_id']}|{r['task_name']}" for r in active], label='Pick active instance')
            def on_choose(e):
                val = e.args[0] if isinstance(e.args, list) and e.args else None
                if val:
                    iid = val.split('|',1)[0]
                    inst_input.set_value(iid)
            inst_select.on('update:model-value', on_choose)

        # actuals
        actual_relief = ui.slider(min=0, max=10, value=5, label='Actual Relief')
        actual_cognitive = ui.slider(min=0, max=10, value=5, label='Actual Cognitive Demand')
        actual_emotional = ui.slider(min=0, max=10, value=5, label='Actual Emotional Demand')
        completion_pct = ui.slider(min=0, max=100, step=5, value=100, label='Completion %')
        actual_time = ui.number(label='Actual time minutes', value=0)
        notes = ui.textarea(label='Notes (optional)')

        def submit_completion():
            iid = inst_input.value.strip()
            if not iid:
                ui.notify("Instance ID required", color='negative')
                return
            actual = {
                'actual_relief': int(actual_relief.value),
                'actual_cognitive': int(actual_cognitive.value),
                'actual_emotional': int(actual_emotional.value),
                'completion_percent': int(completion_pct.value),
                'time_actual_minutes': int(actual_time.value),
                'notes': notes.value
            }
            im.complete_instance(iid, actual)
            ui.notify("Instance completed", color='positive')
            ui.navigate.to('/')

        ui.button("Submit Completion", on_click=submit_completion)
