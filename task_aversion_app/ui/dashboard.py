# ui/dashboard.py
from nicegui import ui
import json
import html
import plotly.express as px
import plotly.graph_objects as go
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.emotion_manager import EmotionManager
from backend.analytics import Analytics

tm = TaskManager()
im = InstanceManager()
em = EmotionManager()
an = Analytics()

# Module-level variables for dashboard state
dash_filters = {}
RECOMMENDATION_METRICS = [
    {"label": "Relief score (high)", "key": "relief_score"},
    {"label": "Net relief (high)", "key": "net_relief_proxy"},
    {"label": "Cognitive load (low)", "key": "cognitive_load"},
    {"label": "Emotional load (low)", "key": "emotional_load"},
    {"label": "Net load (low)", "key": "net_load"},
    {"label": "Efficiency (high)", "key": "historical_efficiency"},
    {"label": "Stress level (low)", "key": "stress_level"},
    {"label": "Behavioral score (high)", "key": "behavioral_score"},
    {"label": "Net wellbeing (high)", "key": "net_wellbeing_normalized"},
    {"label": "Physical load (low)", "key": "physical_load"},
]


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


def get_current_task():
    """Get the currently running task (one with started_at set and not completed)."""
    active = im.list_active_instances()
    for inst in active:
        if inst.get('started_at') and inst.get('started_at').strip():
            return inst
    return None


def start_instance(instance_id, container=None):
    """Start an instance and update the container to show ongoing time."""
    # Check if there's already a current task running
    current = get_current_task()
    if current and current.get('instance_id') != instance_id:
        ui.notify("You need to finish the current task first", color='warning')
        return
    
    im.start_instance(instance_id)
    ui.notify("Instance started", color='positive')
    
    # Reload the page to update the current task display
    ui.navigate.reload()
    
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

    df = tm.get_all()
    if df is None or df.empty:
        print("[Dashboard] no templates found")
        template_col.clear()
        with template_col:
            ui.markdown("_No templates available_")
        return

    rows = df.to_dict(orient='records')
    print(f"[Dashboard] showing {len(rows)} templates")

    template_col.clear()

    # Use 3 nested columns for templates
    with template_col:
        col1 = ui.column().classes("w-1/3")
        col2 = ui.column().classes("w-1/3")
        col3 = ui.column().classes("w-1/3")
        columns = [col1, col2, col3]
        
        for idx, t in enumerate(rows):
            col = columns[idx % 3]
            with col:
                with ui.card().classes("p-2 mb-2 w-full"):
                    ui.markdown(f"**{t['name']}**").classes("text-xs")
                    with ui.row().classes("gap-1"):
                        ui.button("INIT", on_click=lambda tid=t['task_id']: init_quick(tid)).props("dense size=sm")
                        ui.button("EDIT", on_click=lambda task=t: edit_template(task)).props("dense size=sm color=blue")
                        ui.button("DELETE", on_click=lambda tid=t['task_id']: delete_template(tid)).props("dense size=sm color=red")


def delete_instance(instance_id):
    im.delete_instance(instance_id)
    ui.notify("Deleted", color='negative')
    ui.navigate.reload()

def edit_template(task):
    """Open a dialog to edit a task template."""
    print(f"[Dashboard] edit_template called: {task.get('task_id')}")
    
    task_id = task.get('task_id')
    current_name = task.get('name', '')
    current_desc = task.get('description', '')
    current_task_type = task.get('task_type', 'Work')
    current_est = task.get('default_estimate_minutes', 0)
    
    try:
        current_est = int(current_est) if current_est else 0
    except (TypeError, ValueError):
        current_est = 0
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl p-4'):
        ui.label("Edit Task Template").classes("text-xl font-bold mb-4")
        
        name_input = ui.input(label="Task Name", value=current_name).classes("w-full")
        desc_input = ui.textarea(label="Description (optional)", value=current_desc).classes("w-full")
        task_type_select = ui.select(
            ['Work', 'Play', 'Self care'], 
            label='Task Type', 
            value=current_task_type
        ).classes("w-full")
        est_input = ui.number(label='Default estimate minutes', value=current_est).classes("w-full")
        
        def save_edit():
            if not name_input.value.strip():
                ui.notify("Task name required", color='negative')
                return
            
            success = tm.update_task(
                task_id,
                name=name_input.value.strip(),
                description=desc_input.value or '',
                task_type=task_type_select.value,
                default_estimate_minutes=int(est_input.value or 0)
            )
            
            if success:
                ui.notify("Task updated", color='positive')
                dialog.close()
                refresh_templates()
            else:
                ui.notify("Update failed", color='negative')
        
        with ui.row().classes("gap-2 mt-4"):
            ui.button("Save", on_click=save_edit).props("color=primary")
            ui.button("Cancel", on_click=dialog.close)
    
    dialog.open()


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
# HELPER FUNCTIONS FOR METRIC TOOLTIPS
# ----------------------------------------------------------

