"""Coursera vs Task Aversion System Comparative Analysis.

Experimental page for analyzing Coursera task completion patterns
and comparing productivity metrics on days with vs without Coursera.
"""
from nicegui import ui
from backend.analytics import Analytics
from backend.task_manager import TaskManager
from backend.auth import get_current_user
from backend.security_utils import escape_for_display
from ui.error_reporting import handle_error_with_ui
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json


@ui.page("/experimental/coursera-analysis")
def coursera_analysis_page():
    """Page for analyzing Coursera task patterns and productivity impact."""
    
    # Get current user for data isolation
    current_user_id = get_current_user()
    if current_user_id is None:
        ui.navigate.to('/login')
        return
    
    analytics = Analytics()
    task_manager = TaskManager()
    
    ui.label("Coursera vs Task Aversion System Analysis").classes("text-3xl font-bold mb-4")
    ui.label("Compare Coursera task patterns and productivity impact").classes("text-gray-600 mb-6")
    
    # Get data
    try:
        # Load instances and tasks
        instances_df = analytics._load_instances(user_id=current_user_id)
        tasks_df = task_manager.get_all(user_id=current_user_id)
        
        # Find Coursera task
        coursera_tasks = tasks_df[tasks_df['name'].str.contains('Coursera', case=False, na=False)]
        
        if coursera_tasks.empty:
            with ui.card().classes("w-full max-w-4xl p-6 bg-yellow-50 border border-yellow-200"):
                ui.label("No Coursera Task Found").classes("text-lg font-semibold text-yellow-800 mb-2")
                ui.label("Please create a task named 'Coursera' to enable this analysis.").classes("text-yellow-700")
            ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")
            return
        
        coursera_task_id = coursera_tasks.iloc[0]['task_id']
        coursera_task_name = coursera_tasks.iloc[0]['name']
        
        # Filter to completed instances
        completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            with ui.card().classes("w-full max-w-4xl p-6 bg-yellow-50 border border-yellow-200"):
                ui.label("No Completed Tasks Found").classes("text-lg font-semibold text-yellow-800 mb-2")
                ui.label("Complete some tasks to see analysis.").classes("text-yellow-700")
            ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")
            return
        
        # Parse dates
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        completed['completed_date'] = completed['completed_at_dt'].dt.date
        
        # Get Coursera instances
        coursera_instances = completed[completed['task_id'] == coursera_task_id].copy()
        
        # Get all unique dates with completions
        all_dates = sorted(completed['completed_date'].unique())
        
        # Identify days with Coursera
        coursera_dates = set(coursera_instances['completed_date'].unique())
        
        # Calculate daily productivity scores
        days_with_coursera = []
        days_without_coursera = []
        
        for date_obj in all_dates:
            daily_scores = analytics.calculate_daily_scores(target_date=datetime.combine(date_obj, datetime.min.time()))
            
            if date_obj in coursera_dates:
                # Get Coursera time for this day
                day_coursera = coursera_instances[coursera_instances['completed_date'] == date_obj]
                coursera_time = pd.to_numeric(day_coursera['duration_minutes'], errors='coerce').fillna(0).sum()
                days_with_coursera.append({
                    'date': date_obj,
                    'productivity_score': daily_scores['productivity_score'],
                    'execution_score': daily_scores['execution_score'],
                    'grit_score': daily_scores['grit_score'],
                    'composite_score': daily_scores['composite_score'],
                    'coursera_time': coursera_time
                })
            else:
                days_without_coursera.append({
                    'date': date_obj,
                    'productivity_score': daily_scores['productivity_score'],
                    'execution_score': daily_scores['execution_score'],
                    'grit_score': daily_scores['grit_score'],
                    'composite_score': daily_scores['composite_score']
                })
        
        # Summary Statistics
        with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
            ui.label("Summary Statistics").classes("text-xl font-semibold mb-4")
            
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    ui.label("Coursera Task").classes("font-semibold")
                    ui.label(escape_for_display(coursera_task_name)).classes("text-lg")
                
                with ui.column().classes("flex-1"):
                    ui.label("Total Coursera Instances").classes("font-semibold")
                    ui.label(f"{len(coursera_instances)} completed").classes("text-lg")
                
                with ui.column().classes("flex-1"):
                    ui.label("Total Coursera Time").classes("font-semibold")
                    coursera_total_time = pd.to_numeric(coursera_instances['duration_minutes'], errors='coerce').fillna(0).sum()
                    ui.label(f"{coursera_total_time:.1f} minutes ({coursera_total_time/60:.1f} hours)").classes("text-lg")
                
                with ui.column().classes("flex-1"):
                    ui.label("Days with Coursera").classes("font-semibold")
                    ui.label(f"{len(coursera_dates)} days").classes("text-lg")
        
        # Comparison: Days with vs without Coursera
        if days_with_coursera and days_without_coursera:
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Productivity Score Comparison").classes("text-xl font-semibold mb-4")
                
                # Calculate averages
                with_coursera_avg = {
                    'productivity': sum(d['productivity_score'] for d in days_with_coursera) / len(days_with_coursera),
                    'execution': sum(d['execution_score'] for d in days_with_coursera) / len(days_with_coursera),
                    'grit': sum(d['grit_score'] for d in days_with_coursera) / len(days_with_coursera),
                    'composite': sum(d['composite_score'] for d in days_with_coursera) / len(days_with_coursera)
                }
                
                without_coursera_avg = {
                    'productivity': sum(d['productivity_score'] for d in days_without_coursera) / len(days_without_coursera),
                    'execution': sum(d['execution_score'] for d in days_without_coursera) / len(days_without_coursera),
                    'grit': sum(d['grit_score'] for d in days_without_coursera) / len(days_without_coursera),
                    'composite': sum(d['composite_score'] for d in days_without_coursera) / len(days_without_coursera)
                }
                
                # Comparison table
                with ui.column().classes("w-full gap-4"):
                    # Header
                    with ui.row().classes("w-full font-semibold border-b pb-2"):
                        ui.label("Metric").classes("flex-1")
                        ui.label("Days WITH Coursera").classes("flex-1 text-center")
                        ui.label("Days WITHOUT Coursera").classes("flex-1 text-center")
                        ui.label("Difference").classes("flex-1 text-center")
                    
                    # Productivity Score
                    diff_prod = with_coursera_avg['productivity'] - without_coursera_avg['productivity']
                    with ui.row().classes("w-full border-b pb-2"):
                        ui.label("Productivity Score").classes("flex-1")
                        ui.label(f"{with_coursera_avg['productivity']:.2f}").classes("flex-1 text-center")
                        ui.label(f"{without_coursera_avg['productivity']:.2f}").classes("flex-1 text-center")
                        diff_class = "text-green-600" if diff_prod > 0 else "text-red-600" if diff_prod < 0 else ""
                        ui.label(f"{diff_prod:+.2f}").classes(f"flex-1 text-center font-semibold {diff_class}")
                    
                    # Execution Score
                    diff_exec = with_coursera_avg['execution'] - without_coursera_avg['execution']
                    with ui.row().classes("w-full border-b pb-2"):
                        ui.label("Execution Score").classes("flex-1")
                        ui.label(f"{with_coursera_avg['execution']:.2f}").classes("flex-1 text-center")
                        ui.label(f"{without_coursera_avg['execution']:.2f}").classes("flex-1 text-center")
                        diff_class = "text-green-600" if diff_exec > 0 else "text-red-600" if diff_exec < 0 else ""
                        ui.label(f"{diff_exec:+.2f}").classes(f"flex-1 text-center font-semibold {diff_class}")
                    
                    # Grit Score
                    diff_grit = with_coursera_avg['grit'] - without_coursera_avg['grit']
                    with ui.row().classes("w-full border-b pb-2"):
                        ui.label("Grit Score").classes("flex-1")
                        ui.label(f"{with_coursera_avg['grit']:.2f}").classes("flex-1 text-center")
                        ui.label(f"{without_coursera_avg['grit']:.2f}").classes("flex-1 text-center")
                        diff_class = "text-green-600" if diff_grit > 0 else "text-red-600" if diff_grit < 0 else ""
                        ui.label(f"{diff_grit:+.2f}").classes(f"flex-1 text-center font-semibold {diff_class}")
                    
                    # Composite Score
                    diff_comp = with_coursera_avg['composite'] - without_coursera_avg['composite']
                    with ui.row().classes("w-full"):
                        ui.label("Composite Score").classes("flex-1 font-semibold")
                        ui.label(f"{with_coursera_avg['composite']:.2f}").classes("flex-1 text-center font-semibold")
                        ui.label(f"{without_coursera_avg['composite']:.2f}").classes("flex-1 text-center font-semibold")
                        diff_class = "text-green-600" if diff_comp > 0 else "text-red-600" if diff_comp < 0 else ""
                        ui.label(f"{diff_comp:+.2f}").classes(f"flex-1 text-center font-semibold {diff_class}")
        
        # Charts
        if days_with_coursera or days_without_coursera:
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Productivity Score Over Time").classes("text-xl font-semibold mb-4")
                
                # Create comparison chart
                fig = go.Figure()
                
                if days_with_coursera:
                    dates_with = [d['date'] for d in days_with_coursera]
                    scores_with = [d['productivity_score'] for d in days_with_coursera]
                    fig.add_trace(go.Scatter(
                        x=dates_with,
                        y=scores_with,
                        mode='markers+lines',
                        name='Days WITH Coursera',
                        marker=dict(size=10, color='#3b82f6'),
                        line=dict(color='#3b82f6', width=2)
                    ))
                
                if days_without_coursera:
                    dates_without = [d['date'] for d in days_without_coursera]
                    scores_without = [d['productivity_score'] for d in days_without_coursera]
                    fig.add_trace(go.Scatter(
                        x=dates_without,
                        y=scores_without,
                        mode='markers+lines',
                        name='Days WITHOUT Coursera',
                        marker=dict(size=8, color='#94a3b8', symbol='circle-open'),
                        line=dict(color='#94a3b8', width=1, dash='dot')
                    ))
                
                fig.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Productivity Score",
                    hovermode='x unified',
                    height=400,
                    showlegend=True
                )
                
                ui.plotly(fig).classes("w-full")
        
        # Coursera Time Distribution
        if days_with_coursera:
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Coursera Time Spent Per Day").classes("text-xl font-semibold mb-4")
                
                coursera_times = [d['coursera_time'] for d in days_with_coursera]
                dates = [d['date'] for d in days_with_coursera]
                
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=dates,
                    y=coursera_times,
                    name='Coursera Time (minutes)',
                    marker_color='#10b981'
                ))
                
                fig2.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Minutes",
                    height=300,
                    showlegend=False
                )
                
                ui.plotly(fig2).classes("w-full")
                
                # Stats
                avg_time = sum(coursera_times) / len(coursera_times)
                ui.label(f"Average time per day: {avg_time:.1f} minutes").classes("text-sm text-gray-600 mt-2")
        
        # Detailed Coursera Instance List
        if not coursera_instances.empty:
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Coursera Task Instances").classes("text-xl font-semibold mb-4")
                
                # Sort by date descending
                coursera_sorted = coursera_instances.sort_values('completed_at_dt', ascending=False)
                
                with ui.column().classes("w-full gap-2"):
                    for idx, row in coursera_sorted.head(20).iterrows():
                        date_str = row['completed_at_dt'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['completed_at_dt']) else 'Unknown'
                        duration = pd.to_numeric(row.get('duration_minutes', 0), errors='coerce')
                        relief = pd.to_numeric(row.get('relief_score', 0), errors='coerce')
                        cognitive = pd.to_numeric(row.get('cognitive_load', 0), errors='coerce')
                        
                        with ui.card().classes("p-3 border border-gray-200"):
                            with ui.row().classes("w-full items-center justify-between"):
                                ui.label(date_str).classes("font-semibold")
                                if pd.notna(duration):
                                    ui.label(f"{duration:.0f} min").classes("text-sm")
                                if pd.notna(relief):
                                    ui.label(f"Relief: {relief:.1f}").classes("text-xs text-gray-600")
                                if pd.notna(cognitive):
                                    ui.label(f"Cognitive: {cognitive:.1f}").classes("text-xs text-gray-600")
    
    except Exception as e:
        handle_error_with_ui(
            operation="load coursera analysis data",
            error=e,
            user_id=current_user_id,
            context={"page": "coursera_analysis"},
            user_message="Failed to load Coursera analysis data. Please try again or contact support."
        )
    
    ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")

