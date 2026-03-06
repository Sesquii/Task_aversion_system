from typing import Optional, Any
from nicegui import ui
from backend.instance_manager import InstanceManager
from backend.user_state import UserStateManager
from backend.task_manager import TaskManager
from backend.auth import get_current_user
from backend.security_utils import escape_for_display
from backend.app_time import format_for_display
from ui.error_reporting import handle_error_with_ui
import json
from datetime import datetime, date

im = InstanceManager()
user_state = UserStateManager()
task_manager = TaskManager()
DEFAULT_USER_ID = "default_user"

# Default cancellation categories (for cancelled task editing)
DEFAULT_CANCELLATION_CATEGORIES = {
    'did_while_another_active': 'Did task while another task was active',
    'deferred_to_plan': 'Deferred to plan instead of executing',
    'development_test': 'Development/test task',
    'accidental_initialization': 'Accidentally initialized',
    'failed_to_complete': 'Failed to complete task',
    'other': 'Other reason'
}

ITEMS_PER_PAGE = 25


def get_all_cancellation_categories(user_id: Optional[int] = None):
    """Get all cancellation categories (default + custom).
    
    Args:
        user_id: User ID to get custom categories for. If None, gets current user.
    """
    if user_id is None:
        user_id = get_current_user()
    user_id_str = str(user_id) if user_id is not None else DEFAULT_USER_ID
    custom_categories = user_state.get_cancellation_categories(user_id_str)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


def list_all_completed_instances(user_id: Optional[int] = None):
    """List all completed instances (not just recent ones).
    
    Args:
        user_id: User ID to filter instances by. If None, gets current user.
    """
    if user_id is None:
        user_id = get_current_user()
    
    if im.use_db:
        return _list_all_completed_instances_db(user_id=user_id)
    else:
        return _list_all_completed_instances_csv(user_id=user_id)


def _list_all_completed_instances_csv(user_id: Optional[int] = None):
    """CSV-specific list_all_completed_instances.
    
    Args:
        user_id: User ID to filter instances by. If None, returns empty for security.
    """
    if user_id is None:
        print("[TaskEditingManager] WARNING: _list_all_completed_instances_csv() called without user_id - returning empty for security")
        return []
    
    im._reload()
    df = im.df[im.df['completed_at'].astype(str).str.strip() != '']
    
    # Filter by user_id if column exists
    if 'user_id' in df.columns:
        # CSV stores user_id as string, so convert to string for comparison
        df = df[df['user_id'].astype(str) == str(user_id)]
    else:
        print("[TaskEditingManager] WARNING: user_id column not found in CSV - returning empty for security")
        return []
    
    if df.empty:
        return []
    df = df.sort_values("completed_at", ascending=False)
    return df.to_dict(orient="records")


def _list_all_completed_instances_db(user_id: Optional[int] = None):
    """Database-specific list_all_completed_instances.
    
    Args:
        user_id: User ID to filter instances by. If None, returns empty for security.
    """
    if user_id is None:
        print("[TaskEditingManager] WARNING: _list_all_completed_instances_db() called without user_id - returning empty for security")
        return []
    
    try:
        with im.db_session() as session:
            instances = session.query(im.TaskInstance).filter(
                im.TaskInstance.completed_at.isnot(None),
                im.TaskInstance.user_id == user_id
            ).order_by(
                im.TaskInstance.completed_at.desc()
            ).all()
            return [instance.to_dict() for instance in instances]
    except Exception as e:
        handle_error_with_ui(
            'list_completed_instances',
            e,
            user_id=user_id
        )
        return []