def create_metric_tooltip_chart(dates, values, current_daily_avg, weekly_avg, three_month_avg, metric_name, current_line_color='#22c55e'):
    """Create a Plotly line chart for metric tooltip with reference lines.
    
    Args:
        dates: List of date strings
        values: List of daily values (already averaged per day)
        current_daily_avg: Daily average for current week (7d total / 7)
        weekly_avg: Weekly average (average of daily values over last 7 days)
        three_month_avg: 3-month average (average of all daily values)
        metric_name: Name of the metric
        current_line_color: Color for the current value line (green/yellow/red based on performance)
    """
    if not dates or not values or len(dates) == 0:
        return None
    
    # Create a line chart
    fig = go.Figure()
    
    # Add historical data line (daily values)
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode='lines',
        name='Daily',
        line=dict(color='#3b82f6', width=2),
        hovertemplate='%{x}<br>%{y:.2f}<extra></extra>'
    ))
    
    # Check for overlapping lines (within 0.1% difference to account for floating point precision)
    def values_overlap(val1, val2, tolerance=0.001):
        """Check if two values are effectively the same (overlapping)."""
        if val1 == 0 and val2 == 0:
            return True
        if val1 == 0 or val2 == 0:
            return False
        try:
            max_val = max(abs(val1), abs(val2))
            if max_val == 0:
                return True
            return abs(val1 - val2) / max_val < tolerance
        except (ZeroDivisionError, TypeError):
            return False
    
    # Determine which lines to show (hide overlapping ones, prioritize current value line)
    show_current = current_daily_avg > 0
    show_weekly = weekly_avg > 0 and not values_overlap(weekly_avg, current_daily_avg)
    show_three_month = three_month_avg > 0 and not values_overlap(three_month_avg, current_daily_avg)
    
    # Also check if weekly and 3-month overlap (but not with current)
    if show_weekly and show_three_month and values_overlap(weekly_avg, three_month_avg):
        # If they overlap, show the one closer to current, or just show weekly
        show_three_month = False
    
    # Add current daily average line (dashed, color based on performance)
    # This line always takes priority if it overlaps with others
    if show_current:
        fig.add_trace(go.Scatter(
            x=[dates[0], dates[-1]] if len(dates) > 1 else dates,
            y=[current_daily_avg, current_daily_avg],
            mode='lines',
            name='Current Daily Avg',
            line=dict(color=current_line_color, width=2, dash='dash'),
            hovertemplate=f'Current Daily Avg: {current_daily_avg:.2f}<extra></extra>'
        ))
    
    # Add weekly average line (dashed black) - only if not overlapping with current
    if show_weekly:
        fig.add_trace(go.Scatter(
            x=[dates[0], dates[-1]] if len(dates) > 1 else dates,
            y=[weekly_avg, weekly_avg],
            mode='lines',
            name='Weekly Avg',
            line=dict(color='#000000', width=2, dash='dash'),
            hovertemplate=f'Weekly Avg: {weekly_avg:.2f}<extra></extra>'
        ))
    
    # Add 3-month average line (dashed grey) - only if not overlapping with current or weekly
    if show_three_month:
        fig.add_trace(go.Scatter(
            x=[dates[0], dates[-1]] if len(dates) > 1 else dates,
            y=[three_month_avg, three_month_avg],
            mode='lines',
            name='3-Month Avg',
            line=dict(color='#6b7280', width=2, dash='dash'),
            hovertemplate=f'3-Month Avg: {three_month_avg:.2f}<extra></extra>'
        ))
    
    # Calculate min and max for y-axis (include all values and reference lines)
    all_y_values = values.copy()
    if current_daily_avg > 0:
        all_y_values.append(current_daily_avg)
    if weekly_avg > 0:
        all_y_values.append(weekly_avg)
    if three_month_avg > 0:
        all_y_values.append(three_month_avg)
    
    y_min = min(all_y_values) if all_y_values else 0
    y_max = max(all_y_values) if all_y_values else 1
    
    # Add small padding (5% of range)
    y_range = y_max - y_min
    if y_range > 0:
        y_padding = y_range * 0.05
        y_min = max(0, y_min - y_padding)  # Don't go below 0
        y_max = y_max + y_padding
    else:
        # If all values are the same, add some padding
        y_min = max(0, y_min - y_min * 0.1)
        y_max = y_max + y_max * 0.1
    
    fig.update_layout(
        title=f'{metric_name} Over Time (Last 90 Days)',
        xaxis_title='Date',
        yaxis_title=metric_name,
        height=300,
        margin=dict(l=50, r=20, t=50, b=50),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode='x unified',
        yaxis=dict(range=[y_min, y_max]),
    )
    
    return fig


