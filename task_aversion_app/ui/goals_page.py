"""Goals page - Landing page for goal tracking features."""
from nicegui import ui
from fastapi import Request
import pandas as pd
from backend.user_state import UserStateManager
from backend.task_manager import TaskManager
from backend.analytics import Analytics
from backend.auth import get_current_user

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"
task_manager = TaskManager()
analytics = Analytics()

# Define the priority milestones
MILESTONES = [
    {
        'id': 'recommendation_refinement',
        'title': 'Recommendation System Refinement',
        'description': 'Quick win, high impact - improve recommendation algorithm effectiveness',
        'priority': 1
    },
    {
        'id': 'robust_scores',
        'title': 'More Robust Scores',
        'description': 'Foundation for everything else - enhance score calculations',
        'priority': 2
    },
    {
        'id': 'representative_composite',
        'title': 'More Representative Composite',
        'description': 'Depends on robust scores - improve composite score representation',
        'priority': 3
    },
    {
        'id': 'jobs_system',
        'title': 'Jobs System',
        'description': 'Organizes your 37 tasks; plan exists',
        'priority': 4
    },
    {
        'id': 'cleaner_interface',
        'title': 'Cleaner Interface/Visuals',
        'description': 'Important for public release - improve UI/UX',
        'priority': 5
    },
    {
        'id': 'website_preparation',
        'title': 'Website Preparation',
        'description': 'Big milestone; OAuth plan exists - prepare for public deployment',
        'priority': 6
    }
]


