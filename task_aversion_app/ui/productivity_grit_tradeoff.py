"""Productivity vs Grit Tradeoff Analysis.

Experimental page for analyzing the relationship between productivity scores
and grit scores across all tasks. Helps identify tasks that excel in one metric
but not the other, revealing patterns in task performance.
"""
from nicegui import ui
from backend.analytics import Analytics
from backend.task_manager import TaskManager
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import numpy as np


@ui.page("/experimental/productivity-grit-tradeoff")
def productivity_grit_tradeoff_page():
    """Page for analyzing productivity vs grit score tradeoffs across tasks."""
    
    analytics = Analytics()
    task_manager = TaskManager()
    
    ui.label("Productivity vs Grit Tradeoff Analysis").classes("text-3xl font-bold mb-4")
    ui.label("Explore the relationship between productivity (efficiency) and grit (persistence) across all tasks").classes("text-gray-600 mb-6")
    
    try:
        # Load data
        instances_df = analytics._load_instances()
        tasks_df = task_manager.get_all()
        
        # Filter to completed instances
        completed = instances_df[instances_df['completed_at'].astype(str).str.len() > 0].copy()
        if completed.empty:
            with ui.card().classes("w-full max-w-4xl p-6 bg-yellow-50 border border-yellow-200"):
                ui.label("No Completed Tasks Found").classes("text-lg font-semibold text-yellow-800 mb-2")
                ui.label("Complete some tasks to see analysis.").classes("text-yellow-700")
            ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")
            return
        
        # Calculate task completion counts for grit score
        from collections import Counter
        task_completion_counts = Counter(completed['task_id'].tolist())
        task_completion_counts_dict = dict(task_completion_counts)
        
        # Get self-care and work/play data for productivity score
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        completed = completed.dropna(subset=['completed_at_dt'])
        completed['completed_date'] = completed['completed_at_dt'].dt.date
        
        # Calculate productivity and grit scores for each instance
        task_stats = {}
        
        # Get self-care tasks per day
        self_care_per_day = {}
        for date_str, group in completed.groupby(completed['completed_date']):
            date_key = date_str.strftime('%Y-%m-%d')
            if 'task_type' in group.columns:
                task_types = group['task_type'].astype(str).str.lower()
            else:
                task_types = pd.Series(['work'] * len(group), index=group.index)
            self_care_count = len(task_types[task_types.isin(['self care', 'selfcare', 'self-care'])])
            self_care_per_day[date_key] = self_care_count
        
        # Get work/play time per day
        work_play_time = {}
        for date_str, group in completed.groupby(completed['completed_date']):
            date_key = date_str.strftime('%Y-%m-%d')
            if 'task_type' in group.columns:
                task_types = group['task_type'].astype(str).str.lower()
            else:
                task_types = pd.Series(['work'] * len(group), index=group.index)
            durations = pd.to_numeric(group['duration_minutes'], errors='coerce').fillna(0)
            work_mask = task_types == 'work'
            play_mask = task_types == 'play'
            work_time = durations[work_mask].sum()
            play_time = durations[play_mask].sum()
            work_play_time[date_key] = {'work_time': work_time, 'play_time': play_time}
        
        # Calculate weekly average time
        weekly_avg_time = 0.0
        try:
            work_volume_metrics = analytics.get_daily_work_volume_metrics(days=7)
            weekly_avg_time = work_volume_metrics.get('avg_daily_work_time', 0.0) * 7.0
        except Exception:
            pass
        
        # Calculate scores for each completed instance
        productivity_scores_list = []
        grit_scores_list = []
        task_ids_list = []
        task_names_list = []
        
        for _, row in completed.iterrows():
            try:
                # Productivity score
                prod_score = analytics.calculate_productivity_score(
                    row=row,
                    self_care_tasks_per_day=self_care_per_day,
                    weekly_avg_time=weekly_avg_time,
                    work_play_time_per_day=work_play_time
                )
                
                # Grit score
                grit_score = analytics.calculate_grit_score(
                    row=row,
                    task_completion_counts=task_completion_counts_dict
                )
                
                task_id = row['task_id']
                task_row = tasks_df[tasks_df['task_id'] == task_id]
                task_name = task_row.iloc[0]['name'] if not task_row.empty else task_id
                
                productivity_scores_list.append(prod_score)
                grit_scores_list.append(grit_score)
                task_ids_list.append(task_id)
                task_names_list.append(task_name)
                
            except Exception as e:
                # Skip if calculation fails
                continue
        
        if not productivity_scores_list:
            with ui.card().classes("w-full max-w-4xl p-6 bg-yellow-50 border border-yellow-200"):
                ui.label("Unable to Calculate Scores").classes("text-lg font-semibold text-yellow-800 mb-2")
                ui.label("Could not calculate productivity and grit scores for any tasks.").classes("text-yellow-700")
            ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")
            return
        
        # Create DataFrame with scores
        scores_df = pd.DataFrame({
            'task_id': task_ids_list,
            'task_name': task_names_list,
            'productivity': productivity_scores_list,
            'grit': grit_scores_list
        })
        
        # Calculate average scores per task
        task_averages = scores_df.groupby('task_id').agg({
            'task_name': 'first',
            'productivity': 'mean',
            'grit': 'mean'
        }).reset_index()
        
        # Calculate instance counts per task
        instance_counts = scores_df.groupby('task_id').size().reset_index(name='instance_count')
        task_averages = task_averages.merge(instance_counts, on='task_id')
        
        # Filter to tasks with at least 2 instances for more reliable averages
        task_averages_filtered = task_averages[task_averages['instance_count'] >= 2].copy()
        
        # Summary Statistics
        with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
            ui.label("Summary Statistics").classes("text-xl font-semibold mb-4")
            
            overall_prod_avg = scores_df['productivity'].mean()
            overall_grit_avg = scores_df['grit'].mean()
            correlation = scores_df['productivity'].corr(scores_df['grit'])
            
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    ui.label("Overall Average Productivity").classes("font-semibold")
                    ui.label(f"{overall_prod_avg:.2f}").classes("text-lg")
                
                with ui.column().classes("flex-1"):
                    ui.label("Overall Average Grit").classes("font-semibold")
                    ui.label(f"{overall_grit_avg:.2f}").classes("text-lg")
                
                with ui.column().classes("flex-1"):
                    ui.label("Correlation (r)").classes("font-semibold")
                    ui.label(f"{correlation:.3f}").classes("text-lg")
                
                with ui.column().classes("flex-1"):
                    ui.label("Tasks Analyzed").classes("font-semibold")
                    ui.label(f"{len(task_averages_filtered)} tasks").classes("text-lg")
        
        # Interpretation
        with ui.card().classes("w-full max-w-4xl p-6 mb-6 bg-blue-50 border border-blue-200"):
            ui.label("Understanding the Metrics").classes("text-lg font-semibold mb-2")
            ui.label(
                "• Productivity Score: Rewards efficiency - completing tasks quickly relative to estimates\n"
                "• Grit Score: Rewards persistence - doing the same task multiple times and spending adequate time\n"
                "• These metrics often trade off: efficient tasks (high productivity) may have lower grit, "
                "while persistent/repeated tasks (high grit) may sacrifice efficiency."
            ).classes("text-sm text-blue-900 whitespace-pre-line")
        
        if len(task_averages_filtered) > 0:
            # Calculate quadrants (based on median split)
            prod_median = task_averages_filtered['productivity'].median()
            grit_median = task_averages_filtered['grit'].median()
            
            # Categorize tasks
            def categorize_task(row):
                prod = row['productivity']
                grit = row['grit']
                if prod >= prod_median and grit >= grit_median:
                    return 'High Both'
                elif prod >= prod_median and grit < grit_median:
                    return 'High Prod, Low Grit'
                elif prod < prod_median and grit >= grit_median:
                    return 'Low Prod, High Grit'
                else:
                    return 'Low Both'
            
            task_averages_filtered['category'] = task_averages_filtered.apply(categorize_task, axis=1)
            
            # Quadrant Analysis
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Quadrant Analysis").classes("text-xl font-semibold mb-4")
                ui.label(f"Median split: Productivity ≥ {prod_median:.1f}, Grit ≥ {grit_median:.1f}").classes("text-sm text-gray-600 mb-4")
                
                category_counts = task_averages_filtered['category'].value_counts()
                
                with ui.row().classes("w-full gap-4"):
                    for category in ['High Both', 'High Prod, Low Grit', 'Low Prod, High Grit', 'Low Both']:
                        count = category_counts.get(category, 0)
                        with ui.column().classes("flex-1 p-3 border border-gray-300 rounded"):
                            ui.label(category).classes("font-semibold text-sm")
                            ui.label(f"{count} tasks").classes("text-xl")
            
            # Scatter Plot
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Productivity vs Grit Scatter Plot").classes("text-xl font-semibold mb-4")
                ui.label("Each point represents a task (averaged across all instances). Hover to see task name and details.").classes("text-sm text-gray-600 mb-4")
                
                fig = go.Figure()
                
                # Color by category
                colors = {
                    'High Both': '#22c55e',  # Green
                    'High Prod, Low Grit': '#3b82f6',  # Blue
                    'Low Prod, High Grit': '#f59e0b',  # Orange
                    'Low Both': '#ef4444'  # Red
                }
                
                for category in ['High Both', 'High Prod, Low Grit', 'Low Prod, High Grit', 'Low Both']:
                    category_data = task_averages_filtered[task_averages_filtered['category'] == category]
                    if not category_data.empty:
                        fig.add_trace(go.Scatter(
                            x=category_data['productivity'],
                            y=category_data['grit'],
                            mode='markers+text',
                            name=category,
                            text=category_data['task_name'],
                            textposition="top center",
                            textfont=dict(size=10),
                            marker=dict(
                                size=10 + category_data['instance_count'] * 2,  # Size by instance count
                                color=colors[category],
                                opacity=0.7,
                                line=dict(width=1, color='white')
                            ),
                            hovertemplate='<b>%{text}</b><br>' +
                                        'Productivity: %{x:.2f}<br>' +
                                        'Grit: %{y:.2f}<br>' +
                                        'Instances: %{customdata}<extra></extra>',
                            customdata=category_data['instance_count']
                        ))
                
                # Add median lines
                fig.add_hline(y=grit_median, line_dash="dash", line_color="gray", 
                            annotation_text=f"Grit Median ({grit_median:.1f})", annotation_position="right")
                fig.add_vline(x=prod_median, line_dash="dash", line_color="gray",
                            annotation_text=f"Prod Median ({prod_median:.1f})", annotation_position="top")
                
                fig.update_layout(
                    xaxis_title="Average Productivity Score",
                    yaxis_title="Average Grit Score",
                    hovermode='closest',
                    height=600,
                    showlegend=True
                )
                
                ui.plotly(fig).classes("w-full")
            
            # Task Lists by Quadrant
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("Tasks by Quadrant").classes("text-xl font-semibold mb-4")
                
                with ui.column().classes("w-full gap-4"):
                    for category in ['High Prod, Low Grit', 'Low Prod, High Grit', 'High Both', 'Low Both']:
                        category_tasks = task_averages_filtered[task_averages_filtered['category'] == category].sort_values(
                            by=['productivity', 'grit'], ascending=[False, False]
                        )
                        
                        if not category_tasks.empty:
                            with ui.expansion(f"{category} ({len(category_tasks)} tasks)", icon="info").classes("w-full"):
                                with ui.column().classes("w-full gap-2 mt-2"):
                                    for _, task_row in category_tasks.iterrows():
                                        with ui.card().classes("p-3 border border-gray-200"):
                                            with ui.row().classes("w-full items-center justify-between"):
                                                ui.label(task_row['task_name']).classes("font-semibold")
                                                with ui.row().classes("gap-4"):
                                                    ui.label(f"Prod: {task_row['productivity']:.1f}").classes("text-sm")
                                                    ui.label(f"Grit: {task_row['grit']:.1f}").classes("text-sm")
                                                    ui.label(f"({task_row['instance_count']} instances)").classes("text-xs text-gray-500")
            
            # Top Tasks Table
            with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
                ui.label("All Tasks (Sorted by Productivity)").classes("text-xl font-semibold mb-4")
                
                sorted_tasks = task_averages_filtered.sort_values('productivity', ascending=False)
                
                with ui.column().classes("w-full gap-2"):
                    # Header
                    with ui.row().classes("w-full font-semibold border-b pb-2"):
                        ui.label("Task Name").classes("flex-1")
                        ui.label("Prod Avg").classes("flex-0 w-24 text-center")
                        ui.label("Grit Avg").classes("flex-0 w-24 text-center")
                        ui.label("Difference").classes("flex-0 w-24 text-center")
                        ui.label("Instances").classes("flex-0 w-20 text-center")
                    
                    for _, task_row in sorted_tasks.iterrows():
                        diff = task_row['productivity'] - task_row['grit']
                        diff_class = "text-green-600" if diff > 0 else "text-red-600" if diff < 0 else ""
                        
                        with ui.row().classes("w-full border-b pb-2"):
                            ui.label(task_row['task_name']).classes("flex-1 text-sm")
                            ui.label(f"{task_row['productivity']:.1f}").classes("flex-0 w-24 text-center text-sm")
                            ui.label(f"{task_row['grit']:.1f}").classes("flex-0 w-24 text-center text-sm")
                            ui.label(f"{diff:+.1f}").classes(f"flex-0 w-24 text-center text-sm font-semibold {diff_class}")
                            ui.label(f"{task_row['instance_count']}").classes("flex-0 w-20 text-center text-xs text-gray-500")
        
        else:
            with ui.card().classes("w-full max-w-4xl p-6 bg-yellow-50 border border-yellow-200"):
                ui.label("Insufficient Data").classes("text-lg font-semibold text-yellow-800 mb-2")
                ui.label("Need at least 2 completed instances per task for reliable analysis. Complete more task instances to see analysis.").classes("text-yellow-700")
    
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"[Productivity-Grit Tradeoff] Error: {error_msg}")
        
        with ui.card().classes("w-full max-w-4xl p-6 bg-red-50 border border-red-200"):
            ui.label("Error Loading Data").classes("text-lg font-semibold text-red-800 mb-2")
            ui.label(f"An error occurred: {str(e)}").classes("text-red-700")
            with ui.expansion("Technical Details", icon="info").classes("w-full mt-2"):
                ui.code(error_msg).classes("text-xs")
    
    ui.button("Back to Experimental", on_click=lambda: ui.navigate.to("/experimental")).classes("mt-4")

