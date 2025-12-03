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


def start_instance(instance_id, container=None):
    """Start an instance and update the container to show ongoing time."""
    im.start_instance(instance_id)
    ui.notify("Instance started", color='positive')
    
    # If container provided, replace button with ongoing timer
    if container:
        container.clear()
        with container:
            timer_label = ui.label("").classes("text-sm font-semibold text-blue-600")
            update_ongoing_timer(instance_id, timer_label)


def go_complete(instance_id):
    ui.navigate.to(f'/complete_task?instance_id={instance_id}')


def go_cancel(instance_id):
    ui.navigate.to(f'/cancel_task?instance_id={instance_id}')


def format_elapsed_time(minutes):
    """Format elapsed time in minutes as HH:MM or M min."""
    if minutes < 60:
        return f"{int(minutes)} min"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours}:{mins:02d}"


def update_ongoing_timer(instance_id, timer_element):
    """Update the ongoing timer display for a started instance."""
    instance = im.get_instance(instance_id)
    if not instance or not instance.get('started_at'):
        # Instance no longer active or not started, stop timer
        if timer_element:
            timer_element.text = ""
        return
    
    try:
        from datetime import datetime
        import pandas as pd
        started_at = pd.to_datetime(instance['started_at'])
        now = datetime.now()
        elapsed_minutes = (now - started_at).total_seconds() / 60.0
        elapsed_str = format_elapsed_time(elapsed_minutes)
        
        # Update the element text
        if timer_element:
            timer_element.text = f"Ongoing for {elapsed_str}"
        
        # Schedule next update in 1 second (only if instance is still active)
        active_instances = im.list_active_instances()
        is_still_active = any(inst.get('instance_id') == instance_id for inst in active_instances)
        if is_still_active:
            ui.timer(1.0, lambda: update_ongoing_timer(instance_id, timer_element), once=True)
    except Exception as e:
        print(f"[Dashboard] Error updating timer: {e}")


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

    # Use grid layout for templates
    with template_col:
        for t in filtered:
            with ui.card().classes("p-2 mb-2"):
                ui.markdown(f"**{t['name']}** — v{t['version']}")
                with ui.row().classes("gap-1"):
                    ui.button("INIT", on_click=lambda tid=t['task_id']: init_quick(tid)).props("dense size=sm")
                    ui.button("DELETE", on_click=lambda tid=t['task_id']: delete_template(tid)).props("dense size=sm color=red")


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
        /* Zoom-responsive scaling - maintains bottom position */
        html {
            zoom: 1;
        }
        
        body {
            margin: 0;
            padding: 0;
            overflow-x: hidden;
        }
        
        /* Dashboard container with viewport-based sizing */
        .dashboard-container {
            width: 100%;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            transform-origin: top center;
        }
        
        /* Three-column layout */
        .dashboard-layout {
            display: flex;
            width: 100%;
            height: calc(100vh - 120px);
            gap: 1rem;
            padding: 0.5rem;
            box-sizing: border-box;
        }
        
        .dashboard-column {
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .column-left {
            width: 25%;
            min-width: 250px;
        }
        
        .column-middle {
            width: 40%;
            min-width: 300px;
        }
        
        .column-right {
            width: 35%;
            min-width: 300px;
        }
        
        /* Scrollable sections */
        .scrollable-section {
            overflow-y: auto;
            overflow-x: hidden;
            flex: 1;
            border: 1px solid #e5e7eb;
            border-radius: 0.5rem;
            padding: 0.75rem;
            margin-bottom: 0.5rem;
        }
        
        .scrollable-section:last-child {
            margin-bottom: 0;
        }
        
        /* Small text for compact display */
        .small * { 
            font-size: 0.85rem !important; 
        }
        
        /* Task tooltip styling */
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
        
        /* Current task indicator */
        .current-task-indicator {
            color: #ef4444;
            font-weight: bold;
            font-size: 1rem;
            margin: 0.5rem 0;
        }
        
        .current-task-line {
            width: 2px;
            background-color: #ef4444;
            min-height: 100px;
            margin: 0.5rem 0;
        }
        
        /* Template grid */
        .template-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 0.5rem;
        }
        
        /* Recommendation cards */
        .recommendation-card {
            margin-bottom: 0.75rem;
            padding: 0.75rem;
            border: 1px solid #e5e7eb;
            border-radius: 0.375rem;
            background: white;
        }
        
        /* Responsive adjustments */
        @media (max-width: 1400px) {
            .dashboard-layout {
                gap: 0.75rem;
                padding: 0.25rem;
            }
        }
        
        /* Ensure proper scaling on zoom */
        @media screen {
            .dashboard-container {
                transform-origin: top left;
            }
        }
    </style>
    <script>
        // Handle zoom-responsive behavior
        function updateZoomScale() {
            const container = document.querySelector('.dashboard-container');
            if (container) {
                // Browser zoom is handled automatically, but we can adjust if needed
                const zoomLevel = window.devicePixelRatio || 1;
                // The browser handles zoom, so we just ensure proper layout
            }
        }
        
        window.addEventListener('resize', updateZoomScale);
        updateZoomScale();
    </script>
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

    # Main dashboard container
    with ui.column().classes("dashboard-container w-full"):
        # ====================================================================
        # COLUMN 1 — Left Column (Header, Create Task, Quick Tasks, Templates)
        # ====================================================================
        with ui.row().classes("dashboard-layout w-full"):
            with ui.column().classes("dashboard-column column-left gap-2"):
                # Header
                ui.label("Task Aversion Dashboard").classes("text-2xl font-bold mb-2")
                
                # Create Task Button
                ui.button("+ CREATE TASK",
                          on_click=lambda: ui.navigate.to('/create_task'),
                          color='primary').classes("w-full text-lg py-3 mb-2")
                
                # Quick Tasks Section
                with ui.column().classes("scrollable-section"):
                    ui.markdown("### Quick Tasks (Last 5)")
                    
                    recent = tm.get_recent(limit=5) if hasattr(tm, "get_recent") else []
                    
                    if not recent:
                        ui.label("No recent tasks").classes("text-xs text-gray-500")
                    else:
                        for r in recent:
                            with ui.row().classes("justify-between items-center mb-1"):
                                ui.label(r['name']).classes("text-sm")
                                ui.button("INIT", 
                                          on_click=lambda n=r['name']: init_quick(n)
                                          ).props("dense size=sm")
                
                # Templates Section
                with ui.column().classes("scrollable-section"):
                    ui.markdown("### Task Templates")
                    
                    # Search bar
                    global search
                    search = ui.input(
                        label="Search task templates",
                        placeholder="Type to filter...",
                    ).classes("w-full mb-2")
                    
                    search.on('input', lambda _: refresh_templates())
                    
                    global template_col
                    template_col = ui.column().classes('w-full')
                    refresh_templates()

            # ====================================================================
            # COLUMN 2 — Middle Column (Summary, Active Tasks, Current Task, Recently Completed)
            # ====================================================================
            with ui.column().classes("dashboard-column column-middle gap-2"):
                # Summary Section
                build_summary_section()
                
                # Active Tasks Section
                with ui.column().classes("scrollable-section"):
                    ui.label("Active Initialized Tasks").classes("text-lg font-bold mb-2")
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
                            
                            with ui.card().classes("w-full p-2 task-card-hover mb-2").props(f'data-instance-id="{instance_id}"').style("position: relative;"):
                                # Task name and time estimate
                                with ui.row().classes("justify-between items-center w-full"):
                                    ui.label(inst.get("task_name")).classes("text-md font-bold")
                                    ui.label(f"{time_estimate} min").classes("text-sm text-gray-600")
                                
                                # Initialization time
                                initialized_at = inst.get('initialized_at', '')
                                if initialized_at:
                                    ui.label(f"Initialized: {initialized_at}").classes("text-xs text-gray-500 mt-1")
                                
                                # Buttons row
                                with ui.row().classes("justify-end gap-2 mt-2"):
                                    # Start button or ongoing timer container
                                    start_container = ui.column().classes("items-center")
                                    started_at = inst.get('started_at', '')
                                    if started_at:
                                        # Show ongoing timer
                                        with start_container:
                                            timer_label = ui.label("").classes("text-sm font-semibold text-blue-600")
                                            update_ongoing_timer(instance_id, timer_label)
                                    else:
                                        # Show start button
                                        with start_container:
                                            ui.button("Start",
                                                      on_click=lambda i=inst['instance_id'], c=start_container: start_instance(i, c)
                                                      ).props("dense").classes("bg-green-500")
                                    
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
                
                # Current Task Indicator
                ui.label("CURRENT TASK").classes("current-task-indicator")
                ui.html('<div class="current-task-line"></div>', sanitize=False)
                
                # Recently Completed Section
                build_recently_completed_panel()

            # ====================================================================
            # COLUMN 3 — Right Column (Analytics Pulse, Recommendations)
            # ====================================================================
            with ui.column().classes("dashboard-column column-right gap-2"):
                # Analytics Pulse Header
                ui.label("Analytics pulse").classes("text-xl font-bold mb-2")
                
                # Recommendations Section
                build_recommendations_section()


