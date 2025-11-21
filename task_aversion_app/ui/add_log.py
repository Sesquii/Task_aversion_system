from nicegui import ui
from datetime import datetime

def build_add_log_page(task_manager):

    ui.label("Add Task Log Entry").classes("text-2xl font-bold mb-4")

    existing_tasks = task_manager.get_all_tasks()

    with ui.column().classes("w-full max-w-xl gap-4"):

        # -------------------------
        # Task selection
        # -------------------------
        ui.label("Task:")

        NEW_TASK_SENTINEL = "➕ New Task"

        task_input = ui.select(
            label="Select task",
            options=existing_tasks + [NEW_TASK_SENTINEL],
        )

        # Hidden text field, revealed only when adding a new task
        new_task_field = ui.input(
            label="New task name",
            placeholder="Type the new task...",
        )
        new_task_field.set_visibility(False)

        # Show/hide the text box based on dropdown selection
        def on_task_change(e):
            new_task_field.set_visibility(e.value == NEW_TASK_SENTINEL)

        task_input.on('update:model-value', on_task_change)

        # -------------------------
        # Button-based metrics
        # -------------------------
        def choose_value(label_text, max_value):
            ui.label(label_text)
            holder = ui.label("")

            def set_value(v):
                holder.set_text(str(v))

            with ui.row():
                for n in range(max_value + 1):
                    ui.button(str(n), on_click=lambda v=n: set_value(v))

            return holder

        aversion_label = choose_value("Aversion (0-10)", 10)
        relief_pred_label = choose_value("Relief Prediction (0-10)", 10)
        relief_actual_label = choose_value("Relief Actual (0-10)", 10)
        completion_label = choose_value("Completion % (0–100, increments of 10)", 10)
        overextend_label = choose_value("Perceived Overextension (0-10)", 10)

        # -------------------------
        # Additional numeric fields
        # -------------------------
        est_time = ui.number(label="Estimated minutes", value=0)
        actual_time = ui.number(label="Actual minutes", value=0)

        # -------------------------
        # Blocker + comment
        # -------------------------
        blocker = ui.select(
            ["None", "Fear", "Overwhelm", "Confusion", "Time", "Energy", "Other"],
            value="None",
            label="Blocker Type"
        )

        comment = ui.textarea(label="Comment (optional)", placeholder="Notes...")

        # -------------------------
        # Save Button
        # -------------------------
        def save():

            # Determine correct task name
            if task_input.value == NEW_TASK_SENTINEL:
                task_name = new_task_field.value
            else:
                task_name = task_input.value

            # Validate
            if not task_name or task_name.strip() == "":
                ui.notify("Task name is required.", color="negative")
                return

            # Ensure task exists
            task_manager.add_task_if_missing(task_name)

            # Helper to safely cast numbers
            def safe_int(label):
                t = label.text.strip()
                return int(t) if t.isdigit() else None

            entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "task": task_name,
                "aversion_level": safe_int(aversion_label),
                "relief_prediction": safe_int(relief_pred_label),
                "relief_actual": safe_int(relief_actual_label),
                "completion_percent": safe_int(completion_label) * 10 if safe_int(completion_label) is not None else None,
                "perceived_overextension": safe_int(overextend_label),
                "time_estimate_minutes": est_time.value,
                "time_actual_minutes": actual_time.value,
                "comment": comment.value,
                "blocker_type": blocker.value,
            }

            task_manager.save_log_entry(entry)

            task_manager.update_task_metadata(
                task_name,
                entry["aversion_level"] or 0,
                entry["relief_actual"] or 0
            )

            ui.notify("Log saved!", color="positive")

        ui.button("Save Log Entry", on_click=save).classes("mt-4")
