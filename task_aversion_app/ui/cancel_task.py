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

        reason_for_canceling = ui.textarea(
            label='Reason for Canceling',
            placeholder='Why are you canceling this task?'
        ).classes("w-full")

        def submit_cancellation():
            iid = (inst_input.value or "").strip()
            if not iid:
                ui.notify("Instance ID required", color='negative')
                return

            if not reason_for_canceling.value or not reason_for_canceling.value.strip():
                ui.notify("Please provide a reason for canceling", color='negative')
                return

            actual = {
                'reason_for_canceling': reason_for_canceling.value.strip(),
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

