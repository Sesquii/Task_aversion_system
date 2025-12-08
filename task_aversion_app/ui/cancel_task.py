from nicegui import ui
from fastapi import Request
from backend.instance_manager import InstanceManager

im = InstanceManager()


def cancel_task_page(task_manager, emotion_manager):

    @ui.page('/cancel_task')
    def page(request: Request):
        ui.label("Cancel Task").classes("text-xl font-bold")

        params = dict(request.query_params)
        instance_id = params.get("instance_id")

        inst_input = ui.input(
            label='Instance ID (or leave blank to choose)',
            value=instance_id or ''
        )

        if not instance_id:
            active = im.list_active_instances()
            inst_select = ui.select(
                options=[f"{r['instance_id']} | {r['task_name']}" for r in active],
                label='Pick active instance'
            )

            def on_choose(e):
                if e.args:
                    iid = e.args[0].split('|', 1)[0]
                    inst_input.set_value(iid)

            inst_select.on('update:model-value', on_choose)

        ui.label("Emotional State at Cancellation")
        actual_emotional = ui.slider(min=0, max=10, value=5)

        ui.label("Mental Load at Cancellation")
        actual_cognitive = ui.slider(min=0, max=10, value=5)

        ui.label("Relief Expectation")
        actual_relief = ui.slider(min=0, max=10, value=5)

        ui.label("Progress %")
        completion_pct = ui.slider(min=0, max=100, step=5, value=50)

        ui.label("Time Spent (minutes)")
        actual_time = ui.number(value=0)

        reason_for_canceling = ui.textarea(
            label='Reason for Canceling',
            placeholder='Why are you canceling this task?'
        )

        notes = ui.textarea(label='Notes (optional)')

        def submit_cancellation():
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
                'reason_for_canceling': reason_for_canceling.value or "",
                'notes': notes.value or "",
                'cancelled': True
            }

            try:
                im.cancel_instance(iid, actual)
            except Exception as exc:
                ui.notify(str(exc), color='negative')
                return

            ui.notify("Instance cancelled", color='warning')
            ui.navigate.to('/')

        ui.button("Submit Cancellation", color="warning", on_click=submit_cancellation)

