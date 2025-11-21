from nicegui import ui
from datetime import datetime

def build_add_log_page(task_manager):

    print("DEBUG: build_add_log_page() called")

    existing_tasks = task_manager.get_all_tasks()
    print("DEBUG: existing_tasks =", existing_tasks)

    ui.label("Add Task Log Entry").classes("text-2xl font-bold mb-4")

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
        print("DEBUG: task_input created. options =", task_input.options if hasattr(task_input, 'options') else 'no options attr')
        try:
            print("DEBUG: task_input initial value =", task_input.value)
        except Exception as e:
            print("DEBUG: task_input initial value read failed:", e)

        # Hidden text field, revealed only when adding a new task
        new_task_field = ui.input(
            label="New task name",
            placeholder="Type the new task...",
        )
        new_task_field.set_visibility(False)
        try:
            vis = new_task_field.visible
        except Exception:
            try:
                vis = new_task_field.get_visibility()
            except Exception:
                vis = 'unknown'
        print("DEBUG: new_task_field created. visible =", vis)

        # Show/hide the text box based on dropdown selection
        def on_task_change(e):
            print("DEBUG: on_task_change fired. event:", e)
            args = getattr(e, 'args', None)
            print("DEBUG: on_task_change e.args =", args)

            val = None
            if isinstance(args, dict) and 'label' in args:
                val = args['label']  # <-- USE THE LABEL
            elif isinstance(args, dict) and 'value' in args:
                val = args['value']
            else:
                try:
                    val = e.value
                except Exception:
                    val = None

            print("DEBUG: on_task_change resolved value =", val)

            new_task_field.set_visibility(val == NEW_TASK_SENTINEL)
            try:
                print("DEBUG: new_task_field.visible after toggle =", new_task_field.visible)
            except Exception:
                try:
                    print("DEBUG: new_task_field.get_visibility() after toggle =", new_task_field.get_visibility())
                except Exception as ex:
                    print("DEBUG: cannot read visibility after toggle:", ex)


        # Attach event handler
        task_input.on('update:model-value', on_task_change)
        print("DEBUG: handler attached to task_input")

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
            print("DEBUG: Save pressed")
            print("DEBUG: task_input.value =", getattr(task_input, 'value', None))
            print("DEBUG: new_task_field.value =", getattr(new_task_field, 'value', None))
            print("DEBUG: aversion_label.text =", getattr(aversion_label, 'text', None))
            print("DEBUG: relief_pred_label.text =", getattr(relief_pred_label, 'text', None))
            print("DEBUG: completion_label.text =", getattr(completion_label, 'text', None))
            print("DEBUG: overextend_label.text =", getattr(overextend_label, 'text', None))
            print("DEBUG: est_time.value =", est_time.value, "actual_time.value =", actual_time.value)
            print("DEBUG: blocker.value =", blocker.value, "comment.value =", comment.value)

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
            print("DEBUG: entry passed to task_manager.save_log_entry:", entry)
            try:
                import os
                size = os.path.getsize(task_manager.logs_path)
                print("DEBUG: logs file size after save:", size)
            except Exception as e:
                print("DEBUG: failed to stat logs file:", e)

            task_manager.update_task_metadata(
                task_name,
                entry["aversion_level"] or 0,
                entry["relief_actual"] or 0
            )

            ui.notify("Log saved!", color="positive")

        ui.button("Save Log Entry", on_click=save).classes("mt-4")