def get_all_tasks_chronologically(user_id: Optional[int] = None):
    """Get all completed and cancelled tasks, sorted by most recent timestamp first.
    
    Args:
        user_id: User ID to filter tasks by. If None, gets current user.
    """
    if user_id is None:
        user_id = get_current_user()
    
    if user_id is None:
        print("[TaskEditingManager] WARNING: get_all_tasks_chronologically() called without user_id - returning empty for security")
        return []
    
    completed = list_all_completed_instances(user_id=user_id)
    cancelled = im.list_cancelled_instances(user_id=user_id)
    
    # Add status label and timestamp to each task
    all_tasks = []
    
    for task in completed:
        task['_status'] = 'completed'
        task['_timestamp'] = task.get('completed_at', '')
        all_tasks.append(task)
    
    for task in cancelled:
        task['_status'] = 'cancelled'
        task['_timestamp'] = task.get('cancelled_at', '')
        all_tasks.append(task)
    
    # Sort by timestamp (most recent first)
    # Handle empty timestamps by putting them at the end
    def sort_key(task):
        timestamp = task.get('_timestamp', '')
        if not timestamp or timestamp.strip() == '':
            return ''
        # Use string comparison (ISO format timestamps sort correctly as strings)
        # Most timestamps are in format like "2024-01-15 10:30:00" which sorts correctly
        return timestamp
    
    all_tasks.sort(key=sort_key, reverse=True)

    return all_tasks


def _parse_timestamp_to_date(ts: Any) -> Optional[date]:
    """Parse completed_at/cancelled_at string to date for range comparison. Returns None if invalid."""
    if not ts or (isinstance(ts, str) and not ts.strip()):
        return None
    try:
        s = str(ts).strip()
        # Handle "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD"
        if " " in s:
            s = s.split(" ")[0]
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _task_matches_search(task: dict, query: str) -> bool:
    """Return True if task name or notes (actual JSON) contain the search query (case-insensitive)."""
    if not query or not query.strip():
        return True
    q = query.strip().lower()
    name = (task.get("task_name") or "")
    if q in name.lower():
        return True
    actual_raw = task.get("actual") or "{}"
    if isinstance(actual_raw, dict):
        actual_data = actual_raw
    else:
        try:
            actual_data = json.loads(actual_raw) if actual_raw else {}
        except json.JSONDecodeError:
            actual_data = {}
    # Search in common text fields
    for key in ("reason_for_canceling", "notes", "note", "description"):
        val = actual_data.get(key)
        if val and isinstance(val, str) and q in val.lower():
            return True
    return False


def _task_in_date_range(task: dict, date_from: Optional[date], date_to: Optional[date]) -> bool:
    """Return True if task timestamp falls within [date_from, date_to] (inclusive)."""
    ts = task.get("_timestamp")
    d = _parse_timestamp_to_date(ts)
    if d is None:
        return True  # Include tasks with no date when filtering by range
    if date_from is not None and d < date_from:
        return False
    if date_to is not None and d > date_to:
        return False
    return True


def mark_instance_as_edited(instance_id):
    """Mark an instance as edited by adding is_edited flag to actual data."""
    # Get current user for data isolation
    user_id = get_current_user()
    if user_id is None:
        print("[task_editing_manager] WARNING: mark_instance_as_edited() called without logged-in user")
        return False
    
    instance = im.get_instance(instance_id, user_id=user_id)
    if not instance:
        return False
    
    actual_str = instance.get('actual', '{}')
    try:
        if isinstance(actual_str, str):
            actual_data = json.loads(actual_str) if actual_str else {}
        else:
            actual_data = actual_str if isinstance(actual_str, dict) else {}
    except json.JSONDecodeError:
        actual_data = {}
    
    # Mark as edited with timestamp
    actual_data['is_edited'] = True
    actual_data['edited_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Update the instance
    if im.use_db:
        return _update_actual_data_db(instance_id, actual_data)
    else:
        return _update_actual_data_csv(instance_id, actual_data)


def _update_actual_data_csv(instance_id, actual_data):
    """CSV-specific update_actual_data."""
    import json
    im._reload()
    matches = im.df.index[im.df['instance_id'] == instance_id]
    if len(matches) == 0:
        return False
    
    idx = matches[0]
    im.df.at[idx, 'actual'] = json.dumps(actual_data)
    im._save()
    return True


def _update_actual_data_db(instance_id, actual_data):
    """Database-specific update_actual_data."""
    try:
        import json
        with im.db_session() as session:
            instance = session.query(im.TaskInstance).filter(
                im.TaskInstance.instance_id == instance_id
            ).first()
            if not instance:
                return False
            
            instance.actual = json.dumps(actual_data)
            session.commit()
            return True
    except Exception as e:
        handle_error_with_ui(
            'update_task_actual_data',
            e,
            user_id=get_current_user(),
            context={'instance_id': instance_id}
        )
        return False


def _open_delete_confirm(instance_id: str, refresh_callback, user_id: Optional[int]) -> None:
    """Open confirmation dialog and delete the task instance on confirm."""
    if user_id is None:
        user_id = get_current_user()
    with ui.dialog() as dlg, ui.card().classes("w-full max-w-md p-4 gap-3"):
        ui.label("Delete task instance?").classes("text-lg font-semibold")
        ui.label("This cannot be undone. The task instance will be permanently removed.").classes("text-sm text-gray-600")
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=dlg.close).classes("bg-gray-500 text-white")

            def do_delete():
                try:
                    if im.delete_instance(instance_id, user_id=user_id):
                        dlg.close()
                        if refresh_callback:
                            refresh_callback()
                        ui.notify("Task instance deleted", color="positive")
                    else:
                        ui.notify("Could not delete task instance", color="negative")
                except Exception as e:
                    handle_error_with_ui(
                        "delete_task_instance",
                        e,
                        user_id=user_id,
                        context={"instance_id": instance_id},
                    )

            ui.button("Delete", on_click=do_delete, color="negative").classes("bg-red-500 text-white")
    dlg.open()


