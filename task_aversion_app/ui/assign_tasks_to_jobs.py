# ui/assign_tasks_to_jobs.py
"""Page to assign existing task templates to jobs. Select job(s) at top, then Assign from task list."""
from nicegui import ui

from backend.auth import get_current_user
from backend.task_manager import TaskManager
from backend.job_manager import JobManager
from backend.security_utils import escape_for_display


def register_assign_tasks_to_jobs_page(task_manager: TaskManager) -> None:
    """Register the /assign-tasks-to-jobs page."""

    jm = JobManager()

    @ui.page("/assign-tasks-to-jobs")
    def page() -> None:
        user_id = get_current_user()
        if user_id is None:
            ui.notify("You must be logged in", color="negative")
            ui.navigate.to("/login")
            return

        ui.button("Back to Jobs", icon="arrow_back", on_click=lambda: ui.navigate.to("/jobs")).classes("mb-4")
        ui.label("Assign tasks to jobs").classes("text-2xl font-bold")
        ui.label(
            "Select one or more jobs below, then click Assign on a task to add it to those jobs."
        ).classes("text-sm text-gray-600 mb-4")

        try:
            tasks = task_manager.get_all(user_id=user_id)
        except ValueError:
            tasks = []
        if isinstance(tasks, list):
            task_list = tasks
        else:
            task_list = tasks.to_dict(orient="records") if hasattr(tasks, "to_dict") else []

        all_jobs = jm.get_all_jobs()
        if not all_jobs:
            ui.label("No jobs yet. Create your first job, then you can assign tasks to it.").classes(
                "text-gray-500 mb-2"
            )
            ui.button("Create job", on_click=lambda: ui.navigate.to("/create-job"), color="primary")
            return

        if not task_list:
            ui.label("No task templates. Create tasks from the dashboard first.").classes("text-gray-500")
            return

        # Jobs section: checkboxes at top (which job(s) to assign to)
        ui.label("Assign to job(s)").classes("text-sm font-semibold")
        ui.label("Select the job(s) you want to assign tasks to. Then use Assign on each task below.").classes(
            "text-xs text-gray-500 mb-2"
        )
        job_checkboxes = {}
        with ui.row().classes("gap-3 flex-wrap mb-4"):
            for job in all_jobs:
                jid = job.get("job_id", "")
                jname = job.get("name", "Unnamed")
                job_checkboxes[jid] = ui.checkbox(jname, value=False).classes("text-sm")

        # Filter: exclude tasks that already have at least one job
        exclude_assigned_cb = ui.checkbox(
            "Exclude tasks that already have a job",
            value=False,
        ).classes("text-sm mb-2")
        search_in = ui.input(placeholder="Filter tasks by name...").classes("w-full mb-2").props("clearable dense")

        # Pending assignments: task_id -> set of job_ids to add. Applied on Save.
        pending_assignments: dict[str, set[str]] = {}

        container = ui.column().classes("w-full gap-2")

        save_row = ui.row().classes("w-full mt-4 sticky bottom-2 gap-2")

        def update_save_row() -> None:
            save_row.clear()
            with save_row:
                if pending_assignments:
                    count = sum(len(s) for s in pending_assignments.values())
                    ui.label(f"{len(pending_assignments)} task(s) queued, {count} assignment(s)").classes(
                        "self-center text-sm text-gray-600"
                    )
                    ui.button("Save changes", icon="save", on_click=finalize_assignments, color="primary")
                    ui.button("Discard", on_click=discard_pending)

        def do_assign(tid: str) -> None:
            sel = [jid for jid, cb in job_checkboxes.items() if cb.value]
            if not sel:
                ui.notify("Select at least one job above first", color="warning")
                return
            pending_assignments[tid] = pending_assignments.get(tid, set()) | set(sel)
            ui.notify("Queued; click Save changes at the bottom to apply", color="info")
            render_rows()
            update_save_row()

        def finalize_assignments() -> None:
            if not pending_assignments:
                return
            for tid, add_job_ids in pending_assignments.items():
                full = task_manager.get_task(tid, user_id=user_id) or {}
                current = set(full.get("job_ids") or [])
                task_manager.assign_to_jobs(tid, list(current | add_job_ids), user_id=user_id)
            pending_assignments.clear()
            ui.notify("All assignments saved", color="positive")
            render_rows()
            update_save_row()

        def discard_pending() -> None:
            pending_assignments.clear()
            ui.notify("Pending changes discarded", color="info")
            render_rows()
            update_save_row()

        def render_rows() -> None:
            container.clear()
            q = (search_in.value or "").strip().lower()
            exclude_assigned = exclude_assigned_cb.value
            with container:
                for t in task_list:
                    name = (t.get("name") or "").strip()
                    task_id = t.get("task_id")
                    if not task_id:
                        continue
                    if q and q not in name.lower():
                        continue
                    full = task_manager.get_task(task_id, user_id=user_id) or t
                    current_job_ids = set(full.get("job_ids") or [])
                    effective_job_ids = current_job_ids | pending_assignments.get(task_id, set())
                    if exclude_assigned and current_job_ids:
                        continue
                    job_names = [j.get("name", "?") for j in all_jobs if j.get("job_id") in effective_job_ids]
                    has_pending = task_id in pending_assignments
                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                            with ui.column().classes("flex-1 min-w-0"):
                                ui.label(escape_for_display(name)).classes("font-medium")
                                ui.label(f"Type: {t.get('task_type') or 'Work'}").classes("text-xs text-gray-500")
                                if job_names:
                                    ui.label("In: " + ", ".join(escape_for_display(n) for n in job_names)).classes(
                                        "text-xs text-green-600"
                                    )
                                else:
                                    ui.label("Not in any job").classes("text-xs text-gray-400")
                                if has_pending:
                                    ui.label("(pending save)").classes("text-xs text-amber-600")

                            ui.button(
                                "Assign",
                                on_click=lambda tid=task_id: do_assign(tid),
                            ).props("dense size=sm")

        def on_filter_change() -> None:
            render_rows()

        exclude_assigned_cb.on("update:model-value", on_filter_change)
        search_in.on("update:model-value", lambda: render_rows())
        render_rows()
        update_save_row()