def get_metric_bg_class(current_value, average_value):
    """Get background color class based on comparison to average.
    
    Returns:
        Tuple of (class_name, color_hex) where color_hex is for the chart line
    """
    if average_value == 0:
        return ("", "#6b7280")  # No data, default grey
    
    # Calculate percentage difference
    if average_value > 0:
        percent_diff = ((current_value - average_value) / average_value) * 100
    else:
        percent_diff = 0
    
    # Green if 10% or more above average
    if percent_diff >= 10:
        return ("metric-bg-green", "#22c55e")  # Green
    # Red if 10% or more below average
    elif percent_diff <= -10:
        return ("metric-bg-red", "#ef4444")  # Red
    # Yellow for average (within 10%)
    else:
        return ("metric-bg-yellow", "#eab308")  # Yellow


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
            flex-wrap: nowrap;
            width: 100%;
            height: calc(100vh - 180px);
            gap: 1rem;
            padding: 0.5rem;
            box-sizing: border-box;
            align-items: stretch;
        }
        
        .dashboard-column {
            display: flex;
            flex-direction: column;
            min-width: 0;
            overflow: hidden;
            box-sizing: border-box;
        }
        
        .column-left {
            flex: 0 0 25%;
            min-width: 250px;
            max-width: 25%;
        }
        
        .column-middle {
            flex: 0 0 35%;
            min-width: 280px;
            max-width: 35%;
        }
        
        .column-right {
            flex: 0 0 40%;
            min-width: 300px;
            max-width: 40%;
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
            width: 100%;
            box-sizing: border-box;
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
        
        /* Half-width columns for metrics layout */
        .half-width-left {
            flex: 0 0 50% !important;
            width: 50% !important;
            max-width: 50% !important;
            box-sizing: border-box;
        }
        
        .half-width-right {
            flex: 0 0 50% !important;
            width: 50% !important;
            max-width: 50% !important;
            box-sizing: border-box;
        }
        
        .metrics-row {
            display: flex !important;
            flex-direction: row !important;
            width: 100% !important;
            gap: 0.5rem;
        }
        
        /* Metric tooltip styling */
        .metric-tooltip {
            position: fixed;
            background: white;
            color: #1f2937;
            padding: 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            z-index: 10000;
            min-width: 300px;
            max-width: 500px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            border: 1px solid #e5e7eb;
        }
        
        .metric-tooltip.visible {
            opacity: 1;
        }
        
        .metric-card-hover {
            position: relative;
            cursor: pointer;
            transition: transform 0.1s;
        }
        
        .metric-card-hover:hover {
            transform: scale(1.02);
        }
        
        /* Color coding for metrics */
        .metric-bg-green {
            background-color: #d1fae5 !important;
        }
        
        .metric-bg-yellow {
            background-color: #fef3c7 !important;
        }
        
        .metric-bg-red {
            background-color: #fee2e2 !important;
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
    <script>
        function initMetricTooltips() {
            document.querySelectorAll('.metric-card-hover').forEach(function(card) {
                const tooltipId = card.getAttribute('data-tooltip-id');
                if (!tooltipId) return;
                
                const tooltip = document.getElementById('tooltip-' + tooltipId);
                if (!tooltip) return;
                
                let hoverTimeout;
                
                card.addEventListener('mouseenter', function() {
                    hoverTimeout = setTimeout(function() {
                        tooltip.classList.add('visible');
                        positionMetricTooltip(card, tooltip);
                    }, 300);
                });
                
                card.addEventListener('mouseleave', function() {
                    clearTimeout(hoverTimeout);
                    tooltip.classList.remove('visible');
                });
                
                card.addEventListener('mousemove', function(e) {
                    if (tooltip.classList.contains('visible')) {
                        positionMetricTooltip(card, tooltip, e);
                    }
                });
            });
        }
        
        function positionMetricTooltip(card, tooltip, event) {
            const rect = card.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            
            let left = rect.left + rect.width / 2 - tooltipRect.width / 2;
            // Always position below the cursor/card
            let top = event ? event.clientY + 10 : rect.bottom + 10;
            
            if (event) {
                left = event.clientX - tooltipRect.width / 2;
            }
            
            // Keep tooltip within viewport horizontally
            if (left < 10) left = 10;
            if (left + tooltipRect.width > window.innerWidth - 10) {
                left = window.innerWidth - tooltipRect.width - 10;
            }
            
            // Always keep tooltip below cursor, but adjust if it would go off bottom
            if (top + tooltipRect.height > window.innerHeight - 10) {
                // If it would go off bottom, position above cursor instead
                top = (event ? event.clientY : rect.top) - tooltipRect.height - 10;
                // But if that would go off top, just position at bottom of viewport
                if (top < 10) {
                    top = window.innerHeight - tooltipRect.height - 10;
                }
            }
            
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
            tooltip.style.pointerEvents = 'none'; // Prevent tooltip from interfering with mouse
        }
        
        // Initialize on page load and after DOM updates
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initMetricTooltips);
        } else {
            initMetricTooltips();
        }
        
        // Re-initialize after a short delay to catch dynamically added elements
        setTimeout(initMetricTooltips, 100);
    </script>
    """)

    # Main dashboard container
    with ui.column().classes("dashboard-container w-full"):
        # ====================================================================
        # TOP HEADER SECTION - Title and Analytics Button
        # ====================================================================
        with ui.row().classes("w-full justify-between items-center mb-4").props('id="tas-dashboard-header" data-tooltip-id="dashboard_header"'):
            ui.label("Task Aversion Dashboard").classes("text-4xl font-bold mb-3")
            with ui.row().classes("gap-2"):
                ui.button("Analytics",
                          on_click=lambda: ui.navigate.to('/analytics'),
                          icon="bar_chart").classes("text-xl py-3 px-6").props('id="tas-analytics-link" data-tooltip-id="analytics_link"')
                ui.button("Settings",
                          on_click=lambda: ui.navigate.to('/settings'),
                          icon="settings").classes("text-xl py-3 px-6").props('data-tooltip-id="settings_link"')
        
        # ====================================================================
        # MAIN THREE-COLUMN LAYOUT
        # ====================================================================
        with ui.row().classes("dashboard-layout w-full gap-4"):
            # ====================================================================
            # COLUMN 1 — Left Column
            # ====================================================================
            with ui.column().classes("dashboard-column column-left gap-2").props('id="tas-quick-actions" data-tooltip-id="quick_actions"'):
                # Create Task Button
                ui.button("+ CREATE TASK",
                          on_click=lambda: ui.navigate.to('/create_task'),
                          color='primary').classes("w-full text-lg py-3 mb-2")
                
                # Row with left half (metrics + quick tasks) and right half (recently completed)
                # Create a proper flex row container
                with ui.element('div').classes("metrics-row").style("display: flex !important; flex-direction: row !important; width: 100% !important; gap: 0.5rem; margin-bottom: 0.5rem; align-items: flex-start;"):
                    # Left half: Productivity Time, Weekly Relief Score, Quick Tasks
                    left_half = ui.column().classes("half-width-left gap-2")
                    with left_half:
                        # Productivity metrics
                        relief_summary = an.get_relief_summary()
                        
                        # Get historical data for weekly hours
                        hours_history = an.get_weekly_hours_history()
                        hours = relief_summary['productivity_time_minutes'] / 60.0
                        # Use weekly average * 7 for color coding (compare weekly total to average weekly total)
                        avg_weekly_total = hours_history.get('weekly_average', 0.0) * 7.0
                        hours_bg_class, hours_line_color = get_metric_bg_class(hours, avg_weekly_total)
                        
                        # Weekly Hours Card with hover tooltip
                        hours_card = ui.card().classes(f"w-full p-3 metric-card-hover {hours_bg_class}").props('data-tooltip-id="weekly-hours"')
                        with hours_card:
                            ui.label("Weekly Productivity Time").classes("text-xs text-gray-500 mb-1")
                            if hours >= 1:
                                ui.label(f"{hours:.1f} hours").classes("text-2xl font-bold")
                                ui.label(f"({relief_summary['productivity_time_minutes']:.0f} min)").classes("text-sm text-gray-400")
                            else:
                                ui.label(f"{relief_summary['productivity_time_minutes']:.0f} min").classes("text-2xl font-bold")
                        
                        # Get historical data for weekly relief
                        relief_history = an.get_weekly_relief_history()
                        weekly_relief = relief_summary.get('weekly_relief_score', 0.0)
                        # Use weekly average * 7 for color coding (compare weekly total to average weekly total)
                        avg_weekly_total = relief_history.get('weekly_average', 0.0) * 7.0
                        relief_bg_class, relief_line_color = get_metric_bg_class(weekly_relief, avg_weekly_total)
                        
                        # Weekly Relief Card with hover tooltip
                        relief_card = ui.card().classes(f"w-full p-3 metric-card-hover {relief_bg_class}").props('data-tooltip-id="weekly-relief"')
                        with relief_card:
                            ui.label("Weekly Relief Score").classes("text-xs text-gray-500 mb-1")
                            ui.label(f"{weekly_relief:.2f}").classes("text-2xl font-bold text-blue-600")
                        
                        # Create tooltip containers and render Plotly charts
                        hours_tooltip_id = 'tooltip-weekly-hours'
                        relief_tooltip_id = 'tooltip-weekly-relief'
                        
                        # Create tooltip HTML containers first
                        ui.add_body_html(f'<div id="{hours_tooltip_id}" class="metric-tooltip" style="min-width: 400px; max-width: 500px;"></div>')
                        ui.add_body_html(f'<div id="{relief_tooltip_id}" class="metric-tooltip" style="min-width: 400px; max-width: 500px;"></div>')
                        
                        # Render charts using NiceGUI plotly in temporary containers, then move to tooltips
                        if hours_history.get('dates') and hours_history.get('hours') and hours_history.get('has_sufficient_data', False):
                            # Calculate current daily average (weekly total / 7)
                            current_daily_avg = hours_history.get('current_value', 0.0) / 7.0 if hours_history.get('current_value', 0.0) > 0 else 0.0
                            hours_fig = create_metric_tooltip_chart(
                                hours_history['dates'],
                                hours_history['hours'],  # Already daily values
                                current_daily_avg,
                                hours_history.get('weekly_average', 0.0),
                                hours_history.get('three_month_average', 0.0),
                                'Daily Hours',
                                hours_line_color  # Pass the color based on performance
                            )
                            if hours_fig:
                                # Create temporary container for chart
                                with ui.element('div').props(f'id="{hours_tooltip_id}-temp"').style("position: absolute; left: -9999px; top: -9999px; visibility: hidden;"):
                                    ui.plotly(hours_fig)
                                # Move chart to tooltip
                                ui.run_javascript(f'''
                                    function moveHoursChart() {{
                                        const temp = document.getElementById('{hours_tooltip_id}-temp');
                                        const tooltip = document.getElementById('{hours_tooltip_id}');
                                        if (temp && tooltip) {{
                                            const plotlyDiv = temp.querySelector('.plotly');
                                            if (plotlyDiv && plotlyDiv.offsetHeight > 0) {{
                                                tooltip.innerHTML = '';
                                                tooltip.appendChild(plotlyDiv);
                                                temp.remove();
                                                return true;
                                            }}
                                        }}
                                        return false;
                                    }}
                                    
                                    // Try multiple times with increasing delays
                                    setTimeout(function() {{
                                        if (!moveHoursChart()) {{
                                            setTimeout(function() {{
                                                if (!moveHoursChart()) {{
                                                    setTimeout(moveHoursChart, 300);
                                                }}
                                            }}, 200);
                                        }}
                                    }}, 300);
                                ''')
                        elif hours_history.get('dates') and hours_history.get('hours'):
                            # Not enough data
                            ui.run_javascript(f'''
                                const tooltip = document.getElementById('{hours_tooltip_id}');
                                if (tooltip) {{
                                    tooltip.innerHTML = '<div class="text-xs text-gray-500 p-4 text-center">Needs more data<br>(At least 2 weeks required)</div>';
                                }}
                            ''')
                        
                        if relief_history.get('dates') and relief_history.get('relief_points') and relief_history.get('has_sufficient_data', False):
                            # Calculate current daily average (weekly total / 7)
                            current_daily_avg = relief_history.get('current_value', 0.0) / 7.0 if relief_history.get('current_value', 0.0) > 0 else 0.0
                            relief_fig = create_metric_tooltip_chart(
                                relief_history['dates'],
                                relief_history['relief_points'],  # Already daily values
                                current_daily_avg,
                                relief_history.get('weekly_average', 0.0),
                                relief_history.get('three_month_average', 0.0),
                                'Daily Relief Points',
                                relief_line_color  # Pass the color based on performance
                            )
                            if relief_fig:
                                with ui.element('div').props(f'id="{relief_tooltip_id}-temp"').style("position: absolute; left: -9999px; top: -9999px; visibility: hidden;"):
                                    ui.plotly(relief_fig)
                                ui.run_javascript(f'''
                                    function moveReliefChart() {{
                                        const temp = document.getElementById('{relief_tooltip_id}-temp');
                                        const tooltip = document.getElementById('{relief_tooltip_id}');
                                        if (temp && tooltip) {{
                                            const plotlyDiv = temp.querySelector('.plotly');
                                            if (plotlyDiv && plotlyDiv.offsetHeight > 0) {{
                                                tooltip.innerHTML = '';
                                                tooltip.appendChild(plotlyDiv);
                                                temp.remove();
                                                return true;
                                            }}
                                        }}
                                        return false;
                                    }}
                                    
                                    // Try multiple times with increasing delays
                                    setTimeout(function() {{
                                        if (!moveReliefChart()) {{
                                            setTimeout(function() {{
                                                if (!moveReliefChart()) {{
                                                    setTimeout(moveReliefChart, 300);
                                                }}
                                            }}, 200);
                                        }}
                                    }}, 300);
                                ''')
                        elif relief_history.get('dates') and relief_history.get('relief_points'):
                            # Not enough data
                            ui.run_javascript(f'''
                                const tooltip = document.getElementById('{relief_tooltip_id}');
                                if (tooltip) {{
                                    tooltip.innerHTML = '<div class="text-xs text-gray-500 p-4 text-center">Needs more data<br>(At least 2 weeks required)</div>';
                                }}
                            ''')
                        
                        # Quick Tasks
                        with ui.card().classes("w-full p-2"):
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
                    
                    # Right half: Recently Completed (scrollable, aligned to end after quick tasks)
                    right_half = ui.column().classes("half-width-right")
                    with right_half:
                        with ui.card().classes("w-full p-2").style("display: flex; flex-direction: column; align-self: flex-start; height: 100%;"):
                            ui.label("Recently Completed").classes("font-bold text-sm mb-2")
                            ui.separator()
                            # Scrollable content area - matches height of left half content
                            completed_scroll = ui.column().classes("w-full mt-2").style("overflow-y: auto; overflow-x: hidden; max-height: 400px;")
                            with completed_scroll:
                                # Get completed tasks and display them
                                completed = im.list_recent_completed(limit=20) if hasattr(im, "list_recent_completed") else []
                                
                                if not completed:
                                    ui.label("No completed tasks").classes("text-xs text-gray-500")
                                else:
                                    for c in completed:
                                        completed_at = str(c.get('completed_at', ''))
                                        with ui.row().classes("justify-between items-center mb-1"):
                                            ui.label(c['task_name']).classes("text-xs")
                                            if completed_at:
                                                parts = completed_at.split()
                                                if len(parts) >= 2:
                                                    date_part = parts[0]
                                                    time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                                                    ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                                                else:
                                                    ui.label(completed_at).classes("text-xs text-gray-400")
                
                # Task Templates section - directly below the row
                with ui.column().classes("scrollable-section flex-1"):
                    ui.markdown("### Task Templates")
                    
                    global template_col
                    template_col = ui.row().classes('w-full gap-2')
                    refresh_templates()

            # ====================================================================
            # COLUMN 2 — Middle Column
            # ====================================================================
            with ui.column().classes("dashboard-column column-middle gap-2"):
                # Top half: Active Tasks in 2 nested columns
                with ui.column().classes("scrollable-section").style("height: 50%; max-height: 50%;").props('id="tas-active-tasks" data-tooltip-id="active_tasks"'):
                    ui.label("Active Initialized Tasks").classes("text-lg font-bold mb-2")
                    ui.separator()
                    
                    active = im.list_active_instances()
                    current_task = get_current_task()
                    # Filter out current task from active list
                    active_not_current = [a for a in active if a.get('instance_id') != (current_task.get('instance_id') if current_task else None)]
                    
                    if not active_not_current:
                        ui.label("No active tasks").classes("text-xs text-gray-500")
                    else:
                        # Split into 2 columns
                        with ui.row().classes("w-full gap-2"):
                            col1 = ui.column().classes("w-1/2")
                            col2 = ui.column().classes("w-1/2")
                            
                            for idx, inst in enumerate(active_not_current):
                                col = col1 if idx % 2 == 0 else col2
                                with col:
                                    # Parse predicted data
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
                                    
                                    task_id = inst.get('task_id')
                                    formatted_tooltip = format_colored_tooltip(predicted_data, task_id)
                                    tooltip_id = f"tooltip-{inst['instance_id']}"
                                    instance_id = inst['instance_id']
                                    
                                    with ui.card().classes("w-full p-2 task-card-hover mb-2").props(f'data-instance-id="{instance_id}"').style("position: relative;"):
                                        ui.label(inst.get("task_name")).classes("text-sm font-bold")
                                        ui.label(f"{time_estimate} min").classes("text-xs text-gray-600")
                                        
                                        initialized_at = inst.get('initialized_at', '')
                                        if initialized_at:
                                            ui.label(f"Init: {initialized_at}").classes("text-xs text-gray-500")
                                        
                                        with ui.row().classes("gap-1 mt-1"):
                                            ui.button("Start",
                                                      on_click=lambda i=inst['instance_id']: start_instance(i)
                                                      ).props("dense size=sm").classes("bg-green-500")
                                            ui.button("Complete",
                                                      on_click=lambda i=inst['instance_id']: go_complete(i)
                                                      ).props("dense size=sm")
                                            ui.button("Cancel",
                                                      on_click=lambda i=inst['instance_id']: go_cancel(i)
                                                      ).props("dense size=sm color=red")
                                        
                                        tooltip_html = f'<div id="{tooltip_id}" class="task-tooltip">{formatted_tooltip}</div>'
                                        ui.add_body_html(tooltip_html)
                        
                        ui.run_javascript('setTimeout(initTaskTooltips, 200);')
                
                # Bottom half: Current Task
                with ui.column().classes("scrollable-section").style("height: 50%; max-height: 50%;"):
                    ui.label("CURRENT TASK").classes("current-task-indicator text-lg font-bold mb-2")
                    ui.html('<div class="current-task-line"></div>', sanitize=False)
                    
                    if current_task:
                        # Parse predicted data
                        predicted_str = current_task.get("predicted") or "{}"
                        try:
                            predicted_data = json.loads(predicted_str) if isinstance(predicted_str, str) else predicted_str
                        except (json.JSONDecodeError, TypeError):
                            predicted_data = {}
                        
                        time_estimate = predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0
                        try:
                            time_estimate = int(time_estimate)
                        except (TypeError, ValueError):
                            time_estimate = 0
                        
                        task_id = current_task.get('task_id')
                        formatted_tooltip = format_colored_tooltip(predicted_data, task_id)
                        tooltip_id = f"tooltip-{current_task['instance_id']}"
                        instance_id = current_task['instance_id']
                        
                        with ui.card().classes("w-full p-3 task-card-hover").props(f'data-instance-id="{instance_id}"').style("position: relative;"):
                            ui.label(current_task.get("task_name")).classes("text-xl font-bold mb-2")
                            ui.label(f"Estimated: {time_estimate} min").classes("text-sm text-gray-600 mb-2")
                            
                            started_at = current_task.get('started_at', '')
                            if started_at:
                                timer_label = ui.label("").classes("text-lg font-semibold text-blue-600 mb-2")
                                update_ongoing_timer(instance_id, timer_label)
                            
                            initialized_at = current_task.get('initialized_at', '')
                            if initialized_at:
                                ui.label(f"Initialized: {initialized_at}").classes("text-xs text-gray-500 mb-2")
                            
                            with ui.row().classes("gap-2 mt-2"):
                                ui.button("Complete",
                                          on_click=lambda i=instance_id: go_complete(i)
                                          ).classes("bg-green-500")
                                ui.button("Cancel",
                                          color="warning",
                                          on_click=lambda i=instance_id: go_cancel(i)
                                          )
                            
                            tooltip_html = f'<div id="{tooltip_id}" class="task-tooltip">{formatted_tooltip}</div>'
                            ui.add_body_html(tooltip_html)
                        
                        ui.run_javascript('setTimeout(initTaskTooltips, 200);')
                    else:
                        ui.label("No current task").classes("text-sm text-gray-500 mt-4")

            # ====================================================================
            # COLUMN 3 — Right Column (Recommendations only)
            # ====================================================================
            with ui.column().classes("dashboard-column column-right gap-2"):
                # Recommendations Section
                build_recommendations_section()


def build_summary_section():
    """Build the summary section with productivity time and productivity efficiency."""
    relief_summary = an.get_relief_summary()
    
    with ui.column().classes("w-full mb-2"):
        ui.label("Summary").classes("text-lg font-bold mb-2")
        
        with ui.column().classes("w-full gap-2"):
            # Productivity Time
            with ui.card().classes("p-2 w-full"):
                ui.label("Productivity Time").classes("text-xs text-gray-500")
                hours = relief_summary['productivity_time_minutes'] / 60.0
                if hours >= 1:
                    ui.label(f"{hours:.1f} hours ({relief_summary['productivity_time_minutes']:.0f} min)").classes("text-sm font-bold")
                else:
                    ui.label(f"{relief_summary['productivity_time_minutes']:.0f} min").classes("text-sm font-bold")
            
            # Default Relief Points
            with ui.card().classes("p-2 w-full"):
                ui.label("Default Relief Points").classes("text-xs text-gray-500")
                points = relief_summary['default_relief_points']
                color_class = "text-green-600" if points >= 0 else "text-red-600"
                ui.label(f"{points:+.2f} (actual-expected)").classes(f"text-sm font-bold {color_class}")
            
            # Net Relief Points
            with ui.card().classes("p-2 w-full"):
                ui.label("Net Relief Points").classes("text-xs text-gray-500")
                net_points = relief_summary['net_relief_points']
                ui.label(f"{net_points:.2f} (calibrated, a)").classes("text-sm font-bold text-green-600")
            
            # Positive Relief Stats
            with ui.card().classes("p-2 w-full"):
                ui.label("Positive Relief").classes("text-xs text-gray-500")
                pos_count = relief_summary['positive_relief_count']
                pos_avg = relief_summary['positive_relief_avg']
                ui.label(f"{pos_count} tasks Aug: +{pos_avg:.2f}").classes("text-sm font-bold")
            
            # Negative Relief Stats
            with ui.card().classes("p-2 w-full"):
                ui.label("Negative Relief").classes("text-xs text-gray-500")
                neg_count = relief_summary['negative_relief_count']
                ui.label(f"{neg_count} tasks").classes("text-sm font-bold")
            
            # Efficiency Stats
            with ui.card().classes("p-2 w-full"):
                ui.label("Productivity Efficiency").classes("text-xs text-gray-500")
                avg_eff = relief_summary.get('avg_efficiency', 0.0)
                high_eff = relief_summary.get('high_efficiency_count', 0)
                low_eff = relief_summary.get('low_efficiency_count', 0)
                ui.label(f"{avg_eff:.1f} High: {high_eff} (low)").classes("text-sm font-bold")
            
            # Relief × Duration Score (per task average)
            with ui.card().classes("p-2 w-full"):
                ui.label("Avg Relief × Duration").classes("text-xs text-gray-500")
                avg_rd = relief_summary.get('avg_relief_duration_score', 0.0)
                ui.label(f"{avg_rd:.2f}").classes("text-sm font-bold text-blue-600")
            
            # Total Relief × Duration Score
            with ui.card().classes("p-2 w-full"):
                ui.label("Total Relief × Duration").classes("text-xs text-gray-500")
                total_rd = relief_summary.get('total_relief_duration_score', 0.0)
                ui.label(f"{total_rd:.2f}").classes("text-sm font-bold text-blue-600")
            
            # Total Relief Score (same as total_relief_duration_score, but shown separately for clarity)
            with ui.card().classes("p-2 w-full"):
                ui.label("Total Relief Score").classes("text-xs text-gray-500")
                total_relief = relief_summary.get('total_relief_score', 0.0)
                ui.label(f"{total_relief:.2f}").classes("text-sm font-bold text-green-600")


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recently Completed").classes("font-bold text-sm mb-2")
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
                    ui.label(c['task_name']).classes("text-xs")
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
    """Build the recommendations section with multi-metric filtering."""
    print(f"[Dashboard] Rendering recommendations section")
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric multi-select
        metrics_select = ui.select(
            options=metric_labels,
            label="Filter by metrics (multi-select)",
            value=default_metrics,
            multiple=True,
        ).classes("w-full mb-2")
        
        # Max duration filter
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
                refresh_recommendations(rec_container, metrics_select.value, metric_key_map)
            
            ui.button("APPLY", on_click=apply_filter).props("dense")
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Refresh on metric changes
        def on_metrics_change(e=None):
            selected_values = None
            if e and hasattr(e, 'args') and e.args:
                if isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    selected_values = e.args[0]
                elif isinstance(e.args, dict):
                    selected_values = e.args.get('value') or e.args.get('label')
            if selected_values is None:
                selected_values = metrics_select.value if hasattr(metrics_select, 'value') else default_metrics
            refresh_recommendations(rec_container, selected_values, metric_key_map)
        
        metrics_select.on('update:model-value', on_metrics_change)
        
        # Initial render
        refresh_recommendations(rec_container, metrics_select.value, metric_key_map)


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None):
    """Refresh the recommendations display based on selected metrics."""
    target_container.clear()
    
    # Normalize selected metrics (list of labels)
    if selected_metrics is None:
        selected_metrics = []
    if isinstance(selected_metrics, str):
        selected_metrics = [selected_metrics]
    if metric_key_map is None:
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
    
    metric_keys = [metric_key_map.get(label, label) for label in selected_metrics if label]
    if not metric_keys:
        metric_keys = ["relief_score"]
    
    # Get recommendations for the selected metrics (top 3)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    recs = an.recommendations_by_category(metric_keys, filters, limit=3)
    print(f"[Dashboard] Recommendations result ({len(recs)} entries) for metrics '{metric_keys}', filters {filters}")
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for rec in recs:
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            metric_values = rec.get('metric_values', {}) or {}
            
            # Format the recommendation card
            with ui.card().classes("recommendation-card"):
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show score
                score_val = rec.get('score')
                score_text = f"Score: {score_val}" if score_val is not None else "Score: —"
                ui.label(score_text).classes("text-xs text-gray-600 mb-1")
                
                # Show only the selected metrics
                for label in selected_metrics:
                    key = metric_key_map.get(label, label)
                    val = metric_values.get(key, "—")
                    try:
                        if isinstance(val, (int, float)):
                            display_val = f"{val:.1f}"
                        else:
                            display_val = str(val)
                    except Exception:
                        display_val = "—"
                    ui.label(f"{label}: {display_val}").classes("text-xs text-gray-500")
                
                ui.button("INITIALIZE",
                          on_click=lambda rid=rec.get('task_id'): init_quick(rid)
                          ).props("dense size=sm").classes("w-full")
