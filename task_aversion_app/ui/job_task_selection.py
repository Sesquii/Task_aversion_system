# ui/job_task_selection.py
"""Job task selection page: list tasks for a job with Initialize and Add Task options."""
import json

from nicegui import ui
from fastapi import Request

from backend.auth import get_current_user
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.job_manager import JobManager
from backend.security_utils import ValidationError
from backend.security_utils import escape_for_display


def register_job_task_selection_page(task_manager: TaskManager) -> None:
    """Register the /job-tasks page."""

    im = InstanceManager()
    jm = JobManager()

    @ui.page("/job-tasks")
    def page(request: Request) -> None:
        user_id = get_current_user()
        if user_id is None:
            ui.notify("You must be logged in", color="negative")
            ui.navigate.to("/login")
            return

        job_id = request.query_params.get("job_id", "").strip()
        if not job_id:
            ui.notify("Missing job_id", color="negative")
            ui.navigate.to("/")
            return

        job = jm.get_job(job_id)
        if not job:
            ui.notify("Job not found", color="negative")
            ui.navigate.to("/")
            return

        job_name = job.get("name", "Unnamed")
        task_type = job.get("task_type", "Work")

        ui.button("Back to Dashboard", icon="arrow_back", on_click=lambda: ui.navigate.to("/")).classes("mb-4")
        ui.label(f"Job: {escape_for_display(job_name)}").classes("text-2xl font-bold")
        ui.label(f"Type: {escape_for_display(task_type)}").classes("text-sm text-gray-500 mb-4")

        tasks = jm.get_tasks_for_job(job_id, user_id=user_id)

        def do_init(task_id: str) -> None:
            task = task_manager.get_task(task_id, user_id=user_id)
            if not task:
                ui.notify("Task not found", color="negative")
                return
            default_estimate = task.get("default_estimate_minutes") or 0
            try:
                default_estimate = int(default_estimate)
            except (TypeError, ValueError):
                default_estimate = 0
            inst_id = im.create_instance(
                task["task_id"],
                task["name"],
                task_version=task.get("version") or 1,
                predicted={"time_estimate_minutes": default_estimate},
                user_id=user_id,
            )
            ui.navigate.to(f"/initialize-task?instance_id={inst_id}")

        def add_task_to_job() -> None:
            with ui.dialog() as dlg, ui.card().classes("w-full max-w-xl p-4"):
                ui.label("Create task template for this job").classes("text-lg font-semibold mb-2")
                name_in = ui.input(label="Task name").classes("w-full")
                desc_in = ui.textarea(label="Description (optional)").classes("w-full")
                est_in = ui.number(label="Default estimate minutes", value=0).classes("w-full")

                def save_new() -> None:
                    nonlocal tasks
                    try:
                        tid = task_manager.create_task(
                            name_in.value or "",
                            description=desc_in.value or "",
                            categories=json.dumps([]),
                            default_estimate_minutes=int(est_in.value or 0),
                            task_type=task_type,
                            user_id=user_id,
                            job_ids=[job_id],
                        )
                        ui.notify(f"Task created: {tid}", color="positive")
                        dlg.close()
                        tasks = jm.get_tasks_for_job(job_id, user_id=user_id)
                        render_tasks()
                    except ValidationError as e:
                        ui.notify(str(e), color="negative")
                    except Exception as e:
                        ui.notify(f"Failed to create task: {e}", color="negative")

                with ui.row().classes("gap-2 mt-3"):
                    ui.button("Create", on_click=save_new, color="primary")
                    ui.button("Cancel", on_click=dlg.close)
            dlg.open()

        with ui.row().classes("w-full gap-2 mb-4"):
            search_in = ui.input(
                placeholder="Search tasks in this job...",
                value="",
            ).classes("flex-1").props("clearable dense")
            ui.button("Add task to job", icon="add", on_click=add_task_to_job, color="primary")

        container = ui.column().classes("w-full gap-2")

        def render_tasks() -> None:
            container.clear()
            with container:
                q = (search_in.value or "").strip().lower()
                for t in tasks:
                    name = (t.get("name") or "").strip()
                    desc = (t.get("description") or "").strip()
                    tid = t.get("task_id")
                    if not tid:
                        continue
                    if q and q not in name.lower() and q not in desc.lower():
                        continue
                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("justify-between items-center w-full gap-2 flex-wrap"):
                            with ui.column().classes("flex-1 min-w-0"):
                                ui.label(escape_for_display(name)).classes("font-medium")
                                if desc:
                                    ui.label(escape_for_display(desc[:200] + ("..." if len(desc) > 200 else ""))).classes(
                                    "text-xs text-gray-500"
                                )
                            ui.button(
                                "Initialize",
                                icon="play_arrow",
                                on_click=lambda tid=tid: do_init(tid),
                            ).props("dense size=sm")

        search_in.on("update:model-value", lambda: render_tasks())
        render_tasks()

        if not tasks:
            with container:
                ui.label("No tasks in this job yet.").classes("text-gray-500")
                ui.button("Add task to job", on_click=add_task_to_job, color="primary").classes("mt-2")
