# ui/create_job.py
"""Create and manage jobs. Users create jobs first, then create task templates and assign them to jobs."""
from nicegui import ui

from backend.auth import get_current_user
from backend.job_manager import JobManager
from backend.security_utils import escape_for_display


def register_create_job_page() -> None:
    """Register the /create-job page."""

    @ui.page("/create-job")
    def page() -> None:
        user_id = get_current_user()
        if user_id is None:
            ui.notify("You must be logged in", color="negative")
            ui.navigate.to("/login")
            return

        jm = JobManager()

        ui.button("Back", icon="arrow_back", on_click=lambda: ui.navigate.to("/jobs")).classes("mb-4")
        ui.label("Create job").classes("text-2xl font-bold")
        ui.label(
            "Jobs group your tasks (e.g. Development, Fitness). Create a job, then create task templates and assign them to it."
        ).classes("text-sm text-gray-600 mb-4")

        with ui.card().classes("w-full max-w-xl p-4 gap-3"):
            ui.label("New job").classes("text-lg font-semibold")
            name_input = ui.input(label="Job name", placeholder="e.g. Development, Fitness").classes("w-full")
            task_type_select = ui.select(
                ["Work", "Self care", "Play"],
                label="Type",
                value="Work",
            ).classes("w-full")
            desc_input = ui.input(
                label="Description (optional)",
                placeholder="e.g. Coding and side projects",
            ).classes("w-full")

            def save_job() -> None:
                name = (name_input.value or "").strip()
                if not name:
                    ui.notify("Job name required", color="negative")
                    return
                try:
                    jm.create_job(
                        name=name,
                        task_type=task_type_select.value or "Work",
                        description=(desc_input.value or "").strip(),
                    )
                    ui.notify("Job created", color="positive")
                    name_input.value = ""
                    desc_input.value = ""
                    refresh_list()
                except Exception as e:
                    ui.notify(f"Failed to create job: {e}", color="negative")

            ui.button("Create job", on_click=save_job, color="primary")

        ui.label("Your jobs").classes("text-lg font-semibold mt-6")
        jobs_container = ui.column().classes("w-full gap-2")

        def refresh_list() -> None:
            jobs_container.clear()
            with jobs_container:
                jobs = jm.get_all_jobs()
                if not jobs:
                    ui.label("No jobs yet. Create one above.").classes("text-gray-500")
                    return
                for job in jobs:
                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.column().classes("flex-1 min-w-0"):
                                ui.label(escape_for_display(job.get("name", "Unnamed"))).classes("font-medium")
                                ui.label(job.get("task_type", "Work")).classes("text-xs text-gray-500")
                            ui.button(
                                "Open",
                                on_click=lambda jid=job.get("job_id"): ui.navigate.to(f"/job-tasks?job_id={jid}"),
                            ).props("dense size=sm")

        refresh_list()
