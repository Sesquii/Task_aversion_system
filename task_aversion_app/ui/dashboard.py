# ui/dashboard.py
from nicegui import ui
import json
import html
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.emotion_manager import EmotionManager
from backend.analytics import Analytics

tm = TaskManager()
im = InstanceManager()
em = EmotionManager()
an = Analytics()
dash_filters = an.default_filters()
print(f"[Dashboard] Initial dash_filters: {dash_filters}")


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
# Tooltip Formatting Helper
# ----------------------------------------------------------

def format_colored_tooltip(predicted_data, task_id):
    """Format predicted data as HTML with color-coded values based on thresholds and averages."""
    # Get averages for this task
    averages = im.get_previous_task_averages(task_id) if task_id else {}
    
    # Calculate average time estimate from previous instances
    avg_time_estimate = None
    if task_id:
        im._reload()
        initialized = im.df[
            (im.df['task_id'] == task_id) & 
            (im.df['initialized_at'].astype(str).str.strip() != '')
        ].copy()
        if not initialized.empty:
            time_values = []
            for idx in initialized.index:
                predicted_str = str(initialized.at[idx, 'predicted'] or '{}').strip()
                if predicted_str and predicted_str != '{}':
                    try:
                        pred_dict = json.loads(predicted_str)
                        time_val = pred_dict.get('time_estimate_minutes') or pred_dict.get('estimate')
                        if time_val is not None:
                            try:
                                time_values.append(float(time_val))
                            except (ValueError, TypeError):
                                pass
                    except (json.JSONDecodeError, Exception):
                        pass
            if time_values:
                avg_time_estimate = sum(time_values) / len(time_values)
    
    def get_load_color(value):
        """Get color for load values (0-100): green 0-30, yellow 30-70, red 70-100"""
        if value <= 30:
            return "#22c55e"  # green
        elif value <= 70:
            return "#eab308"  # yellow
        else:
            return "#ef4444"  # red
    
    def get_time_color(value, avg):
        """Get color for time estimate: green if >5min less, yellow if ±5min, blue if >5min more"""
        if avg is None:
            return "#6b7280"  # gray if no average
        diff = value - avg
        if diff < -5:
            return "#22c55e"  # green
        elif abs(diff) <= 5:
            return "#eab308"  # yellow
        else:
            return "#3b82f6"  # blue
    
    def get_motivation_color(value):
        """Get color for motivation: yellow below 50, green above 50"""
        if value < 50:
            return "#eab308"  # yellow
        else:
            return "#22c55e"  # green
    
    def get_value_with_deviation_color(value, avg, higher_is_worse=True):
        """Get color based on percentage deviation from average.
        For load values: higher is worse, so >10% above average = red, >10% below = green
        For relief: higher is better, so >10% above average = green, >10% below = red"""
        if avg is None or avg == 0:
            return get_load_color(value) if higher_is_worse else get_motivation_color(value)
        
        deviation_pct = ((value - avg) / avg) * 100
        
        if higher_is_worse:
            # For load values: higher is worse
            if deviation_pct > 10:
                return "#ef4444"  # red - significantly harder
            elif deviation_pct < -10:
                return "#22c55e"  # green - significantly easier
            else:
                return "#eab308"  # yellow - within 10%
        else:
            # For relief: higher is better
            if deviation_pct > 10:
                return "#22c55e"  # green - significantly better
            elif deviation_pct < -10:
                return "#ef4444"  # red - significantly worse
            else:
                return "#eab308"  # yellow - within 10%
    
    lines = []
    lines.append('<div style="font-family: monospace; font-size: 0.75rem; line-height: 1.6;">')
    
    # Time Estimate
    time_est = predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0
    try:
        time_est = float(time_est)
    except (ValueError, TypeError):
        time_est = 0
    time_color = get_time_color(time_est, avg_time_estimate)
    avg_text = f" (avg: {avg_time_estimate:.1f} min)" if avg_time_estimate else ""
    lines.append(f'<div><strong>Time Estimate:</strong> <span style="color: {time_color}; font-weight: bold;">{time_est:.0f} min</span>{avg_text}</div>')
    
    # Expected Relief
    relief = predicted_data.get('expected_relief')
    if relief is not None:
        try:
            relief = float(relief)
            if relief <= 10:
                relief = relief * 10  # Scale from 0-10 to 0-100
            avg_relief = averages.get('expected_relief')
            relief_color = get_value_with_deviation_color(relief, avg_relief, higher_is_worse=False)
            avg_text = f" (avg: {avg_relief:.1f})" if avg_relief else ""
            lines.append(f'<div><strong>Expected Relief:</strong> <span style="color: {relief_color}; font-weight: bold;">{relief:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Cognitive Load
    cog_load = predicted_data.get('expected_cognitive_load')
    if cog_load is not None:
        try:
            cog_load = float(cog_load)
            if cog_load <= 10:
                cog_load = cog_load * 10  # Scale from 0-10 to 0-100
            avg_cog = averages.get('expected_cognitive_load')
            cog_color = get_value_with_deviation_color(cog_load, avg_cog, higher_is_worse=True)
            avg_text = f" (avg: {avg_cog:.1f})" if avg_cog else ""
            lines.append(f'<div><strong>Cognitive Load:</strong> <span style="color: {cog_color}; font-weight: bold;">{cog_load:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Physical Load
    phys_load = predicted_data.get('expected_physical_load')
    if phys_load is not None:
        try:
            phys_load = float(phys_load)
            if phys_load <= 10:
                phys_load = phys_load * 10  # Scale from 0-10 to 0-100
            avg_phys = averages.get('expected_physical_load')
            phys_color = get_value_with_deviation_color(phys_load, avg_phys, higher_is_worse=True)
            avg_text = f" (avg: {avg_phys:.1f})" if avg_phys else ""
            lines.append(f'<div><strong>Physical Load:</strong> <span style="color: {phys_color}; font-weight: bold;">{phys_load:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Emotional Load
    emo_load = predicted_data.get('expected_emotional_load')
    if emo_load is not None:
        try:
            emo_load = float(emo_load)
            if emo_load <= 10:
                emo_load = emo_load * 10  # Scale from 0-10 to 0-100
            avg_emo = averages.get('expected_emotional_load')
            emo_color = get_value_with_deviation_color(emo_load, avg_emo, higher_is_worse=True)
            avg_text = f" (avg: {avg_emo:.1f})" if avg_emo else ""
            lines.append(f'<div><strong>Emotional Load:</strong> <span style="color: {emo_color}; font-weight: bold;">{emo_load:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Motivation
    motivation = predicted_data.get('motivation')
    if motivation is not None:
        try:
            motivation = float(motivation)
            if motivation <= 10:
                motivation = motivation * 10  # Scale from 0-10 to 0-100
            avg_mot = averages.get('motivation')
            mot_color = get_motivation_color(motivation)
            if avg_mot:
                # Also consider deviation from average
                deviation_pct = ((motivation - avg_mot) / avg_mot) * 100 if avg_mot > 0 else 0
                if abs(deviation_pct) > 10:
                    mot_color = get_value_with_deviation_color(motivation, avg_mot, higher_is_worse=False)
            avg_text = f" (avg: {avg_mot:.1f})" if avg_mot else ""
            lines.append(f'<div><strong>Motivation:</strong> <span style="color: {mot_color}; font-weight: bold;">{motivation:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Other fields
    other_fields = ['emotions', 'physical_context', 'description']
    for field in other_fields:
        value = predicted_data.get(field)
        if value:
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value)
            lines.append(f'<div><strong>{field.replace("_", " ").title()}:</strong> {html.escape(str(value))}</div>')
    
    lines.append('</div>')
    return ''.join(lines)


# ----------------------------------------------------------
# MAIN DASHBOARD
# ----------------------------------------------------------

def build_dashboard(task_manager):

    ui.add_head_html("""
    <style>
        .small * { font-size: 0.85rem !important; }
        
        .task-tooltip {
            position: absolute;
            background: #1f2937;
            color: white;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 0.75rem;
            z-index: 1000;
            max-width: 350px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }
        
        .task-tooltip div {
            margin: 4px 0;
        }
        
        .task-tooltip strong {
            color: #e5e7eb;
        }
        
        .task-tooltip.visible {
            opacity: 1;
        }
        
        .task-card-hover {
            position: relative;
        }
    </style>
    <script>
        function initTaskTooltips() {
            document.querySelectorAll('.task-card-hover').forEach(function(card) {
                const instanceId = card.getAttribute('data-instance-id');
                if (!instanceId) return;
                
                const tooltip = document.getElementById('tooltip-' + instanceId);
                if (!tooltip) return;
                
                let hoverTimeout;
                
                card.addEventListener('mouseenter', function() {
                    hoverTimeout = setTimeout(function() {
                        tooltip.classList.add('visible');
                        positionTooltip(card, tooltip);
                    }, 1500);
                });
                
                card.addEventListener('mouseleave', function() {
                    clearTimeout(hoverTimeout);
                    tooltip.classList.remove('visible');
                });
                
                card.addEventListener('mousemove', function(e) {
                    if (tooltip.classList.contains('visible')) {
                        positionTooltip(card, tooltip, e);
                    }
                });
            });
        }
        
        function positionTooltip(card, tooltip, event) {
            const rect = card.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            
            let left = rect.left + rect.width / 2 - tooltipRect.width / 2;
            let top = rect.bottom + 10;
            
            if (event) {
                left = event.clientX - tooltipRect.width / 2;
                top = event.clientY - tooltipRect.height - 10;
            }
            
            // Keep tooltip within viewport
            if (left < 10) left = 10;
            if (left + tooltipRect.width > window.innerWidth - 10) {
                left = window.innerWidth - tooltipRect.width - 10;
            }
            if (top < 10) {
                top = rect.top - tooltipRect.height - 10;
            }
            
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        }
        
        // Initialize on page load and after DOM updates
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initTaskTooltips);
        } else {
            initTaskTooltips();
        }
        
        // Re-initialize after a short delay to catch dynamically added elements
        setTimeout(initTaskTooltips, 100);
    </script>
    """)

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
                    for idx, inst in enumerate(active):
                        # Parse predicted data to extract time estimate
                        predicted_str = inst.get("predicted") or "{}"
                        try:
                            predicted_data = json.loads(predicted_str) if isinstance(predicted_str, str) else predicted_str
                        except (json.JSONDecodeError, TypeError):
                            predicted_data = {}
                        
                        time_estimate = predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0
                        try:
                            time_estimate = int(time_estimate)
                        except (TypeError, ValueError):
                            time_estimate = 0
                        
                        # Format predicted data for tooltip with color coding
                        task_id = inst.get('task_id')
                        formatted_tooltip = format_colored_tooltip(predicted_data, task_id)
                        
                        tooltip_id = f"tooltip-{inst['instance_id']}"
                        instance_id = inst['instance_id']
                        
                        with ui.card().classes("w-full p-2 task-card-hover").props(f'data-instance-id="{instance_id}"').style("position: relative;"):
                            # Task name and time estimate
                            with ui.row().classes("justify-between items-center w-full"):
                                ui.label(inst.get("task_name")).classes("text-md font-bold")
                                ui.label(f"{time_estimate} min").classes("text-sm text-gray-600")
                            
                            # Buttons row
                            with ui.row().classes("justify-end gap-2 mt-2"):
                                ui.button("Complete",
                                          on_click=lambda i=inst['instance_id']: go_complete(i)
                                          ).props("dense")

                                ui.button("Cancel",
                                          color="warning",
                                          on_click=lambda i=inst['instance_id']: go_cancel(i)
                                          ).props("dense")
                            
                            # Add tooltip element to body with formatted HTML
                            tooltip_html = f'<div id="{tooltip_id}" class="task-tooltip">{formatted_tooltip}</div>'
                            ui.add_body_html(tooltip_html)
                    
                    # Initialize tooltips after all cards are created
                    ui.run_javascript('setTimeout(initTaskTooltips, 200);')

            # Recently Completed Section (bottom quarter)
            build_recently_completed_panel()

        # ====================================================================
        # COLUMN 3 — Right Column (Analytics + Recommendations)
        # ====================================================================
        with ui.column().classes("w-1/3 h-full gap-4"):

            # Analytics Panel
            build_compact_analytics_panel()

            # Recommendations (merged with focus options)
            build_recommendations_section()


def build_summary_section():
    """Build the summary section with productivity time and relief points."""
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
            
            # Default Relief Points
            with ui.card().classes("p-3 min-w-[180px]"):
                ui.label("Default Relief Points").classes("text-xs text-gray-500")
                points = relief_summary['default_relief_points']
                color_class = "text-green-600" if points >= 0 else "text-red-600"
                ui.label(f"{points:+.2f}").classes(f"text-lg font-bold {color_class}")
                ui.label("(actual - expected)").classes("text-xs text-gray-400")
            
            # Net Relief Points
            with ui.card().classes("p-3 min-w-[180px]"):
                ui.label("Net Relief Points").classes("text-xs text-gray-500")
                net_points = relief_summary['net_relief_points']
                ui.label(f"{net_points:.2f}").classes("text-lg font-bold text-green-600")
                ui.label("(calibrated, ≥0)").classes("text-xs text-gray-400")
            
            # Positive Relief Stats
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Positive Relief").classes("text-xs text-gray-500")
                pos_count = relief_summary['positive_relief_count']
                pos_avg = relief_summary['positive_relief_avg']
                ui.label(f"{pos_count} tasks").classes("text-sm font-bold")
                ui.label(f"Avg: +{pos_avg:.2f}").classes("text-xs text-green-600")
                ui.label(f"Total: +{relief_summary['positive_relief_total']:.2f}").classes("text-xs text-gray-400")
            
            # Negative Relief Stats
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Negative Relief").classes("text-xs text-gray-500")
                neg_count = relief_summary['negative_relief_count']
                neg_avg = relief_summary['negative_relief_avg']
                ui.label(f"{neg_count} tasks").classes("text-sm font-bold")
                if neg_count > 0:
                    ui.label(f"Avg: -{neg_avg:.2f}").classes("text-xs text-red-600")
                    ui.label(f"Total: -{relief_summary['negative_relief_total']:.2f}").classes("text-xs text-gray-400")
                else:
                    ui.label("None").classes("text-xs text-gray-400")
            
            # Efficiency Stats
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Productivity Efficiency").classes("text-xs text-gray-500")
                avg_eff = relief_summary.get('avg_efficiency', 0.0)
                high_eff = relief_summary.get('high_efficiency_count', 0)
                low_eff = relief_summary.get('low_efficiency_count', 0)
                ui.label(f"{avg_eff:.1f}").classes("text-lg font-bold")
                ui.label(f"High: {high_eff} | Low: {low_eff}").classes("text-xs text-gray-400")
                ui.label("(time × completion × relief)").classes("text-xs text-gray-400")


def build_recently_completed_panel():
    """Build the recently completed tasks panel with optional date grouping."""
    from collections import defaultdict
    
    with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto h-1/4"):
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


def build_compact_analytics_panel():
    metrics = an.get_dashboard_metrics()
    print(f"[Dashboard] Metrics snapshot: {metrics}")

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


def build_recommendations_section():
    """Build the recommendations section with filters."""
    print(f"[Dashboard] Rendering recommendations section with filters: {dash_filters}")
    
    with ui.column().classes("w-full border rounded-lg p-3 overflow-y-auto flex-1"):
        ui.label("Recommendations").classes("font-bold text-lg")
        ui.separator()
        
        # Filters
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            def apply_filter():
                value = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if value is not None:
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = None
                dash_filters['max_duration'] = value
                print(f"[Dashboard] Filter applied: max_duration = {value}, filters = {dash_filters}")
                refresh_recommendations(rec_container)
            
            ui.button("Apply", on_click=apply_filter).props("dense")
        
        # Note about future filtering options
        ui.label("More filtering options will be added later").classes("text-xs text-gray-500 mb-2")
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container)


def refresh_recommendations(target_container):
    """Refresh the recommendations display."""
    target_container.clear()
    recs = an.recommendations(dash_filters)
    print(f"[Dashboard] Recommendations result ({len(recs)} entries) for filters {dash_filters}")
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for rec in recs:
            with ui.card().classes("p-2 mb-2"):
                task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
                ui.label(task_label).classes("font-bold text-sm")
                ui.label(rec.get('reason', '')).classes("text-xs text-gray-600")
                ui.label(f"Duration: {rec.get('duration') or '—'}m").classes("text-xs text-gray-500")
                ui.label(f"Relief {rec.get('relief')} | Cog {rec.get('cognitive_load')}").classes("text-xs text-gray-500")
                ui.button("Initialize",
                          on_click=lambda rid=rec.get('task_id'): init_quick(rid)
                          ).props("dense").classes("mt-2")
