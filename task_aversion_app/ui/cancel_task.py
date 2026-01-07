from nicegui import ui
from fastapi import Request
from backend.instance_manager import InstanceManager
from backend.user_state import UserStateManager

im = InstanceManager()
user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"

# Default cancellation categories
DEFAULT_CANCELLATION_CATEGORIES = {
    'did_while_another_active': 'Did task while another task was active',
    'deferred_to_plan': 'Deferred to plan instead of executing',
    'development_test': 'Development/test task',
    'accidental_initialization': 'Accidentally initialized',
    'failed_to_complete': 'Failed to complete task',
    'other': 'Other reason'
}


def get_all_cancellation_categories():
    """Get all cancellation categories (default + custom)."""
    custom_categories = user_state.get_cancellation_categories(DEFAULT_USER_ID)
    # Merge custom with default (custom takes precedence if key conflicts)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


def cancel_task_page(task_manager, emotion_manager):

    @ui.page('/cancel_task')
    def page(request: Request):
        ui.label("Cancel Task").classes("text-xl font-bold mb-4")

        params = dict(request.query_params)
        instance_id = params.get("instance_id")

        with ui.card().classes("w-full max-w-2xl p-4 gap-3"):
            inst_input = ui.input(
                label='Instance ID (or leave blank to choose)',
                value=instance_id or ''
            )

            if not instance_id:
                active = im.list_active_instances()
                if active:
                    inst_select = ui.select(
                        options=[f"{r['instance_id']} | {r['task_name']}" for r in active],
                        label='Pick active instance'
                    )

                    def on_choose(e):
                        if e.args:
                            iid = e.args[0].split('|', 1)[0].strip()
                            inst_input.set_value(iid)

                    inst_select.on('update:model-value', on_choose)
                else:
                    ui.label("No active instances to cancel").classes("text-gray-500")

            ui.separator()

            # Load all categories (default + custom)
            all_categories = get_all_cancellation_categories()
            
            ui.label("Cancellation Category (Required)").classes("text-sm font-semibold")
            cancellation_category = ui.select(
                options=all_categories,
                label='Select a category',
                value='other'
            ).classes("w-full").props("dense outlined")
            ui.label("Choose the reason why you're cancelling this task.").classes("text-xs text-gray-500 mb-2")

            reason_for_canceling = ui.textarea(
                label='Additional Notes (optional)',
                placeholder='Any additional details about why you\'re canceling this task...'
            ).classes("w-full")

            def submit_cancellation():
                iid = (inst_input.value or "").strip()
                if not iid:
                    ui.notify("Instance ID required", color='negative')
                    return

                if not cancellation_category.value:
                    ui.notify("Please select a cancellation category", color='negative')
                    return

                actual = {
                    'cancellation_category': cancellation_category.value,
                    'reason_for_canceling': reason_for_canceling.value.strip() if reason_for_canceling.value else '',
                    'cancelled': True
                }

                try:
                    im.cancel_instance(iid, actual)
                except Exception as exc:
                    ui.notify(str(exc), color='negative')
                    return

                ui.notify("Instance cancelled", color='warning')
                # Navigate to dashboard - it will refresh on load
                ui.navigate.to('/')

            ui.button("Submit Cancellation", color="warning", on_click=submit_cancellation).classes("mt-2")