def build_summary_section():
    """Build the summary section with productivity time and relief points."""
    relief_summary = an.get_relief_summary()
    
    with ui.card().classes("w-full mb-2 p-3"):
        ui.label("Summary").classes("text-lg font-bold mb-2")
        
        with ui.row().classes("w-full gap-2 flex-wrap"):
            # Productivity Time
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label("Productivity Time").classes("text-xs text-gray-500")
                hours = relief_summary['productivity_time_minutes'] / 60.0
                if hours >= 1:
                    ui.label(f"{hours:.1f} hours ({relief_summary['productivity_time_minutes']:.0f} min)").classes("text-sm font-bold")
                else:
                    ui.label(f"{relief_summary['productivity_time_minutes']:.0f} min").classes("text-sm font-bold")
            
            # Default Relief Points
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label("Default Relief Points").classes("text-xs text-gray-500")
                points = relief_summary['default_relief_points']
                color_class = "text-green-600" if points >= 0 else "text-red-600"
                ui.label(f"{points:+.2f} (actual-expected)").classes(f"text-sm font-bold {color_class}")
            
            # Net Relief Points
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label("Net Relief Points").classes("text-xs text-gray-500")
                net_points = relief_summary['net_relief_points']
                ui.label(f"{net_points:.2f} (calibrated, a)").classes("text-sm font-bold text-green-600")
            
            # Positive Relief Stats
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label("Positive Relief").classes("text-xs text-gray-500")
                pos_count = relief_summary['positive_relief_count']
                pos_avg = relief_summary['positive_relief_avg']
                ui.label(f"{pos_count} tasks Aug: +{pos_avg:.2f}").classes("text-sm font-bold")
            
            # Negative Relief Stats
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label("Negative Relief").classes("text-xs text-gray-500")
                neg_count = relief_summary['negative_relief_count']
                ui.label(f"{neg_count} tasks").classes("text-sm font-bold")
            
            # Efficiency Stats
            with ui.card().classes("p-2 min-w-[140px]"):
                ui.label("Productivity Efficiency").classes("text-xs text-gray-500")
                avg_eff = relief_summary.get('avg_efficiency', 0.0)
                high_eff = relief_summary.get('high_efficiency_count', 0)
                low_eff = relief_summary.get('low_efficiency_count', 0)
                ui.label(f"{avg_eff:.1f} High: {high_eff} (low)").classes("text-sm font-bold")


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    from collections import defaultdict
    
    with ui.column().classes("scrollable-section"):
        ui.label("Recently Completed").classes("font-bold text-lg mb-2")
        ui.separator()
        
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
            
            # Show flat list with date and time
            with completed_container:
                for c in completed:
                    completed_at = str(c.get('completed_at', ''))
                    # Format: "Task Name YYYY-MM-DD HH:MM"
                    with ui.row().classes("justify-between items-center mb-1"):
                        ui.label(c['task_name']).classes("text-sm")
                        if completed_at:
                            # Extract date and time parts
                            parts = completed_at.split()
                            if len(parts) >= 2:
                                date_part = parts[0]
                                time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                                ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                            else:
                                ui.label(completed_at).classes("text-xs text-gray-400")
        
        # Initial render
        refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with filters."""
    print(f"[Dashboard] Rendering recommendations section with filters: {dash_filters}")
    
    with ui.column().classes("scrollable-section"):
        ui.label("Recommendations").classes("font-bold text-lg mb-2")
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
            
            ui.button("APPLY", on_click=apply_filter).props("dense")
        
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
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            reason = rec.get('reason', '')
            duration = rec.get('duration') or '—'
            relief = rec.get('relief') or '—'
            cognitive = rec.get('cognitive_load') or '—'
            emotional = rec.get('emotional_load') or '—'
            
            # Format the recommendation card to match image
            with ui.card().classes("recommendation-card"):
                # Title (e.g., "Highest Relief:", "Shortest Task:")
                title = rec.get('title', '')
                if title:
                    ui.label(f"{title}").classes("text-xs font-semibold text-gray-600 mb-1")
                
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Reason line with all metrics
                reason_parts = []
                if relief != '—':
                    reason_parts.append(f"relief {relief}")
                if cognitive != '—':
                    reason_parts.append(f"cognitive {cognitive}")
                if emotional != '—':
                    reason_parts.append(f"emotional {emotional}")
                
                reason_text = " / ".join(reason_parts) if reason_parts else reason
                ui.label(f"{reason_text}.").classes("text-xs text-gray-600 mb-1")
                
                # Duration and summary
                ui.label(f"Duration: {duration}m.").classes("text-xs text-gray-500 mb-1")
                ui.label(f"Relief {relief} | Cog {cognitive}").classes("text-xs text-gray-500 mb-2")
                
                # Initialize button
                ui.button("INITIALIZE",
                          on_click=lambda rid=rec.get('task_id'): init_quick(rid)
                          ).props("dense size=sm").classes("w-full")
