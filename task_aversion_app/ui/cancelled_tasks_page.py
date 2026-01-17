from typing import Optional
from nicegui import ui
from backend.instance_manager import InstanceManager
from backend.user_state import UserStateManager
from backend.task_manager import TaskManager
from backend.auth import get_current_user
from backend.security_utils import escape_for_display
from ui.error_reporting import handle_error_with_ui
import json
import re
from collections import defaultdict
from datetime import datetime

im = InstanceManager()
user_state = UserStateManager()
task_manager = TaskManager()
DEFAULT_USER_ID = "default_user"

# Default cancellation categories
DEFAULT_CANCELLATION_CATEGORIES = {
    'did_while_another_active': 'Did task while another task was active',
    'deferred_to_plan': 'Deferred to plan instead of executing',
    'development_test': 'Development/test task',
    'accidental_initialization': 'Accidentally initialized',
    'failed_to_complete': 'Failed to complete task',
    'other': 'Other reason'
}


def get_all_cancellation_categories(user_id: Optional[int] = None):
    """Get all cancellation categories (default + custom).
    
    Args:
        user_id: User ID to get custom categories for. If None, gets current user.
    """
    if user_id is None:
        from backend.auth import get_current_user
        user_id = get_current_user()
    user_id_str = str(user_id) if user_id is not None else DEFAULT_USER_ID
    custom_categories = user_state.get_cancellation_categories(user_id_str)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


def sanitize_category_key(key: str) -> str:
    """Convert a label to a valid category key (lowercase, underscores, no spaces)."""
    # Convert to lowercase and replace spaces/special chars with underscores
    key = re.sub(r'[^a-z0-9_]', '_', key.lower())
    # Remove multiple underscores
    key = re.sub(r'_+', '_', key)
    # Remove leading/trailing underscores
    key = key.strip('_')
    return key or 'custom_category'


def get_cancellation_penalties(user_id: Optional[int] = None):
    """Get cancellation penalty configuration."""
    if user_id is None:
        from backend.auth import get_current_user
        user_id = get_current_user()
    user_id_str = str(user_id) if user_id is not None else DEFAULT_USER_ID
    
    penalties = user_state.get_cancellation_penalties(user_id_str)
    if not penalties:
        # Default penalties
        return {
            'development_test': 0.0,
            'accidental_initialization': 0.0,
            'deferred_to_plan': 0.1,  # 10% penalty (underestimation factor)
            'did_while_another_active': 0.0,  # No penalty if done elsewhere
            'failed_to_complete': 1.0,  # Full penalty (planned but not done)
            'other': 0.5  # Default 50% penalty
        }
    return penalties


