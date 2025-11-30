# ui/dashboard.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.emotion_manager import EmotionManager
from backend.analytics import Analytics

tm = TaskManager()
im = InstanceManager()
em = EmotionManager()
an = Analytics()


# ----------------------------------------------------------
# Helper Button Handlers
# ----------------------------------------------------------


def init_quick(task_ref):
    """Initialize a task template by name or id."""
    task = tm.get_task(task_ref)
    if not task:
        task = tm.find_by_name(task_ref)
    if not task:
        ui.notify("Task not found", color='negative')
        return

    default_estimate = task.get('default_estimate_minutes') or 0
    try:
        default_estimate = int(default_estimate)
    except (TypeError, ValueError):
        default_estimate = 0

    inst_id = im.create_instance(
        task['task_id'],
        task['name'],
        task_version=task.get('version') or 1,
        predicted={'time_estimate_minutes': default_estimate},
    )
    ui.navigate.to(f'/initialize-task?instance_id={inst_id}')


def start_instance(instance_id):
    im.start_instance(instance_id)
    ui.notify("Instance started", color='positive')


def go_complete(instance_id):
    ui.navigate.to(f'/complete_task?instance_id={instance_id}')


def go_cancel(instance_id):
    ui.navigate.to(f'/cancel_task?instance_id={instance_id}')


def show_details(instance_id):
    inst = InstanceManager.get_instance(instance_id)

    with ui.dialog() as dialog, ui.card():
        ui.label(f"Instance ID: {instance_id}")
        ui.markdown(f"```json\n{inst}\n```")
        ui.button("Close", on_click=dialog.close)

    dialog.open()
def refresh_templates():
    print("[Dashboard] refresh_templates() called")

    query = (search.value or "").lower().strip()
    print(f"[Dashboard] search query: {query}")

    df = tm.get_all()
    if df is None or df.empty:
        print("[Dashboard] no templates found")
        template_col.clear()
        with template_col:
            ui.markdown("_No templates available_")
        return

    rows = df.to_dict(orient='records')
    filtered = [r for r in rows if query in r['name'].lower()]
    print(f"[Dashboard] filtered: {len(filtered)} rows")

    template_col.clear()

    for t in filtered:
        with template_col:
            with ui.card().classes("mb-2 p-2"):
                ui.markdown(f"**{t['name']}** — v{t['version']}")
                with ui.row():
                    ui.button("Init", on_click=lambda tid=t['task_id']: init_quick(tid))
                    ui.button("Delete", on_click=lambda tid=t['task_id']: delete_template(tid))


def delete_instance(instance_id):
    im.delete_instance(instance_id)
    ui.notify("Deleted", color='negative')
    ui.navigate.reload()

def delete_template(task_id):
    print(f"[Dashboard] delete_template called: {task_id}")

    if tm.delete_by_id(task_id):
        ui.notify("Task deleted", color="positive")
    else:
        ui.notify("Delete failed", color="negative")

    refresh_templates()




# ----------------------------------------------------------
# MAIN DASHBOARD
# ----------------------------------------------------------

def build_dashboard(task_manager):

    ui.add_head_html("<style>.small * { font-size: 0.85rem !important; }</style>")

    ui.label("Task Aversion Dashboard").classes("text-2xl font-bold mb-4 small")

    # Summary section at the top
    build_summary_section()

    # Outer layout: 3 columns
    with ui.row().classes("w-full h-screen gap-4 small"):

        # ====================================================================
        # COLUMN 1 — Left Column
        # ====================================================================
        with ui.column().classes("w-1/4 h-full gap-3"):

            # Create Task Button (Pinned)
            with ui.row().classes("sticky top-0 bg-white z-50 py-2"):
                ui.button("➕ Create Task",
                          on_click=lambda: ui.navigate.to('/create_task'),
                          color='primary').classes("w-full")

            # Search bar
            global search
            search = ui.input(
                label="Search task templates",
                placeholder="Type to filter...",
            ).classes("w-full mb-2")

            search.on('input', lambda _: refresh_templates())   # live filtering!


            # Quick Tasks Section
            with ui.column().classes("w-full border rounded-lg p-2 overflow-y-auto flex-1"):
                ui.markdown("### Quick Tasks (Last 5)")

                recent = tm.get_recent(limit=5) if hasattr(tm, "get_recent") else []
                quick_col = ui.column()

                if not recent:
                    ui.label("No recent tasks").classes("text-xs text-gray-500")
                else:
                    for r in recent:
                        with ui.row().classes("justify-between items-center"):
                            ui.label(r['name']).classes("text-sm")
                            ui.button("Init", 
                                      on_click=lambda n=r['name']: init_quick(n)
                                      ).props("dense")

            # Templates Section
            with ui.column().classes("w-full border rounded-lg p-2 overflow-y-auto flex-1"):
                ui.markdown("### Task Templates")
                global template_col
                template_col = ui.column().classes('w-full h-80 overflow-auto border rounded-lg p-2')
                refresh_templates()

        # ====================================================================
        # COLUMN 2 — Middle Column (Active Tasks + Recently Completed)
        # ====================================================================
        with ui.column().classes("w-1/3 h-full gap-2"):

            # Active Tasks Section (takes up most of the space)
            with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto flex-1"):
                ui.label("Active Initialized Tasks").classes("text-lg font-bold")
                ui.separator()

                active = im.list_active_instances()

                if not active:
                    ui.label("No active tasks").classes("text-xs text-gray-500")
                else:
                    for inst in active:
                        with ui.card().classes("w-full p-2"):
                            ui.label(inst.get("task_name")).classes("text-md font-bold")
                            ui.label(f"Created: {inst.get('created_at')}").classes("text-xs")
                            ui.label(str(inst.get("predicted"))).classes("text-xs text-gray-600")

                            with ui.row().classes("justify-end gap-2"):
                                ui.button("Start",
                                          on_click=lambda i=inst['instance_id']: start_instance(i)
                                          ).props("dense")

                                ui.button("Complete",
                                          on_click=lambda i=inst['instance_id']: go_complete(i)
                                          ).props("dense")

                                ui.button("Cancel",
                                          color="warning",
                                          on_click=lambda i=inst['instance_id']: go_cancel(i)
                                          ).props("dense")

                                ui.button("Delete",
                                          color="negative",
                                          on_click=lambda i=inst['instance_id']: delete_instance(i)
                                          ).props("dense")

            # Recently Completed Section
            build_recently_completed_panel()

        # ====================================================================
        # COLUMN 3 — Right Column (Recommendations)
        # ====================================================================
        with ui.column().classes("w-1/3 h-full gap-4"):

            # Recommendations
            with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto flex-1"):
                ui.label("Recommendations").classes("font-bold text-lg")
                ui.markdown("_⚠️ Note: These recommendations are not fully calibrated._").classes("text-xs text-gray-500 mb-2")
                ui.separator()

                recs = an.recommendations() if hasattr(an, "recommendations") else []

                if not recs:
                    ui.label("No recommendations").classes("text-xs text-gray-500")
                else:
                    for r in recs:
                        with ui.card().classes("p-2 mb-2"):
                            task_label = r.get('task_name') or r.get('title') or "Recommendation"
                            ui.label(task_label).classes("font-bold text-sm")
                            ui.label(r.get('reason', '')).classes("text-xs text-gray-600")
                            ui.button("Start",
                                      on_click=lambda rid=r.get('task_id'): init_quick(rid)
                                      ).props("dense")