@ui.page("/goals")
def goals_page(request: Request = None):
    """Goals landing page."""
    
    # Get current user for data isolation
    current_user_id = get_current_user()
    if current_user_id is None:
        ui.navigate.to('/login')
        return
    
    ui.label("Goals").classes("text-3xl font-bold mb-4")
    ui.label("Track and manage your productivity and performance goals.").classes("text-gray-600 mb-6")
    
    # Milestone Tracking Section
    with ui.card().classes("w-full max-w-4xl p-6 mb-6"):
        ui.label("Development Milestones").classes("text-xl font-semibold mb-4")
        ui.label("Track progress on key development priorities.").classes("text-sm text-gray-600 mb-4")
        
        milestones_data = user_state.get_milestones(DEFAULT_USER_ID)
        
        for milestone in MILESTONES:
            milestone_id = milestone['id']
            milestone_info = milestones_data.get(milestone_id, {})
            status = milestone_info.get('status', 'not_started')
            notes = milestone_info.get('notes', '')
            
            with ui.card().classes("p-4 mb-3 border border-gray-300"):
                with ui.row().classes("w-full items-start gap-4"):
                    with ui.column().classes("flex-1 gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(f"#{milestone['priority']}").classes("text-sm font-bold text-gray-500")
                            ui.label(milestone['title']).classes("text-lg font-semibold")
                            # Status badge
                            status_colors = {
                                'not_started': 'bg-gray-200 text-gray-700',
                                'in_progress': 'bg-blue-200 text-blue-800',
                                'completed': 'bg-green-200 text-green-800'
                            }
                            status_labels = {
                                'not_started': 'Not Started',
                                'in_progress': 'In Progress',
                                'completed': 'Completed'
                            }
                            ui.badge(
                                status_labels.get(status, 'Not Started'),
                                color=status_colors.get(status, 'bg-gray-200').split()[0].replace('bg-', '')
                            ).classes("ml-2")
                        
                        ui.label(milestone['description']).classes("text-sm text-gray-700")
                        
                        if notes:
                            with ui.card().classes("mt-2 p-2 bg-gray-50"):
                                ui.label("Notes:").classes("text-xs font-semibold text-gray-600")
                                ui.label(notes).classes("text-xs text-gray-700")
                    
                    # Status selector
                    with ui.column().classes("gap-2"):
                        status_select = ui.select(
                            options={
                                'not_started': 'Not Started',
                                'in_progress': 'In Progress',
                                'completed': 'Completed'
                            },
                            value=status,
                            label="Status"
                        ).props("dense outlined").classes("min-w-[150px]")
                        
                        notes_input = ui.textarea(
                            label="Notes",
                            value=notes,
                            placeholder="Add notes about this milestone..."
                        ).props("dense outlined").classes("min-w-[200px]")
                        
                        def update_milestone(m_id=milestone_id):
                            new_status = status_select.value
                            new_notes = notes_input.value or ""
                            user_state.update_milestone(m_id, new_status, new_notes, DEFAULT_USER_ID)
                            ui.notify("Milestone updated!", color="positive")
                            ui.navigate.to("/goals")
                        
                        ui.button("Update", on_click=update_milestone).classes("bg-blue-500 text-white")
    
    # Goals List
    with ui.card().classes("w-full max-w-4xl p-6"):
        ui.label("Available Goals").classes("text-xl font-semibold mb-4")
        
        # Productivity Hours Goal Tracking
        with ui.card().classes("p-4 mb-4 border border-gray-300"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Productivity Hours Goal Tracking").classes("text-lg font-semibold")
                    ui.label(
                        "Track weekly productivity hours vs goals with rolling 7-day or "
                        "Monday-based week calculations. Includes daily trend visualization "
                        "and pace projection."
                    ).classes("text-sm text-gray-700")
                ui.button(
                    "Open",
                    on_click=lambda: ui.navigate.to("/goals/productivity-hours")
                ).classes("bg-blue-500 text-white ml-4")
        
        # Task Template Goals Section
        with ui.card().classes("p-4 mb-4 border border-gray-300"):
            ui.label("Task Template Goals").classes("text-lg font-semibold mb-2")
            ui.label(
                "Set goals for specific task templates. Track completion frequency, "
                "target relief scores, and other metrics per template. Baselines are "
                "calculated automatically from your historical data."
            ).classes("text-sm text-gray-700 mb-4")
            
            # Get all task templates
            try:
                all_tasks = task_manager.get_all(user_id=current_user_id)
                if not all_tasks.empty:
                    # Get template goals from user state
                    template_goals = user_state.get_template_goals(DEFAULT_USER_ID)
                    
                    # Show a few templates as examples (limit to 5 for now)
                    task_sample = all_tasks.head(10)
                    
                    with ui.expansion("View/Edit Template Goals", icon='assignment').classes("w-full"):
                        for idx, task_row in task_sample.iterrows():
                            task_id = task_row.get('task_id', '')
                            task_name = task_row.get('name', 'Unknown Task')
                            task_type = task_row.get('task_type', 'Work')
                            
                            if not task_id:
                                continue
                            
                            goal_data = template_goals.get(task_id, {})
                            
                            with ui.card().classes("p-3 mb-2 bg-gray-50"):
                                with ui.row().classes("w-full items-start gap-4"):
                                    with ui.column().classes("flex-1 gap-2"):
                                        ui.label(f"{task_name} ({task_type})").classes("text-sm font-semibold")
                                        
                                        # Calculate baseline from historical data
                                        try:
                                            # Get completed instances for this task
                                            from backend.instance_manager import InstanceManager
                                            im = InstanceManager()
                                            instances = im.get_all_instances()
                                            task_instances = instances[instances['task_id'] == task_id]
                                            completed = task_instances[task_instances['status'] == 'completed']
                                            
                                            if not completed.empty:
                                                avg_relief = completed['relief_score'].mean() if 'relief_score' in completed.columns else None
                                                avg_duration = completed['duration_minutes'].mean() if 'duration_minutes' in completed.columns else None
                                                completion_count = len(completed)
                                                
                                                baseline_text = f"Baseline: {completion_count} completions"
                                                if avg_relief is not None and not pd.isna(avg_relief):
                                                    baseline_text += f", {avg_relief:.1f} avg relief"
                                                if avg_duration is not None and not pd.isna(avg_duration):
                                                    baseline_text += f", {avg_duration:.1f} min avg"
                                                ui.label(baseline_text).classes("text-xs text-gray-600")
                                            else:
                                                ui.label("No baseline data yet").classes("text-xs text-gray-500")
                                        except Exception as e:
                                            ui.label("Baseline calculation unavailable").classes("text-xs text-gray-500")
                                    
                                    with ui.column().classes("gap-2 min-w-[200px]"):
                                        # Goal inputs
                                        target_freq = ui.number(
                                            label="Target completions/week",
                                            value=float(goal_data.get('target_frequency', 0)) if goal_data.get('target_frequency') else None,
                                            min=0,
                                            max=50,
                                            step=1
                                        ).props("dense outlined")
                                        
                                        target_relief = ui.number(
                                            label="Target avg relief",
                                            value=float(goal_data.get('target_relief', 0)) if goal_data.get('target_relief') else None,
                                            min=0,
                                            max=100,
                                            step=1
                                        ).props("dense outlined")
                                        
                                        def save_template_goal(t_id=task_id):
                                            goal = {
                                                'target_frequency': float(target_freq.value) if target_freq.value else None,
                                                'target_relief': float(target_relief.value) if target_relief.value else None,
                                            }
                                            # Remove None values
                                            goal = {k: v for k, v in goal.items() if v is not None}
                                            user_state.update_template_goal(t_id, goal, DEFAULT_USER_ID)
                                            ui.notify("Template goal saved!", color="positive")
                                        
                                        ui.button("Save Goal", on_click=save_template_goal).classes("bg-green-500 text-white text-xs")
                else:
                    ui.label("No task templates found. Create some tasks first!").classes("text-sm text-gray-500")
            except Exception as e:
                ui.label(f"Error loading templates: {str(e)}").classes("text-sm text-red-500")
        
        # Placeholder for future goals
        with ui.card().classes("p-4 bg-gray-50 border border-gray-200"):
            ui.label("More goal tracking features coming soon...").classes("text-sm text-gray-500 italic")
    
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4")

