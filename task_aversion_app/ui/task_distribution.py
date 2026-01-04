"""Task Distribution Analysis Page.

Shows pie charts of task template completion distribution.
Eventually will support jobs system with separate charts per job.
"""
from nicegui import ui
import pandas as pd
import plotly.express as px
from typing import Dict, List, Optional

from backend.instance_manager import InstanceManager
from backend.task_manager import TaskManager


@ui.page("/experimental/task-distribution")
def task_distribution_page():
    """Task distribution analysis page with pie charts."""
    
    ui.label("Task Distribution").classes("text-3xl font-bold mb-4")
    ui.label(
        "Visualize how task completion is distributed across different task templates. "
        "Each pie chart shows the proportion of completed instances for each task template."
    ).classes("text-gray-600 mb-6")
    
    # Note about future jobs system
    with ui.card().classes("p-4 mb-6 bg-blue-50 border border-blue-200"):
        ui.label("Note: Future Jobs System Implementation").classes("text-sm font-semibold text-blue-800 mb-2")
        ui.label(
            "This page will be refined when the jobs system is implemented. "
            "The final design will include a pie chart for all jobs showing task distribution, "
            "and separate charts for each job displaying its contained tasks."
        ).classes("text-sm text-blue-700")
    
    instance_manager = InstanceManager()
    task_manager = TaskManager()
    
    # Get all instances (we'll filter by status)
    all_instances = _get_all_instances(instance_manager)
    
    if not all_instances or len(all_instances) == 0:
        with ui.card().classes("p-6 w-full"):
            ui.label("No task instances yet.").classes("text-lg text-gray-500")
            ui.label("Create and work on some tasks to see distribution charts.").classes("text-sm text-gray-400 mt-2")
        ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")
        return
    
    # Filter checkboxes
    with ui.card().classes("p-4 mb-6 bg-gray-50 border border-gray-200"):
        ui.label("Filter by Status").classes("text-lg font-semibold mb-3")
        with ui.row().classes("gap-4"):
            include_completed = ui.checkbox("Include Completed", value=True).classes("text-sm")
            include_cancelled = ui.checkbox("Include Cancelled", value=False).classes("text-sm")
            include_initialized = ui.checkbox("Include Initialized", value=False).classes("text-sm")
    
    # Chart containers
    chart_container_count = ui.column().classes("w-full")
    chart_container_time = ui.column().classes("w-full")
    stats_table_container = ui.column().classes("w-full")
    
    def update_charts():
        """Update charts based on current filter settings."""
        # Clear previous content
        chart_container_count.clear()
        chart_container_time.clear()
        stats_table_container.clear()
        
        # Get filter settings
        show_completed = include_completed.value
        show_cancelled = include_cancelled.value
        show_initialized = include_initialized.value
        
        if not (show_completed or show_cancelled or show_initialized):
            with chart_container_count:
                with ui.card().classes("p-6 w-full"):
                    ui.label("Please select at least one status to display.").classes("text-gray-500")
            return
        
        # Filter instances based on status
        filtered_instances = []
        for inst in all_instances:
            completed_at = inst.get('completed_at', '') or ''
            cancelled_at = inst.get('cancelled_at', '') or ''
            initialized_at = inst.get('initialized_at', '') or ''
            
            is_completed = str(completed_at).strip() != ''
            is_cancelled = str(cancelled_at).strip() != ''
            is_initialized = str(initialized_at).strip() != '' and not is_completed and not is_cancelled
            
            if (is_completed and show_completed) or (is_cancelled and show_cancelled) or (is_initialized and show_initialized):
                filtered_instances.append(inst)
        
        if not filtered_instances:
            with chart_container_count:
                with ui.card().classes("p-6 w-full"):
                    ui.label("No instances match the selected filters.").classes("text-gray-500")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(filtered_instances)
        
        # Get task names for labels
        task_names = {}
        unique_task_ids = df['task_id'].unique()
        for task_id in unique_task_ids:
            task = task_manager.get_task(task_id)
            if task:
                task_names[task_id] = task.get('name', task_id)
            else:
                task_names[task_id] = task_id
        
        # Chart 1: Number of tasks by template
        task_counts = df.groupby('task_id').size().reset_index(name='count')
        task_counts['task_name'] = task_counts['task_id'].map(task_names)
        task_counts = task_counts.sort_values('count', ascending=False)
        
        with chart_container_count:
            with ui.card().classes("p-6 w-full mb-4"):
                ui.label("Task Count Distribution").classes("text-xl font-bold mb-4")
                status_labels = []
                if show_completed:
                    status_labels.append("completed")
                if show_cancelled:
                    status_labels.append("cancelled")
                if show_initialized:
                    status_labels.append("initialized")
                status_text = ", ".join(status_labels)
                ui.label(
                    f"Total instances: {len(filtered_instances)} ({status_text}) across {len(task_counts)} task templates"
                ).classes("text-sm text-gray-600 mb-4")
                
                if len(task_counts) > 0:
                    fig = px.pie(
                        task_counts,
                        values='count',
                        names='task_name',
                        title='Distribution of Task Instances by Template (Count)',
                        hole=0.4,
                    )
                    fig.update_traces(
                        textposition='inside',
                        textinfo='percent+label',
                        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
                    )
                    fig.update_layout(
                        margin=dict(l=20, r=20, t=40, b=20),
                        showlegend=True,
                        legend=dict(
                            orientation="v",
                            yanchor="middle",
                            y=0.5,
                            xanchor="left",
                            x=1.05
                        )
                    )
                    ui.plotly(fig)
                else:
                    ui.label("No data to display").classes("text-gray-500")
        
        # Chart 2: Time spent by template
        # Calculate time spent for each instance
        # For completed: use duration_minutes if available, otherwise estimate
        # For cancelled/initialized: use duration_minutes if available, otherwise 0
        time_data = []
        for _, row in df.iterrows():
            task_id = row.get('task_id', '')
            duration = row.get('duration_minutes', '')
            
            # Try to parse duration
            try:
                if duration and str(duration).strip():
                    time_minutes = float(duration)
                else:
                    # For non-completed tasks without duration, use 0
                    time_minutes = 0.0
            except (ValueError, TypeError):
                time_minutes = 0.0
            
            time_data.append({
                'task_id': task_id,
                'time_minutes': time_minutes
            })
        
        time_df = pd.DataFrame(time_data)
        if len(time_df) > 0:
            time_by_task = time_df.groupby('task_id')['time_minutes'].sum().reset_index(name='total_time')
            time_by_task['task_name'] = time_by_task['task_id'].map(task_names)
            time_by_task = time_by_task[time_by_task['total_time'] > 0]  # Only show tasks with time spent
            time_by_task = time_by_task.sort_values('total_time', ascending=False)
            
            with chart_container_time:
                with ui.card().classes("p-6 w-full mb-4"):
                    ui.label("Time Spent Distribution").classes("text-xl font-bold mb-4")
                    total_time_hours = time_by_task['total_time'].sum() / 60.0 if len(time_by_task) > 0 else 0
                    ui.label(
                        f"Total time: {total_time_hours:.1f} hours across {len(time_by_task)} task templates"
                    ).classes("text-sm text-gray-600 mb-4")
                    
                    if len(time_by_task) > 0:
                        fig = px.pie(
                            time_by_task,
                            values='total_time',
                            names='task_name',
                            title='Distribution of Time Spent by Template (Minutes)',
                            hole=0.4,
                        )
                        fig.update_traces(
                            textposition='inside',
                            textinfo='percent+label',
                            hovertemplate='<b>%{label}</b><br>Time: %{value:.1f} min<br>Percentage: %{percent}<extra></extra>'
                        )
                        fig.update_layout(
                            margin=dict(l=20, r=20, t=40, b=20),
                            showlegend=True,
                            legend=dict(
                                orientation="v",
                                yanchor="middle",
                                y=0.5,
                                xanchor="left",
                                x=1.05
                            )
                        )
                        ui.plotly(fig)
                    else:
                        ui.label("No time data available for selected instances.").classes("text-gray-500")
        
        # Statistics table
        with stats_table_container:
            with ui.card().classes("p-6 w-full mb-4"):
                ui.label("Task Template Statistics").classes("text-xl font-bold mb-4")
                
                # Combine count and time data
                stats_rows = []
                for _, count_row in task_counts.iterrows():
                    task_id = count_row['task_id']
                    task_name = count_row['task_name']
                    count = int(count_row['count'])
                    
                    # Get time for this task
                    time_row = time_by_task[time_by_task['task_id'] == task_id]
                    total_time = time_row['total_time'].iloc[0] if len(time_row) > 0 else 0.0
                    time_hours = total_time / 60.0
                    
                    # Calculate percentages
                    count_pct = (count / len(filtered_instances) * 100) if len(filtered_instances) > 0 else 0
                    total_time_all = time_by_task['total_time'].sum() if len(time_by_task) > 0 else 1
                    time_pct = (total_time / total_time_all * 100) if total_time_all > 0 else 0
                    
                    stats_rows.append({
                        'task_name': task_name,
                        'count': count,
                        'count_percentage': f"{count_pct:.1f}%",
                        'time_hours': f"{time_hours:.1f}",
                        'time_percentage': f"{time_pct:.1f}%"
                    })
                
                columns = [
                    {'name': 'task_name', 'label': 'Task Template', 'field': 'task_name', 'sortable': True},
                    {'name': 'count', 'label': 'Count', 'field': 'count', 'sortable': True},
                    {'name': 'count_percentage', 'label': 'Count %', 'field': 'count_percentage', 'sortable': True},
                    {'name': 'time_hours', 'label': 'Time (hours)', 'field': 'time_hours', 'sortable': True},
                    {'name': 'time_percentage', 'label': 'Time %', 'field': 'time_percentage', 'sortable': True},
                ]
                ui.table(columns=columns, rows=stats_rows).classes("w-full").props("dense flat bordered")
    
    # Set up checkbox change handlers
    include_completed.on("update:model-value", lambda _: update_charts())
    include_cancelled.on("update:model-value", lambda _: update_charts())
    include_initialized.on("update:model-value", lambda _: update_charts())
    
    # Initial chart render
    update_charts()
    
    ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")


def _get_all_instances(instance_manager: InstanceManager) -> List[Dict]:
    """Get all task instances as a list of dictionaries.
    
    Works with both CSV and database backends.
    """
    if instance_manager.use_db:
        return _get_all_instances_db(instance_manager)
    else:
        return _get_all_instances_csv(instance_manager)


def _get_all_instances_csv(instance_manager: InstanceManager) -> List[Dict]:
    """Get all instances from CSV backend."""
    instance_manager._reload()
    return instance_manager.df.to_dict(orient='records')


def _get_all_instances_db(instance_manager: InstanceManager) -> List[Dict]:
    """Get all instances from database backend."""
    try:
        with instance_manager.db_session() as session:
            all_instances = session.query(instance_manager.TaskInstance).all()
            return [instance.to_dict() for instance in all_instances]
    except Exception as e:
        print(f"[TaskDistribution] Error getting all instances: {e}")
        return []