def build_summary_section():
    """Build the summary section with productivity time and productivity efficiency."""
    relief_summary = an.get_relief_summary()
    
    with ui.card().classes("w-full mb-4 p-4"):
        ui.label("Summary").classes("text-xl font-bold mb-3")
        
        with ui.row().classes("w-full gap-4 flex-wrap"):
            # Productivity Time
            with ui.card().classes("p-3 min-w-[180px]"):
                ui.label("Productivity Time").classes("text-xs text-gray-500")
                hours = relief_summary['productivity_time_minutes'] / 60.0
                if hours >= 1:
                    ui.label(f"{hours:.1f} hours").classes("text-lg font-bold")
                    ui.label(f"({relief_summary['productivity_time_minutes']:.0f} min)").classes("text-xs text-gray-400")
                else:
                    ui.label(f"{relief_summary['productivity_time_minutes']:.0f} min").classes("text-lg font-bold")
            
            # Efficiency Stats
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Productivity Efficiency").classes("text-xs text-gray-500")
                avg_eff = relief_summary.get('avg_efficiency', 0.0)
                high_eff = relief_summary.get('high_efficiency_count', 0)
                low_eff = relief_summary.get('low_efficiency_count', 0)
                ui.label(f"{avg_eff:.1f}").classes("text-lg font-bold")
                ui.label(f"High: {high_eff} | Low: {low_eff}").classes("text-xs text-gray-400")
                ui.label("(experimental calculation)").classes("text-xs text-gray-400 italic")


def build_recently_completed_panel():
    """Build the recently completed tasks panel with optional date grouping."""
    from collections import defaultdict
    
    with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto flex-1"):
        ui.label("Recently Completed").classes("font-bold text-lg")
        ui.separator()
        
        # Toggle for date grouping
        group_by_date = ui.checkbox("Group by date", value=False).classes("mb-2")
        
        # Container for completed tasks
        completed_container = ui.column().classes("w-full")
        
        def refresh_completed():
            completed_container.clear()
            
            completed = im.list_recent_completed(limit=20) \
                if hasattr(im, "list_recent_completed") else []
            
            if not completed:
                with completed_container:
                    ui.label("No completed tasks").classes("text-xs text-gray-500")
                return
            
            if group_by_date.value:
                # Group by date
                grouped = defaultdict(list)
                for c in completed:
                    # Extract date from completed_at (format: "YYYY-MM-DD HH:MM")
                    completed_at = str(c.get('completed_at', ''))
                    if completed_at:
                        date_part = completed_at.split()[0] if ' ' in completed_at else completed_at[:10]
                        grouped[date_part].append(c)
                
                # Sort dates descending
                sorted_dates = sorted(grouped.keys(), reverse=True)
                
                with completed_container:
                    for date in sorted_dates:
                        with ui.card().classes("w-full p-2 mb-2"):
                            ui.label(date).classes("font-bold text-sm text-gray-600 mb-1")
                            for c in grouped[date]:
                                with ui.row().classes("justify-between items-center mb-1"):
                                    ui.label(c['task_name']).classes("text-sm")
                                    # Show time if available
                                    completed_at = str(c.get('completed_at', ''))
                                    time_part = completed_at.split()[1] if ' ' in completed_at else ''
                                    if time_part:
                                        ui.label(time_part).classes("text-xs text-gray-400")
            else:
                # No grouping - show flat list
                with completed_container:
                    for c in completed:
                        with ui.row().classes("justify-between items-center"):
                            ui.label(c['task_name']).classes("text-sm")
                            ui.label(str(c['completed_at'])).classes("text-xs text-gray-400")
        
        # Update when toggle changes
        group_by_date.on('update:model-value', lambda _: refresh_completed())
        
        # Initial render
        refresh_completed()
