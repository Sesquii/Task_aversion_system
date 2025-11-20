from nicegui import ui
from datetime import datetime

def build_add_log_page(task_manager):

    try:
        ui.label("Add Task Log Entry").classes("text-2xl font-bold mb-4")
    except Exception as e:
        ui.notify(f"UI error: {e}", color='red')
        raise

    with ui.column().classes("w-full max-w-xl gap-4"):

        # -------------------------
        # Task selection
        # -------------------------
        ui.label("Task:")

        task_input = ui.select(
            options=task_manager.get_task_list() + ["<Create new task>"],
            value=None,
            label="Choose task",
        )

        new_task_field = ui.input(
            label="New task name",
            placeholder="Enter new task...",
            visible=False,
        )

        def on_task_change():
            if task_input.value == "<Create new task>":
                new_task_field.visible = True
            else:
                new_task_field.visible = False

        task_input.on_change(on_task_change)

        # -------------------------
        # Button-based metrics
        # -------------------------

        def choose_value(label_text, max_value):
            ui.label(label_text)

            holder = ui.label("Not selected")

            def set_value(v):
                holder.set_text(str(v))

            with ui.row():
                for n in range(max_value + 1):
                    ui.button(str(n), on_click=lambda v=n: set_value(v))

            return holder

        aversion_label = choose_value("Aversion (0-10)", 10)
        relief_pred_label = choose_value("Relief Prediction (0-10)", 10)
        relief_actual_label = choose_value("Relief Actual (0-10)", 10)
        completion_label = choose_value("Completion % (0-100)", 10)

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
            task_name = (
                new_task_field.value
                if task_input.value == "<Create new task>"
                else task_input.value
            )

            if not task_name:
                ui.notify("Task name is required", color="negative")
                return

            # ensure new tasks exist in tasks.csv
            task_manager.add_task_if_missing(task_name)

            entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "task": task_name,
                "aversion_level": int(aversion_label.text) if aversion_label.text.isdigit() else None,
                "relief_prediction": int(relief_pred_label.text) if relief_pred_label.text.isdigit() else None,
                "relief_actual": int(relief_actual_label.text) if relief_actual_label.text.isdigit() else None,
                "completion_percent": int(completion_label.text) * 10 if completion_label.text.isdigit() else None,
                "perceived_overextension": int(overextend_label.text) if overextend_label.text.isdigit() else None,
                "time_estimate_minutes": est_time.value,
                "time_actual_minutes": actual_time.value,
                "comment": comment.value,
                "blocker_type": blocker.value,
            }

            task_manager.save_log_entry(entry)
            task_manager.update_task_metadata(
                task_name,
                entry["aversion_level"],
                entry["relief_actual"] if entry["relief_actual"] else 0
            )

            ui.notify("Log saved!", color="positive")

        ui.button("Save Log Entry", on_click=save).classes("mt-4")
