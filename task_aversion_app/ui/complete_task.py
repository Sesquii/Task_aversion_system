# ui/complete_task.py
from nicegui import ui
from fastapi import Request
from backend.instance_manager import InstanceManager

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

        # ----- Actual values -----

        ui.label("Actual Relief")
        actual_relief = ui.slider(min=0, max=10, value=5)

        ui.label("Actual Cognitive Demand")
        actual_cognitive = ui.slider(min=0, max=10, value=5)

        ui.label("Actual Emotional Demand")
        actual_emotional = ui.slider(min=0, max=10, value=5)

        ui.label("Actual Physical Demand")
        actual_physical = ui.slider(min=0, max=10, value=5)

        ui.label("Completion %")
        completion_pct = ui.slider(min=0, max=100, step=5, value=100)

        ui.label("Actual Time (minutes)")
        actual_time = ui.number(value=0)

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