@ui.page("/cancelled-tasks")
def cancelled_tasks_page():
    # Get current user ID
    user_id = get_current_user()
    if user_id is None:
        ui.navigate.to('/login')
        return
    
    user_id_str = str(user_id) if user_id is not None else DEFAULT_USER_ID
    
    ui.label("Cancelled Tasks Analytics").classes("text-2xl font-bold mb-4")
    ui.label("View and analyze cancelled task patterns. Edit tasks and configure penalties in Settings.").classes("text-gray-600 mb-4")
    
    # Create view container and refresh function first
    view_container = ui.column().classes("w-full")
    
    # Define render functions (they'll access refresh_view via closure)
    def render_task_list(instances, refresh_callback=None):
        """Render a list of cancelled task instances."""
        with ui.column().classes("w-full gap-2 mt-2"):
            for inst in instances:
                instance_id = inst.get('instance_id', '')
                
                with ui.card().classes("w-full p-3 border border-gray-200"):
                    with ui.row().classes("w-full items-start justify-between gap-3"):
                        with ui.column().classes("flex-1 gap-1"):
                            ui.label(escape_for_display(inst.get('task_name', 'Unknown Task'))).classes("text-base font-semibold")
                            ui.label(f"Instance ID: {instance_id}").classes("text-xs text-gray-500")
                            
                            # Parse actual data to get category and notes
                            actual_data = inst.get('actual', '{}')
                            if isinstance(actual_data, str):
                                try:
                                    actual_data = json.loads(actual_data)
                                except:
                                    actual_data = {}
                            
                            category = actual_data.get('cancellation_category', 'other')
                            all_categories = get_all_cancellation_categories(user_id=user_id)
                            category_label = all_categories.get(category, category or 'Other reason')
                            notes = actual_data.get('reason_for_canceling', '')
                            
                            # Get penalty for this category
                            penalties = get_cancellation_penalties(user_id=user_id)
                            penalty = penalties.get(category, 0.5)
                            
                            with ui.row().classes("items-center gap-2 mt-1"):
                                ui.label("Category:").classes("text-xs text-gray-600 font-semibold")
                                ui.label(category_label).classes("text-xs bg-orange-100 text-orange-800 px-2 py-1 rounded")
                                ui.label(f"Penalty: {penalty*100:.0f}%").classes("text-xs bg-red-100 text-red-800 px-2 py-1 rounded")
                            
                            if notes:
                                with ui.row().classes("items-start gap-2 mt-1"):
                                    ui.label("Notes:").classes("text-xs text-gray-600 font-semibold")
                                    ui.label(escape_for_display(notes)).classes("text-xs text-gray-700 flex-1")
                            
                            cancelled_at = inst.get('cancelled_at', '')
                            if cancelled_at:
                                ui.label(f"Cancelled: {cancelled_at}").classes("text-xs text-gray-500 mt-1")
                        
                        # Show task details
                        with ui.column().classes("text-right gap-1 items-end"):
                            created_at = inst.get('created_at', '')
                            if created_at:
                                ui.label(f"Created: {created_at}").classes("text-xs text-gray-400")
                            
                            initialized_at = inst.get('initialized_at', '')
                            if initialized_at:
                                ui.label(f"Initialized: {initialized_at}").classes("text-xs text-gray-400")
                            
                            def edit_cancelled_task(inst_id=instance_id, inst_data=inst):
                                """Open dialog to edit cancelled task category and notes."""
                                # Parse actual data
                                actual_data = inst_data.get('actual', '{}')
                                if isinstance(actual_data, str):
                                    try:
                                        actual_data = json.loads(actual_data)
                                    except:
                                        actual_data = {}
                                
                                current_category = actual_data.get('cancellation_category', 'other')
                                current_notes = actual_data.get('reason_for_canceling', '')
                                
                                with ui.dialog() as dialog, ui.card().classes("w-full max-w-md p-4 gap-3"):
                                    ui.label("Edit Cancelled Task").classes("text-lg font-semibold")
                                    
                                    all_cats = get_all_cancellation_categories(user_id=user_id)
                                    edit_category_select = ui.select(
                                        options=all_cats,
                                        label='Cancellation Category',
                                        value=current_category
                                    ).classes("w-full").props("dense outlined")
                                    
                                    edit_notes_textarea = ui.textarea(
                                        label='Additional Notes',
                                        value=current_notes,
                                        placeholder='Any additional details...'
                                    ).classes("w-full")
                                    
                                    def save_edit():
                                        new_category = edit_category_select.value
                                        new_notes = edit_notes_textarea.value.strip() if edit_notes_textarea.value else ''
                                        
                                        if not new_category:
                                            ui.notify("Please select a category", color="negative")
                                            return
                                        
                                        try:
                                            cancellation_data = {
                                                'cancellation_category': new_category,
                                                'reason_for_canceling': new_notes
                                            }
                                            im.update_cancelled_instance(inst_id, cancellation_data)
                                            dialog.close()
                                            if refresh_callback:
                                                refresh_callback()
                                            else:
                                                ui.navigate.reload()
                                            ui.notify("Cancelled task updated", color="positive")
                                        except Exception as e:
                                            handle_error_with_ui(
                                                'update_cancelled_task',
                                                e,
                                                user_id=get_current_user(),
                                                context={'instance_id': inst_id}
                                            )
                                    
                                    with ui.row().classes("w-full justify-end gap-2 mt-2"):
                                        ui.button("Cancel", on_click=dialog.close).classes("bg-gray-500 text-white")
                                        ui.button("Save", on_click=save_edit, color="positive").classes("bg-green-500 text-white")
                                
                                dialog.open()
                            
                            ui.button("Edit", on_click=lambda inst_id=instance_id: edit_cancelled_task(inst_id, inst)).classes("text-xs bg-blue-500 text-white mt-2")
    
    def render_by_category(instances):
        """Group cancelled tasks by cancellation category."""
        if not instances:
            ui.label("No cancelled tasks found.").classes("text-gray-500 p-4")
            return
        
        # Group by category
        by_category = defaultdict(list)
        all_categories = get_all_cancellation_categories(user_id=user_id)
        
        for inst in instances:
            actual_data = inst.get('actual', '{}')
            if isinstance(actual_data, str):
                try:
                    actual_data = json.loads(actual_data)
                except:
                    actual_data = {}
            category = actual_data.get('cancellation_category', 'other')
            category_label = all_categories.get(category, category or 'Other reason')
            by_category[category_label].append(inst)
        
        ui.label(f"Total: {len(instances)} cancelled task(s)").classes("text-sm font-semibold mb-3")
        
        # Sort by count (most cancelled first)
        sorted_categories = sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True)
        
        for category_label, category_instances in sorted_categories:
            with ui.expansion(f"{category_label} ({len(category_instances)} task(s))", icon='cancel').classes("w-full mb-2"):
                render_task_list(category_instances, refresh_view)
    
    def render_by_task_template(instances):
        """Group cancelled tasks by task template (task_name)."""
        if not instances:
            ui.label("No cancelled tasks found.").classes("text-gray-500 p-4")
            return
        
        # Group by task name
        by_task = defaultdict(list)
        
        for inst in instances:
            task_name = inst.get('task_name', 'Unknown Task')
            by_task[task_name].append(inst)
        
        ui.label(f"Total: {len(instances)} cancelled task(s)").classes("text-sm font-semibold mb-3")
        
        # Sort by count (most cancelled first)
        sorted_tasks = sorted(by_task.items(), key=lambda x: len(x[1]), reverse=True)
        
        for task_name, task_instances in sorted_tasks:
            with ui.expansion(f"{task_name} ({len(task_instances)} cancellation(s))", icon='task').classes("w-full mb-2"):
                render_task_list(task_instances, refresh_view)
    
    def render_all_tasks(instances):
        """Render all cancelled tasks in a flat list."""
        if not instances:
            ui.label("No cancelled tasks found.").classes("text-gray-500 p-4")
            return
        
        ui.label(f"Total: {len(instances)} cancelled task(s)").classes("text-sm font-semibold mb-3")
        render_task_list(instances, refresh_view)
    
    # View mode selector
    view_mode = ui.radio(
        ['By Category', 'By Task Template', 'All Tasks'],
        value='By Category'
    ).classes("mb-4").props("inline")
    
    # Filter controls
    with ui.row().classes("w-full gap-3 items-end mb-4"):
        category_filter = ui.select(
            options={'all': 'All Categories', **get_all_cancellation_categories(user_id=user_id)},
            label='Filter by Category',
            value='all'
        ).classes("flex-1").props("dense outlined")
        
        def refresh_category_filter():
            """Refresh the category filter dropdown options."""
            current_value = category_filter.value
            new_options = {'all': 'All Categories', **get_all_cancellation_categories(user_id=user_id)}
            # Update options - try set_options first, fall back to direct assignment
            if hasattr(category_filter, 'set_options'):
                category_filter.set_options(new_options)
            else:
                category_filter.options = new_options
            # Restore the current value if it still exists, otherwise set to 'all'
            if current_value and current_value in new_options:
                category_filter.set_value(current_value)
            else:
                category_filter.set_value('all')
        
        def refresh_view():
            view_container.clear()
            with view_container:
                try:
                    cancelled_instances = im.list_cancelled_instances(user_id=user_id)
                    
                    # Filter by category if selected
                    selected_category = category_filter.value
                    if selected_category and selected_category != 'all':
                        filtered_instances = []
                        for inst in cancelled_instances:
                            actual_data = inst.get('actual', '{}')
                            if isinstance(actual_data, str):
                                try:
                                    actual_data = json.loads(actual_data)
                                except:
                                    actual_data = {}
                            inst_category = actual_data.get('cancellation_category', 'other')
                            if inst_category == selected_category:
                                filtered_instances.append(inst)
                        cancelled_instances = filtered_instances
                    
                    mode = view_mode.value
                    
                    if mode == 'By Category':
                        render_by_category(cancelled_instances)
                    elif mode == 'By Task Template':
                        render_by_task_template(cancelled_instances)
                    else:
                        render_all_tasks(cancelled_instances)
                except Exception as e:
                    handle_error_with_ui(
                        'load_cancelled_tasks',
                        e,
                        user_id=get_current_user()
                    )
                    ui.label("Error loading cancelled tasks. Please try refreshing.").classes("text-red-500 p-4")
        
        ui.button("Refresh", on_click=refresh_view).classes("bg-blue-500 text-white")
    
    # Add view container to page
    view_container
    
    # Initial load
    view_mode.on('update:model-value', lambda: refresh_view())
    category_filter.on('update:model-value', lambda: refresh_view())
    refresh_view()
    
    # Statistics Section
    ui.separator().classes("my-6")
    with ui.card().classes("w-full max-w-4xl p-4 gap-3"):
        ui.label("Cancellation Statistics").classes("text-lg font-semibold")
        ui.label("Configure penalties in Settings.").classes("text-sm text-gray-600 mb-3")
        
        def render_statistics():
            try:
                cancelled_instances = im.list_cancelled_instances(user_id=user_id)
                
                if not cancelled_instances:
                    ui.label("No cancelled tasks to analyze.").classes("text-gray-500 p-4")
                    return
                
                # Statistics by category
                by_category = defaultdict(int)
                by_task = defaultdict(int)
                total_penalty = 0.0
                penalties = get_cancellation_penalties(user_id=user_id)
                
                for inst in cancelled_instances:
                    actual_data = inst.get('actual', '{}')
                    if isinstance(actual_data, str):
                        try:
                            actual_data = json.loads(actual_data)
                        except:
                            actual_data = {}
                    
                    category = actual_data.get('cancellation_category', 'other')
                    task_name = inst.get('task_name', 'Unknown Task')
                    
                    by_category[category] += 1
                    by_task[task_name] += 1
                    
                    # Calculate penalty impact
                    penalty = penalties.get(category, 0.5)
                    predicted = inst.get('predicted', '{}')
                    if isinstance(predicted, str):
                        try:
                            predicted = json.loads(predicted)
                        except:
                            predicted = {}
                    time_estimate = float(predicted.get('time_estimate_minutes', 0) or 0)
                    total_penalty += (time_estimate / 10.0) * penalty
                
                all_categories = get_all_cancellation_categories(user_id=user_id)
                
                with ui.column().classes("w-full gap-4"):
                    # Category breakdown
                    ui.label("By Cancellation Category").classes("text-base font-semibold")
                    with ui.card().classes("w-full p-3"):
                        sorted_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
                        for cat_key, count in sorted_categories:
                            cat_label = all_categories.get(cat_key, cat_key)
                            penalty = penalties.get(cat_key, 0.5)
                            with ui.row().classes("items-center justify-between w-full mb-2"):
                                ui.label(f"{escape_for_display(cat_label)}: {count}").classes("text-sm")
                                ui.label(f"Penalty: {penalty*100:.0f}%").classes("text-xs text-gray-500")
                    
                    # Task breakdown
                    ui.label("Most Cancelled Tasks").classes("text-base font-semibold")
                    with ui.card().classes("w-full p-3"):
                        sorted_tasks = sorted(by_task.items(), key=lambda x: x[1], reverse=True)[:10]
                        for task_name, count in sorted_tasks:
                            ui.label(f"{escape_for_display(task_name)}: {count} cancellation(s)").classes("text-sm mb-1")
                    
                    # Total penalty impact
                    ui.label("Total Penalty Impact").classes("text-base font-semibold")
                    with ui.card().classes("w-full p-3"):
                        ui.label(f"Total Productivity Penalty: {total_penalty:.1f} points").classes("text-lg font-bold text-red-600")
                        ui.label(f"Based on {len(cancelled_instances)} cancelled task(s)").classes("text-xs text-gray-500")
            except Exception as e:
                handle_error_with_ui(
                    'calculate_cancelled_tasks_statistics',
                    e,
                    user_id=get_current_user()
                )
                ui.label("Error calculating statistics. Please try refreshing.").classes("text-red-500 p-4")
        
        render_statistics()
    
    # Cancellation Categories Management Section
    ui.separator().classes("my-6")
    with ui.card().classes("w-full max-w-4xl p-4 gap-3"):
        ui.label("Cancellation Categories").classes("text-lg font-semibold")
        ui.label("Manage custom cancellation categories. Default categories cannot be deleted.").classes("text-sm text-gray-600 mb-3")
        
        def refresh_categories_list():
            categories_list_container.clear()
            with categories_list_container:
                all_categories = get_all_cancellation_categories(user_id=user_id)
                user_id_str = str(user_id) if user_id is not None else DEFAULT_USER_ID
                custom_categories = user_state.get_cancellation_categories(user_id_str)
                
                if not all_categories:
                    ui.label("No categories found.").classes("text-gray-500 p-4")
                else:
                    with ui.column().classes("w-full gap-2"):
                        for cat_key, cat_label in sorted(all_categories.items()):
                            is_default = cat_key in DEFAULT_CANCELLATION_CATEGORIES
                            with ui.card().classes("w-full p-3 border border-gray-200"):
                                with ui.row().classes("w-full items-center justify-between gap-3"):
                                    with ui.column().classes("flex-1 gap-1"):
                                        ui.label(escape_for_display(cat_label)).classes("text-base font-semibold")
                                        ui.label(f"Key: {cat_key}").classes("text-xs text-gray-500")
                                        if is_default:
                                            ui.label("Default category").classes("text-xs text-blue-600")
                                    
                                    if not is_default:
                                        def delete_category(key=cat_key, uid=user_id_str):
                                            user_state.remove_cancellation_category(key, uid)
                                            refresh_categories_list()
                                            # Refresh the category filter dropdown
                                            refresh_category_filter()
                                            # Refresh the view to update category filters and lists
                                            refresh_view()
                                            ui.notify("Category deleted", color="positive")
                                        
                                        ui.button("Delete", on_click=lambda k=cat_key: delete_category(k, user_id_str), color="negative").classes("text-xs")
                        
                        # Add new category form
                        ui.separator().classes("my-2")
                        with ui.card().classes("w-full p-3 bg-gray-50 border border-gray-300"):
                            ui.label("Add New Category").classes("text-sm font-semibold mb-2")
                            with ui.row().classes("w-full gap-2 items-end"):
                                new_category_label_input = ui.input(
                                    label="Category Label",
                                    placeholder="e.g., Changed my mind"
                                ).classes("flex-1")
                                
                                def add_category():
                                    label = new_category_label_input.value.strip()
                                    if not label:
                                        ui.notify("Please enter a category label", color="negative")
                                        return
                                    
                                    # Generate key from label
                                    key = sanitize_category_key(label)
                                    
                                    # Check if key already exists
                                    all_cats = get_all_cancellation_categories(user_id=user_id)
                                    if key in all_cats:
                                        # Make it unique
                                        counter = 1
                                        original_key = key
                                        while key in all_cats:
                                            key = f"{original_key}_{counter}"
                                            counter += 1
                                    
                                    user_state.add_cancellation_category(key, label, user_id_str)
                                    new_category_label_input.set_value("")
                                    refresh_categories_list()
                                    # Refresh the category filter dropdown
                                    refresh_category_filter()
                                    # Refresh the view to update category filters and lists
                                    refresh_view()
                                    ui.notify("Category added", color="positive")
                                
                                ui.button("Add", on_click=add_category, color="positive").classes("bg-green-500 text-white")
        
        categories_list_container = ui.column().classes("w-full mt-3")
        refresh_categories_list()

