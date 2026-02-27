# ui/jobs_page.py
"""Jobs page: create jobs and manage job-based organization when user is ready."""

from nicegui import ui

from backend.auth import get_current_user
from backend.job_manager import JobManager
from backend.security_utils import escape_for_display


def register_jobs_page() -> None:
    """Register the /jobs page."""

    @ui.page("/jobs")
    def page() -> None:
        user_id = get_current_user()
        if user_id is None:
            ui.notify("You must be logged in", color="negative")
            ui.navigate.to("/login")
            return

        jm = JobManager()

        ui.button("Back to Dashboard", icon="arrow_back", on_click=lambda: ui.navigate.to("/")).classes("mb-4")
        ui.label("Jobs").classes("text-2xl font-bold")
        ui.label(
            "Jobs are an optional organization layer. Create jobs and then assign existing templates to them when you're ready."
        ).classes("text-sm text-gray-600 mb-4")

        with ui.card().classes("w-full max-w-xl p-4 gap-3"):
            ui.label("Create job").classes("text-lg font-semibold")
            name_in = ui.input(label="Job name", placeholder="e.g. Development, Fitness").classes("w-full")
            type_in = ui.select(["Work", "Self care", "Play"], value="Work", label="Type").classes("w-full")
            desc_in = ui.input(label="Description (optional)").classes("w-full")

            def create_job() -> None:
                name = (name_in.value or "").strip()
                if not name:
                    ui.notify("Job name required", color="negative")
                    return
                try:
                    jm.create_job(name=name, task_type=type_in.value or "Work", description=(desc_in.value or "").strip())
                    ui.notify("Job created", color="positive")
                    name_in.value = ""
                    desc_in.value = ""
                    refresh_jobs()
                except Exception as e:
                    ui.notify(f"Failed to create job: {e}", color="negative")

            ui.button("Create job", on_click=create_job, color="primary")

        with ui.card().classes("w-full max-w-xl p-4 gap-3 mt-4"):
            ui.label("Assign templates").classes("text-lg font-semibold")
            ui.label("Assign your existing task templates to jobs.").classes("text-sm text-gray-600")
            ui.button("Assign tasks to jobs", on_click=lambda: ui.navigate.to("/assign-tasks-to-jobs")).classes("w-full")

        ui.label("Your jobs").classes("text-lg font-semibold mt-6")
        jobs_container = ui.column().classes("w-full gap-2")

        def refresh_jobs() -> None:
            jobs_container.clear()
            with jobs_container:
                jobs = jm.get_all_jobs()
                if not jobs:
                    ui.label("No jobs yet.").classes("text-gray-500")
                    return
                for job in jobs:
                    jid = job.get("job_id", "")
                    with ui.card().classes("w-full p-3"):
                        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                            with ui.column().classes("flex-1 min-w-0"):
                                ui.label(escape_for_display(job.get("name", "Unnamed"))).classes("font-medium")
                                ui.label(escape_for_display(job.get("task_type", "Work"))).classes("text-xs text-gray-500")
                            ui.button(
                                "Open",
                                on_click=lambda jid=jid: ui.navigate.to(f"/job-tasks?job_id={jid}"),
                            ).props("dense size=sm")

        refresh_jobs()