def edit_cancelled_task_dialog(instance_id, inst_data, refresh_callback, user_id: Optional[int] = None):
    """Open dialog to edit cancelled task category and notes (reused from cancelled_tasks_page).
    
    Args:
        instance_id: Instance ID to edit
        inst_data: Instance data dictionary
        refresh_callback: Callback function to refresh the view
        user_id: User ID for data isolation. If None, gets current user.
    """
    if user_id is None:
        user_id = get_current_user()
    
    # Parse actual data
    actual_data = inst_data.get('actual', '{}')
    if isinstance(actual_data, str):
        try:
            actual_data = json.loads(actual_data)
        except json.JSONDecodeError:
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
                im.update_cancelled_instance(instance_id, cancellation_data)
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
                    user_id=user_id,
                    context={'instance_id': instance_id}
                )
        
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=dialog.close).classes("bg-gray-500 text-white")
            ui.button("Save", on_click=save_edit, color="positive").classes("bg-green-500 text-white")
    
    dialog.open()


@ui.page("/task-editing-manager")
def task_editing_manager_page():
    # Get current user ID
    user_id = get_current_user()
    if user_id is None:
        ui.navigate.to('/login')
        return
    ui.label("Task Editing Manager").classes("text-2xl font-bold mb-4")
    ui.label("Edit completed and cancelled task instances.").classes("text-gray-600 mb-4")
    
    # Create view container and refresh function
    view_container = ui.column().classes("w-full")
    pagination_info = ui.label("").classes("text-sm text-gray-600 mb-2")
    
    # Current page state (use a mutable container that can be accessed in closures)
    class PageState:
        def __init__(self):
            self.value = 1
    
    page_state = PageState()
    
    def render_task_list(instances, refresh_callback=None):
        """Render a list of task instances with edit buttons."""
        view_container.clear()
        with view_container:
            if not instances:
                ui.label("No tasks found.").classes("text-gray-500 p-4")
                return
            
            # Apply pagination
            page_num = page_state.value
            start_idx = (page_num - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            paginated_tasks = instances[start_idx:end_idx]
            
            total_pages = (len(instances) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            pagination_info.text = f"Page {page_num} of {total_pages} ({len(instances)} total tasks)"
            
            with ui.column().classes("w-full gap-2 mt-2"):
                for inst in paginated_tasks:
                    instance_id = inst.get('instance_id', '')
                    task_name = inst.get('task_name', 'Unknown Task')
                    status = inst.get('_status', 'unknown')
                    timestamp = inst.get('_timestamp', '')
                    
                    with ui.card().classes("w-full p-3 border border-gray-200"):
                        with ui.row().classes("w-full items-start justify-between gap-3"):
                            with ui.column().classes("flex-1 gap-1"):
                                # Status label
                                status_label_color = "text-green-600" if status == 'completed' else "text-orange-600"
                                status_label_text = "COMPLETED" if status == 'completed' else "CANCELLED"
                                ui.label(status_label_text).classes(f"text-xs font-bold {status_label_color} mb-1")
                                
                                ui.label(escape_for_display(task_name)).classes("text-base font-semibold")
                                ui.label(f"Instance ID: {instance_id}").classes("text-xs text-gray-500")
                                
                                # Show status-specific information
                                if status == 'cancelled':
                                    actual_data = inst.get('actual', '{}')
                                    if isinstance(actual_data, str):
                                        try:
                                            actual_data = json.loads(actual_data)
                                        except json.JSONDecodeError:
                                            actual_data = {}
                                    
                                    category = actual_data.get('cancellation_category', 'other')
                                    all_categories = get_all_cancellation_categories(user_id=user_id)
                                    category_label = all_categories.get(category, category or 'Other reason')
                                    
                                    ui.label(f"Category: {category_label}").classes("text-xs text-gray-600")
                                    
                                    if timestamp:
                                        ui.label(f"Cancelled: {format_for_display(timestamp)}").classes("text-xs text-gray-500 mt-1")
                                else:  # completed
                                    if timestamp:
                                        ui.label(f"Completed: {format_for_display(timestamp)}").classes("text-xs text-gray-500 mt-1")
                                    
                                    # Check if edited
                                    actual_data = inst.get('actual', '{}')
                                    if isinstance(actual_data, str):
                                        try:
                                            actual_data = json.loads(actual_data)
                                        except json.JSONDecodeError:
                                            actual_data = {}
                                    
                                    if actual_data.get('is_edited'):
                                        edited_at = actual_data.get('edited_at', 'Unknown')
                                        ui.label(f"[EDITED] Last edited: {format_for_display(edited_at) if edited_at != 'Unknown' else edited_at}").classes("text-xs text-orange-600 font-semibold mt-1")
                            
                            # Edit buttons
                            with ui.column().classes("text-right gap-1 items-end"):
                                created_at = inst.get('created_at', '')
                                if created_at:
                                    ui.label(f"Created: {format_for_display(created_at)}").classes("text-xs text-gray-400")
                                
                                initialized_at = inst.get('initialized_at', '')
                                if initialized_at:
                                    ui.label(f"Initialized: {format_for_display(initialized_at)}").classes("text-xs text-gray-400")
                                
                                if status == 'cancelled':
                                    ui.button("Edit", on_click=lambda inst_id=instance_id, inst_data=inst, uid=user_id: edit_cancelled_task_dialog(inst_id, inst_data, refresh_view, uid)).classes("text-xs bg-blue-500 text-white mt-2")
                                    ui.button("Delete", on_click=lambda inst_id=instance_id: _open_delete_confirm(inst_id, refresh_view, user_id)).classes("text-xs bg-red-500 text-white mt-2")
                                else:  # completed
                                    def edit_initialization(inst_id=instance_id):
                                        """Navigate to edit initialization page."""
                                        mark_instance_as_edited(inst_id)
                                        ui.navigate.to(f"/initialize-task?instance_id={inst_id}&edit=true")

                                    def edit_completion(inst_id=instance_id):
                                        """Navigate to edit completion page."""
                                        mark_instance_as_edited(inst_id)
                                        ui.navigate.to(f"/complete_task?instance_id={inst_id}&edit=true")

                                    with ui.row().classes("gap-2 mt-2"):
                                        ui.button("Edit Init", on_click=lambda inst_id=instance_id: edit_initialization(inst_id)).classes("text-xs bg-blue-500 text-white")
                                        ui.button("Edit Completion", on_click=lambda inst_id=instance_id: edit_completion(inst_id)).classes("text-xs bg-green-500 text-white")

                                ui.button("Delete", on_click=lambda inst_id=instance_id: _open_delete_confirm(inst_id, refresh_view, user_id)).classes("text-xs bg-red-500 text-white mt-2")
            
            # Pagination controls
            if total_pages > 1:
                with ui.row().classes("w-full justify-center gap-2 mt-4"):
                    if page_num > 1:
                        ui.button("← Previous", on_click=lambda: change_page(-1)).classes("bg-gray-500 text-white")
                    else:
                        ui.button("← Previous", on_click=lambda: None).classes("bg-gray-300 text-gray-500").props("disabled")
                    
                    ui.label(f"Page {page_num} of {total_pages}").classes("text-sm text-gray-600")
                    
                    if page_num < total_pages:
                        ui.button("Next →", on_click=lambda: change_page(1)).classes("bg-gray-500 text-white")
                    else:
                        ui.button("Next →", on_click=lambda: None).classes("bg-gray-300 text-gray-500").props("disabled")
    
    # Task type filter (define before functions that use it)
    task_type_filter = ui.select(
        options={'all': 'All Tasks', 'completed': 'Completed Tasks', 'cancelled': 'Cancelled Tasks'},
        label='Filter by Status',
        value='all'
    ).classes("mb-4").props("dense outlined")

    # Date range filter
    with ui.row().classes("items-end gap-2 flex-wrap mb-4"):
        date_from_input = ui.input(
            label="From date",
            placeholder="YYYY-MM-DD"
        ).classes("min-w-[140px]").props("dense outlined")
        date_to_input = ui.input(
            label="To date",
            placeholder="YYYY-MM-DD"
        ).classes("min-w-[140px]").props("dense outlined")
        ui.label("Leave empty for no date limit.").classes("text-xs text-gray-500 self-center")

    # Semantic search: task name and notes
    search_input = ui.input(
        label="Search in task names and notes",
        placeholder="Type to search..."
    ).classes("w-full max-w-md mb-4").props("dense outlined clearable")

    def get_filtered_tasks():
        """Get tasks based on current filter, date range, and search query."""
        selected_type = task_type_filter.value
        all_tasks = get_all_tasks_chronologically(user_id=user_id)

        if selected_type == 'all':
            tasks = all_tasks
        elif selected_type == 'completed':
            tasks = [t for t in all_tasks if t.get('_status') == 'completed']
        elif selected_type == 'cancelled':
            tasks = [t for t in all_tasks if t.get('_status') == 'cancelled']
        else:
            tasks = all_tasks

        # Date range filter
        date_from_val = None
        date_to_val = None
        try:
            if date_from_input.value and str(date_from_input.value).strip():
                date_from_val = datetime.strptime(
                    str(date_from_input.value).strip()[:10], "%Y-%m-%d"
                ).date()
        except (ValueError, TypeError):
            pass
        try:
            if date_to_input.value and str(date_to_input.value).strip():
                date_to_val = datetime.strptime(
                    str(date_to_input.value).strip()[:10], "%Y-%m-%d"
                ).date()
        except (ValueError, TypeError):
            pass
        if date_from_val is not None or date_to_val is not None:
            tasks = [t for t in tasks if _task_in_date_range(t, date_from_val, date_to_val)]

        # Semantic search filter
        query = (search_input.value or "").strip()
        if query:
            tasks = [t for t in tasks if _task_matches_search(t, query)]

        return tasks
    
    def refresh_view():
        """Refresh the view with current filter and page."""
        try:
            all_tasks = get_filtered_tasks()
            render_task_list(all_tasks, refresh_view)
        except Exception as e:
            handle_error_with_ui(
                'refresh_task_editing_view',
                e,
                user_id=get_current_user()
            )
            view_container.clear()
            with view_container:
                ui.label("Error loading tasks. Please try refreshing.").classes("text-red-500 p-4")
    
    def change_page(delta):
        """Change the current page."""
        all_tasks = get_filtered_tasks()
        total_pages = (len(all_tasks) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        new_page = page_state.value + delta
        if 1 <= new_page <= total_pages:
            page_state.value = new_page
            refresh_view()
    
    # Filter change handler - reset to page 1 when filter changes
    def on_filter_change():
        page_state.value = 1
        refresh_view()
    
    task_type_filter.on('update:model-value', on_filter_change)
    
    ui.button("Refresh", on_click=refresh_view).classes("bg-blue-500 text-white mb-4")
    
    # Add pagination info and view container to page
    pagination_info
    view_container
    
    # Initial load
    refresh_view()
