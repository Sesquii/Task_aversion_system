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
dash_filters = an.default_filters()


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
        # COLUMN 2 — Middle Column (Active Tasks)
        # ====================================================================
        with ui.column().classes("w-1/3 h-full border rounded-lg p-3 overflow-y-auto gap-2"):

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

            build_compact_analytics_panel()
            build_recommendation_strip()
        # ====================================================================
        # COLUMN 3 — Right Column (Completed + Recommendations)
        # ====================================================================
        with ui.column().classes("w-1/3 h-full gap-4"):

            # Recent completions
            with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto flex-1"):
                ui.label("Recently Completed").classes("font-bold text-lg")
                ui.separator()

                completed = im.list_recent_completed(limit=20) \
                    if hasattr(im, "list_recent_completed") else []

                if not completed:
                    ui.label("No completed tasks").classes("text-xs text-gray-500")
                else:
                    for c in completed:
                        with ui.row().classes("justify-between items-center"):
                            ui.label(c['task_name']).classes("text-sm")
                            ui.label(str(c['completed_at'])).classes("text-xs text-gray-400")

            # Recommendations
            with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto flex-1"):
                ui.label("Recommendations").classes("font-bold text-lg")
                ui.separator()

                recs = an.recommendations() if hasattr(an, "recommendations") else []

                if not recs:
                    ui.label("No recommendations").classes("text-xs text-gray-500")
                else:
                    for r in recs:
                        with ui.card().classes("p-2 mb-2"):
                            ui.label(r['name']).classes("font-bold text-sm")
                            ui.label(r.get('reason', '')).classes("text-xs text-gray-600")
                            ui.button("Start",
                                      on_click=lambda rid=r['task_id']: init_quick(rid)
                                      ).props("dense")


def build_compact_analytics_panel():
    metrics = an.get_dashboard_metrics()

    def metric_card(title, value, subtitle=''):
        with summary_row:
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label(title).classes("text-xs text-gray-500")
                ui.label(value).classes("text-lg font-bold")
                if subtitle:
                    ui.label(subtitle).classes("text-xs text-gray-400")

    with ui.expansion("Analytics pulse", icon="bar_chart", value=False).classes("w-full"):
        summary_row = ui.row().classes("gap-2 flex-wrap")
        counts = metrics.get('counts', {})
        quality = metrics.get('quality', {})
        time_stats = metrics.get('time', {})

        metric_card("Active", counts.get('active', 0))
        metric_card("Done (7d)", counts.get('completed_7d', 0))
        metric_card("Avg Relief", quality.get('avg_relief', 0), "/10")
        metric_card("Cog Load", quality.get('avg_cognitive_load', 0), "/10")
        metric_card("Median Duration", f"{time_stats.get('median_duration', 0)} min")
        metric_card("Avg Delay", f"{time_stats.get('avg_delay', 0)} min")

        ui.button(
            "Open Analytics Studio",
            icon="dashboard",
            on_click=lambda: ui.navigate.to('/analytics'),
        ).classes("mt-2")


def build_recommendation_strip():
    ui.separator()
    ui.label("Manual Recommendations").classes("font-bold text-md")

    filter_row = ui.row().classes("gap-2 flex-wrap")

    max_duration = ui.number(
        label="Max duration (min)",
        value=dash_filters.get('max_duration'),
    ).classes("w-32")
    min_relief = ui.number(
        label="Min relief",
        value=dash_filters.get('min_relief'),
    ).classes("w-28")
    max_cog = ui.number(
        label="Max cognitive load",
        value=dash_filters.get('max_cognitive_load'),
    ).classes("w-40")
    focus_metric = ui.select(
        label="Focus",
        options=[
            {'label': 'Relief', 'value': 'relief'},
            {'label': 'Shortest', 'value': 'duration'},
            {'label': 'Low Cognitive', 'value': 'cognitive'},
        ],
        value=dash_filters.get('focus_metric'),
    ).classes("w-44")

    rec_strip = ui.row().classes("gap-3 flex-wrap mt-2")

    def _update_and_refresh(key, raw_value):
        value = raw_value if raw_value not in (None, '', 'None') else None
        if key in ('max_duration', 'min_relief', 'max_cognitive_load') and value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = None
        dash_filters[key] = value
        refresh_recommendations(rec_strip)

    max_duration.on('change', lambda e: _update_and_refresh('max_duration', e.value))
    min_relief.on('change', lambda e: _update_and_refresh('min_relief', e.value))
    max_cog.on('change', lambda e: _update_and_refresh('max_cognitive_load', e.value))
    focus_metric.on('change', lambda e: _update_and_refresh('focus_metric', e.value))

    refresh_recommendations(rec_strip)


def refresh_recommendations(target_row):
    target_row.clear()
    recs = an.recommendations(dash_filters)
    if not recs:
        with target_row:
            ui.label("No candidates under current filters").classes("text-xs text-gray-500")
        return

    for rec in recs:
        with target_row:
            with ui.card().classes("p-2 min-w-[180px]"):
                ui.label(rec['title']).classes("text-xs uppercase text-gray-500")
                ui.label(rec['task_name']).classes("text-sm font-bold")
                ui.label(rec['reason']).classes("text-xs text-gray-600")
                ui.label(f"Duration: {rec.get('duration') or '—'}m").classes("text-xs")
                ui.label(f"Relief {rec.get('relief')} | Cog {rec.get('cognitive_load')}").classes("text-xs")
                ui.button(
                    "Initialize",
                    on_click=lambda rid=rec['task_id']: init_quick(rid),
                ).props("dense")
