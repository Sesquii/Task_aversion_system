# ui/dashboard.py
from nicegui import ui
import json
import html
import os
import time
import logging
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.emotion_manager import EmotionManager
from backend.analytics import Analytics
from backend.user_state import UserStateManager
from backend.performance_logger import get_perf_logger as get_init_perf_logger
from backend.recommendation_logger import recommendation_logger
from backend.bootup_logger import get_bootup_logger

# Setup performance logging for monitored metrics
PERF_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs')
PERF_LOG_FILE = None
perf_logger = None

try:
    os.makedirs(PERF_LOG_DIR, exist_ok=True)
    PERF_LOG_FILE = os.path.join(PERF_LOG_DIR, f'monitored_metrics_perf_{datetime.now().strftime("%Y%m%d")}.log')
    
    # Configure logging
    perf_logger = logging.getLogger('monitored_metrics_perf')
    perf_logger.setLevel(logging.DEBUG)
    # Prevent duplicate handlers
    perf_logger.handlers.clear()
    handler = logging.FileHandler(PERF_LOG_FILE, mode='a', encoding='utf-8')
    # Use a custom formatter to include microseconds (time.strftime doesn't support %f)
    class MicrosecondFormatter(logging.Formatter):
        def formatTime(self, record, datefmt=None):
            dt = datetime.fromtimestamp(record.created)
            return dt.strftime('%Y-%m-%d %H:%M:%S.%f')
    handler.setFormatter(MicrosecondFormatter('%(asctime)s [%(levelname)s] %(message)s'))
    perf_logger.addHandler(handler)
    perf_logger.propagate = False  # Prevent propagation to root logger
except Exception as e:
    print(f"[Dashboard] Warning: Could not setup performance logging: {e}")
    # Create a null logger that does nothing
    perf_logger = logging.getLogger('monitored_metrics_perf_null')
    perf_logger.addHandler(logging.NullHandler())

def safe_log(level, message):
    """Safely log a message, falling back to print if logging fails."""
    try:
        if perf_logger:
            if level == 'info':
                perf_logger.info(message)
            elif level == 'error':
                perf_logger.error(message)
            elif level == 'warning':
                perf_logger.warning(message)
            elif level == 'debug':
                perf_logger.debug(message)
    except Exception as e:
        # Fallback to print if logging fails
        print(f"[Dashboard Perf Log Error] {e}: {message}")

tm = TaskManager()
im = InstanceManager()

# Global variables for initialized tasks search
initialized_tasks_container = None
initialized_search_input_ref = None

# #region agent log
import json
def debug_log(location, message, data=None, hypothesis_id=None):
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            log_entry = {
                'location': location,
                'message': message,
                'data': data or {},
                'timestamp': int(time.time() * 1000),
                'sessionId': 'debug-session',
                'runId': 'run1',
                'hypothesisId': hypothesis_id
            }
            f.write(json.dumps(log_entry) + '\n')
    except: pass
# #endregion
em = EmotionManager()
an = Analytics()
user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"

# Module-level variables for dashboard state
dash_filters = {}
_monitored_metrics_state = {
    'metric_cards': {},
    'selected_metrics': [],
    'coloration_baseline': 'last_3_months',
    'analytics_instance': None,
    'refresh_timer': None
}
RECOMMENDATION_METRICS = [
    {"label": "Relief score (high)", "key": "relief_score"},
    {"label": "Net relief (high)", "key": "net_relief_proxy"},
    {"label": "Mental Energy Needed (low)", "key": "mental_energy_needed"},
    {"label": "Task Difficulty (low)", "key": "task_difficulty"},
    {"label": "Distress (low)", "key": "emotional_load"},
    {"label": "Net load (low)", "key": "net_load"},
    {"label": "Efficiency (high)", "key": "historical_efficiency"},
    {"label": "Stress level (low)", "key": "stress_level"},
    {"label": "Behavioral score (high)", "key": "behavioral_score"},
    {"label": "Net wellbeing (high)", "key": "net_wellbeing_normalized"},
    {"label": "Physical load (low)", "key": "physical_load"},
]


# ----------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------

# Note: All inputs now use 0-100 scale natively.
# Old data may have 0-10 scale values, but we use them as-is (no scaling).
# This is acceptable since old 0-10 data was only used for a short time.


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
    """Start an instance (first time) and update the container to show ongoing time."""
    # Check if there's already a current task running
    current = get_current_task()
    if current and current.get('instance_id') != instance_id:
        ui.notify("You need to finish the current task first", color='warning')
        return
    
    im.start_instance(instance_id)
    ui.notify("Instance started", color='positive')
    
    # Reload the page to update the current task display
    ui.navigate.reload()

def resume_instance(instance_id, container=None):
    """Resume a paused instance and update the container to show ongoing time."""
    # Check if there's already a current task running
    current = get_current_task()
    if current and current.get('instance_id') != instance_id:
        ui.notify("You need to finish the current task first", color='warning')
        return
    
    im.resume_instance(instance_id)
    ui.notify("Instance resumed", color='positive')
    
    # Reload the page to update the current task display
    # Use a small delay to ensure cache invalidation completes
    ui.timer(0.1, lambda: ui.navigate.reload(), once=True)
    
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


def open_pause_dialog(instance_id):
    """Show dialog to pause an instance with optional reason and completion percentage.
    
    The task is paused immediately when the dialog opens, and the dialog is just for
    collecting optional notes and completion percentage.
    """
    # Pause the task immediately (with no reason/completion yet)
    try:
        im.pause_instance(instance_id, reason=None, completion_percentage=0.0)
        ui.notify("Task paused", color='info')
    except Exception as exc:
        ui.notify(f"Error pausing task: {str(exc)}", color='negative')
        return
    
    # Now show dialog to collect optional notes and completion percentage
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Add pause notes (optional)").classes("text-lg font-bold mb-2")
        ui.label("Task is already paused. You can add notes below or just close this dialog.").classes("text-sm text-gray-600 mb-3")
        
        # Warning about pause/resume bug
        with ui.card().classes("p-2 mb-3 bg-orange-50 border border-orange-200"):
            ui.label("⚠️ WARNING: There is a known bug where time spent on task may not always save correctly between pause and resume. Please verify your time is tracked correctly after resuming.").classes("text-xs text-orange-700")
        
        reason_input = ui.textarea(
            label="Reason (optional)",
            placeholder="Why did you pause this task?"
        ).classes("w-full")
        
        completion_input = ui.number(
            label="Completion percentage",
            value=0,
            min=0,
            max=100,
            step=1,
            format="%.0f"
        ).classes("w-full")

        def update_pause_info():
            """Update the pause reason and completion percentage without recalculating time."""
            reason_text = (reason_input.value or "").strip()
            completion_pct = completion_input.value
            if completion_pct is None:
                completion_pct = 0
            try:
                completion_pct = float(completion_pct)
                if completion_pct < 0:
                    completion_pct = 0
                elif completion_pct > 100:
                    completion_pct = 100
            except (ValueError, TypeError):
                completion_pct = 0
            
            try:
                # Get the current instance and update its actual JSON directly
                # This avoids recalculating time since we already paused
                instance = im.get_instance(instance_id)
                if instance:
                    import json
                    actual_str = instance.get("actual") or "{}"
                    try:
                        actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                    except (json.JSONDecodeError, TypeError):
                        actual_data = {}
                    
                    # Update pause reason and completion percentage
                    if reason_text:
                        actual_data['pause_reason'] = reason_text
                    elif 'pause_reason' in actual_data and not reason_text:
                        # Remove pause_reason if user cleared it
                        del actual_data['pause_reason']
                    actual_data['pause_completion_percentage'] = completion_pct
                    
                    # Save the updated actual data by updating the instance directly
                    # We need to call pause_instance again but it will preserve time_spent_before_pause
                    # since the task is already paused (started_at is empty)
                    im.pause_instance(instance_id, reason_text if reason_text else None, completion_pct)
                    ui.notify("Pause notes updated", color='positive')
                dialog.close()
                ui.navigate.reload()
            except Exception as exc:
                ui.notify(f"Error updating pause info: {str(exc)}", color='negative')

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Close", color="warning", on_click=dialog.close)
            ui.button("Save Notes", color="primary", on_click=update_pause_info)

    dialog.open()


def format_elapsed_time(minutes):
    """Format elapsed time in minutes as HH:MM or M min."""
    if minutes < 60:
        return f"{int(minutes)} min"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"{hours}:{mins:02d}"


def update_ongoing_timer(instance_id, timer_element):
    """Update the ongoing timer display for a started instance.
    
    This function updates the timer display and schedules the next update.
    It includes error handling to prevent timer leaks when clients disconnect.
    """
    # Early return if element is not provided
    if not timer_element:
        return
    
    # Check if instance is still active
    instance = im.get_instance(instance_id)
    if not instance or not instance.get('started_at'):
        # Instance no longer active or not started, stop timer
        try:
            timer_element.text = ""
        except (AttributeError, RuntimeError, Exception):
            # Element is invalid, silently stop
            pass
        return
    
    try:
        from datetime import datetime
        import pandas as pd
        import json
        
        started_at = pd.to_datetime(instance['started_at'])
        now = datetime.now()
        current_elapsed_minutes = (now - started_at).total_seconds() / 60.0
        
        # Get time spent before pause (if task was paused and resumed)
        time_spent_before_pause = 0.0
        actual_str = instance.get('actual', '{}')
        if actual_str:
            try:
                if isinstance(actual_str, str):
                    actual_data = json.loads(actual_str) if actual_str else {}
                else:
                    actual_data = actual_str if isinstance(actual_str, dict) else {}
                
                time_before = actual_data.get('time_spent_before_pause', 0.0)
                if isinstance(time_before, (int, float)):
                    time_spent_before_pause = float(time_before)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        
        # Total elapsed time = current session + time from previous sessions
        total_elapsed_minutes = current_elapsed_minutes + time_spent_before_pause
        elapsed_str = format_elapsed_time(total_elapsed_minutes)
        
        # Update the element text (with comprehensive error handling)
        try:
            timer_element.text = f"Ongoing for {elapsed_str}"
        except (AttributeError, RuntimeError, Exception):
            # Element is no longer valid (client disconnected), stop timer
            return
        
        # Schedule next update in 1 second (only if instance is still active and element/client are valid)
        # Use try/except to catch any errors during timer creation
        try:
            # Verify element is still valid before creating new timer
            try:
                # Try to access element properties to verify it's still valid
                _ = timer_element.text
            except (AttributeError, RuntimeError, Exception):
                # Element is no longer valid, stop timer
                return
            
            # Check if element's client is still valid before creating timer
            # Based on NiceGUI issue #3028: elements can be used after client disconnects
            # We need to verify the element is still in the client's elements dictionary
            try:
                # Check element's client property (more reliable than ui.context.client)
                element_client = getattr(timer_element, 'client', None)
                context_client = None
                try:
                    context_client = ui.context.client
                except (AttributeError, RuntimeError):
                    pass
                
                # If element has a client, check if it's still valid
                # Per NiceGUI issue #3028 (https://github.com/zauberzeug/nicegui/issues/3028),
                # elements can be used after clients disconnect, causing KeyErrors when NiceGUI
                # tries to clean them up. We verify the element is still functional before using it.
                if element_client:
                    try:
                        # Try to access client properties to verify it's still valid
                        _ = element_client.id
                        _ = element_client.outbox
                        
                        # Additional check: try to access element's internal state
                        # If element was removed from client, accessing its id might fail
                        element_id = getattr(timer_element, 'id', None)
                        if element_id is None:
                            return
                        
                        # Try a "dry run" operation on the element to verify it's still functional
                        # We already updated the text above, so if that succeeded, element should be valid
                        # But we do one more check by trying to read a property
                        try:
                            _ = timer_element.text
                        except (AttributeError, RuntimeError, KeyError, Exception):
                            return
                    except (AttributeError, RuntimeError, KeyError, Exception):
                        return
                elif context_client:
                    # Fallback to context client if element doesn't have one
                    try:
                        _ = context_client.id
                        _ = context_client.outbox
                    except (AttributeError, RuntimeError, Exception):
                        return
                else:
                    # No client available at all
                    return
            except (AttributeError, RuntimeError, KeyError, Exception):
                # Error checking client, stop timer to be safe
                return
            
            active_instances = im.list_active_instances()
            is_still_active = any(inst.get('instance_id') == instance_id for inst in active_instances)
            if is_still_active:
                # Create next timer with error handling in the callback
                def safe_update():
                    try:
                        update_ongoing_timer(instance_id, timer_element)
                    except Exception:
                        # Silently stop if update fails (client likely disconnected)
                        pass
                
                # Final check: verify client is still valid right before creating timer
                # This helps reduce race conditions where client gets deleted between checks
                try:
                    # Re-check element client one more time right before timer creation
                    final_client = getattr(timer_element, 'client', None)
                    if final_client:
                        try:
                            # Quick validation - access id and outbox
                            _ = final_client.id
                            _ = final_client.outbox
                        except (AttributeError, RuntimeError, Exception):
                            return
                except Exception:
                    return
                
                # Wrap timer creation in try/except to catch client deletion errors
                # Note: NiceGUI may log a warning if client is deleted, but we try to prevent it
                try:
                    # Create timer - if client is deleted, NiceGUI will log a warning but not raise
                    # The warning is informational and doesn't crash the app
                    ui.timer(1.0, safe_update, once=True)
                except (AttributeError, RuntimeError, Exception, BaseException):
                    # Client was deleted or invalid, stop timer silently
                    pass
        except Exception:
            # Stop timer if any error occurs during scheduling
            pass
    except Exception:
        # Log unexpected errors but don't create new timer
        # Silently fail to avoid console spam
        pass


def show_details(instance_id):
    inst = InstanceManager.get_instance(instance_id)

    with ui.dialog() as dialog, ui.card():
        ui.label(f"Instance ID: {instance_id}")
        ui.markdown(f"```json\n{inst}\n```")
        ui.button("Close", on_click=dialog.close)

    dialog.open()
def refresh_initialized_tasks(search_query=None):
    """
    Refresh the initialized tasks display with optional search filtering.
    
    Args:
        search_query: Optional string to filter tasks by name, description, notes, or pause notes
    """
    global initialized_tasks_container, initialized_search_input_ref
    # #region agent log
    debug_log('dashboard.py:470', 'refresh_initialized_tasks called', {'search_query': search_query, 'container_is_none': initialized_tasks_container is None, 'container_id': str(id(initialized_tasks_container)) if initialized_tasks_container else None, 'input_ref_is_none': initialized_search_input_ref is None}, 'H1')
    # #endregion
    
    # Get search query from input if not provided
    if search_query is None and initialized_search_input_ref is not None:
        try:
            current_value = initialized_search_input_ref.value
            search_query = str(current_value).strip() if current_value else None
            if search_query == '':
                search_query = None
        except Exception:
            search_query = None
    
    refresh_start = time.perf_counter()
    print(f"[Dashboard] refresh_initialized_tasks() called with search_query='{search_query}'")
    
    try:
        init_perf_logger = get_init_perf_logger()
        init_perf_logger.log_event("refresh_initialized_tasks_start", search_query=search_query)
    except:
        init_perf_logger = None
    
    # Check if container exists
    if initialized_tasks_container is None:
        print("[Dashboard] ERROR: initialized_tasks_container is None, cannot refresh. Will retry after delay.")
        # #region agent log
        debug_log('dashboard.py:492', 'Initialized tasks container is None, scheduling retry', {}, 'H1')
        # #endregion
        def retry_refresh():
            refresh_initialized_tasks(search_query)
        ui.timer(5.0, retry_refresh, once=True)
        return
    
    # Get active instances (excluding current task)
    if init_perf_logger:
        with init_perf_logger.operation("list_active_instances"):
            active = im.list_active_instances()
        with init_perf_logger.operation("get_current_task"):
            current_task = get_current_task()
    else:
        active = im.list_active_instances()
        current_task = get_current_task()
    
    # Filter out current task from active list
    active_not_current = [a for a in active if a.get('instance_id') != (current_task.get('instance_id') if current_task else None)]
    
    print(f"[Dashboard] Total initialized tasks before filtering: {len(active_not_current)}")
    
    # Apply search filter if provided
    if search_query:
        search_query = str(search_query).strip().lower()
        print(f"[Dashboard] Applying search filter: '{search_query}'")
        
        filtered_instances = []
        for inst in active_not_current:
            # Parse predicted data for description
            predicted_str = inst.get("predicted") or "{}"
            try:
                predicted_data = json.loads(predicted_str) if isinstance(predicted_str, str) else predicted_str
            except (json.JSONDecodeError, TypeError):
                predicted_data = {}
            
            # Parse actual data for pause notes
            actual_str = inst.get("actual") or "{}"
            try:
                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
            except (json.JSONDecodeError, TypeError):
                actual_data = {}
            
            # Get task name from instance
            task_name = str(inst.get("task_name", "")).lower()
            
            # Get description from predicted data
            description = str(predicted_data.get('description', '')).lower()
            
            # Get pause notes from actual data
            pause_reason = str(actual_data.get('pause_reason', '')).lower()
            
            # Get task-level notes
            task_id = inst.get('task_id')
            task_notes = ''
            if task_id:
                try:
                    task_notes = str(tm.get_task_notes(task_id) or '').lower()
                except Exception:
                    pass
            
            # Check if search query matches any field
            matches_name = search_query in task_name
            matches_description = search_query in description
            matches_pause_notes = search_query in pause_reason
            matches_task_notes = search_query in task_notes
            
            if matches_name or matches_description or matches_pause_notes or matches_task_notes:
                filtered_instances.append(inst)
                print(f"[Dashboard] Instance '{inst.get('task_name')}' matched search (name={matches_name}, desc={matches_description}, pause={matches_pause_notes}, notes={matches_task_notes})")
        
        active_not_current = filtered_instances
        print(f"[Dashboard] Initialized tasks after filtering: {len(active_not_current)}")
    else:
        print("[Dashboard] No search query provided, showing all initialized tasks")
    
    # Clear the container
    initialized_tasks_container.clear()
    
    if not active_not_current:
        print("[Dashboard] No initialized tasks to display after filtering")
        with initialized_tasks_container:
            if search_query:
                ui.markdown(f"_No initialized tasks match '{search_query}'_")
            else:
                ui.markdown("_No initialized tasks available_")
        return
    
    print(f"[Dashboard] Rendering {len(active_not_current)} initialized tasks in 2-column layout")
    
    # Render initialized tasks in 2 columns
    with initialized_tasks_container:
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
                    
                    # Check if this task has pause notes and completion percentage
                    actual_str = inst.get("actual") or "{}"
                    has_pause_notes = False
                    completion_pct = None
                    is_paused = False
                    try:
                        actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                        pause_reason = actual_data.get('pause_reason', '')
                        has_pause_notes = bool(pause_reason and pause_reason.strip())
                        # Check if task is paused (has 'paused' flag in actual_data)
                        is_paused = actual_data.get('paused', False)
                        # Get completion percentage if available
                        completion_pct = actual_data.get('pause_completion_percentage')
                        if completion_pct is not None:
                            try:
                                completion_pct = float(completion_pct)
                            except (ValueError, TypeError):
                                completion_pct = None
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    with ui.card().classes("w-full p-2 task-card-hover mb-2 context-menu-card").props(f'data-instance-id="{instance_id}" data-context-menu="instance"').style("position: relative;"):
                        # Hidden buttons for context menu actions (initialized tasks: View, Add Note, Complete)
                        ui.button("", on_click=lambda iid=instance_id: view_initialized_instance(iid)).props(f'id="context-btn-instance-view-{instance_id}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id: add_instance_note(iid)).props(f'id="context-btn-instance-addnote-{instance_id}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id: go_complete(iid)).props(f'id="context-btn-instance-complete-{instance_id}"').style("display: none;")
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.label(inst.get("task_name")).classes("text-sm font-bold flex-1")
                            # Small indicator icon if task has pause notes
                            if has_pause_notes:
                                ui.icon("pause_circle", size="sm").classes("text-orange-500").tooltip("This task was paused - see notes when you start it")
                        ui.label(f"{time_estimate} min").classes("text-xs text-gray-600")
                        
                        # Show completion percentage if task was paused
                        if completion_pct is not None:
                            ui.label(f"Progress: {int(completion_pct)}%").classes("text-xs font-semibold text-blue-600")
                        
                        initialized_at = inst.get('initialized_at', '')
                        if initialized_at:
                            ui.label(f"Initialize: {initialized_at}").classes("text-xs text-gray-500")
                        
                        # Show initialization description if available
                        init_description = predicted_data.get('description', '')
                        if init_description and init_description.strip():
                            ui.label(init_description.strip()).classes("text-xs text-gray-700 mt-1 italic").style("max-width: 100%; word-wrap: break-word;")
                        
                        with ui.row().classes("gap-1 mt-1"):
                            # Show "Resume" button if task is paused, otherwise "Start"
                            if is_paused:
                                ui.button("Resume",
                                          on_click=lambda i=inst['instance_id']: resume_instance(i)
                                          ).props("dense size=sm").classes("bg-blue-500")
                            else:
                                ui.button("Start",
                                          on_click=lambda i=inst['instance_id']: start_instance(i)
                                          ).props("dense size=sm").classes("bg-green-500")
                            ui.button("Cancel",
                                      on_click=lambda i=inst['instance_id']: go_cancel(i)
                                      ).props("dense size=sm color=red")
                        
                        tooltip_html = f'<div id="{tooltip_id}" class="task-tooltip">{formatted_tooltip}</div>'
                        ui.add_body_html(tooltip_html)
        
        # Re-initialize tooltips and context menus
        ui.run_javascript('setTimeout(initTaskTooltips, 200);')
        ui.run_javascript("setTimeout(initContextMenus, 100);")
    
    refresh_duration = (time.perf_counter() - refresh_start) * 1000
    if init_perf_logger:
        init_perf_logger.log_timing("refresh_initialized_tasks_total", refresh_duration, search_query=search_query)
    print(f"[Dashboard] refresh_initialized_tasks() completed successfully in {refresh_duration:.2f}ms")


def refresh_templates(search_query=None):
    """
    Refresh the task templates display with optional search filtering.
    
    Args:
        search_query: Optional string to filter templates by name, description, or task_type
    """
    global template_col
    # #region agent log
    debug_log('dashboard.py:690', 'refresh_templates called', {'search_query': search_query, 'container_is_none': template_col is None, 'container_id': str(id(template_col)) if template_col else None}, 'H1')
    # #endregion
    
    # Check if container exists
    if template_col is None:
        print("[Dashboard] ERROR: template_col is None, cannot refresh. Will retry after delay.")
        # #region agent log
        debug_log('dashboard.py:694', 'Template container is None, scheduling retry', {}, 'H1')
        # #endregion
        def retry_refresh():
            refresh_templates(search_query)
        ui.timer(5.0, retry_refresh, once=True)
        return
    
    refresh_start = time.perf_counter()
    print(f"[Dashboard] refresh_templates() called with search_query='{search_query}'")
    print(f"[Dashboard] search_query type: {type(search_query)}, value: {repr(search_query)}")

    try:
        init_perf_logger = get_init_perf_logger()
        init_perf_logger.log_event("refresh_templates_start", search_query=search_query)
    except:
        init_perf_logger = None
    
    if init_perf_logger:
        with init_perf_logger.operation("tm.get_all"):
            df = tm.get_all()
    else:
        df = tm.get_all()
    print(f"[Dashboard] Retrieved dataframe: shape={df.shape if df is not None else 'None'}, empty={df.empty if df is not None else 'N/A'}")
    
    if df is None or df.empty:
        print("[Dashboard] no templates found - dataframe is None or empty")
        template_col.clear()
        with template_col:
            ui.markdown("_No templates available_")
        return

    rows = df.to_dict(orient='records')
    print(f"[Dashboard] Total templates before filtering: {len(rows)}")
    
    # Apply search filter if provided
    if search_query:
        search_query = str(search_query).strip().lower()
        print(f"[Dashboard] Applying search filter: '{search_query}'")
        
        filtered_rows = []
        for row in rows:
            # Search in name, description, and task_type
            name = str(row.get('name', '')).lower()
            description = str(row.get('description', '')).lower()
            task_type = str(row.get('task_type', '')).lower()
            
            matches_name = search_query in name
            matches_description = search_query in description
            matches_task_type = search_query in task_type
            
            if matches_name or matches_description or matches_task_type:
                filtered_rows.append(row)
                print(f"[Dashboard] Template '{row.get('name')}' matched search (name={matches_name}, desc={matches_description}, type={matches_task_type})")
        
        rows = filtered_rows
        print(f"[Dashboard] Templates after filtering: {len(rows)}")
    else:
        print("[Dashboard] No search query provided, showing all templates")

    template_col.clear()

    if not rows:
        print("[Dashboard] No templates to display after filtering")
        with template_col:
            if search_query:
                ui.markdown(f"_No templates match '{search_query}'_")
            else:
                ui.markdown("_No templates available_")
        return

    print(f"[Dashboard] Rendering {len(rows)} templates in 3-column layout")

    # Use 3 nested columns for templates
    with template_col:
        col1 = ui.column().classes("w-1/3")
        col2 = ui.column().classes("w-1/3")
        col3 = ui.column().classes("w-1/3")
        columns = [col1, col2, col3]
        
        for idx, t in enumerate(rows):
            col = columns[idx % 3]
            print(f"[Dashboard] Rendering template {idx+1}/{len(rows)}: '{t.get('name')}' in column {idx % 3 + 1}")
            with col:
                task_id = t['task_id']
                card_id = f"template-{task_id}"
                with ui.card().classes("p-2 mb-2 w-full context-menu-card").props(f'id="{card_id}" data-template-id="{task_id}" data-context-menu="template"'):
                    ui.markdown(f"**{t['name']}**").classes("text-xs")
                    ui.button("Initialize", on_click=lambda tid=task_id: init_quick(tid)).props("dense size=sm").classes("w-full")
                    # Hidden buttons for context menu actions
                    ui.button("", on_click=lambda task=t: edit_template(task)).props(f'id="context-btn-template-edit-{task_id}"').style("display: none;")
                    ui.button("", on_click=lambda task=t: copy_template(task)).props(f'id="context-btn-template-copy-{task_id}"').style("display: none;")
                    ui.button("", on_click=lambda tid=task_id: delete_template(tid)).props(f'id="context-btn-template-delete-{task_id}"').style("display: none;")
    
    refresh_duration = (time.perf_counter() - refresh_start) * 1000
    if init_perf_logger:
        init_perf_logger.log_timing("refresh_templates_total", refresh_duration, search_query=search_query)
    print(f"[Dashboard] refresh_templates() completed successfully in {refresh_duration:.2f}ms")
    # Re-initialize context menus after templates are refreshed
    ui.run_javascript("setTimeout(initContextMenus, 100);")


def delete_instance(instance_id):
    im.delete_instance(instance_id)
    ui.notify("Deleted", color='negative')
    ui.navigate.reload()


def reset_metric_score(metric_key: str):
    """Reset a metric score to 0 (temporary workaround for testing).
    
    Args:
        metric_key: The metric key to reset (e.g., 'daily_productivity_score_idle_refresh')
    """
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'sessionId': 'debug-session',
                'runId': 'run1',
                'hypothesisId': 'RESET_SCORE',
                'location': 'dashboard.py:reset_metric_score',
                'message': 'reset_metric_score called',
                'data': {
                    'metric_key': metric_key
                },
                'timestamp': int(time.time() * 1000)
            }) + '\n')
    except Exception as e:
        print(f"[Dashboard] Error logging reset_metric_score call: {e}")
    # #endregion
    
    global _monitored_metrics_state
    metric_cards_ref = _monitored_metrics_state.get('metric_cards', {})
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'sessionId': 'debug-session',
                'runId': 'run1',
                'hypothesisId': 'RESET_SCORE',
                'location': 'dashboard.py:reset_metric_score',
                'message': 'Checking metric_cards state',
                'data': {
                    'metric_key': metric_key,
                    'metric_cards_keys': list(metric_cards_ref.keys()),
                    'metric_key_in_cards': metric_key in metric_cards_ref,
                    'has_monitored_state': '_monitored_metrics_state' in globals()
                },
                'timestamp': int(time.time() * 1000)
            }) + '\n')
    except Exception as e:
        print(f"[Dashboard] Error logging metric_cards check: {e}")
    # #endregion
    
    if metric_key not in metric_cards_ref:
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'RESET_SCORE',
                    'location': 'dashboard.py:reset_metric_score',
                    'message': 'Metric key not found in metric_cards',
                    'data': {
                        'metric_key': metric_key,
                        'available_keys': list(metric_cards_ref.keys())
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[Dashboard] Error logging not found: {e}")
        # #endregion
        ui.notify(f"Metric {metric_key} not found", color='warning')
        return
    
    card_info = metric_cards_ref.get(metric_key)
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'sessionId': 'debug-session',
                'runId': 'run1',
                'hypothesisId': 'RESET_SCORE',
                'location': 'dashboard.py:reset_metric_score',
                'message': 'Card info retrieved',
                'data': {
                    'metric_key': metric_key,
                    'has_card_info': card_info is not None,
                    'card_info_keys': list(card_info.keys()) if card_info else [],
                    'has_value_label': card_info.get('value_label') is not None if card_info else False
                },
                'timestamp': int(time.time() * 1000)
            }) + '\n')
    except Exception as e:
        print(f"[Dashboard] Error logging card_info: {e}")
    # #endregion
    
    if card_info and card_info.get('value_label'):
        value_label = card_info['value_label']
        
        # #region agent log
        try:
            current_value = None
            if hasattr(value_label, 'text'):
                try:
                    current_value = value_label.text
                except:
                    pass
            elif hasattr(value_label, 'get_text'):
                try:
                    current_value = value_label.get_text()
                except:
                    pass
            
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'RESET_SCORE',
                    'location': 'dashboard.py:reset_metric_score',
                    'message': 'About to update value_label',
                    'data': {
                        'metric_key': metric_key,
                        'current_value': current_value,
                        'has_text_attr': hasattr(value_label, 'text'),
                        'has_set_text': hasattr(value_label, 'set_text'),
                        'value_label_type': type(value_label).__name__
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[Dashboard] Error logging before update: {e}")
        # #endregion
        
        if hasattr(value_label, 'text'):
            value_label.text = '0.0'
            update_method = 'text'
        elif hasattr(value_label, 'set_text'):
            value_label.set_text('0.0')
            update_method = 'set_text'
        else:
            update_method = 'none'
        
        # Set the manually_reset flag to prevent auto-updates
        card_info['manually_reset'] = True
        
        # #region agent log
        try:
            new_value = None
            if hasattr(value_label, 'text'):
                try:
                    new_value = value_label.text
                except:
                    pass
            elif hasattr(value_label, 'get_text'):
                try:
                    new_value = value_label.get_text()
                except:
                    pass
            
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'RESET_SCORE',
                    'location': 'dashboard.py:reset_metric_score',
                    'message': 'Value label updated and manually_reset flag set',
                    'data': {
                        'metric_key': metric_key,
                        'update_method': update_method,
                        'new_value': new_value,
                        'target_value': '0.0',
                        'manually_reset_flag_set': True
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[Dashboard] Error logging after update: {e}")
        # #endregion
        
        ui.notify(f"Reset {metric_key} to 0.0", color='info')
    else:
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'RESET_SCORE',
                    'location': 'dashboard.py:reset_metric_score',
                    'message': 'Card info or value_label is None',
                    'data': {
                        'metric_key': metric_key,
                        'card_info_is_none': card_info is None,
                        'value_label_is_none': card_info.get('value_label') is None if card_info else 'N/A'
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[Dashboard] Error logging no value_label: {e}")
        # #endregion


def edit_monitored_metrics_config():
    """Edit monitored metrics configuration."""
    from backend.user_state import UserStateManager
    user_state = UserStateManager()
    DEFAULT_USER_ID = "default_user"
    
    # Get current config
    config = user_state.get_monitored_metrics_config(DEFAULT_USER_ID)
    current_selected = config.get('selected_metrics', ['productivity_time', 'productivity_score'])
    current_baseline = config.get('coloration_baseline', 'last_3_months')
    
    # Available metrics
    available_metrics_list = [
        {'key': 'productivity_time', 'label': 'Weekly Productivity Time'},
        {'key': 'productivity_score', 'label': 'Weekly Productivity Score'},
    ]
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl p-6'):
        ui.label("Configure Monitored Metrics").classes("text-xl font-bold mb-4")
        
        # Metric selection (up to 4)
        ui.label("Select Metrics (up to 4):").classes("text-sm font-semibold mb-2")
        metric_checkboxes = {}
        for metric in available_metrics_list:
            is_selected = metric['key'] in current_selected
            checkbox = ui.checkbox(metric['label'], value=is_selected)
            metric_checkboxes[metric['key']] = checkbox
        
        ui.separator().classes("my-4")
        
        # Coloration baseline selection
        ui.label("Coloration Baseline:").classes("text-sm font-semibold mb-2")
        # NiceGUI select expects a dict mapping values to labels
        baseline_options = {
            'last_3_months': 'Last 3 Months',
            'last_month': 'Last Month',
            'last_week': 'Last Week',
            'average': 'Average (Weekly + 3-Month)',
            'all_data': 'All Data',
        }
        baseline_select = ui.select(
            baseline_options,
            value=current_baseline,
            label="Compare metrics relative to:"
        ).classes("w-full")
        
        with ui.row().classes("gap-2 mt-6 justify-end"):
            ui.button("Cancel", on_click=dialog.close)
            def save_config():
                # Get selected metrics
                selected = [key for key, checkbox in metric_checkboxes.items() if checkbox.value]
                
                # Limit to 4
                if len(selected) > 4:
                    ui.notify("Maximum 4 metrics allowed. Selecting first 4.", color='warning')
                    selected = selected[:4]
                
                # Ensure at least one metric is selected
                if not selected:
                    ui.notify("Please select at least one metric", color='warning')
                    return
                
                # Save configuration
                try:
                    new_config = {
                        'selected_metrics': selected,
                        'coloration_baseline': baseline_select.value
                    }
                    user_state.set_monitored_metrics_config(new_config, DEFAULT_USER_ID)
                    ui.notify("Configuration saved", color='positive')
                    dialog.close()
                    ui.navigate.reload()
                except Exception as e:
                    ui.notify(f"Error saving configuration: {e}", color='negative')
            ui.button("Save", on_click=save_config, color='primary')
    
    dialog.open()


def add_instance_note(instance_id):
    """Add a note to an instance (active or initialized)."""
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg p-4'):
        ui.label("Add Note").classes("text-xl font-bold mb-4")
        note_input = ui.textarea(label="Note", placeholder="Enter your note here...").classes("w-full").props("rows=5")
        
        with ui.row().classes("gap-2 mt-4 justify-end"):
            ui.button("Cancel", on_click=dialog.close)
            def save_note():
                note_text = note_input.value.strip()
                if not note_text:
                    ui.notify("Note cannot be empty", color='warning')
                    return
                try:
                    im.append_instance_notes(instance_id, note_text)
                    ui.notify("Note added", color='positive')
                    dialog.close()
                    ui.navigate.reload()
                except Exception as e:
                    ui.notify(f"Error adding note: {e}", color='negative')
            ui.button("Save", on_click=save_note, color='primary')
        
    dialog.open()


def view_instance_notes(instance_id):
    """View all notes for an instance (task-level notes + pause notes if any)."""
    instance = im.get_instance(instance_id)
    if not instance:
        ui.notify("Instance not found", color='negative')
        return
    
    # Get task-level notes (shared across all instances)
    task_id = instance.get('task_id')
    if task_id:
        notes = tm.get_task_notes(task_id)
    else:
        notes = ''
    
    # Get pause notes from instance actual data (instance-specific)
    actual_raw = instance.get('actual', '{}') or '{}'
    try:
        actual_data = json.loads(actual_raw) if isinstance(actual_raw, str) else actual_raw
    except json.JSONDecodeError:
        actual_data = {}
    
    pause_reason = actual_data.get('pause_reason', '') or ''
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl p-4'):
        ui.label("Task Notes").classes("text-xl font-bold mb-4")
        
        # Regular notes (shared across instances with same initialization description)
        if notes:
            ui.label("Notes").classes("text-md font-semibold mb-2")
            ui.markdown(notes).classes("w-full p-4 bg-gray-50 rounded border mb-4").style("max-height: 300px; overflow-y: auto; white-space: pre-wrap;")
        else:
            ui.label("No notes yet").classes("text-gray-500 p-4 mb-4")
        
        # Pause notes (instance-specific, shown separately)
        if pause_reason:
            ui.label("Pause Notes (instance-specific)").classes("text-md font-semibold mt-4 mb-2 text-orange-600")
            ui.label(pause_reason.strip()).classes("w-full p-4 bg-orange-50 border border-orange-200 rounded").style("max-height: 200px; overflow-y: auto; white-space: pre-wrap;")
        
        with ui.row().classes("gap-2 mt-4 justify-end"):
            ui.button("Close", on_click=dialog.close, color='primary')
        
    dialog.open()


def copy_instance(instance_id):
    """Create a new instance based on an existing instance."""
    instance = im.get_instance(instance_id)
    if not instance:
        ui.notify("Instance not found", color='negative')
        return
    
    # Get the task template
    task_id = instance.get('task_id')
    task = tm.get_task(task_id)
    if not task:
        ui.notify("Task template not found", color='negative')
        return
    
    # Get predicted data from the instance
    predicted_str = instance.get('predicted', '{}') or '{}'
    try:
        predicted_data = json.loads(predicted_str) if isinstance(predicted_str, str) else predicted_str
    except (json.JSONDecodeError, TypeError):
        predicted_data = {}
    
    # Create a new instance with the same predicted data
    new_instance_id = im.create_instance(
        task_id,
        task['name'],
        task_version=task.get('version') or 1,
        predicted=predicted_data
    )
    
    if new_instance_id:
        ui.notify("Instance copied", color='positive')
        ui.navigate.reload()
    else:
        ui.notify("Failed to copy instance", color='negative')


def view_initialized_instance(instance_id):
    """View an initialized instance's expected values, time, and notes in a friendly UI."""
    instance = im.get_instance(instance_id)
    if not instance:
        ui.notify("Instance not found", color='negative')
        return
    
    # Check if instance is initialized
    initialized_at = instance.get('initialized_at', '')
    if not initialized_at or str(initialized_at).strip() == '':
        ui.notify("Instance not yet initialized", color='warning')
        return
    
    # Get predicted data (expected values)
    predicted_raw = instance.get('predicted', '{}') or '{}'
    try:
        predicted_data = json.loads(predicted_raw) if isinstance(predicted_raw, str) else predicted_raw
    except json.JSONDecodeError:
        predicted_data = {}
    
    # Get notes from actual data (shared across instances with same initialization description)
    actual_raw = instance.get('actual', '{}') or '{}'
    try:
        actual_data = json.loads(actual_raw) if isinstance(actual_raw, str) else actual_raw
    except json.JSONDecodeError:
        actual_data = {}
    
    notes = actual_data.get('notes', '') or ''
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl p-6'):
        ui.label("Initialized Task Details").classes("text-2xl font-bold mb-4")
        
        # Task name
        task_name = instance.get('task_name', 'Unknown Task')
        ui.label(f"Task: {task_name}").classes("text-lg font-semibold mb-2")
        
        # Initialized timestamp
        if initialized_at:
            ui.label(f"Initialized: {initialized_at}").classes("text-sm text-gray-600 mb-4")
        
        # Expected time
        time_estimate = predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0
        try:
            time_estimate = int(float(time_estimate))
        except (ValueError, TypeError):
            time_estimate = 0
        ui.label("Expected Time").classes("text-md font-semibold mt-4 mb-1")
        ui.label(f"{time_estimate} minutes").classes("text-lg mb-4")
        
        # Expected values section
        ui.label("Expected Values").classes("text-md font-semibold mt-4 mb-2")
        
        with ui.card().classes("w-full p-4 bg-gray-50"):
            # Expected aversion
            expected_aversion = predicted_data.get('expected_aversion') or predicted_data.get('initialization_expected_aversion') or 0
            try:
                expected_aversion = int(float(expected_aversion))
            except (ValueError, TypeError):
                expected_aversion = 0
            ui.label(f"Expected Aversion: {expected_aversion}/100").classes("text-sm mb-2")
            
            # Expected relief
            expected_relief = predicted_data.get('expected_relief', 0)
            try:
                expected_relief = int(float(expected_relief))
            except (ValueError, TypeError):
                expected_relief = 0
            ui.label(f"Expected Relief: {expected_relief}/100").classes("text-sm mb-2")
            
            # Expected mental energy
            expected_mental_energy = predicted_data.get('expected_mental_energy', 0)
            try:
                expected_mental_energy = int(float(expected_mental_energy))
            except (ValueError, TypeError):
                expected_mental_energy = 0
            ui.label(f"Expected Mental Energy: {expected_mental_energy}/100").classes("text-sm mb-2")
            
            # Expected difficulty
            expected_difficulty = predicted_data.get('expected_difficulty', 0)
            try:
                expected_difficulty = int(float(expected_difficulty))
            except (ValueError, TypeError):
                expected_difficulty = 0
            ui.label(f"Expected Difficulty: {expected_difficulty}/100").classes("text-sm mb-2")
            
            # Expected emotional load
            expected_emotional = predicted_data.get('expected_emotional_load', 0)
            try:
                expected_emotional = int(float(expected_emotional))
            except (ValueError, TypeError):
                expected_emotional = 0
            ui.label(f"Expected Emotional Load: {expected_emotional}/100").classes("text-sm mb-2")
            
            # Expected physical load
            expected_physical = predicted_data.get('expected_physical_load', 0)
            try:
                expected_physical = int(float(expected_physical))
            except (ValueError, TypeError):
                expected_physical = 0
            ui.label(f"Expected Physical Load: {expected_physical}/100").classes("text-sm")
        
        # Emotions section
        ui.label("Emotions").classes("text-md font-semibold mt-4 mb-2")
        emotion_values = predicted_data.get('emotion_values', {})
        if isinstance(emotion_values, str):
            try:
                emotion_values = json.loads(emotion_values) if emotion_values else {}
            except json.JSONDecodeError:
                emotion_values = {}
        if not isinstance(emotion_values, dict):
            emotion_values = {}
        
        # Also check for old 'emotions' field (comma-separated string or list) for backward compatibility
        if not emotion_values:
            emotions_data = predicted_data.get('emotions', '') or ''
            if isinstance(emotions_data, str):
                emotion_list = [e.strip() for e in emotions_data.split(',') if e.strip()]
            elif isinstance(emotions_data, list):
                emotion_list = [e for e in emotions_data if e]
            else:
                emotion_list = []
            if emotion_list:
                emotion_values = {emotion: 50 for emotion in emotion_list}  # Default value of 50 for old format
        
        if emotion_values:
            with ui.card().classes("w-full p-4 bg-blue-50"):
                for emotion, value in emotion_values.items():
                    try:
                        value_int = int(float(value)) if value is not None else 50
                    except (ValueError, TypeError):
                        value_int = 50
                    ui.label(f"• {emotion}: {value_int}/100").classes("text-sm mb-1")
        else:
            ui.label("No emotions specified").classes("text-gray-500 p-4")
        
        # Notes section (shared across instances with same initialization description)
        ui.label("Notes").classes("text-md font-semibold mt-4 mb-2")
        if notes:
            ui.markdown(notes).classes("w-full p-4 bg-gray-50 rounded border").style("max-height: 300px; overflow-y: auto; white-space: pre-wrap;")
        else:
            ui.label("No notes yet").classes("text-gray-500 p-4")
        
        # Description if available
        description = predicted_data.get('description', '')
        if description and description.strip():
            ui.label("Description").classes("text-md font-semibold mt-4 mb-2")
            ui.label(description.strip()).classes("text-sm text-gray-700 p-3 bg-gray-50 rounded border").style("max-height: 200px; overflow-y: auto; white-space: pre-wrap;")
        
        with ui.row().classes("gap-2 mt-6 justify-end"):
            ui.button("Close", on_click=dialog.close, color='primary')
        
    dialog.open()


def edit_instance(instance_id):
    """Edit a completed instance - navigate to completion page in edit mode."""
    instance = im.get_instance(instance_id)
    if not instance:
        ui.notify("Instance not found", color='negative')
        return
    
    # Check if instance is completed
    is_completed = instance.get('is_completed', False)
    completed_at = instance.get('completed_at', '')
    if is_completed or (completed_at and str(completed_at).strip() != ''):
        # Navigate to completion page in edit mode
        ui.navigate.to(f'/complete_task?instance_id={instance_id}&edit=true')
        return
    
    ui.notify("Instance not completed", color='warning')


def edit_completed_instance(instance_id):
    """Edit a completed instance - navigate to completion page with edit mode."""
    instance = im.get_instance(instance_id)
    if not instance:
        ui.notify("Instance not found", color='negative')
        return
    
    # Check if instance is completed
    completed_at = instance.get('completed_at', '')
    if not completed_at or str(completed_at).strip() == '':
        ui.notify("Instance not completed", color='warning')
        return
    
    # Navigate to completion page to edit
    ui.navigate.to(f'/complete_task?instance_id={instance_id}&edit=true')


def edit_template(task):
    """Open a dialog to edit a task template."""
    print(f"[Dashboard] edit_template called: {task.get('task_id')}")
    
    task_id = task.get('task_id')
    current_name = task.get('name', '')
    current_desc = task.get('description', '')
    current_task_type = task.get('task_type', 'Work')
    current_est = task.get('default_estimate_minutes', 0)
    
    # Get routine scheduling fields
    current_routine_frequency = task.get('routine_frequency', 'none') or 'none'
    current_routine_time = task.get('routine_time', '00:00') or '00:00'
    current_routine_days_str = task.get('routine_days_of_week', '[]') or '[]'
    current_completion_window_hours = task.get('completion_window_hours', '') or ''
    current_completion_window_days = task.get('completion_window_days', '') or ''
    
    try:
        current_est = int(current_est) if current_est else 0
    except (TypeError, ValueError):
        current_est = 0
    
    # Parse routine days
    try:
        current_routine_days = json.loads(current_routine_days_str) if isinstance(current_routine_days_str, str) else current_routine_days_str
        if not isinstance(current_routine_days, list):
            current_routine_days = []
    except (json.JSONDecodeError, TypeError):
        current_routine_days = []
    
    try:
        current_completion_window_hours = int(current_completion_window_hours) if current_completion_window_hours else None
    except (TypeError, ValueError):
        current_completion_window_hours = None
    
    try:
        current_completion_window_days = int(current_completion_window_days) if current_completion_window_days else None
    except (TypeError, ValueError):
        current_completion_window_days = None
    
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
        
        # Routine scheduling section
        ui.label("Routine Scheduling (Optional)").classes("text-lg font-semibold mt-4")
        
        routine_frequency = ui.select(
            ['none', 'daily', 'weekly'],
            label='Routine Frequency',
            value=current_routine_frequency
        ).classes("w-full")
        
        # Day of week selection (for weekly)
        day_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_checkboxes = {}
        day_container = ui.column().classes("gap-2")
        
        def update_day_visibility():
            """Show/hide day selection based on frequency"""
            day_container.set_visibility(routine_frequency.value in ['daily', 'weekly'])
        
        routine_frequency.on('update:model-value', lambda: update_day_visibility())
        
        with day_container:
            ui.label("Select days of week (leave all unchecked for daily to run every day):").classes("text-sm")
            for i, day in enumerate(day_labels):
                day_checkboxes[i] = ui.checkbox(day, value=(i in current_routine_days))
        
        day_container.set_visibility(current_routine_frequency in ['daily', 'weekly'])
        
        # Time picker
        routine_time = ui.input(
            label='Routine Time (HH:MM, 24-hour format)',
            value=current_routine_time,
            placeholder='00:00'
        ).classes("w-full max-w-xs")
        
        # Completion window (hours and days)
        ui.label("Completion Window (Optional)").classes("text-sm font-semibold")
        ui.label("Time to complete task after initialization without penalty").classes("text-xs text-gray-500")
        with ui.row().classes("gap-4"):
            completion_window_hours = ui.number(
                label='Hours',
                value=current_completion_window_hours,
                placeholder='Hours',
                min=0
            ).classes("flex-1")
            completion_window_days = ui.number(
                label='Days',
                value=current_completion_window_days,
                placeholder='Days',
                min=0
            ).classes("flex-1")
        
        def save_edit():
            if not name_input.value.strip():
                ui.notify("Task name required", color='negative')
                return

            # Validate time format
            time_str = routine_time.value.strip() or '00:00'
            try:
                # Basic validation: should be HH:MM format
                parts = time_str.split(':')
                if len(parts) != 2:
                    raise ValueError("Invalid time format")
                hour = int(parts[0])
                minute = int(parts[1])
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    raise ValueError("Invalid time values")
                # Normalize format
                time_str = f"{hour:02d}:{minute:02d}"
            except (ValueError, IndexError):
                ui.notify("Invalid time format. Use HH:MM (24-hour format, e.g., 09:30)", color='negative')
                return

            # Get selected days for daily or weekly routine
            selected_days = []
            if routine_frequency.value in ['daily', 'weekly']:
                selected_days = [i for i, cb in day_checkboxes.items() if cb.value]
                if routine_frequency.value == 'weekly' and not selected_days:
                    ui.notify("Please select at least one day for weekly routine", color='negative')
                    return
                # For daily, if no days selected, it means every day (empty list)
                # If days are selected, it means only on those days

            # Get completion window values (None if empty)
            completion_window_hours_val = None
            if completion_window_hours.value is not None and completion_window_hours.value > 0:
                completion_window_hours_val = int(completion_window_hours.value)
            
            completion_window_days_val = None
            if completion_window_days.value is not None and completion_window_days.value > 0:
                completion_window_days_val = int(completion_window_days.value)
            
            # Convert selected_days to JSON string for CSV compatibility
            selected_days_json = json.dumps(selected_days)
            
            success = tm.update_task(
                task_id,
                name=name_input.value.strip(),
                description=desc_input.value or '',
                task_type=task_type_select.value,
                default_estimate_minutes=int(est_input.value or 0),
                routine_frequency=routine_frequency.value,
                routine_days_of_week=selected_days_json,
                routine_time=time_str,
                completion_window_hours=completion_window_hours_val,
                completion_window_days=completion_window_days_val
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


def copy_template(task):
    """Open a dialog to copy a task template."""
    print(f"[Dashboard] copy_template called: {task.get('task_id')}")
    
    # Get all current values from the template
    current_name = task.get('name', '')
    current_desc = task.get('description', '')
    current_task_type = task.get('task_type', 'Work')
    current_est = task.get('default_estimate_minutes', 0)
    current_type = task.get('type', 'one-time')
    current_is_recurring = task.get('is_recurring', 'False')
    current_categories = task.get('categories', '[]')
    current_default_aversion_str = task.get('default_initial_aversion', '') or ''
    
    # Get routine scheduling fields
    current_routine_frequency = task.get('routine_frequency', 'none') or 'none'
    current_routine_time = task.get('routine_time', '00:00') or '00:00'
    current_routine_days_str = task.get('routine_days_of_week', '[]') or '[]'
    current_completion_window_hours = task.get('completion_window_hours', '') or ''
    current_completion_window_days = task.get('completion_window_days', '') or ''
    
    try:
        current_est = int(current_est) if current_est else 0
    except (TypeError, ValueError):
        current_est = 0
    
    # Parse default_initial_aversion
    current_default_aversion = None
    if current_default_aversion_str:
        try:
            current_default_aversion = int(float(current_default_aversion_str))
            if current_default_aversion < 0 or current_default_aversion > 100:
                current_default_aversion = None
        except (ValueError, TypeError):
            current_default_aversion = None
    
    # Parse is_recurring
    is_recurring_bool = str(current_is_recurring).lower() in ('true', '1', 'yes')
    
    # Parse routine days
    try:
        current_routine_days = json.loads(current_routine_days_str) if isinstance(current_routine_days_str, str) else current_routine_days_str
        if not isinstance(current_routine_days, list):
            current_routine_days = []
    except (json.JSONDecodeError, TypeError):
        current_routine_days = []
    
    try:
        current_completion_window_hours = int(current_completion_window_hours) if current_completion_window_hours else None
    except (TypeError, ValueError):
        current_completion_window_hours = None
    
    try:
        current_completion_window_days = int(current_completion_window_days) if current_completion_window_days else None
    except (TypeError, ValueError):
        current_completion_window_days = None
    
    # Default name with " (Copy)" appended
    default_copy_name = f"{current_name} (Copy)" if current_name else "New Task (Copy)"
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-2xl p-4'):
        ui.label("Copy Task Template").classes("text-xl font-bold mb-4")
        
        name_input = ui.input(label="Task Name", value=default_copy_name).classes("w-full")
        desc_input = ui.textarea(label="Description (optional)", value=current_desc).classes("w-full")
        task_type_select = ui.select(
            ['Work', 'Play', 'Self care'], 
            label='Task Type', 
            value=current_task_type
        ).classes("w-full")
        est_input = ui.number(label='Default estimate minutes', value=current_est).classes("w-full")
        
        # Aversion checkbox - checked if original had a default aversion value > 0
        aversion_checkbox = ui.checkbox("Check if you are averse to starting this task", value=(current_default_aversion is not None and current_default_aversion > 0))
        
        # Routine scheduling section
        ui.label("Routine Scheduling (Optional)").classes("text-lg font-semibold mt-4")
        
        routine_frequency = ui.select(
            ['none', 'daily', 'weekly'],
            label='Routine Frequency',
            value=current_routine_frequency
        ).classes("w-full")
        
        # Day of week selection (for weekly)
        day_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_checkboxes = {}
        day_container = ui.column().classes("gap-2")
        
        def update_day_visibility():
            """Show/hide day selection based on frequency"""
            day_container.set_visibility(routine_frequency.value in ['daily', 'weekly'])
        
        routine_frequency.on('update:model-value', lambda: update_day_visibility())
        
        with day_container:
            ui.label("Select days of week (leave all unchecked for daily to run every day):").classes("text-sm")
            for i, day in enumerate(day_labels):
                day_checkboxes[i] = ui.checkbox(day, value=(i in current_routine_days))
        
        day_container.set_visibility(current_routine_frequency in ['daily', 'weekly'])
        
        # Time picker
        routine_time = ui.input(
            label='Routine Time (HH:MM, 24-hour format)',
            value=current_routine_time,
            placeholder='00:00'
        ).classes("w-full max-w-xs")
        
        # Completion window (hours and days)
        ui.label("Completion Window (Optional)").classes("text-sm font-semibold")
        ui.label("Time to complete task after initialization without penalty").classes("text-xs text-gray-500")
        with ui.row().classes("gap-4"):
            completion_window_hours = ui.number(
                label='Hours',
                value=current_completion_window_hours,
                placeholder='Hours',
                min=0
            ).classes("flex-1")
            completion_window_days = ui.number(
                label='Days',
                value=current_completion_window_days,
                placeholder='Days',
                min=0
            ).classes("flex-1")
        
        def save_copy():
            if not name_input.value.strip():
                ui.notify("Task name required", color='negative')
                return

            # Validate time format
            time_str = routine_time.value.strip() or '00:00'
            try:
                # Basic validation: should be HH:MM format
                parts = time_str.split(':')
                if len(parts) != 2:
                    raise ValueError("Invalid time format")
                hour = int(parts[0])
                minute = int(parts[1])
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    raise ValueError("Invalid time values")
                # Normalize format
                time_str = f"{hour:02d}:{minute:02d}"
            except (ValueError, IndexError):
                ui.notify("Invalid time format. Use HH:MM (24-hour format, e.g., 09:30)", color='negative')
                return

            # Get default aversion value - if checkbox is checked, set to 50, otherwise 0
            default_aversion = 50 if aversion_checkbox.value else 0

            # Get selected days for daily or weekly routine
            selected_days = []
            if routine_frequency.value in ['daily', 'weekly']:
                selected_days = [i for i, cb in day_checkboxes.items() if cb.value]
                if routine_frequency.value == 'weekly' and not selected_days:
                    ui.notify("Please select at least one day for weekly routine", color='negative')
                    return
                # For daily, if no days selected, it means every day (empty list)
                # If days are selected, it means only on those days

            # Get completion window values (None if empty)
            completion_window_hours_val = None
            if completion_window_hours.value is not None and completion_window_hours.value > 0:
                completion_window_hours_val = int(completion_window_hours.value)
            
            completion_window_days_val = None
            if completion_window_days.value is not None and completion_window_days.value > 0:
                completion_window_days_val = int(completion_window_days.value)
            
            # Create new task with copied data
            tid = tm.create_task(
                name_input.value.strip(),
                description=desc_input.value or '',
                ttype=current_type,
                is_recurring=is_recurring_bool,
                categories=current_categories,
                default_estimate_minutes=int(est_input.value or 0),
                task_type=task_type_select.value,
                default_initial_aversion=default_aversion,
                routine_frequency=routine_frequency.value,
                routine_days_of_week=selected_days,
                routine_time=time_str,
                completion_window_hours=completion_window_hours_val,
                completion_window_days=completion_window_days_val
            )
            
            if tid:
                ui.notify("Task template copied", color='positive')
                dialog.close()
                refresh_templates()
            else:
                ui.notify("Copy failed", color='negative')
        
        with ui.row().classes("gap-2 mt-4"):
            ui.button("Create Copy", on_click=save_copy).props("color=primary")
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
        # Get all instances for this task (including completed)
        all_instances = im.get_instances_by_task_id(task_id, include_completed=True)
        # Filter to only initialized instances
        initialized = [
            inst for inst in all_instances
            if inst.get('initialized_at') and str(inst.get('initialized_at', '')).strip() != ''
        ]
        if initialized:
            time_values = []
            for inst in initialized:
                predicted_str = str(inst.get('predicted', '{}') or '{}').strip()
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
    
    # Use the module-level helper function
    pass
    
    # Expected Relief (0-100 scale, old data may have 0-10 values but we use as-is)
    relief = predicted_data.get('expected_relief')
    if relief is not None:
        try:
            relief = float(relief)
            avg_relief = averages.get('expected_relief')
            relief_color = get_value_with_deviation_color(relief, avg_relief, higher_is_worse=False)
            avg_text = f" (avg: {avg_relief:.1f})" if avg_relief else ""
            lines.append(f'<div><strong>Expected Relief:</strong> <span style="color: {relief_color}; font-weight: bold;">{relief:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Mental Energy Needed (0-100 scale, old data may have 0-10 values but we use as-is)
    mental_energy = predicted_data.get('expected_mental_energy')
    if mental_energy is None:
        # Backward compatibility: try old cognitive_load
        old_cog = predicted_data.get('expected_cognitive_load')
        if old_cog is not None:
            try:
                mental_energy = float(old_cog)
            except (ValueError, TypeError):
                pass
    if mental_energy is not None:
        try:
            mental_energy = float(mental_energy)
            avg_mental = averages.get('expected_mental_energy')
            if avg_mental is None:
                avg_mental = averages.get('expected_cognitive_load')  # Backward compatibility
            mental_color = get_value_with_deviation_color(mental_energy, avg_mental, higher_is_worse=True)
            avg_text = f" (avg: {avg_mental:.1f})" if avg_mental else ""
            lines.append(f'<div><strong>Mental Energy Needed:</strong> <span style="color: {mental_color}; font-weight: bold;">{mental_energy:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Task Difficulty (0-100 scale, old data may have 0-10 values but we use as-is)
    difficulty = predicted_data.get('expected_difficulty')
    if difficulty is None:
        # Backward compatibility: try old cognitive_load
        old_cog = predicted_data.get('expected_cognitive_load')
        if old_cog is not None:
            try:
                difficulty = float(old_cog)
            except (ValueError, TypeError):
                pass
    if difficulty is not None:
        try:
            difficulty = float(difficulty)
            avg_diff = averages.get('expected_difficulty')
            if avg_diff is None:
                avg_diff = averages.get('expected_cognitive_load')  # Backward compatibility
            diff_color = get_value_with_deviation_color(difficulty, avg_diff, higher_is_worse=True)
            avg_text = f" (avg: {avg_diff:.1f})" if avg_diff else ""
            lines.append(f'<div><strong>Task Difficulty:</strong> <span style="color: {diff_color}; font-weight: bold;">{difficulty:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Physical Load (0-100 scale, old data may have 0-10 values but we use as-is)
    phys_load = predicted_data.get('expected_physical_load')
    if phys_load is not None:
        try:
            phys_load = float(phys_load)
            avg_phys = averages.get('expected_physical_load')
            phys_color = get_value_with_deviation_color(phys_load, avg_phys, higher_is_worse=True)
            avg_text = f" (avg: {avg_phys:.1f})" if avg_phys else ""
            lines.append(f'<div><strong>Physical Load:</strong> <span style="color: {phys_color}; font-weight: bold;">{phys_load:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Expected Distress (0-100 scale, old data may have 0-10 values but we use as-is)
    emo_load = predicted_data.get('expected_emotional_load')
    if emo_load is not None:
        try:
            emo_load = float(emo_load)
            avg_emo = averages.get('expected_emotional_load')
            emo_color = get_value_with_deviation_color(emo_load, avg_emo, higher_is_worse=True)
            avg_text = f" (avg: {avg_emo:.1f})" if avg_emo else ""
            lines.append(f'<div><strong>Expected Distress:</strong> <span style="color: {emo_color}; font-weight: bold;">{emo_load:.1f}</span>{avg_text}</div>')
        except (ValueError, TypeError):
            pass
    
    # Motivation (0-100 scale, old data may have 0-10 values but we use as-is)
    motivation = predicted_data.get('motivation')
    if motivation is not None:
        try:
            motivation = float(motivation)
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


def _get_value_key_from_history(history_data: dict) -> str:
    """Auto-detect the value key from history data.
    
    Args:
        history_data: Dict with historical data
        
    Returns:
        Key name for values (e.g., 'hours', 'relief_points', 'productivity_scores')
    """
    # Common value keys in history data
    possible_keys = ['hours', 'relief_points', 'productivity_scores', 'scores', 'values']
    for key in possible_keys:
        if key in history_data and history_data[key] and isinstance(history_data[key], list):
            return key
    return None


def get_baseline_value(history_data: dict, baseline_type: str, value_key: str = None) -> float:
    """Get baseline value for a metric based on baseline type.
    
    Generic function that works with any metric's history data structure.
    
    Args:
        history_data: Dict with historical data (from get_weekly_hours_history or similar)
        baseline_type: One of 'last_3_months', 'last_month', 'last_week', 'average', 'all_data'
        value_key: Optional key name for values (e.g., 'hours', 'relief_points'). 
                   If None, will auto-detect from history_data
    
    Returns:
        Baseline value (float) - daily average
    """
    # Auto-detect value key if not provided
    if value_key is None:
        value_key = _get_value_key_from_history(history_data)
    
    # Get values list (empty list if not found)
    values = history_data.get(value_key, []) if value_key else []
    dates = history_data.get('dates', [])
    
    # Handle each baseline type generically
    if baseline_type == 'last_3_months':
        return history_data.get('three_month_average', 0.0)
    
    elif baseline_type == 'last_month':
        # Calculate last month average from daily data
        if dates and values and len(dates) == len(values):
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.now() - timedelta(days=30)
            last_month_values = []
            for i, date_str in enumerate(dates):
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    if date_obj >= thirty_days_ago.date() and i < len(values):
                        last_month_values.append(float(values[i]))
                except (ValueError, TypeError):
                    continue
            if last_month_values:
                return sum(last_month_values) / len(last_month_values)
        # Fallback to weekly average if calculation fails
        return history_data.get('weekly_average', 0.0)
    
    elif baseline_type == 'last_week':
        return history_data.get('weekly_average', 0.0)
    
    elif baseline_type == 'average':
        # Average of weekly_average and three_month_average
        weekly = history_data.get('weekly_average', 0.0)
        three_month = history_data.get('three_month_average', 0.0)
        if weekly > 0 and three_month > 0:
            return (weekly + three_month) / 2.0
        return weekly if weekly > 0 else three_month
    
    elif baseline_type == 'all_data':
        # Average of all historical values
        if values:
            try:
                numeric_values = [float(v) for v in values if v is not None]
                if numeric_values:
                    return sum(numeric_values) / len(numeric_values)
            except (ValueError, TypeError):
                pass
        # Fallback to weekly average
        return history_data.get('weekly_average', 0.0)
    
    else:
        # Default to three_month_average
        return history_data.get('three_month_average', 0.0)


def render_monitored_metrics_section(container):
    """Render the monitored metrics section with up to 4 configurable metrics.
    
    Args:
        container: UI container to render into
    """
    from datetime import datetime, timedelta
    import json
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:1788', 'message': 'render_monitored_metrics_section entry', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    metrics_start = time.perf_counter()
    init_perf_logger = get_init_perf_logger()
    init_perf_logger.log_event("render_monitored_metrics_start")
    
    # Get configuration
    config = user_state.get_monitored_metrics_config(DEFAULT_USER_ID)
    selected_metrics = config.get('selected_metrics', ['productivity_time', 'productivity_score'])
    coloration_baseline = config.get('coloration_baseline', 'last_3_months')
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'dashboard.py:1806', 'message': 'selected_metrics before limit', 'data': {'selected_metrics': selected_metrics, 'count': len(selected_metrics)}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    # Limit to 4 metrics
    selected_metrics = selected_metrics[:4]
    
    # Create metrics grid and header immediately
    with container:
        # Header with edit and update buttons
        with ui.row().classes("w-full justify-between items-center mb-2"):
            ui.label("Monitored Metrics").classes("text-sm font-semibold")
            with ui.row().classes("gap-1"):
                ui.button("Update", on_click=update_monitored_metrics).props("dense size=sm").classes("bg-green-500 text-white")
                ui.button("Edit", on_click=lambda: open_metrics_config_dialog()).props("dense size=sm")
        
        # Experimental warning
        with ui.row().classes("w-full mb-2"):
            ui.label("⚠️ EXPERIMENTAL: Some data may not load correctly. See Analytics page for all correct data.").classes("text-xs text-orange-600 italic")
        
        # Metrics grid - 2 columns, 2 rows
        metrics_grid = ui.row().classes("w-full gap-1").style("display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.25rem;")
        
        # Create placeholder cards for all selected metrics immediately
        metric_cards = {}  # Store card references: metric_key -> {card, value_label, baseline_label, tooltip_id}
        for metric_key in selected_metrics:
            with metrics_grid:
                card = ui.card().classes("p-2 metric-card-hover bg-gray-100 context-menu-card").style("min-width: 0;").props(f'data-context-menu="metric" data-metric-key="{metric_key}"')
                with card:
                    label_widget = ui.label("Loading...").classes("text-xs text-gray-500 mb-0.5")
                    value_label = ui.label("...").classes("text-lg font-bold")
                    baseline_label = ui.label("...").classes("text-xs text-gray-400")
                    
                    # Create hidden button for context menu reset action (only for daily_productivity_score_idle_refresh)
                    if metric_key == 'daily_productivity_score_idle_refresh':
                        reset_button_id = f'context-btn-metric-reset-{metric_key}'
                        ui.button("", on_click=lambda key=metric_key: reset_metric_score(key)).props(f'id="{reset_button_id}"').style("display: none;")
                
                # Create tooltip container
                tooltip_id = f'monitored-{metric_key}'
                ui.add_body_html(f'<div id="tooltip-{tooltip_id}" class="metric-tooltip" style="min-width: 400px; max-width: 500px;"><div style="padding: 10px; text-align: center; color: #666;">Loading...</div></div>')
                
                metric_cards[metric_key] = {
                    'card': card,
                    'label': label_widget,
                    'value_label': value_label,
                    'baseline_label': baseline_label,
                    'tooltip_id': tooltip_id,
                    'rendered': False,
                    'metric_key': metric_key,
                    'manually_reset': False  # Flag to prevent auto-updates after manual reset
                }
    
    def get_targeted_metric_values(metrics_list, an):
        """Get only the specific metric values needed, without calculating all metrics.
        
        This is much faster than calling get_relief_summary(), get_dashboard_metrics(), etc.
        which calculate everything. Only calls the full functions if absolutely necessary.
        
        Returns:
            dict with keys: 'relief_summary', 'quality_metrics', 'composite_scores'
            Each contains only the values needed for the selected metrics.
        """
        result = {
            'relief_summary': {},
            'quality_metrics': {},
            'composite_scores': {}
        }
        
        # Metrics that come from relief_summary
        relief_metrics = {'productivity_time', 'productivity_score'}
        needs_productivity_time = 'productivity_time' in metrics_list
        needs_productivity_score = 'productivity_score' in metrics_list
        
        if needs_productivity_time or needs_productivity_score:
            # Use lightweight function for productivity_time
            if needs_productivity_time:
                if hasattr(an, 'get_productivity_time_minutes'):
                    result['relief_summary']['productivity_time_minutes'] = an.get_productivity_time_minutes()
                else:
                    # Fallback: get from relief_summary (cached, so not too expensive)
                    relief = an.get_relief_summary()
                    result['relief_summary']['productivity_time_minutes'] = relief.get('productivity_time_minutes', 0)
            
            if needs_productivity_score:
                # For productivity_score, we need weekly_productivity_score from relief_summary
                # Note: get_relief_summary() is cached, so if it was already called, this is fast
                # If productivity_time was already loaded above, we might have the cache
                if 'productivity_time_minutes' in result['relief_summary'] and hasattr(an, '_relief_summary_cache'):
                    # Try to get from cache if available
                    if an._relief_summary_cache is not None:
                        result['relief_summary']['weekly_productivity_score'] = an._relief_summary_cache.get('weekly_productivity_score', 0.0)
                    else:
                        relief = an.get_relief_summary()
                        result['relief_summary']['weekly_productivity_score'] = relief.get('weekly_productivity_score', 0.0)
                else:
                    relief = an.get_relief_summary()
                    result['relief_summary']['weekly_productivity_score'] = relief.get('weekly_productivity_score', 0.0)
                    # Also get productivity_time_minutes if we didn't already
                    if needs_productivity_time and 'productivity_time_minutes' not in result['relief_summary']:
                        result['relief_summary']['productivity_time_minutes'] = relief.get('productivity_time_minutes', 0)
        
        # Metrics that come from quality_metrics (dashboard_metrics)
        # Only get the specific metrics we need, not all dashboard metrics
        quality_metric_keys = []
        for metric in metrics_list:
            if metric not in relief_metrics and metric != 'execution_score':
                # Check if this metric is likely in quality_metrics
                # Common quality metrics: avg_*, thoroughness_*, adjusted_wellbeing, etc.
                if (metric.startswith('avg_') or 
                    metric.startswith('thoroughness_') or 
                    metric in ['adjusted_wellbeing', 'adjusted_wellbeing_normalized', 
                              'general_aversion_score', 'expected_relief']):
                    quality_metric_keys.append(metric)
        
        if quality_metric_keys:
            # Build list of dashboard metric keys to request (format: 'category.key')
            dashboard_metric_keys = []
            for key in quality_metric_keys:
                # Map metric keys to dashboard metric paths
                if key.startswith('avg_'):
                    dashboard_metric_keys.append(f'quality.{key}')
                elif key in ['adjusted_wellbeing', 'adjusted_wellbeing_normalized', 'thoroughness_score', 'thoroughness_factor']:
                    dashboard_metric_keys.append(f'quality.{key}')
                elif key == 'general_aversion_score':
                    dashboard_metric_keys.append(f'aversion.{key}')
                elif key == 'expected_relief':
                    dashboard_metric_keys.append('quality.avg_expected_relief')
            
            # Call get_dashboard_metrics() with selective calculation
            metrics_data = an.get_dashboard_metrics(metrics=dashboard_metric_keys) if hasattr(an, 'get_dashboard_metrics') else {}
            quality = metrics_data.get('quality', {})
            aversion = metrics_data.get('aversion', {})
            
            # Extract only the metrics we need
            for key in quality_metric_keys:
                if key in quality:
                    result['quality_metrics'][key] = quality[key]
                elif f'avg_{key}' in quality:
                    result['quality_metrics'][key] = quality[f'avg_{key}']
                elif key in aversion:
                    result['quality_metrics'][key] = aversion[key]
                elif key == 'expected_relief' and 'avg_expected_relief' in quality:
                    result['quality_metrics'][key] = quality['avg_expected_relief']
        
        # Metrics that come from composite_scores
        known_composite_metrics = {'execution_score', 'grit_score', 'tracking_consistency_score', 
                                   'work_volume_score', 'work_consistency_score', 'life_balance_score',
                                   'completion_rate', 'self_care_frequency', 'weekly_relief_score'}
        composite_metric_keys = [m for m in metrics_list if m in known_composite_metrics and m != 'execution_score']
        
        if composite_metric_keys:
            # Call get_all_scores_for_composite() with selective calculation
            # (execution_score is handled separately in chunks)
            all_composite = an.get_all_scores_for_composite(days=7, metrics=list(composite_metric_keys)) if hasattr(an, 'get_all_scores_for_composite') else {}
            
            # Extract only the metrics we need
            for key in composite_metric_keys:
                if key in all_composite:
                    result['composite_scores'][key] = all_composite[key]
        
        return result
    
    def determine_needed_data_sources(metrics_list):
        """Determine which data sources are needed based on selected metrics.
        
        Returns:
            dict with keys: 'needs_relief', 'needs_quality', 'needs_composite', 'needs_execution_score'
        """
        # Metrics that need relief_summary
        relief_metrics = {'productivity_time', 'productivity_score'}
        needs_relief = any(m in relief_metrics for m in metrics_list)
        
        # Metrics that are known to be in composite_scores
        known_composite_metrics = {'execution_score', 'grit_score', 'tracking_consistency_score', 
                                   'work_volume_score', 'work_consistency_score', 'life_balance_score',
                                   'completion_rate', 'self_care_frequency'}
        needs_quality = False
        needs_composite = False
        needs_execution_score = False
        
        for metric in metrics_list:
            if metric in relief_metrics:
                continue  # Already handled by needs_relief
            elif metric == 'execution_score':
                needs_execution_score = True
                needs_composite = True  # execution_score is part of composite
            elif metric in known_composite_metrics:
                needs_composite = True
            else:
                # Generic metric - could be in quality_metrics or composite_scores
                # Load quality_metrics first (cheaper), but also load composite as fallback
                # since get_value checks quality first, then composite
                needs_quality = True
                # Also load composite as fallback for generic metrics
                needs_composite = True
        
        return {
            'needs_relief': needs_relief,
            'needs_quality': needs_quality,
            'needs_composite': needs_composite,
            'needs_execution_score': needs_execution_score
        }
    
    def load_and_render():
        """Load metrics data incrementally using ui.timer to keep UI responsive (single-threaded).
        
        Uses targeted loading to only calculate the specific metrics displayed, not all available metrics.
        """
        # State for incremental loading - persists between timer calls
        load_state = {
            'step': 0,  # 0=targeted_load, 1=execution_score (if needed), 2=render
            'relief_summary': None,
            'quality_metrics': None,
            'composite_scores': None,
            'timer': None
        }
        
        def process_next_step():
            """Process one step of loading, then yield back to event loop.
            
            Uses targeted loading to only calculate metrics that are actually displayed.
            """
            try:
                if load_state['step'] == 0:
                    # Step 1: Get only the specific metric values we need (targeted loading)
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'TARGETED', 'location': 'dashboard.py:process_next_step', 'message': 'step 0: calling get_targeted_metric_values', 'data': {'selected_metrics': selected_metrics, 'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    try:
                        with init_perf_logger.operation("get_targeted_metric_values"):
                            targeted_data = get_targeted_metric_values(selected_metrics, an)
                            load_state['relief_summary'] = targeted_data.get('relief_summary', {})
                            load_state['quality_metrics'] = targeted_data.get('quality_metrics', {})
                            load_state['composite_scores'] = targeted_data.get('composite_scores', {})
                    except Exception as e:
                        print(f"[Dashboard] Error getting targeted metric values: {e}")
                        import traceback
                        traceback.print_exc()
                        load_state['relief_summary'] = {}
                        load_state['quality_metrics'] = {}
                        load_state['composite_scores'] = {}
                    
                    # Check if we need execution_score
                    needs_execution_score = 'execution_score' in selected_metrics
                    
                    if needs_execution_score:
                        # Initialize execution score chunked calculation state
                        load_state['execution_score_state'] = {}
                        load_state['step'] = 1
                    else:
                        # Skip execution score - not needed, go straight to render
                        load_state['step'] = 2
                    
                    # Update metrics with loaded data (before execution_score if needed)
                    _update_metric_cards_incremental(
                        metric_cards,
                        selected_metrics,
                        load_state['relief_summary'],
                        load_state['quality_metrics'],
                        load_state['composite_scores'],
                        coloration_baseline,
                        an,
                        init_perf_logger
                    )
                    
                    # Schedule next step
                    load_state['timer'] = ui.timer(0.1, process_next_step, once=True)
                    
                elif load_state['step'] == 1:
                    # Step 2: Calculate execution score in chunks (only if needed)
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'CHUNK', 'location': 'dashboard.py:process_next_step', 'message': 'step 1: processing execution score chunk', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    try:
                        if hasattr(an, 'get_execution_score_chunked'):
                            # Process a batch of instances (5 at a time) with persistence
                            load_state['execution_score_state'] = an.get_execution_score_chunked(
                                load_state['execution_score_state'], 
                                batch_size=5,
                                user_id="default",
                                persist=True
                            )
                            
                            if load_state['execution_score_state'].get('completed', False):
                                # All instances processed - update composite scores and move to render
                                avg_score = load_state['execution_score_state'].get('avg_execution_score', 50.0)
                                load_state['composite_scores']['execution_score'] = avg_score
                                # Update metrics that depend on execution_score
                                _update_metric_cards_incremental(
                                    metric_cards,
                                    selected_metrics,
                                    load_state['relief_summary'],
                                    load_state['quality_metrics'],
                                    load_state['composite_scores'],
                                    coloration_baseline,
                                    an,
                                    init_perf_logger
                                )
                                load_state['step'] = 2
                            else:
                                # More chunks to process - schedule next chunk
                                load_state['timer'] = ui.timer(0.1, process_next_step, once=True)
                                return  # Yield back to event loop
                        else:
                            # Fallback if chunked method doesn't exist
                            load_state['composite_scores']['execution_score'] = 50.0
                            load_state['step'] = 2
                    except Exception as e:
                        print(f"[Dashboard] Error calculating execution score in chunks: {e}")
                        load_state['composite_scores']['execution_score'] = 50.0
                        load_state['step'] = 2
                    
                    # Schedule render step
                    if load_state['step'] == 2:
                        load_state['timer'] = ui.timer(0.1, process_next_step, once=True)
                    
                elif load_state['step'] == 2:
                    # Step 3: Final render - all data loaded
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'TARGETED', 'location': 'dashboard.py:process_next_step', 'message': 'step 2: final render', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    # Cancel timer
                    if load_state['timer']:
                        load_state['timer'].cancel()
                    
                    # Final update of all metric cards with loaded data
                    try:
                        _update_metric_cards_incremental(
                            metric_cards,
                            selected_metrics,
                            load_state['relief_summary'],
                            load_state['quality_metrics'],
                            load_state['composite_scores'],
                            coloration_baseline,
                            an,
                            init_perf_logger
                        )
                        
                        # Store state for periodic refresh
                        global _monitored_metrics_state
                        _monitored_metrics_state['metric_cards'] = metric_cards
                        _monitored_metrics_state['selected_metrics'] = selected_metrics
                        _monitored_metrics_state['coloration_baseline'] = coloration_baseline
                        _monitored_metrics_state['analytics_instance'] = an
                        
                        # Set up periodic refresh for daily productivity score (resets at midnight)
                        _setup_periodic_metric_refresh(metric_cards, selected_metrics, an)
                    except Exception as e:
                        print(f"[Dashboard] Error updating metric cards: {e}")
                        import traceback
                        traceback.print_exc()
            except Exception as e:
                print(f"[Dashboard] Error in process_next_step: {e}")
                import traceback
                traceback.print_exc()
        
        # Start incremental loading
        load_state['timer'] = ui.timer(0.1, process_next_step, once=True)
    
    # Defer expensive call - allows dashboard to render first
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:render_monitored_metrics_section', 'message': 'setting up ui.timer for load_and_render', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    ui.timer(0.1, load_and_render, once=True)
    
    # Return early - actual rendering happens in load_and_render
    return


def _setup_periodic_metric_refresh(metric_cards, selected_metrics, an):
    """Set up periodic refresh for time-sensitive metrics like daily_productivity_score_idle_refresh.
    
    This function creates a timer that periodically refreshes metrics that depend on current time,
    such as the daily productivity score which resets at midnight each day.
    """
    global _monitored_metrics_state
    
    # Cancel any existing refresh timer
    if _monitored_metrics_state.get('refresh_timer'):
        try:
            _monitored_metrics_state['refresh_timer'].cancel()
        except:
            pass
    
    # Only set up periodic refresh if daily_productivity_score_idle_refresh is selected
    if 'daily_productivity_score_idle_refresh' not in selected_metrics:
        return
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'sessionId': 'debug-session',
                'runId': 'run1',
                'hypothesisId': 'REFRESH_SETUP',
                'location': 'dashboard.py:_setup_periodic_metric_refresh',
                'message': 'Setting up periodic refresh for daily_productivity_score_idle_refresh',
                'data': {},
                'timestamp': int(time.time() * 1000)
            }) + '\n')
    except: pass
    # #endregion
    
    # Track last refresh date to detect midnight crossing
    from datetime import datetime, date
    _monitored_metrics_state['last_refresh_date'] = date.today()
    
    def refresh_idle_metric():
        """Periodically refresh the daily productivity score metric (resets at midnight)."""
        global _monitored_metrics_state
        
        metric_key = 'daily_productivity_score_idle_refresh'
        metric_cards_ref = _monitored_metrics_state.get('metric_cards', {})
        an_ref = _monitored_metrics_state.get('analytics_instance')
        
        if metric_key not in metric_cards_ref or an_ref is None:
            return
        
        # Check if we've crossed midnight
        current_date = date.today()
        last_refresh_date = _monitored_metrics_state.get('last_refresh_date')
        
        # Always refresh (metric updates throughout the day), but log midnight crossing
        should_refresh = True
        if last_refresh_date and current_date != last_refresh_date:
            # Midnight crossed - this is when the score resets
            should_refresh = True
            _monitored_metrics_state['last_refresh_date'] = current_date
        
        if not should_refresh:
            return
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'PERIODIC_REFRESH',
                    'location': 'dashboard.py:refresh_idle_metric',
                    'message': 'Periodic refresh triggered for daily_productivity_score_idle_refresh',
                    'data': {
                        'current_date': str(current_date),
                        'last_refresh_date': str(last_refresh_date) if last_refresh_date else None,
                        'midnight_crossed': current_date != last_refresh_date if last_refresh_date else False
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        try:
            # Recalculate the metric (resets at midnight)
            score_data = an_ref.calculate_daily_productivity_score_with_idle_refresh(
                target_date=None,  # None = current day with rolling calculation
                idle_refresh_hours=8.0  # Deprecated parameter, kept for compatibility
            )
            new_value = score_data.get('daily_score', 0.0)
            
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'PERIODIC_REFRESH',
                        'location': 'dashboard.py:refresh_idle_metric',
                        'message': 'Calculated new value for daily_productivity_score_idle_refresh',
                        'data': {
                            'new_value': new_value,
                            'total_tasks': score_data.get('total_tasks', 0),
                            'segment_count': score_data.get('segment_count', 0)
                        },
                        'timestamp': int(time.time() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            
            # Update the UI
            card_info = metric_cards_ref.get(metric_key)
            if card_info and card_info.get('value_label'):
                formatted_value = f"{new_value:.1f}"
                value_label = card_info['value_label']
                if hasattr(value_label, 'text'):
                    value_label.text = formatted_value
                elif hasattr(value_label, 'set_text'):
                    value_label.set_text(formatted_value)
                
                # #region agent log
                try:
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'PERIODIC_REFRESH',
                            'location': 'dashboard.py:refresh_idle_metric',
                            'message': 'Updated UI with new value',
                            'data': {
                                'formatted_value': formatted_value,
                                'has_text_attr': hasattr(value_label, 'text'),
                                'has_set_text': hasattr(value_label, 'set_text')
                            },
                            'timestamp': int(time.time() * 1000)
                        }) + '\n')
                except: pass
                # #endregion
        except Exception as e:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'PERIODIC_REFRESH',
                        'location': 'dashboard.py:refresh_idle_metric',
                        'message': 'Error during periodic refresh',
                        'data': {'error': str(e)},
                        'timestamp': int(time.time() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            print(f"[Dashboard] Error refreshing daily_productivity_score_idle_refresh: {e}")
    
    # Set up timer to refresh every minute (60 seconds)
    # This ensures we catch midnight crossing and keep the metric updated throughout the day
    refresh_timer = ui.timer(60.0, refresh_idle_metric)
    _monitored_metrics_state['refresh_timer'] = refresh_timer


def _update_metric_cards_incremental(metric_cards, selected_metrics, relief_summary, quality_metrics, composite_scores, coloration_baseline, an, init_perf_logger):
    """Update metric cards incrementally as data becomes available.
    
    Args:
        metric_cards: Dict of metric_key -> {card, value_label, baseline_label, tooltip_id, rendered}
        selected_metrics: List of metric keys to render
        relief_summary: Dict with relief summary data (may be None/partial)
        quality_metrics: Dict with quality metrics (may be None/partial)
        composite_scores: Dict with composite scores (may be None/partial)
        coloration_baseline: Baseline type for coloration
        an: Analytics instance
        init_perf_logger: Performance logger
    """
    import json
    import time
    import pandas as pd
    from ui.analytics_page import CALCULATED_METRICS, ATTRIBUTE_LABELS
    
    # Use provided metrics or empty dicts
    if relief_summary is None:
        relief_summary = {}
    if quality_metrics is None:
        quality_metrics = {}
    if composite_scores is None:
        composite_scores = {}
    
    # Build available_metrics (same logic as render_monitored_metrics_section_loaded)
    available_metrics = {
        'productivity_time': {
            'label': 'Productivity Time',
            'get_value': lambda: relief_summary.get('productivity_time_minutes', 0) / 60.0,
            'format_value': lambda v: f"{v:.1f} hrs" if v >= 1 else f"{relief_summary.get('productivity_time_minutes', 0):.0f} min",
            'get_history': lambda: an.get_weekly_hours_history(),
            'history_key': 'hours',
            'tooltip_id': 'monitored-productivity-time',
            'chart_title': 'Daily Hours'
        },
        'productivity_score': {
            'label': 'Productivity Score',
            'get_value': lambda: relief_summary.get('weekly_productivity_score', 0.0),
            'format_value': lambda v: f"{v:.1f}",
            'get_history': lambda: an.get_weekly_productivity_score_history() if hasattr(an, 'get_weekly_productivity_score_history') else None,
            'history_key': 'scores',
            'tooltip_id': 'monitored-productivity-score',
            'chart_title': 'Daily Productivity Score'
        },
    }
    
    # Build generic metric configs
    for metric_key in selected_metrics:
        if metric_key not in available_metrics:
            label = ATTRIBUTE_LABELS.get(metric_key, metric_key.replace('_', ' ').title())
            
            def make_get_value(key, qual_metrics=quality_metrics, comp_scores=composite_scores, relief=relief_summary, analytics_instance=an):
                def get_generic_value():
                    # ====================================================================
                    # SPECIAL HANDLING FOR CALCULATED METRICS
                    # ====================================================================
                    # Some metrics require on-demand calculation rather than lookup from
                    # standard dictionaries (quality_metrics, relief_summary, composite_scores).
                    # This pattern can be extended for other metrics that need special logic.
                    #
                    # Example: daily_productivity_score_idle_refresh needs to calculate
                    # a daily score that resets at midnight each day.
                    # It's not pre-calculated in any standard metric dictionary.
                    # ====================================================================
                    
                    # Special handling for daily_productivity_score_idle_refresh - calculate on demand
                    # This metric calculates a daily productivity score that accumulates
                    # throughout the day and resets at midnight each day.
                    # For the current day, it accumulates scores from midnight up to the current time.
                    if key == 'daily_productivity_score_idle_refresh':
                        try:
                            score_data = analytics_instance.calculate_daily_productivity_score_with_idle_refresh(
                                target_date=None,  # None = current day with rolling calculation
                                idle_refresh_hours=8.0  # Deprecated parameter, kept for compatibility
                            )
                            result = score_data.get('daily_score', 0.0)
                            return float(result)
                        except Exception as e:
                            print(f"[Dashboard] Error calculating daily_productivity_score_idle_refresh: {e}")
                            return 0.0
                    
                    # Special handling for expected_relief - get from analytics
                    if key == 'expected_relief':
                        try:
                            # Try to get from dashboard_metrics first
                            dashboard_metrics = analytics_instance.get_dashboard_metrics()
                            if dashboard_metrics and 'quality' in dashboard_metrics:
                                val = dashboard_metrics['quality'].get('avg_expected_relief')
                                if val is not None:
                                    return float(val)
                            # Fallback: calculate from instances
                            df = analytics_instance._load_instances()
                            if not df.empty:
                                completed = df[df['completed_at'].astype(str).str.len() > 0]
                                if not completed.empty:
                                    def _get_expected_relief(row):
                                        try:
                                            pred_dict = row.get('predicted_dict', {})
                                            if isinstance(pred_dict, dict):
                                                return pred_dict.get('expected_relief')
                                        except:
                                            pass
                                        return None
                                    expected_reliefs = completed.apply(_get_expected_relief, axis=1)
                                    expected_reliefs = pd.to_numeric(expected_reliefs, errors='coerce').dropna()
                                    if not expected_reliefs.empty:
                                        return float(expected_reliefs.mean())
                        except Exception as e:
                            print(f"[Dashboard] Error getting expected_relief: {e}")
                        return 0.0
                    
                    # Standard lookup for other metrics
                    if key in qual_metrics:
                        val = qual_metrics.get(key)
                        return float(val) if val is not None else 0.0
                    avg_key = f'avg_{key}'
                    if avg_key in qual_metrics:
                        val = qual_metrics.get(avg_key)
                        return float(val) if val is not None else 0.0
                    if key in relief:
                        val = relief.get(key)
                        return float(val) if val is not None else 0.0
                    if key in comp_scores:
                        val = comp_scores.get(key)
                        return float(val) if val is not None else 0.0
                    return 0.0
                return get_generic_value
            
            def make_get_history(key):
                def get_history():
                    if hasattr(an, 'get_generic_metric_history'):
                        return an.get_generic_metric_history(key, days=90)
                    return None
                return get_history
            
            available_metrics[metric_key] = {
                'label': label,
                'get_value': make_get_value(metric_key),
                'format_value': lambda v: f"{v:.1f}",
                'get_history': make_get_history(metric_key),
                'history_key': 'values',
                'tooltip_id': f'monitored-{metric_key}',
                'chart_title': f'Daily {label}'
            }
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'UPDATE', 'location': 'dashboard.py:_update_metric_cards_incremental', 'message': 'update function called', 'data': {'selected_metrics': selected_metrics, 'metric_cards_keys': list(metric_cards.keys()), 'available_metrics_keys': list(available_metrics.keys()), 'has_relief': bool(relief_summary), 'has_quality': bool(quality_metrics), 'has_composite': bool(composite_scores)}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    # Update each metric card if data is available
    for metric_key in selected_metrics:
        if metric_key not in metric_cards or metric_key not in available_metrics:
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'UPDATE', 'location': 'dashboard.py:_update_metric_cards_incremental', 'message': 'skipping metric - not in cards or available', 'data': {'metric_key': metric_key, 'in_cards': metric_key in metric_cards, 'in_available': metric_key in available_metrics}, 'timestamp': int(time.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            continue
        
        card_info = metric_cards[metric_key]
        metric_config = available_metrics[metric_key]
        
        # Skip update if metric was manually reset (temporary workaround)
        if card_info.get('manually_reset', False):
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'UPDATE',
                        'location': 'dashboard.py:_update_metric_cards_incremental',
                        'message': 'Skipping update - metric was manually reset',
                        'data': {
                            'metric_key': metric_key
                        },
                        'timestamp': int(time.time() * 1000)
                    }) + '\n')
            except: pass
            # #endregion
            continue
        
        # Check if we have the minimum data needed to render this metric
        # Some metrics need relief_summary, others need quality_metrics or composite_scores
        try:
            current_value = metric_config['get_value']()
        except Exception as e:
            # Data not ready yet - skip this update
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'UPDATE', 'location': 'dashboard.py:_update_metric_cards_incremental', 'message': 'metric data not ready', 'data': {'metric_key': metric_key, 'error': str(e)}, 'timestamp': int(time.time() * 1000)}) + '\n')
            except: pass
            # #endregion
            continue
        
        # Update card label (change from "Loading..." to actual label)
        try:
            if hasattr(card_info['label'], 'text'):
                card_info['label'].text = metric_config['label']
            elif hasattr(card_info['label'], 'set_text'):
                card_info['label'].set_text(metric_config['label'])
            else:
                print(f"[Dashboard] Label widget for {metric_key} doesn't support text updates")
        except Exception as e:
            print(f"[Dashboard] Error updating label for {metric_key}: {e}")
            import traceback
            traceback.print_exc()
        
        # Update value (change from "..." to actual value)
        try:
            formatted_value = metric_config['format_value'](current_value)
            if hasattr(card_info['value_label'], 'text'):
                card_info['value_label'].text = formatted_value
            elif hasattr(card_info['value_label'], 'set_text'):
                card_info['value_label'].set_text(formatted_value)
            else:
                print(f"[Dashboard] Value label widget for {metric_key} doesn't support text updates")
            # #region agent log
            try:
                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'UPDATE', 'location': 'dashboard.py:_update_metric_cards_incremental', 'message': 'updating metric card value', 'data': {'metric_key': metric_key, 'value': current_value, 'formatted': formatted_value, 'has_text_attr': hasattr(card_info['value_label'], 'text'), 'has_set_text': hasattr(card_info['value_label'], 'set_text')}, 'timestamp': int(time.time() * 1000)}) + '\n')
            except: pass
            # #endregion
        except Exception as e:
            print(f"[Dashboard] Error updating value for {metric_key}: {e}")
            import traceback
            traceback.print_exc()
        
        # Get history for baseline (only once, when fully rendered)
        if not card_info.get('rendered', False):
            try:
                history_data = metric_config['get_history']()
                if history_data is None:
                    history_data = {}
            except Exception as e:
                history_data = {}
            
            # Calculate baseline
            if history_data and len(history_data.get('dates', [])) > 0:
                value_key = metric_config.get('history_key') or _get_value_key_from_history(history_data)
                baseline_daily = get_baseline_value(history_data, coloration_baseline, value_key)
                baseline_value = baseline_daily * 7.0
            else:
                baseline_value = current_value
            
            # Update baseline label
            baseline_label_text = {
                'last_3_months': '3mo avg',
                'last_month': '1mo avg',
                'last_week': '1wk avg',
                'average': 'avg',
                'all_data': 'all avg'
            }.get(coloration_baseline, 'avg')
            
            if 'time' in metric_key.lower() or 'hours' in metric_config.get('label', '').lower():
                if baseline_value > 0:
                    card_info['baseline_label'].text = f"{baseline_label_text}: {baseline_value:.1f}h/wk"
                else:
                    card_info['baseline_label'].text = f"{baseline_label_text}: N/A"
            else:
                if baseline_value > 0:
                    card_info['baseline_label'].text = f"{baseline_label_text}: {baseline_value:.1f}"
                else:
                    card_info['baseline_label'].text = f"{baseline_label_text}: N/A"
            
            # Store baseline for color calculation
            card_info['baseline_value'] = baseline_value
            
            # Update card styling (always update colors, not just on first render)
            bg_class, line_color = get_metric_bg_class(current_value, baseline_value)
            # Update classes - NiceGUI doesn't support direct assignment, so use style for bg color
            # Store bg class for reference
            card_info['current_bg_class'] = bg_class
            # Use style to set background color instead of classes
            bg_color_map = {
                'metric-bg-green': '#d1fae5',
                'metric-bg-yellow': '#fef3c7',
                'metric-bg-red': '#fee2e2',
                '': '#f3f4f6'  # Default gray for no data
            }
            bg_color = bg_color_map.get(bg_class, '#f3f4f6')
            try:
                # Update style with background color
                # NiceGUI cards need style applied directly with !important to override defaults
                card_info['card'].style(f"min-width: 0; background-color: {bg_color} !important;")
            except Exception as e:
                print(f"[Dashboard] Error updating card style for {metric_key}: {e}")
                # Fallback: try adding class directly (if NiceGUI supports it)
                try:
                    # Remove old bg classes and add new one
                    for old_class in ['metric-bg-green', 'metric-bg-yellow', 'metric-bg-red']:
                        if old_class in str(card_info['card'].classes):
                            card_info['card'].classes = card_info['card'].classes.replace(old_class, '')
                    if bg_class:
                        card_info['card'].classes = f"{card_info['card'].classes} {bg_class}".strip()
                except:
                    pass
            try:
                card_info['card'].props(f'data-tooltip-id="{metric_config["tooltip_id"]}"')
            except Exception as e:
                print(f"[Dashboard] Error updating card props for {metric_key}: {e}")
            
            card_info['rendered'] = True
        else:
            # Already rendered - just update colors with current value and stored baseline
            baseline_value = card_info.get('baseline_value', current_value)
            bg_class, line_color = get_metric_bg_class(current_value, baseline_value)
            card_info['current_bg_class'] = bg_class
            bg_color_map = {
                'metric-bg-green': '#d1fae5',
                'metric-bg-yellow': '#fef3c7',
                'metric-bg-red': '#fee2e2',
                '': '#f3f4f6'  # Default gray for no data
            }
            bg_color = bg_color_map.get(bg_class, '#f3f4f6')
            try:
                card_info['card'].style(f"min-width: 0; background-color: {bg_color} !important;")
            except Exception as e:
                print(f"[Dashboard] Error updating card style for {metric_key}: {e}")
            
            # Get history data for tooltip chart
            try:
                history_data = metric_config['get_history']()
                if history_data is None:
                    history_data = {}
            except Exception as e:
                history_data = {}
            
            # Create tooltip chart if history available
            if history_data and history_data.get('dates') and len(history_data.get('dates', [])) > 0:
                try:
                    dates = history_data['dates']
                    values = history_data[metric_config['history_key']]
                    if len(dates) > 0 and len(values) > 0:
                        # Calculate averages for chart
                        current_daily_avg = current_value / 7.0 if current_value > 0 else 0.0
                        weekly_avg = baseline_value / 7.0 if baseline_value > 0 else 0.0
                        three_month_avg = baseline_value / 7.0 if baseline_value > 0 else 0.0
                        
                        fig = create_metric_tooltip_chart(
                            dates,
                            values,
                            current_daily_avg,
                            weekly_avg,
                            three_month_avg,
                            metric_config['chart_title'],
                            line_color
                        )
                        
                        if fig:
                            # Render chart to HTML and move to tooltip (same logic as _render_metrics_cards)
                            chart_html = fig.to_html(include_plotlyjs=False, div_id=f"chart-{metric_config['tooltip_id']}")
                            tooltip_id = metric_config['tooltip_id']
                            
                            # Use JavaScript to move chart into tooltip container
                            ui.run_javascript(f'''
                                (function() {{
                                    var chartDiv = document.getElementById("chart-{tooltip_id}");
                                    var tooltipDiv = document.getElementById("tooltip-{tooltip_id}");
                                    if (chartDiv && tooltipDiv) {{
                                        tooltipDiv.innerHTML = chartDiv.innerHTML;
                                        chartDiv.remove();
                                    }}
                                }})();
                            ''')
                except Exception as e:
                    print(f"[Dashboard] Error creating tooltip chart for {metric_key}: {e}")
            
            card_info['rendered'] = True
    
    # Initialize tooltips after all cards are updated
    ui.run_javascript('''
        setTimeout(function() {
            if (typeof initMetricTooltips === 'function') {
                initMetricTooltips();
            }
        }, 300);
    ''')


def render_monitored_metrics_section_loaded(container, relief_summary, selected_metrics, coloration_baseline, an, init_perf_logger, quality_metrics=None, composite_scores=None):
    """Render monitored metrics section with already-loaded data.
    
    MONITORED METRICS SYSTEM OVERVIEW:
    ===================================
    This system supports monitoring up to 4 metrics on the dashboard. Metrics can be:
    1. Pre-calculated values from dictionaries (quality_metrics, relief_summary, composite_scores)
    2. Calculated on-demand using special handling (see make_get_value function)
    
    Special handling pattern:
    - Some metrics require on-demand calculation (e.g., daily_productivity_score_idle_refresh)
    - These metrics are not in standard dictionaries and need custom calculation logic
    - Special handling is added in the make_get_value() function with if statements
    - This pattern can be extended for other metrics that need custom calculation
    
    To add a new metric with special handling:
    1. Add the metric to CALCULATED_METRICS in analytics_page.py
    2. Add special handling in make_get_value() function (see comments there)
    3. Add special history handling in make_get_history() if needed (see comments there)
    ===================================
    
    Args:
        quality_metrics: Optional dict of quality metrics from get_dashboard_metrics()
        composite_scores: Optional dict of composite scores from get_all_scores_for_composite()
    """
    from datetime import datetime, timedelta
    import json
    from ui.analytics_page import CALCULATED_METRICS, ATTRIBUTE_LABELS
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'dashboard.py:render_monitored_metrics_section_loaded', 'message': 'render_monitored_metrics_section_loaded entry', 'data': {'selected_metrics': selected_metrics, 'has_quality_metrics': quality_metrics is not None, 'has_composite_scores': composite_scores is not None, 'quality_keys': list(quality_metrics.keys()) if quality_metrics else [], 'composite_keys': list(composite_scores.keys()) if composite_scores else []}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    # Use provided metrics or empty dicts (will be populated in lazy load)
    if quality_metrics is None:
        quality_metrics = {}
    if composite_scores is None:
        composite_scores = {}
    
    # Build available_metrics dynamically to support any metric from the options
    available_metrics = {
        'productivity_time': {
            'label': 'Productivity Time',
            'get_value': lambda: relief_summary.get('productivity_time_minutes', 0) / 60.0,
            'format_value': lambda v: f"{v:.1f} hrs" if v >= 1 else f"{relief_summary.get('productivity_time_minutes', 0):.0f} min",
            'get_history': lambda: an.get_weekly_hours_history(),
            'history_key': 'hours',
            'tooltip_id': 'monitored-productivity-time',
            'chart_title': 'Daily Hours'
        },
        'productivity_score': {
            'label': 'Productivity Score',
            'get_value': lambda: relief_summary.get('weekly_productivity_score', 0.0),
            'format_value': lambda v: f"{v:.1f}",
            'get_history': lambda: an.get_weekly_productivity_score_history() if hasattr(an, 'get_weekly_productivity_score_history') else None,
            'history_key': 'scores',
            'tooltip_id': 'monitored-productivity-score',
            'chart_title': 'Daily Productivity Score'
        },
    }
    
    # Build generic metric configs for any metric not already in available_metrics
    for metric_key in selected_metrics:
        if metric_key not in available_metrics:
            # Get label from analytics_page
            label = ATTRIBUTE_LABELS.get(metric_key, metric_key.replace('_', ' ').title())
            
            # Create closure-safe function for getting value (capture all needed data)
            def make_get_value(key, qual_metrics=quality_metrics, comp_scores=composite_scores, relief=relief_summary, analytics_instance=an):
                def get_generic_value():
                    # ====================================================================
                    # SPECIAL HANDLING FOR CALCULATED METRICS
                    # ====================================================================
                    # Some metrics require on-demand calculation rather than lookup from
                    # standard dictionaries (quality_metrics, relief_summary, composite_scores).
                    # This pattern can be extended for other metrics that need special logic.
                    #
                    # Example: daily_productivity_score_idle_refresh needs to calculate
                    # a daily score that resets at midnight each day.
                    # It's not pre-calculated in any standard metric dictionary.
                    #
                    # To add special handling for a new metric:
                    # 1. Add an if statement checking for the metric key
                    # 2. Call the appropriate calculation method from analytics_instance
                    # 3. Return the calculated value as a float
                    # ====================================================================
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'G',
                                'location': 'dashboard.py:get_generic_value',
                                'message': 'getting generic metric value',
                                'data': {
                                    'metric_key': key,
                                    'quality_keys': list(qual_metrics.keys()) if qual_metrics else [],
                                    'composite_keys': list(comp_scores.keys()) if comp_scores else [],
                                    'relief_keys': list(relief.keys()) if relief else []
                                },
                                'timestamp': int(time.time() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    
                    # Special handling for daily_productivity_score_idle_refresh - calculate on demand
                    # This metric calculates a daily productivity score that accumulates
                    # throughout the day and resets at midnight each day.
                    # For the current day, it accumulates scores from midnight up to the current time.
                    if key == 'daily_productivity_score_idle_refresh':
                        try:
                            score_data = analytics_instance.calculate_daily_productivity_score_with_idle_refresh(
                                target_date=None,  # None = current day with rolling calculation
                                idle_refresh_hours=8.0  # Deprecated parameter, kept for compatibility
                            )
                            result = score_data.get('daily_score', 0.0)
                            # #region agent log
                            try:
                                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({
                                        'sessionId': 'debug-session',
                                        'runId': 'run1',
                                        'hypothesisId': 'G',
                                        'location': 'dashboard.py:get_generic_value',
                                        'message': 'calculated daily_productivity_score_idle_refresh',
                                        'data': {'metric_key': key, 'value': result, 'total_tasks': score_data.get('total_tasks', 0)},
                                        'timestamp': int(time.time() * 1000)
                                    }) + '\n')
                            except: pass
                            # #endregion
                            return float(result)
                        except Exception as e:
                            # #region agent log
                            try:
                                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({
                                        'sessionId': 'debug-session',
                                        'runId': 'run1',
                                        'hypothesisId': 'G',
                                        'location': 'dashboard.py:get_generic_value',
                                        'message': 'error calculating daily_productivity_score_idle_refresh',
                                        'data': {'metric_key': key, 'error': str(e)},
                                        'timestamp': int(time.time() * 1000)
                                    }) + '\n')
                            except: pass
                            # #endregion
                            return 0.0
                    
                    # Try quality metrics first (exact match)
                    if key in qual_metrics:
                        val = qual_metrics.get(key)
                        result = float(val) if val is not None else 0.0
                        # #region agent log
                        try:
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'G',
                                    'location': 'dashboard.py:get_generic_value',
                                    'message': 'found in quality_metrics',
                                    'data': {'metric_key': key, 'value': result},
                                    'timestamp': int(time.time() * 1000)
                                }) + '\n')
                        except: pass
                        # #endregion
                        return result
                    
                    # Try with 'avg_' prefix in quality_metrics
                    avg_key = f'avg_{key}'
                    if avg_key in qual_metrics:
                        val = qual_metrics.get(avg_key)
                        result = float(val) if val is not None else 0.0
                        # #region agent log
                        try:
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'G',
                                    'location': 'dashboard.py:get_generic_value',
                                    'message': 'found in quality_metrics with avg_ prefix',
                                    'data': {'metric_key': key, 'avg_key': avg_key, 'value': result},
                                    'timestamp': int(time.time() * 1000)
                                }) + '\n')
                        except: pass
                        # #endregion
                        return result
                    
                    # Try relief_summary
                    if key in relief:
                        val = relief.get(key)
                        result = float(val) if val is not None else 0.0
                        # #region agent log
                        try:
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'G',
                                    'location': 'dashboard.py:get_generic_value',
                                    'message': 'found in relief_summary',
                                    'data': {'metric_key': key, 'value': result},
                                    'timestamp': int(time.time() * 1000)
                                }) + '\n')
                        except: pass
                        # #endregion
                        return result
                    
                    # Try composite_scores (for metrics like grit_score)
                    if key in comp_scores:
                        val = comp_scores.get(key)
                        result = float(val) if val is not None else 0.0
                        # #region agent log
                        try:
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'G',
                                    'location': 'dashboard.py:get_generic_value',
                                    'message': 'found in composite_scores',
                                    'data': {'metric_key': key, 'value': result},
                                    'timestamp': int(time.time() * 1000)
                                }) + '\n')
                        except: pass
                        # #endregion
                        return result
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'G',
                                'location': 'dashboard.py:get_generic_value',
                                'message': 'metric not found, returning 0',
                                'data': {'metric_key': key},
                                'timestamp': int(time.time() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    return 0.0
                return get_generic_value
            
            # Create closure-safe history function
            def make_get_history(key):
                def get_history():
                    # ====================================================================
                    # SPECIAL HANDLING FOR METRIC HISTORY
                    # ====================================================================
                    # Some metrics need custom history retrieval logic instead of the
                    # standard get_generic_metric_history() method. This pattern can be
                    # extended for other metrics that need special history calculation.
                    #
                    # Example: daily_productivity_score_idle_refresh uses get_attribute_trends
                    # to get historical daily values with the idle refresh logic applied.
                    #
                    # To add special handling for a new metric's history:
                    # 1. Add an if statement checking for the metric key
                    # 2. Call the appropriate history method (e.g., get_attribute_trends)
                    # 3. Return the history data in the expected format
                    # ====================================================================
                    
                    # Special handling for daily_productivity_score_idle_refresh - use get_attribute_trends
                    # This ensures the historical data uses the same calculation logic (midnight refresh)
                    # as the current value, providing consistent trend visualization.
                    if key == 'daily_productivity_score_idle_refresh':
                        try:
                            trends = an.get_attribute_trends(key, aggregation='sum', days=90)
                            return trends
                        except Exception as e:
                            print(f"[Dashboard] Error getting history for {key}: {e}")
                            return None
                    
                    # Standard history retrieval for other metrics
                    if hasattr(an, 'get_generic_metric_history'):
                        return an.get_generic_metric_history(key, days=90)
                    return None
                return get_history
            
            available_metrics[metric_key] = {
                'label': label,
                'get_value': make_get_value(metric_key),
                'format_value': lambda v: f"{v:.1f}",
                'get_history': make_get_history(metric_key),
                'history_key': 'values',
                'tooltip_id': f'monitored-{metric_key}',
                'chart_title': f'Daily {label}'
            }
    
    # Create metrics grid (2x2 layout for 4 metrics)
    with container:
        # Header with edit button
        with ui.row().classes("w-full justify-between items-center mb-2"):
            ui.label("Monitored Metrics").classes("text-sm font-semibold")
            ui.button("Edit", on_click=lambda: open_metrics_config_dialog()).props("dense size=sm")
        
        # Metrics grid - 2 columns, 2 rows
        metrics_grid = ui.row().classes("w-full gap-1").style("display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.25rem;")
        
        # #region agent log
        try:
            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'D',
                    'location': 'dashboard.py:render_loaded',
                    'message': 'about to render metrics cards',
                    'data': {
                        'quality_keys_count': len(quality_metrics),
                        'composite_keys_count': len(composite_scores),
                        'selected_metrics': selected_metrics,
                        'available_metrics_keys': list(available_metrics.keys())
                    },
                    'timestamp': int(time.time() * 1000)
                }) + '\n')
        except: pass
        # #endregion
        
        # Render metrics using the extracted function
        _render_metrics_cards(metrics_grid, selected_metrics, available_metrics, relief_summary, coloration_baseline, an, init_perf_logger)
        
        # Initialize tooltips after metrics are rendered
        ui.run_javascript('''
            setTimeout(function() {
                if (typeof initMetricTooltips === 'function') {
                    initMetricTooltips();
                }
            }, 300);
        ''')

def render_metrics_after_load(container, relief_summary, selected_metrics, coloration_baseline):
    """Render metrics after data is loaded."""
    from datetime import datetime, timedelta
    import json
    init_perf_logger = get_init_perf_logger()
    
    # Available metrics configuration
    
    # Available metrics configuration
    available_metrics = {
        'productivity_time': {
            'label': 'Productivity Time',
            'get_value': lambda: relief_summary.get('productivity_time_minutes', 0) / 60.0,
            'format_value': lambda v: f"{v:.1f} hrs" if v >= 1 else f"{relief_summary.get('productivity_time_minutes', 0):.0f} min",
            'get_history': lambda: an.get_weekly_hours_history(),
            'history_key': 'hours',
            'tooltip_id': 'monitored-productivity-time',
            'chart_title': 'Daily Hours'
        },
        'productivity_score': {
            'label': 'Productivity Score',
            'get_value': lambda: relief_summary.get('weekly_productivity_score', 0.0),
            'format_value': lambda v: f"{v:.1f}",
            'get_history': lambda: an.get_weekly_productivity_score_history() if hasattr(an, 'get_weekly_productivity_score_history') else None,
            'history_key': 'scores',
            'tooltip_id': 'monitored-productivity-score',
            'chart_title': 'Daily Productivity Score'
        },
    }
    
    # Create metrics grid (2x2 layout for 4 metrics)
    with container:
        # Header with edit button
        with ui.row().classes("w-full justify-between items-center mb-2"):
            ui.label("Monitored Metrics").classes("text-sm font-semibold")
            ui.button("Edit", on_click=lambda: open_metrics_config_dialog()).props("dense size=sm")
        
        # Loading indicator
        loading_indicator = ui.label("Loading metrics...").classes("text-xs text-gray-400").style("display: none;")
        
        # Metrics grid - 2 columns, 2 rows
        metrics_grid = ui.row().classes("w-full gap-1").style("display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.25rem;")
        
        # Show loading indicator initially
        loading_indicator.style("display: block;")
        
        # Load data in background
        def load_metrics_data():
            """Load metrics data in background and update UI."""
            get_relief_start = time.perf_counter()
            try:
                with init_perf_logger.operation("get_relief_summary"):
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'calling get_relief_summary (lazy)', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    loaded_summary = an.get_relief_summary()
                    # #region agent log
                    try:
                        get_relief_duration = (time.perf_counter() - get_relief_start) * 1000
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'get_relief_summary completed (lazy)', 'data': {'duration_ms': get_relief_duration, 'has_data': bool(loaded_summary)}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    # Load additional metrics data (expensive operations)
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'calling get_dashboard_metrics (lazy)', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    get_metrics_start = time.perf_counter()
                    try:
                        metrics_data = an.get_dashboard_metrics() if hasattr(an, 'get_dashboard_metrics') else {}
                        quality_metrics = metrics_data.get('quality', {})
                    except:
                        quality_metrics = {}
                    get_metrics_duration = (time.perf_counter() - get_metrics_start) * 1000
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'get_dashboard_metrics completed (lazy)', 'data': {'duration_ms': get_metrics_duration, 'quality_keys': list(quality_metrics.keys())}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'calling get_all_scores_for_composite (lazy)', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    get_composite_start = time.perf_counter()
                    try:
                        if hasattr(an, 'get_all_scores_for_composite'):
                            composite_scores = an.get_all_scores_for_composite(days=7) or {}
                        else:
                            composite_scores = {}
                    except:
                        composite_scores = {}
                    get_composite_duration = (time.perf_counter() - get_composite_start) * 1000
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'get_all_scores_for_composite completed (lazy)', 'data': {'duration_ms': get_composite_duration, 'composite_keys': list(composite_scores.keys())}, 'timestamp': int(time.time() * 1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    # Update relief_summary
                    nonlocal relief_summary
                    relief_summary = loaded_summary
                    
                    # Rebuild available_metrics with loaded data
                    from ui.analytics_page import ATTRIBUTE_LABELS
                    available_metrics = {
                        'productivity_time': {
                            'label': 'Productivity Time',
                            'get_value': lambda: loaded_summary.get('productivity_time_minutes', 0) / 60.0,
                            'format_value': lambda v: f"{v:.1f} hrs" if v >= 1 else f"{loaded_summary.get('productivity_time_minutes', 0):.0f} min",
                            'get_history': lambda: an.get_weekly_hours_history(),
                            'history_key': 'hours',
                            'tooltip_id': 'monitored-productivity-time',
                            'chart_title': 'Daily Hours'
                        },
                        'productivity_score': {
                            'label': 'Productivity Score',
                            'get_value': lambda: loaded_summary.get('weekly_productivity_score', 0.0),
                            'format_value': lambda v: f"{v:.1f}",
                            'get_history': lambda: an.get_weekly_productivity_score_history() if hasattr(an, 'get_weekly_productivity_score_history') else None,
                            'history_key': 'scores',
                            'tooltip_id': 'monitored-productivity-score',
                            'chart_title': 'Daily Productivity Score'
                        },
                    }
                    
                    # Add generic metrics with loaded data
                    for metric_key in selected_metrics:
                        if metric_key not in available_metrics:
                            label = ATTRIBUTE_LABELS.get(metric_key, metric_key.replace('_', ' ').title())
                            
                            def make_get_value(key, qual_metrics=quality_metrics, comp_scores=composite_scores, relief=loaded_summary):
                                def get_generic_value():
                                    # Try quality metrics first (exact match)
                                    if key in qual_metrics:
                                        val = qual_metrics.get(key)
                                        return float(val) if val is not None else 0.0
                                    
                                    # Try with 'avg_' prefix
                                    avg_key = f'avg_{key}'
                                    if avg_key in qual_metrics:
                                        val = qual_metrics.get(avg_key)
                                        return float(val) if val is not None else 0.0
                                    
                                    # Try relief_summary
                                    if key in relief:
                                        val = relief.get(key)
                                        return float(val) if val is not None else 0.0
                                    
                                    # Try composite_scores
                                    if key in comp_scores:
                                        val = comp_scores.get(key)
                                        return float(val) if val is not None else 0.0
                                    
                                    return 0.0
                                return get_generic_value
                            
                            available_metrics[metric_key] = {
                                'label': label,
                                'get_value': make_get_value(metric_key),
                                'format_value': lambda v: f"{v:.1f}",
                                'get_history': lambda: None,
                                'history_key': 'values',
                                'tooltip_id': f'monitored-{metric_key}',
                                'chart_title': f'Daily {label}'
                            }
                    
                    # #region agent log
                    try:
                        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'H1',
                                'location': 'dashboard.py:lazy_load',
                                'message': 'about to render metrics with loaded data',
                                'data': {
                                    'quality_keys': list(quality_metrics.keys()),
                                    'composite_keys': list(composite_scores.keys()),
                                    'selected_metrics': selected_metrics,
                                    'available_metrics_keys': list(available_metrics.keys())
                                },
                                'timestamp': int(time.time() * 1000)
                            }) + '\n')
                    except: pass
                    # #endregion
                    
                    # Hide loading indicator
                    loading_indicator.style("display: none;")
                    
                    # Clear and re-render metrics with loaded data
                    metrics_grid.clear()
                    _render_metrics_cards(metrics_grid, selected_metrics, available_metrics, loaded_summary, coloration_baseline, an, init_perf_logger)
                    
                    # Re-initialize tooltips after metrics are rendered
                    ui.run_javascript('''
                        setTimeout(function() {
                            if (typeof initMetricTooltips === 'function') {
                                initMetricTooltips();
                            }
                        }, 200);
                    ''')
            except Exception as e:
                # #region agent log
                try:
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H1', 'location': 'dashboard.py:lazy_load', 'message': 'get_relief_summary error (lazy)', 'data': {'error': str(e)}, 'timestamp': int(time.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                print(f"[Dashboard] Error getting relief summary: {e}")
                loading_indicator.text = "Error loading metrics"
                loading_indicator.classes("text-xs text-red-400")
        
        # Data is already loaded before this function is called, so render immediately


def _render_metrics_cards(metrics_grid, selected_metrics, available_metrics, relief_summary, coloration_baseline, an, init_perf_logger):
    """Render metric cards into the grid. Called initially and after lazy load."""
    import json
    import time
    
    # Render selected metrics
    # IMPORTANT: Only process selected_metrics - do NOT iterate over available_metrics
    # This ensures history functions are only called for selected metrics, not all metrics
    for i, metric_key in enumerate(selected_metrics):
            if metric_key not in available_metrics:
                continue
            
            metric_config = available_metrics[metric_key]
            
            # Get current value
            try:
                current_value = metric_config['get_value']()
            except Exception as e:
                print(f"[Dashboard] Error getting value for {metric_key}: {e}")
                current_value = 0.0
            
            # Get history for baseline calculation - ONLY called for selected metrics
            get_history_start = time.perf_counter()
            try:
                # #region agent log
                try:
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'dashboard.py:1869', 'message': 'calling get_history', 'data': {'metric_key': metric_key}, 'timestamp': int(time.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                with init_perf_logger.operation("get_metric_history", metric_key=metric_key):
                    history_data = metric_config['get_history']()
                get_history_duration = (time.perf_counter() - get_history_start) * 1000
                # #region agent log
                try:
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'dashboard.py:1870', 'message': 'get_history completed', 'data': {'metric_key': metric_key, 'duration_ms': get_history_duration, 'has_data': bool(history_data), 'is_none': history_data is None}, 'timestamp': int(time.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                if history_data is None:
                    history_data = {}
            except Exception as e:
                # #region agent log
                try:
                    with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H2', 'location': 'dashboard.py:1874', 'message': 'get_history error', 'data': {'metric_key': metric_key, 'error': str(e)}, 'timestamp': int(time.time() * 1000)}) + '\n')
                except: pass
                # #endregion
                print(f"[Dashboard] Error getting history for {metric_key}: {e}")
                history_data = {}
            
            # Calculate baseline (generic for any metric)
            # For metrics without history, use current_value as baseline (no comparison)
            if history_data and len(history_data.get('dates', [])) > 0:
                value_key = metric_config.get('history_key') or _get_value_key_from_history(history_data)
                baseline_daily = get_baseline_value(history_data, coloration_baseline, value_key)
                # All metrics store weekly totals in current_value, so convert baseline daily average to weekly
                baseline_value = baseline_daily * 7.0
            else:
                # No history available - use current value as baseline (neutral comparison)
                baseline_value = current_value
            
            # Get color class (compare weekly totals)
            bg_class, line_color = get_metric_bg_class(current_value, baseline_value)
            
            # Map bg_class to background color for inline style
            bg_color_map = {
                'metric-bg-green': '#d1fae5',
                'metric-bg-yellow': '#fef3c7',
                'metric-bg-red': '#fee2e2',
                '': '#f3f4f6'  # Default gray for no data
            }
            bg_color = bg_color_map.get(bg_class, '#f3f4f6')
            
            # Create small metric card
            with metrics_grid:
                metric_card = ui.card().classes(f"p-2 metric-card-hover {bg_class}").style(f"min-width: 0; background-color: {bg_color} !important;").props(f'data-tooltip-id="{metric_config["tooltip_id"]}"')
                with metric_card:
                    ui.label(metric_config['label']).classes("text-xs text-gray-500 mb-0.5")
                    formatted_value = metric_config['format_value'](current_value)
                    ui.label(formatted_value).classes("text-lg font-bold")
                    
                    # Show baseline info
                    baseline_label = {
                        'last_3_months': '3mo avg',
                        'last_month': '1mo avg',
                        'last_week': '1wk avg',
                        'average': 'avg',
                        'all_data': 'all avg'
                    }.get(coloration_baseline, 'avg')
                    
                    # Format baseline display (generic for any metric)
                    if 'time' in metric_key.lower() or 'hours' in metric_config.get('label', '').lower():
                        # Time-based metrics: show as hours/week
                        if baseline_value > 0:
                            ui.label(f"{baseline_label}: {baseline_value:.1f}h/wk").classes("text-xs text-gray-400")
                        else:
                            ui.label(f"{baseline_label}: N/A").classes("text-xs text-gray-400")
                    else:
                        # Score-based metrics: show as number
                        if baseline_value > 0:
                            ui.label(f"{baseline_label}: {baseline_value:.1f}").classes("text-xs text-gray-400")
                        else:
                            ui.label(f"{baseline_label}: N/A").classes("text-xs text-gray-400")
                
                # Create tooltip container
                tooltip_id = metric_config['tooltip_id']
                # Fix: JavaScript looks for 'tooltip-{tooltip_id}', not just '{tooltip_id}'
                # Add a default message for metrics without history
                has_history = history_data and history_data.get('dates') and history_data.get(metric_config['history_key'])
                default_msg = '' if has_history else '<div style="padding: 10px; text-align: center; color: #666;">No history data available</div>'
                ui.add_body_html(f'<div id="tooltip-{tooltip_id}" class="metric-tooltip" style="min-width: 400px; max-width: 500px;">{default_msg}</div>')
                
                # Render chart if history available
                if has_history:
                    dates = history_data['dates']
                    values = history_data[metric_config['history_key']]
                    
                    if len(dates) > 0 and len(values) > 0:
                        # Calculate current daily average (generic: all metrics store weekly totals)
                        current_daily_avg = current_value / 7.0 if current_value > 0 else 0.0
                        
                        # #region agent log
                        try:
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H8', 'location': 'dashboard.py:1930', 'message': 'creating chart', 'data': {'metric_key': metric_key, 'tooltip_id': tooltip_id, 'dates_count': len(dates), 'values_count': len(values)}, 'timestamp': int(time.time() * 1000)}) + '\n')
                        except: pass
                        # #endregion
                        chart_fig = create_metric_tooltip_chart(
                            dates,
                            values,
                            current_daily_avg,
                            history_data.get('weekly_average', 0.0),
                            history_data.get('three_month_average', 0.0),
                            metric_config['chart_title'],
                            line_color
                        )
                        
                        # #region agent log
                        try:
                            with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H8', 'location': 'dashboard.py:1938', 'message': 'chart created', 'data': {'metric_key': metric_key, 'tooltip_id': tooltip_id, 'chart_fig_is_none': chart_fig is None, 'has_chart': bool(chart_fig)}, 'timestamp': int(time.time() * 1000)}) + '\n')
                        except: pass
                        # #endregion
                        
                        if chart_fig:
                            with ui.element('div').props(f'id="{tooltip_id}-temp"').style("position: absolute; left: -9999px; top: -9999px; visibility: hidden;"):
                                ui.plotly(chart_fig)
                            
                            # #region agent log
                            try:
                                with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
                                    f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H7', 'location': 'dashboard.py:1944', 'message': 'running javascript to move chart', 'data': {'tooltip_id': tooltip_id}, 'timestamp': int(time.time() * 1000)}) + '\n')
                            except: pass
                            # #endregion
                            
                            # Fix: Use 'tooltip-{tooltip_id}' to match what JavaScript expects
                            ui.run_javascript(f'''
                                function moveChart_{tooltip_id}() {{
                                    const temp = document.getElementById('{tooltip_id}-temp');
                                    const tooltip = document.getElementById('tooltip-{tooltip_id}');
                                    if (temp && tooltip) {{
                                        const plotlyDiv = temp.querySelector('.plotly');
                                        if (plotlyDiv && plotlyDiv.offsetHeight > 0) {{
                                            tooltip.innerHTML = '';
                                            tooltip.appendChild(plotlyDiv);
                                            temp.remove();
                                            fetch('http://127.0.0.1:7242/ingest/b5ede3c8-fe20-4a9a-a62f-6abc4b864467',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{location:'dashboard.js:moveChart',message:'chart moved successfully',data:{{tooltip_id:'{tooltip_id}'}},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H7'}})}}).catch(()=>{{}});
                                            return true;
                                        }} else {{
                                            fetch('http://127.0.0.1:7242/ingest/b5ede3c8-fe20-4a9a-a62f-6abc4b864467',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{location:'dashboard.js:moveChart',message:'plotlyDiv not found or no height',data:{{tooltip_id:'{tooltip_id}',has_plotly:!!plotlyDiv,height:plotlyDiv?plotlyDiv.offsetHeight:0}},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H7'}})}}).catch(()=>{{}});
                                        }}
                                    }} else {{
                                        fetch('http://127.0.0.1:7242/ingest/b5ede3c8-fe20-4a9a-a62f-6abc4b864467',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{location:'dashboard.js:moveChart',message:'temp or tooltip not found',data:{{tooltip_id:'{tooltip_id}',has_temp:!!temp,has_tooltip:!!tooltip}},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H7'}})}}).catch(()=>{{}});
                                    }}
                                    return false;
                                }}
                                
                                setTimeout(function() {{
                                    if (!moveChart_{tooltip_id}()) {{
                                        setTimeout(function() {{
                                            if (!moveChart_{tooltip_id}()) {{
                                                setTimeout(moveChart_{tooltip_id}, 300);
                                            }}
                                        }}, 200);
                                    }}
                                }}, 300);
                            ''')


def update_monitored_metrics():
    """Update monitored metrics by clearing caches and refreshing data."""
    try:
        from backend.analytics import Analytics
        
        # Clear instance manager caches (class-level, shared across all instances)
        im._invalidate_instance_caches()
        
        # Clear analytics class-level caches (shared across all instances)
        Analytics._relief_summary_cache = None
        Analytics._relief_summary_cache_time = None
        Analytics._composite_scores_cache = None
        Analytics._composite_scores_cache_time = None
        
        # Clear analytics instance caches
        an._invalidate_instances_cache()
        
        # Reload instance manager data
        im._reload()
        
        ui.notify("Monitored metrics updated!", color="positive")
        # Reload the page to show fresh metrics
        ui.navigate.reload()
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        ui.notify(f"Error updating metrics: {error_msg}", color="negative", timeout=5000)
        print(f"[Dashboard] Update metrics error: {traceback.format_exc()}")


def open_metrics_config_dialog():
    """Open dialog to configure monitored metrics."""
    import json
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H6', 'location': 'dashboard.py:1972', 'message': 'open_metrics_config_dialog entry', 'data': {'timestamp': time.time()}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    config = user_state.get_monitored_metrics_config(DEFAULT_USER_ID)
    selected_metrics = config.get('selected_metrics', ['productivity_time', 'productivity_score'])
    coloration_baseline = config.get('coloration_baseline', 'last_3_months')
    
    # Import metrics from analytics_page to get full list
    from ui.analytics_page import CALCULATED_METRICS, NUMERIC_ATTRIBUTE_OPTIONS
    
    # Build available metrics from CALCULATED_METRICS and NUMERIC_ATTRIBUTE_OPTIONS
    available_metric_options = [
        {'key': 'productivity_time', 'label': 'Productivity Time'},
        {'key': 'productivity_score', 'label': 'Productivity Score'},
    ]
    
    # Add other calculated metrics that can be monitored
    for metric in CALCULATED_METRICS:
        if metric['value'] not in ['productivity_time', 'productivity_score']:  # Already added
            # Skip metrics that don't make sense as weekly aggregates (daily counts, etc.)
            if metric['value'] not in ['daily_self_care_tasks']:
                available_metric_options.append({
                    'key': metric['value'],
                    'label': metric['label']
                })
    
    # Add numeric task attributes
    for attr in NUMERIC_ATTRIBUTE_OPTIONS:
        if attr['value'] not in [opt['key'] for opt in available_metric_options]:
            available_metric_options.append({
                'key': attr['value'],
                'label': attr['label']
            })
    
    # #region agent log
    try:
        with open(r'c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'sessionId': 'debug-session', 'runId': 'run1', 'hypothesisId': 'H6', 'location': 'dashboard.py:1981', 'message': 'available_metric_options count', 'data': {'count': len(available_metric_options), 'options': available_metric_options}, 'timestamp': int(time.time() * 1000)}) + '\n')
    except: pass
    # #endregion
    
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg p-4'):
        ui.label("Configure Monitored Metrics").classes("text-xl font-bold mb-4")
        
        # Metric selection
        ui.label("Select Metrics (up to 4):").classes("text-sm font-semibold mb-2")
        metric_checkboxes = {}
        for option in available_metric_options:
            is_selected = option['key'] in selected_metrics
            metric_checkboxes[option['key']] = ui.checkbox(option['label'], value=is_selected)
        
        # Baseline selection
        ui.label("Coloration Baseline:").classes("text-sm font-semibold mt-4 mb-2")
        # NiceGUI select expects a dict mapping values to labels
        baseline_options = {
            'last_3_months': 'Last 3 Months',
            'last_month': 'Last Month',
            'last_week': 'Last Week',
            'average': 'Average',
            'all_data': 'All Data',
        }
        baseline_select = ui.select(
            baseline_options,
            value=coloration_baseline,
            label="Baseline"
        ).classes("w-full")
        
        with ui.row().classes("gap-2 mt-4 justify-end"):
            ui.button("Cancel", on_click=dialog.close)
            
            def save_config():
                # Get selected metrics
                new_selected = [key for key, checkbox in metric_checkboxes.items() if checkbox.value]
                # Limit to 4
                new_selected = new_selected[:4]
                
                # Save configuration
                new_config = {
                    'selected_metrics': new_selected,
                    'coloration_baseline': baseline_select.value
                }
                user_state.set_monitored_metrics_config(new_config, DEFAULT_USER_ID)
                ui.notify("Configuration saved", color='positive')
                dialog.close()
                ui.navigate.reload()
            
            ui.button("Save", on_click=save_config, color='primary')
    
    dialog.open()


# ----------------------------------------------------------
# MAIN DASHBOARD
# ----------------------------------------------------------

def build_dashboard(task_manager):
    dashboard_start_time = time.perf_counter()
    init_perf_logger = get_init_perf_logger()
    init_perf_logger.log_event("dashboard_build_start")
    bootup_logger = get_bootup_logger()
    
    # Add browser-side logging JavaScript
    ui.add_head_html("""
    <script>
    (function() {
        // Browser-side logging for page load and refresh tracking
        let pageLoadStartTime = performance.now();
        let reloadCount = 0;
        let timerCount = 0;
        let connectionFailureCount = 0;
        let requestAttemptCount = 0;
        const pageLoadId = 'load_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        
        // Track fetch/XHR requests to detect connection failures
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            requestAttemptCount++;
            const requestUrl = args[0] instanceof Request ? args[0].url : args[0];
            const requestStart = performance.now();
            
            return originalFetch.apply(this, args)
                .then(response => {
                    const duration = performance.now() - requestStart;
                    if (!response.ok) {
                        connectionFailureCount++;
                        logBrowserEvent('fetch_failure', {
                            url: requestUrl,
                            status: response.status,
                            status_text: response.statusText,
                            duration_ms: duration,
                            request_number: requestAttemptCount
                        });
                    }
                    return response;
                })
                .catch(error => {
                    connectionFailureCount++;
                    const duration = performance.now() - requestStart;
                    logBrowserEvent('connection_error', {
                        url: requestUrl,
                        error_type: error.name,
                        error_message: error.message,
                        duration_ms: duration,
                        request_number: requestAttemptCount,
                        connection_failures: connectionFailureCount
                    });
                    throw error;
                });
        };
        
        // Track XMLHttpRequest to catch old-style requests
        const originalXHROpen = XMLHttpRequest.prototype.open;
        const originalXHRSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.open = function(method, url, ...rest) {
            this._requestUrl = url;
            this._requestMethod = method;
            this._requestStart = performance.now();
            return originalXHROpen.apply(this, [method, url, ...rest]);
        };
        XMLHttpRequest.prototype.send = function(...args) {
            requestAttemptCount++;
            const xhr = this;
            const url = xhr._requestUrl;
            const method = xhr._requestMethod || 'GET';
            
            xhr.addEventListener('error', function() {
                connectionFailureCount++;
                const duration = performance.now() - (xhr._requestStart || performance.now());
                logBrowserEvent('xhr_connection_error', {
                    url: url,
                    method: method,
                    duration_ms: duration,
                    request_number: requestAttemptCount,
                    connection_failures: connectionFailureCount
                });
            });
            
            xhr.addEventListener('load', function() {
                if (xhr.status >= 400) {
                    connectionFailureCount++;
                    const duration = performance.now() - (xhr._requestStart || performance.now());
                    logBrowserEvent('xhr_failure', {
                        url: url,
                        method: method,
                        status: xhr.status,
                        status_text: xhr.statusText,
                        duration_ms: duration,
                        request_number: requestAttemptCount
                    });
                }
            });
            
            return originalXHRSend.apply(this, args);
        };
        
        // Track online/offline events
        window.addEventListener('online', function() {
            logBrowserEvent('network_online', {
                connection_failures: connectionFailureCount,
                request_attempts: requestAttemptCount
            });
        });
        
        window.addEventListener('offline', function() {
            logBrowserEvent('network_offline', {
                connection_failures: connectionFailureCount,
                request_attempts: requestAttemptCount
            });
        });
        
        // Log browser event to server
        function logBrowserEvent(eventType, eventData) {
            try {
                fetch('/api/log-browser-event', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        event_type: eventType,
                        data: {
                            ...eventData,
                            page_load_id: pageLoadId,
                            url: window.location.href,
                            timestamp: new Date().toISOString(),
                            performance_now: performance.now()
                        }
                    })
                }).catch(err => {
                    // Silently fail to avoid recursive logging issues
                    console.error('[BootupLogger] Failed to log browser event:', err);
                });
            } catch (e) {
                // Silently fail to avoid recursive logging issues
                console.error('[BootupLogger] Error logging browser event:', e);
            }
        }
        
        // Log page load start
        logBrowserEvent('page_load_start', {
            path: window.location.pathname,
            referrer: document.referrer,
            navigation_type: performance.navigation ? performance.navigation.type : 'unknown'
        });
        
        // Log when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                const domReadyTime = performance.now() - pageLoadStartTime;
                logBrowserEvent('dom_ready', {
                    dom_ready_time_ms: domReadyTime
                });
            });
        } else {
            const domReadyTime = performance.now() - pageLoadStartTime;
            logBrowserEvent('dom_ready', {
                dom_ready_time_ms: domReadyTime
            });
        }
        
        // Log when page is fully loaded
        window.addEventListener('load', function() {
            const loadTime = performance.now() - pageLoadStartTime;
            logBrowserEvent('page_load_complete', {
                load_time_ms: loadTime
            });
        });
        
        // Track page visibility changes (can indicate reloads)
        document.addEventListener('visibilitychange', function() {
            logBrowserEvent('visibility_change', {
                hidden: document.hidden,
                visibility_state: document.visibilityState
            });
        });
        
        // Override window.location.reload to track reloads
        const originalReload = window.location.reload;
        window.location.reload = function() {
            reloadCount++;
            logBrowserEvent('page_reload_triggered', {
                reload_count: reloadCount,
                stack: new Error().stack
            });
            return originalReload.apply(this, arguments);
        };
        
        // Track beforeunload (often indicates navigation/reload)
        window.addEventListener('beforeunload', function() {
            logBrowserEvent('beforeunload', {
                reload_count: reloadCount
            });
        });
        
        // Track hashchange (some navigation)
        window.addEventListener('hashchange', function() {
            logBrowserEvent('hashchange', {
                new_url: window.location.href,
                old_url: document.referrer
            });
        });
        
        // Track popstate (back/forward navigation)
        window.addEventListener('popstate', function() {
            logBrowserEvent('popstate', {
                state: history.state,
                url: window.location.href
            });
        });
        
        // Store original setTimeout to track timer creation
        const originalSetTimeout = window.setTimeout;
        window.setTimeout = function(func, delay) {
            timerCount++;
            if (typeof delay === 'number' && delay < 1000) {
                logBrowserEvent('timer_created', {
                    timer_id: timerCount,
                    delay_ms: delay,
                    is_short_delay: delay < 1000
                });
            }
            return originalSetTimeout.apply(this, arguments);
        };
        
        // Expose logging function globally for manual logging
        window.bootupLogger = {
            log: logBrowserEvent,
            pageLoadId: pageLoadId,
            reloadCount: reloadCount,
            timerCount: timerCount
        };
    })();
    </script>
    """)

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
        
        .recommendation-card-hover {
            cursor: pointer;
        }
        
        /* Recommendation tooltip styling */
        .recommendation-tooltip {
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
        
        .recommendation-tooltip div {
            margin: 4px 0;
        }
        
        .recommendation-tooltip strong {
            color: #e5e7eb;
        }
        
        .recommendation-tooltip.visible {
            opacity: 1;
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
        
        /* Context menu styling */
        .context-menu {
            position: fixed;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 0.375rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            min-width: 150px;
            padding: 0.25rem 0;
            display: none;
        }
        
        .context-menu-item {
            padding: 0.5rem 1rem;
            cursor: pointer;
            font-size: 0.875rem;
            color: #1f2937;
            transition: background-color 0.15s;
        }
        
        .context-menu-item:hover {
            background-color: #f3f4f6;
        }
        
        .context-menu-item.edit {
            color: #3b82f6;
        }
        
        .context-menu-item.copy {
            color: #22c55e;
        }
        
        .context-menu-item.delete {
            color: #ef4444;
        }
        
        .context-menu-item:first-child {
            border-top-left-radius: 0.375rem;
            border-top-right-radius: 0.375rem;
        }
        
        .context-menu-item:last-child {
            border-bottom-left-radius: 0.375rem;
            border-bottom-right-radius: 0.375rem;
        }
        
        /* Context menu cards - subtle hover effect to indicate interactivity */
        .context-menu-card {
            cursor: context-menu;
        }
        
        .context-menu-card:hover {
            background-color: #f9fafb;
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
            const cards = document.querySelectorAll('.metric-card-hover');
            console.log('[DEBUG] initMetricTooltips: found', cards.length, 'metric cards');
            fetch('http://127.0.0.1:7242/ingest/b5ede3c8-fe20-4a9a-a62f-6abc4b864467',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'dashboard.js:initMetricTooltips',message:'initMetricTooltips called',data:{card_count:cards.length},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H7'})}).catch(()=>{});
            
            cards.forEach(function(card) {
                const tooltipId = card.getAttribute('data-tooltip-id');
                if (!tooltipId) {
                    console.log('[DEBUG] initMetricTooltips: card missing data-tooltip-id');
                    return;
                }
                
                const tooltip = document.getElementById('tooltip-' + tooltipId);
                if (!tooltip) {
                    console.log('[DEBUG] initMetricTooltips: tooltip not found for', tooltipId, 'looking for tooltip-' + tooltipId);
                    fetch('http://127.0.0.1:7242/ingest/b5ede3c8-fe20-4a9a-a62f-6abc4b864467',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'dashboard.js:initMetricTooltips',message:'tooltip element not found',data:{tooltip_id:tooltipId,expected_id:'tooltip-' + tooltipId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'H7'})}).catch(()=>{});
                    return;
                }
                
                console.log('[DEBUG] initMetricTooltips: setting up tooltip for', tooltipId);
                
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
    <script>
        // Context menu functionality
        let contextMenu = null;
        
        function createContextMenu() {
            if (contextMenu) {
                contextMenu.remove();
            }
            contextMenu = document.createElement('div');
            contextMenu.className = 'context-menu';
            contextMenu.id = 'context-menu';
            document.body.appendChild(contextMenu);
            return contextMenu;
        }
        
        function showContextMenu(event, type, id, additionalData) {
            event.preventDefault();
            event.stopPropagation();
            
            const menu = createContextMenu();
            menu.innerHTML = '';
            
            let menuItems = [];
            
            if (type === 'template') {
                menuItems = [
                    { label: 'Edit', action: 'edit', class: 'edit' },
                    { label: 'Copy', action: 'copy', class: 'copy' },
                    { label: 'Delete', action: 'delete', class: 'delete' }
                ];
            } else if (type === 'instance') {
                // Initialized tasks: View, Add Note, Complete
                menuItems = [
                    { label: 'View', action: 'view', class: 'edit' },
                    { label: 'Add Note', action: 'addnote', class: 'edit' },
                    { label: 'Complete', action: 'complete', class: 'copy' }
                ];
            } else if (type === 'completed') {
                // Completed/cancelled tasks: Edit, Delete only
                menuItems = [
                    { label: 'Edit', action: 'edit', class: 'edit' },
                    { label: 'Delete', action: 'delete', class: 'delete' }
                ];
            } else if (type === 'active') {
                // Active tasks: Add Notes, View Notes
                menuItems = [
                    { label: 'Add Note', action: 'addnote', class: 'edit' },
                    { label: 'View Notes', action: 'viewnotes', class: 'edit' }
                ];
            } else if (type === 'metric') {
                // Metric cards: Reset Score (only for daily_productivity_score_idle_refresh)
                if (id === 'daily_productivity_score_idle_refresh') {
                    menuItems = [
                        { label: 'Reset Score', action: 'reset', class: 'delete' }
                    ];
                } else {
                    menuItems = [];
                }
            }
            
            menuItems.forEach(item => {
                const menuItem = document.createElement('div');
                menuItem.className = 'context-menu-item ' + item.class;
                menuItem.textContent = item.label;
                menuItem.addEventListener('click', function(e) {
                    e.stopPropagation();
                    handleContextMenuAction(item.action, type, id, additionalData);
                    hideContextMenu();
                });
                menu.appendChild(menuItem);
            });
            
            menu.style.display = 'block';
            menu.style.left = event.clientX + 'px';
            menu.style.top = event.clientY + 'px';
            
            // Adjust position if menu would go off screen
            setTimeout(() => {
                const rect = menu.getBoundingClientRect();
                if (rect.right > window.innerWidth) {
                    menu.style.left = (event.clientX - rect.width) + 'px';
                }
                if (rect.bottom > window.innerHeight) {
                    menu.style.top = (event.clientY - rect.height) + 'px';
                }
            }, 0);
        }
        
        function hideContextMenu() {
            if (contextMenu) {
                contextMenu.style.display = 'none';
            }
        }
        
        function handleContextMenuAction(action, type, id, additionalData) {
            // Find and click the hidden button for this action
            const buttonId = `context-btn-${type}-${action}-${id}`;
            const button = document.getElementById(buttonId);
            if (button) {
                if (action === 'delete' || action === 'cancel') {
                    const confirmMsg = type === 'template' 
                        ? 'Are you sure you want to delete this task template?'
                        : action === 'cancel'
                        ? 'Are you sure you want to cancel this task?'
                        : 'Are you sure you want to delete this instance?';
                    if (confirm(confirmMsg)) {
                        button.click();
                    }
                } else if (action === 'addnote' || action === 'viewnotes' || action === 'view' || action === 'complete' || action === 'reset') {
                    // No confirmation needed for view/note/complete/reset actions
                    button.click();
                } else {
                    button.click();
                }
            }
        }
        
        // Initialize context menus
        function initContextMenus() {
            // Use a marker to prevent duplicate listeners
            document.querySelectorAll('[data-context-menu]:not([data-context-menu-initialized])').forEach(element => {
                element.setAttribute('data-context-menu-initialized', 'true');
                
                element.addEventListener('contextmenu', function(e) {
                    const type = element.getAttribute('data-context-menu');
                    let id = null;
                    
                    if (type === 'template') {
                        id = element.getAttribute('data-template-id');
                    } else if (type === 'instance' || type === 'completed' || type === 'active') {
                        id = element.getAttribute('data-instance-id');
                    } else if (type === 'metric') {
                        id = element.getAttribute('data-metric-key');
                    }
                    
                    if (id) {
                        showContextMenu(e, type, id, null);
                    }
                });
            });
            
            // Also handle completed task items
            document.querySelectorAll('[data-completed-instance-id]:not([data-context-menu-initialized])').forEach(element => {
                element.setAttribute('data-context-menu-initialized', 'true');
                
                element.addEventListener('contextmenu', function(e) {
                    const id = element.getAttribute('data-completed-instance-id');
                    if (id) {
                        showContextMenu(e, 'completed', id, null);
                    }
                });
            });
        }
        
        // Hide context menu on click outside
        document.addEventListener('click', hideContextMenu);
        document.addEventListener('contextmenu', function(e) {
            if (!e.target.closest('[data-context-menu]') && !e.target.closest('[data-completed-instance-id]') && !e.target.closest('[data-metric-key]')) {
                hideContextMenu();
            }
        });
        
        // Initialize on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                setTimeout(initContextMenus, 200);
            });
        } else {
            setTimeout(initContextMenus, 200);
        }
        
        // Re-initialize after DOM updates
        setTimeout(initContextMenus, 500);
    </script>
    <script>
        function initRecommendationTooltips() {
            const cards = document.querySelectorAll('.recommendation-card-hover');
            
            cards.forEach(function(card, index) {
                const recId = card.getAttribute('data-rec-id');
                
                if (!recId) {
                    return;
                }
                
                const tooltip = document.getElementById('tooltip-' + recId);
                
                if (!tooltip) {
                    return;
                }
                
                // Skip if already initialized
                if (card.hasAttribute('data-tooltip-initialized')) {
                    return;
                }
                card.setAttribute('data-tooltip-initialized', 'true');
                
                let hoverTimeout;
                
                card.addEventListener('mouseenter', function() {
                    hoverTimeout = setTimeout(function() {
                        tooltip.classList.add('visible');
                        positionRecommendationTooltip(card, tooltip);
                    }, 500);
                });
                
                card.addEventListener('mouseleave', function() {
                    clearTimeout(hoverTimeout);
                    tooltip.classList.remove('visible');
                });
                
                card.addEventListener('mousemove', function(e) {
                    if (tooltip.classList.contains('visible')) {
                        positionRecommendationTooltip(card, tooltip, e);
                    }
                });
            });
        }
        
        function positionRecommendationTooltip(card, tooltip, event) {
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
            document.addEventListener('DOMContentLoaded', initRecommendationTooltips);
        } else {
            initRecommendationTooltips();
        }
        
        // Re-initialize after a short delay to catch dynamically added elements
        setTimeout(initRecommendationTooltips, 100);
        setTimeout(initRecommendationTooltips, 500);
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
                ui.button("Summary",
                          on_click=lambda: ui.navigate.to('/summary'),
                          icon="dashboard").classes("text-xl py-3 px-6").props('id="tas-summary-link" data-tooltip-id="summary_link"')
                ui.button("Notes",
                          on_click=lambda: ui.navigate.to('/notes'),
                          icon="note").classes("text-xl py-3 px-6").props('id="tas-notes-link" data-tooltip-id="notes_link"')
                ui.button("Analytics",
                          on_click=lambda: ui.navigate.to('/analytics'),
                          icon="bar_chart").classes("text-xl py-3 px-6").props('id="tas-analytics-link" data-tooltip-id="analytics_link"')
                ui.button("Goals",
                          on_click=lambda: ui.navigate.to('/goals'),
                          icon="target").classes("text-xl py-3 px-6").props('id="tas-goals-link" data-tooltip-id="goals_link"')
                ui.button("Experimental",
                          on_click=lambda: ui.navigate.to('/experimental'),
                          icon="science").classes("text-xl py-3 px-6").props('id="tas-experimental-link" data-tooltip-id="experimental_link"')
                ui.button("Glossary",
                          on_click=lambda: ui.navigate.to('/analytics/glossary'),
                          icon="menu_book").classes("text-xl py-3 px-6").props('data-tooltip-id="glossary_link"')
                ui.button("Known Issues",
                          on_click=lambda: ui.navigate.to('/known-issues'),
                          icon="bug_report").classes("text-xl py-3 px-6").props('data-tooltip-id="known_issues_link"')
                ui.button("Settings",
                          on_click=lambda: ui.navigate.to('/settings'),
                          icon="settings").classes("text-xl py-3 px-6").props('data-tooltip-id="settings_link"')
        
        # ====================================================================
        # DATA ISOLATION WARNING NOTE
        # ====================================================================
        with ui.card().classes("w-full mb-4 p-4 bg-yellow-50 border-2 border-yellow-400"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.icon("warning", size="lg").classes("text-yellow-600")
                with ui.column().classes("flex-1"):
                    ui.label("Dashboard Metrics Temporarily Disabled").classes("text-lg font-bold text-yellow-800")
                    ui.label("Dashboard metrics and analytics are currently disabled because data is duplicated in the database temporarily while working on data isolation in the auth branch. Metrics will be re-enabled once data isolation is complete.").classes("text-sm text-yellow-700")
        
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
                    # Left half: Monitored Metrics, Quick Tasks
                    left_half = ui.column().classes("half-width-left gap-2")
                    with left_half:
                        # Monitored Metrics Section - Now optimized with database-level filtering
                        with init_perf_logger.operation("render_monitored_metrics_section"):
                            render_monitored_metrics_section(left_half)
                        
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
                                        ui.button("Initialize", 
                                                  on_click=lambda n=r['name']: init_quick(n)
                                                  ).props("dense size=sm")
                    
                    # Right half: Recently Completed (scrollable, aligned to end after quick tasks)
                    right_half = ui.column().classes("half-width-right")
                    with right_half:
                        with ui.card().classes("w-full p-2").style("display: flex; flex-direction: column; align-self: flex-start; height: 100%;"):
                            ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
                            ui.separator()
                            # Scrollable content area - matches height of left half content
                            completed_scroll = ui.column().classes("w-full mt-2").style("overflow-y: auto; overflow-x: hidden; max-height: 400px;")
                            with completed_scroll:
                                # Get recent tasks (completed + cancelled) and display them
                                recent_tasks = im.list_recent_tasks(limit=20) if hasattr(im, "list_recent_tasks") else []
                                
                                if not recent_tasks:
                                    ui.label("No recent tasks").classes("text-xs text-gray-500")
                                else:
                                    for c in recent_tasks:
                                        # Get timestamp from either completed_at or cancelled_at
                                        completed_at = str(c.get('completed_at', ''))
                                        cancelled_at = str(c.get('cancelled_at', ''))
                                        status = c.get('status', 'completed')
                                        timestamp_str = completed_at if status == 'completed' else cancelled_at
                                        instance_id_completed = c.get('instance_id', '')
                                        
                                        with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                                            # Show task name with status indicator
                                            task_name = c.get('task_name', 'Unknown')
                                            status_label = " [Cancelled]" if status == 'cancelled' else ""
                                            ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                                            if timestamp_str:
                                                parts = timestamp_str.split()
                                                if len(parts) >= 2:
                                                    date_part = parts[0]
                                                    time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                                                    ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                                                else:
                                                    ui.label(timestamp_str).classes("text-xs text-gray-400")
                                            # Hidden buttons for context menu actions (Edit, Delete only)
                                            if instance_id_completed:
                                                ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                                                ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
                
                # Task Templates section - directly below the row
                with ui.column().classes("scrollable-section flex-1"):
                    ui.markdown("### Task Templates")
                    
                    # Search bar for templates
                    print("[Dashboard] Creating search bar for task templates")
                    search_input = ui.input(
                        label="Search templates",
                        placeholder="Search by name, description, or type..."
                    ).classes("w-full mb-2")
                    print(f"[Dashboard] Search input created: {search_input}")
                    # #region agent log
                    debug_log('dashboard.py:4494', 'Template search input created', {'input_id': str(id(search_input))}, 'H3')
                    # #endregion
                    
                    # Debounce timer for template search input
                    template_search_debounce_timer = None
                    
                    def handle_template_search(e):
                        """Handle search input changes with debouncing."""
                        nonlocal template_search_debounce_timer
                        # #region agent log
                        debug_log('dashboard.py:4500', 'Template search handler triggered', {'has_event': e is not None}, 'H2')
                        # #endregion
                        
                        # Cancel existing timer if any
                        if template_search_debounce_timer is not None:
                            template_search_debounce_timer.deactivate()
                        
                        # Create a debounced function that will execute after user stops typing
                        def apply_template_search():
                            """Apply the template search filter after debounce delay."""
                            try:
                                # Ensure container exists before proceeding
                                global template_col
                                if template_col is None:
                                    print("[Dashboard] template_col is None in search handler, retrying...")
                                    ui.timer(5.0, apply_template_search, once=True)
                                    return
                                
                                current_value = search_input.value
                                search_query = str(current_value).strip() if current_value else None
                                if search_query == '':
                                    search_query = None
                                print(f"[Dashboard] Calling refresh_templates with search_query='{search_query}'")
                                refresh_templates(search_query=search_query)
                            except Exception as ex:
                                print(f"[Dashboard] Error in debounced template search: {ex}")
                                import traceback
                                traceback.print_exc()
                        
                        # Create a timer that will execute after 300ms of no typing
                        template_search_debounce_timer = ui.timer(0.3, apply_template_search, once=True)
                    
                    global template_col
                    template_col = ui.row().classes('w-full gap-2')
                    # #region agent log
                    debug_log('dashboard.py:4533', 'Template container created', {'container_id': str(id(template_col)), 'is_none': template_col is None}, 'H1')
                    # #endregion
                    
                    # Attach search handler immediately to the current input
                    try:
                        # #region agent log
                        debug_log('dashboard.py:4538', 'Attempting to attach template search handler', {'input_id': str(id(search_input)), 'container_exists': template_col is not None}, 'H2')
                        # #endregion
                        search_input.on('update:model-value', handle_template_search)
                        print("[Dashboard] Search input event handler attached")
                        # #region agent log
                        debug_log('dashboard.py:4540', 'Template search handler attached successfully', {}, 'H2')
                        # #endregion
                    except Exception as e:
                        print(f"[Dashboard] Error attaching template search handler: {e}")
                        # #region agent log
                        debug_log('dashboard.py:4542', 'Error attaching template search handler', {'error': str(e)}, 'H2')
                        # #endregion
                    
                    # Call refresh - it will retry automatically if container not ready
                    # #region agent log
                    debug_log('dashboard.py:4546', 'About to call initial refresh_templates', {'container_exists': template_col is not None}, 'H5')
                    # #endregion
                    if init_perf_logger:
                        with init_perf_logger.operation("refresh_templates_initial"):
                            refresh_templates()
                    else:
                        refresh_templates()
                    # #region agent log
                    debug_log('dashboard.py:4551', 'Initial refresh_templates completed', {'container_exists': template_col is not None}, 'H5')
                    # #endregion

            # ====================================================================
            # COLUMN 2 — Middle Column
            # ====================================================================
            with ui.column().classes("dashboard-column column-middle gap-2"):
                # Top half: Active Tasks in 2 nested columns
                with ui.column().classes("scrollable-section").style("height: 50%; max-height: 50%;").props('id="tas-active-tasks" data-tooltip-id="active_tasks"'):
                    if init_perf_logger:
                        with init_perf_logger.operation("list_active_instances"):
                            active = im.list_active_instances()
                        with init_perf_logger.operation("get_current_task"):
                            current_task = get_current_task()
                    else:
                        active = im.list_active_instances()
                        current_task = get_current_task()
                    # Filter out current task from active list
                    active_not_current = [a for a in active if a.get('instance_id') != (current_task.get('instance_id') if current_task else None)]
                    
                    # Calculate total time estimate by task type
                    total_time_by_type = {'Work': 0, 'Play': 0, 'Self care': 0}
                    total_time = 0
                    
                    for inst in active_not_current:
                        # Parse predicted data to get time estimate
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
                        
                        # Get task type from task
                        task_id = inst.get('task_id')
                        if task_id:
                            task = task_manager.get_task(task_id)
                            if task:
                                task_type = task.get('task_type', 'Work')
                                # Normalize task type (handle variations like 'self care', 'selfcare', 'self-care')
                                task_type_normalized = str(task_type).strip()
                                task_type_lower = task_type_normalized.lower()
                                
                                if task_type_lower == 'play':
                                    total_time_by_type['Play'] += time_estimate
                                elif task_type_lower in ['self care', 'selfcare', 'self-care']:
                                    total_time_by_type['Self care'] += time_estimate
                                else:  # Default to Work
                                    total_time_by_type['Work'] += time_estimate
                                total_time += time_estimate
                    
                    # Header with title and time estimate
                    with ui.row().classes("w-full items-center justify-between mb-2"):
                        ui.label("Initialized Tasks").classes("text-lg font-bold")
                        
                        # Time estimate with tooltip
                        time_label = ui.label(f"{total_time} min").classes("text-sm font-semibold text-gray-700" if total_time > 0 else "text-sm text-gray-500")
                        
                        # Create tooltip content with breakdown by task type
                        tooltip_parts = ["Time breakdown:"]
                        tooltip_parts.append(f"Work: {total_time_by_type['Work']} min")
                        tooltip_parts.append(f"Play: {total_time_by_type['Play']} min")
                        tooltip_parts.append(f"Self care: {total_time_by_type['Self care']} min")
                        tooltip_content = "<br>".join(tooltip_parts)
                        
                        # Add tooltip using NiceGUI's tooltip feature
                        time_label.tooltip(tooltip_content)
                    
                    # Search bar for initialized tasks
                    initialized_search_input = ui.input(
                        label="Search initialized tasks",
                        placeholder="Search by name, description, or notes..."
                    ).classes("w-full mb-2")
                    # #region agent log
                    debug_log('dashboard.py:4629', 'Initialized tasks search input created', {'input_id': str(id(initialized_search_input))}, 'H3')
                    # #endregion
                    
                    # Debounce timer for initialized tasks search input
                    initialized_search_debounce_timer = None
                    
                    def handle_initialized_search(e):
                        """Handle search input changes with debouncing."""
                        nonlocal initialized_search_debounce_timer
                        # #region agent log
                        debug_log('dashboard.py:4635', 'Initialized tasks search handler triggered', {'has_event': e is not None}, 'H2')
                        # #endregion
                        
                        # Cancel existing timer if any
                        if initialized_search_debounce_timer is not None:
                            initialized_search_debounce_timer.deactivate()
                        
                        # Create a debounced function that will execute after user stops typing
                        def apply_initialized_search():
                            """Apply the initialized tasks search filter after debounce delay."""
                            try:
                                # Ensure container exists before proceeding
                                global initialized_tasks_container
                                if initialized_tasks_container is None:
                                    print("[Dashboard] initialized_tasks_container is None in search handler, retrying...")
                                    ui.timer(5.0, apply_initialized_search, once=True)
                                    return
                                
                                print(f"[Dashboard] Applying initialized tasks search filter")
                                refresh_initialized_tasks()
                            except Exception as ex:
                                print(f"[Dashboard] Error in debounced initialized tasks search: {ex}")
                                import traceback
                                traceback.print_exc()
                        
                        # Create a timer that will execute after 300ms of no typing
                        initialized_search_debounce_timer = ui.timer(0.3, apply_initialized_search, once=True)
                    
                    ui.separator()
                    
                    # Container for initialized tasks (will be populated by refresh_initialized_tasks)
                    global initialized_tasks_container
                    initialized_tasks_container = ui.column().classes('w-full')
                    # #region agent log
                    debug_log('dashboard.py:4665', 'Initialized tasks container created', {'container_id': str(id(initialized_tasks_container)), 'is_none': initialized_tasks_container is None}, 'H1')
                    # #endregion
                    
                    # Store search input reference for refresh function
                    global initialized_search_input_ref
                    initialized_search_input_ref = initialized_search_input
                    # #region agent log
                    debug_log('dashboard.py:4670', 'Initialized search input ref stored', {'ref_id': str(id(initialized_search_input_ref)), 'input_id': str(id(initialized_search_input))}, 'H3')
                    # #endregion
                    
                    # Attach search handler immediately to the current input
                    try:
                        # #region agent log
                        debug_log('dashboard.py:4675', 'Attempting to attach initialized tasks search handler', {'input_id': str(id(initialized_search_input)), 'container_exists': initialized_tasks_container is not None}, 'H2')
                        # #endregion
                        initialized_search_input.on('update:model-value', handle_initialized_search)
                        print("[Dashboard] Initialized tasks search input event handler attached")
                        # #region agent log
                        debug_log('dashboard.py:4678', 'Initialized tasks search handler attached successfully', {}, 'H2')
                        # #endregion
                    except Exception as e:
                        print(f"[Dashboard] Error attaching initialized tasks search handler: {e}")
                        # #region agent log
                        debug_log('dashboard.py:4681', 'Error attaching initialized tasks search handler', {'error': str(e)}, 'H2')
                        # #endregion
                    
                    # Call refresh - it will retry automatically if container not ready
                    # #region agent log
                    debug_log('dashboard.py:4686', 'About to call initial refresh_initialized_tasks', {'container_exists': initialized_tasks_container is not None}, 'H5')
                    # #endregion
                    refresh_initialized_tasks()
                    # #region agent log
                    debug_log('dashboard.py:4688', 'Initial refresh_initialized_tasks completed', {'container_exists': initialized_tasks_container is not None}, 'H5')
                    # #endregion
                
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
                        
                        # Parse actual data to get pause notes
                        actual_str = current_task.get("actual") or "{}"
                        try:
                            actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                        except (json.JSONDecodeError, TypeError):
                            actual_data = {}
                        
                        pause_reason = actual_data.get('pause_reason', '')
                        
                        time_estimate = predicted_data.get('time_estimate_minutes') or predicted_data.get('estimate') or 0
                        try:
                            time_estimate = int(time_estimate)
                        except (TypeError, ValueError):
                            time_estimate = 0
                        
                        task_id = current_task.get('task_id')
                        formatted_tooltip = format_colored_tooltip(predicted_data, task_id)
                        tooltip_id = f"tooltip-{current_task['instance_id']}"
                        instance_id = current_task['instance_id']
                        
                        # Get layout preference from environment variable (default: "full")
                        layout_mode = os.getenv('INIT_CARD_LAYOUT', 'full').lower()
                        
                        with ui.card().classes("w-full p-3 task-card-hover context-menu-card").props(f'data-instance-id="{instance_id}" data-context-menu="active"').style("position: relative;"):
                            # Hidden buttons for context menu actions (active task: Add Notes, View Notes)
                            ui.button("", on_click=lambda iid=instance_id: add_instance_note(iid)).props(f'id="context-btn-active-addnote-{instance_id}"').style("display: none;")
                            ui.button("", on_click=lambda iid=instance_id: view_instance_notes(iid)).props(f'id="context-btn-active-viewnotes-{instance_id}"').style("display: none;")
                            if layout_mode == 'columns':
                                # Multi-column layout option
                                with ui.row().classes("w-full gap-4"):
                                    # Left column: Main task info
                                    with ui.column().classes("flex-1 gap-2"):
                                        ui.label(current_task.get("task_name")).classes("text-xl font-bold mb-2")
                                        ui.label(f"Estimated: {time_estimate} min").classes("text-sm text-gray-600 mb-2")
                                        
                                        started_at = current_task.get('started_at', '')
                                        if started_at:
                                            timer_label = ui.label("").classes("text-lg font-semibold text-blue-600 mb-2")
                                            update_ongoing_timer(instance_id, timer_label)
                                        
                                        initialized_at = current_task.get('initialized_at', '')
                                        if initialized_at:
                                            ui.label(f"Initialized: {initialized_at}").classes("text-xs text-gray-500 mb-2")
                                        
                                        # Show initialization description if available
                                        init_description = predicted_data.get('description', '')
                                        if init_description and init_description.strip():
                                            ui.label(init_description.strip()).classes("text-sm text-gray-700 mb-2 italic").style("max-width: 100%; word-wrap: break-word;")
                                    
                                    # Right column: Pause notes
                                    with ui.column().classes("flex-1 gap-2"):
                                        if pause_reason and pause_reason.strip():
                                            ui.label("Pause Notes:").classes("text-sm font-semibold text-orange-600 mb-1")
                                            ui.label(pause_reason.strip()).classes("text-sm text-gray-700 mb-2 p-2 bg-orange-50 border border-orange-200 rounded").style("max-width: 100%; word-wrap: break-word;")
                                        else:
                                            # Empty space when no pause notes
                                            ui.label("").classes("text-sm")
                                
                                # Action buttons row
                                with ui.row().classes("gap-2 mt-2 w-full"):
                                    ui.button("Complete",
                                              on_click=lambda i=instance_id: go_complete(i)
                                              ).classes("bg-green-500")
                                    ui.button("Pause",
                                              color="primary",
                                              on_click=lambda i=instance_id: open_pause_dialog(i)
                                              )
                                    ui.button("Cancel",
                                              color="warning",
                                              on_click=lambda i=instance_id: go_cancel(i)
                                              )
                            else:
                                # Full-width layout option (default)
                                ui.label(current_task.get("task_name")).classes("text-xl font-bold mb-2")
                                ui.label(f"Estimated: {time_estimate} min").classes("text-sm text-gray-600 mb-2")
                                
                                started_at = current_task.get('started_at', '')
                                if started_at:
                                    timer_label = ui.label("").classes("text-lg font-semibold text-blue-600 mb-2")
                                    update_ongoing_timer(instance_id, timer_label)
                                
                                initialized_at = current_task.get('initialized_at', '')
                                if initialized_at:
                                    ui.label(f"Initialize: {initialized_at}").classes("text-xs text-gray-500 mb-2")
                                
                                # Show initialization description if available
                                init_description = predicted_data.get('description', '')
                                if init_description and init_description.strip():
                                    ui.label(init_description.strip()).classes("text-sm text-gray-700 mb-2 italic").style("max-width: 100%; word-wrap: break-word;")
                                
                                # Show pause notes if available (full width)
                                if pause_reason and pause_reason.strip():
                                    ui.label("Pause Notes:").classes("text-sm font-semibold text-orange-600 mb-1 mt-2")
                                    ui.label(pause_reason.strip()).classes("text-sm text-gray-700 mb-2 p-2 bg-orange-50 border border-orange-200 rounded").style("max-width: 100%; word-wrap: break-word;")
                                
                                with ui.row().classes("gap-2 mt-2"):
                                    ui.button("Complete",
                                              on_click=lambda i=instance_id: go_complete(i)
                                              ).classes("bg-green-500")
                                    ui.button("Pause",
                                              color="primary",
                                              on_click=lambda i=instance_id: open_pause_dialog(i)
                                              )
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
            
            # Obstacles Overcome Section
            ui.separator().classes("my-2")
            ui.label("Obstacles Overcome").classes("text-sm font-semibold text-gray-700")
            
            # Total Obstacles Score (Robust)
            with ui.card().classes("p-2 w-full border-l-4 border-blue-400"):
                ui.label("Obstacles Score (Robust)").classes("text-xs text-gray-500")
                obstacles_robust = relief_summary.get('total_obstacles_score_robust', 0.0)
                ui.label(f"{obstacles_robust:.1f}").classes("text-sm font-bold text-blue-600")
                ui.label("Median baseline").classes("text-xs text-gray-400")
            
            # Total Obstacles Score (Sensitive)
            with ui.card().classes("p-2 w-full border-l-4 border-purple-400"):
                ui.label("Obstacles Score (Sensitive)").classes("text-xs text-gray-500")
                obstacles_sensitive = relief_summary.get('total_obstacles_score_sensitive', 0.0)
                ui.label(f"{obstacles_sensitive:.1f}").classes("text-sm font-bold text-purple-600")
                ui.label("Trimmed mean baseline").classes("text-xs text-gray-400")
            
            # Weekly Bonus Multipliers
            with ui.card().classes("p-2 w-full bg-green-50"):
                ui.label("Weekly Bonus (Robust)").classes("text-xs text-gray-500")
                bonus_robust = relief_summary.get('weekly_obstacles_bonus_multiplier_robust', 1.0)
                if bonus_robust > 1.0:
                    bonus_pct = (bonus_robust - 1.0) * 100
                    ui.label(f"{bonus_robust:.2f}x (+{bonus_pct:.0f}%)").classes("text-sm font-bold text-green-600")
                else:
                    ui.label("1.0x (no bonus)").classes("text-sm font-bold text-gray-600")
            
            with ui.card().classes("p-2 w-full bg-green-50"):
                ui.label("Weekly Bonus (Sensitive)").classes("text-xs text-gray-500")
                bonus_sensitive = relief_summary.get('weekly_obstacles_bonus_multiplier_sensitive', 1.0)
                if bonus_sensitive > 1.0:
                    bonus_pct = (bonus_sensitive - 1.0) * 100
                    ui.label(f"{bonus_sensitive:.2f}x (+{bonus_pct:.0f}%)").classes("text-sm font-bold text-green-600")
                else:
                    ui.label("1.0x (no bonus)").classes("text-sm font-bold text-gray-600")
            
            # Max Obstacle Spike
            with ui.card().classes("p-2 w-full"):
                ui.label("Max Obstacle Spike (This Week)").classes("text-xs text-gray-500")
                max_spike_robust = relief_summary.get('max_obstacle_spike_robust', 0.0)
                max_spike_sensitive = relief_summary.get('max_obstacle_spike_sensitive', 0.0)
                ui.label(f"Robust: {max_spike_robust:.1f} | Sensitive: {max_spike_sensitive:.1f}").classes("text-sm font-bold")


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')


def build_recently_completed_panel():
    """Build the recently completed tasks panel."""
    ui.label("Recent Tasks").classes("font-bold text-sm mb-2")
    ui.separator()
    
    # Container for recent tasks
    completed_container = ui.column().classes("w-full")
    
    def refresh_completed():
        completed_container.clear()
        
        recent_tasks = im.list_recent_tasks(limit=20) \
            if hasattr(im, "list_recent_tasks") else []
        
        if not recent_tasks:
            with completed_container:
                ui.label("No recent tasks").classes("text-xs text-gray-500")
            return
        
        # Show flat list with date and time
        with completed_container:
            for c in recent_tasks:
                # Get timestamp from either completed_at or cancelled_at
                completed_at = str(c.get('completed_at', ''))
                cancelled_at = str(c.get('cancelled_at', ''))
                status = c.get('status', 'completed')
                timestamp_str = completed_at if status == 'completed' else cancelled_at
                instance_id_completed = c.get('instance_id', '')
                # Format: "Task Name YYYY-MM-DD HH:MM"
                with ui.row().classes("justify-between items-center mb-1 context-menu-card").props(f'data-instance-id="{instance_id_completed}" data-context-menu="completed"').style("cursor: default; padding: 2px 4px; border-radius: 4px;"):
                    # Show task name with status indicator
                    task_name = c.get('task_name', 'Unknown')
                    status_label = " [Cancelled]" if status == 'cancelled' else ""
                    ui.label(f"{task_name}{status_label}").classes("text-xs flex-1")
                    if timestamp_str:
                        # Extract date and time parts
                        parts = timestamp_str.split()
                        if len(parts) >= 2:
                            date_part = parts[0]
                            time_part = parts[1][:5] if len(parts[1]) >= 5 else parts[1]
                            ui.label(f"{date_part} {time_part}").classes("text-xs text-gray-400")
                        else:
                            ui.label(timestamp_str).classes("text-xs text-gray-400")
                    # Hidden buttons for context menu actions (Edit, Delete only)
                    if instance_id_completed:
                        ui.button("", on_click=lambda iid=instance_id_completed: edit_instance(iid)).props(f'id="context-btn-completed-edit-{instance_id_completed}"').style("display: none;")
                        ui.button("", on_click=lambda iid=instance_id_completed: delete_instance(iid)).props(f'id="context-btn-completed-delete-{instance_id_completed}"').style("display: none;")
    
    # Initial render
    refresh_completed()


# Analytics panel is now just a header - removed compact panel


def build_recommendations_section():
    """Build the recommendations section with search-based metric filtering."""
    global dash_filters
    if not dash_filters:
        dash_filters = {}
    with ui.column().classes("scrollable-section"):
        ui.label("Smart Recommendations").classes("font-bold text-lg mb-2")
        ui.separator()
        
        # Recommendation mode toggle
        recommendation_mode = {'value': 'templates'}  # 'templates' or 'instances'
        mode_toggle_row = ui.row().classes("gap-2 mb-2 items-center")
        with mode_toggle_row:
            ui.label("Recommendation Type:").classes("text-sm")
            mode_select = ui.select(
                options={
                    'templates': 'Task Templates',
                    'instances': 'Initialized Tasks'
                },
                value='templates'
            ).classes("w-40")
        
        metric_labels = [m["label"] for m in RECOMMENDATION_METRICS]
        metric_key_map = {m["label"]: m["key"] for m in RECOMMENDATION_METRICS}
        default_metrics = metric_labels[:2] if len(metric_labels) >= 2 else metric_labels
        
        # Metric search input (replaces multi-select)
        metric_search_input = ui.input(
            label="Search metrics",
            placeholder="Search by metric name (e.g., 'relief', 'energy', 'difficulty')..."
        ).classes("w-full mb-2")
        
        # Store selected metrics based on search
        selected_metrics_state = default_metrics.copy()
        
        # Debounce timer for search input
        search_debounce_timer = None
        
        def handle_metric_search(e):
            """Handle metric search input changes with debouncing."""
            nonlocal search_debounce_timer
            
            # Cancel existing timer if any
            if search_debounce_timer is not None:
                search_debounce_timer.deactivate()
            
            # Get the current value
            value = None
            if hasattr(e, 'args'):
                if isinstance(e.args, str):
                    value = e.args
                elif isinstance(e.args, (list, tuple)) and len(e.args) > 0:
                    value = e.args[0]
                elif isinstance(e.args, dict):
                    value = e.args.get('value') or e.args.get('label')
            elif hasattr(e, 'value'):
                value = e.value
            else:
                try:
                    value = metric_search_input.value
                except Exception:
                    pass
            
            # Create a debounced function that will execute after user stops typing
            def apply_search():
                """Apply the search filter after debounce delay."""
                try:
                    current_value = metric_search_input.value
                    search_query = str(current_value).strip().lower() if current_value else None
                    if search_query == '':
                        search_query = None
                    
                    # Filter metrics based on search
                    if search_query:
                        filtered_metrics = [
                            label for label in metric_labels
                            if search_query in label.lower()
                        ]
                        # If search matches nothing, show all metrics (better UX than showing nothing)
                        selected_metrics_state[:] = filtered_metrics if filtered_metrics else metric_labels
                    else:
                        # Empty search shows default metrics
                        selected_metrics_state[:] = default_metrics
                    
                    refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
                except Exception as ex:
                    pass
            
            # Create a timer that will execute after 300ms of no typing
            search_debounce_timer = ui.timer(0.3, apply_search, once=True)
        
        # Use debounced 'update:model-value' event to prevent refresh on every keystroke
        metric_search_input.on('update:model-value', handle_metric_search)
        
        # Filters row
        filter_row = ui.row().classes("gap-2 flex-wrap mb-2 items-end")
        
        with filter_row:
            # Duration filters
            min_duration = ui.number(
                label="Min duration (min)",
                value=dash_filters.get('min_duration'),
            ).classes("w-32")
            
            max_duration = ui.number(
                label="Max duration (min)",
                value=dash_filters.get('max_duration'),
            ).classes("w-32")
            
            # Task type filter
            task_type_select = ui.select(
                options={
                    '': 'All Types',
                    'Work': 'Work',
                    'Play': 'Play',
                    'Self care': 'Self care',
                },
                label="Task Type",
                value=dash_filters.get('task_type', ''),
            ).classes("w-32")
            
            # Recurring filter
            is_recurring_select = ui.select(
                options={
                    '': 'All',
                    'true': 'Recurring',
                    'false': 'One-time',
                },
                label="Recurring",
                value=dash_filters.get('is_recurring', ''),
            ).classes("w-32")
            
            # Categories search filter
            categories_search = ui.input(
                label="Categories",
                placeholder="Search categories...",
                value=dash_filters.get('categories', ''),
            ).classes("w-40")
            
            def apply_filters():
                # Min duration
                min_val = min_duration.value if min_duration.value not in (None, '', 'None') else None
                if min_val is not None:
                    try:
                        min_val = float(min_val)
                    except (TypeError, ValueError):
                        min_val = None
                dash_filters['min_duration'] = min_val
                
                # Max duration
                max_val = max_duration.value if max_duration.value not in (None, '', 'None') else None
                if max_val is not None:
                    try:
                        max_val = float(max_val)
                    except (TypeError, ValueError):
                        max_val = None
                dash_filters['max_duration'] = max_val
                
                # Task type
                task_type_val = task_type_select.value if task_type_select.value else None
                dash_filters['task_type'] = task_type_val
                
                # Is recurring
                is_recurring_val = is_recurring_select.value if is_recurring_select.value else None
                dash_filters['is_recurring'] = is_recurring_val
                
                # Categories
                categories_val = categories_search.value.strip() if categories_search.value else None
                dash_filters['categories'] = categories_val
                
                refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
            
            ui.button("APPLY", on_click=apply_filters).props("dense")
        
        # Handle mode change
        def on_mode_change(e):
            recommendation_mode['value'] = mode_select.value
            refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])
        
        mode_select.on('update:model-value', on_mode_change)
        
        # Recommendations container
        rec_container = ui.column().classes("w-full")
        
        # Initial render
        refresh_recommendations(rec_container, selected_metrics_state, metric_key_map, recommendation_mode['value'])


def refresh_recommendations(target_container, selected_metrics=None, metric_key_map=None, mode='templates'):
    """Refresh the recommendations display based on selected metrics.
    
    Args:
        target_container: UI container to render recommendations in
        selected_metrics: List of metric labels to display
        metric_key_map: Mapping from metric labels to keys
        mode: 'templates' for task templates or 'instances' for initialized tasks
    """
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
    
    # Get recommendations for the selected metrics (top 10)
    # Use module-level dash_filters if available, otherwise empty dict
    filters = globals().get('dash_filters', {})
    
    if mode == 'instances':
        recs = an.recommendations_from_instances(metric_keys, filters, limit=10)
    else:
        recs = an.recommendations_by_category(metric_keys, filters, limit=10)
    
    if not recs:
        with target_container:
            ui.label("No recommendations available").classes("text-xs text-gray-500")
        return
    
    with target_container:
        for idx, rec in enumerate(recs):
            task_label = rec.get('task_name') or rec.get('title') or "Recommendation"
            description = rec.get('description', '').strip()
            score_val = rec.get('score')
            sub_scores = rec.get('sub_scores', {})
            rec_id = f"rec-{idx}-{rec.get('instance_id') or rec.get('task_id') or idx}"
            
            # Format the recommendation card with hover tooltip
            card_element = ui.card().classes("recommendation-card recommendation-card-hover").style("position: relative;")
            card_element.props(f'data-rec-id="{rec_id}"')
            with card_element:
                # Task name
                ui.label(task_label).classes("font-bold text-sm mb-1")
                
                # Show normalized score prominently
                if score_val is not None:
                    score_text = f"Recommendation Score: {score_val:.1f}/100"
                    ui.label(score_text).classes("text-sm font-semibold text-blue-600 mb-2")
                else:
                    ui.label("Score: —").classes("text-xs text-gray-400 mb-2")
                
                # Show initialization notes if available
                if description:
                    with ui.card().classes("bg-gray-50 p-2 mb-2"):
                        ui.label("Notes:").classes("text-xs font-semibold text-gray-600 mb-1")
                        ui.label(description).classes("text-xs text-gray-700")
                else:
                    ui.label("No notes").classes("text-xs text-gray-400 italic mb-2")
                
                # Button action depends on mode
                if mode == 'instances':
                    instance_id = rec.get('instance_id')
                    if instance_id:
                        # Check if instance is paused
                        instance = im.get_instance(instance_id)
                        is_paused = False
                        if instance:
                            actual_str = instance.get("actual") or "{}"
                            try:
                                actual_data = json.loads(actual_str) if isinstance(actual_str, str) else (actual_str if isinstance(actual_str, dict) else {})
                                is_paused = actual_data.get('paused', False)
                            except (json.JSONDecodeError, TypeError):
                                pass
                        
                        # Show "Resume" if paused, otherwise "Start"
                        if is_paused:
                            def log_and_resume(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='resume',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                resume_instance(iid)
                            
                            ui.button("RESUME",
                                      on_click=lambda iid=instance_id: log_and_resume(iid)
                                      ).props("dense size=sm").classes("w-full bg-blue-500")
                        else:
                            def log_and_start(iid):
                                try:
                                    recommendation_logger.log_recommendation_selected(
                                        task_id=rec.get('task_id'),
                                        instance_id=iid,
                                        task_name=task_label,
                                        recommendation_score=score_val,
                                        action='start',
                                        context={
                                            'mode': mode,
                                            'metrics': metric_keys,
                                            'filters': filters,
                                        }
                                    )
                                except Exception:
                                    pass
                                start_instance(iid)
                            
                            ui.button("START",
                                      on_click=lambda iid=instance_id: log_and_start(iid)
                                      ).props("dense size=sm").classes("w-full bg-green-500")
                    else:
                        ui.label("No instance ID").classes("text-xs text-gray-400")
                else:
                    # Template mode - initialize button
                    task_id = rec.get('task_id')
                    if task_id:
                        # Capture task_id in lambda closure
                        def log_and_init(tid):
                            try:
                                recommendation_logger.log_recommendation_selected(
                                    task_id=tid,
                                    instance_id=None,
                                    task_name=task_label,
                                    recommendation_score=score_val,
                                    action='initialize',
                                    context={
                                        'mode': mode,
                                        'metrics': metric_keys,
                                        'filters': filters,
                                    }
                                )
                            except Exception:
                                pass
                            init_quick(tid)
                        
                        ui.button("INITIALIZE",
                                  on_click=lambda tid=task_id: log_and_init(tid)
                                  ).props("dense size=sm").classes("w-full")
                    else:
                        ui.label("No task ID").classes("text-xs text-gray-400")
            
            # Create tooltip with sub-scores using the same pattern as task tooltips
            # Build tooltip content similar to format_colored_tooltip
            tooltip_parts = ['<div style="font-weight: bold; margin-bottom: 8px; color: #e5e7eb;">Detailed Metrics</div>']
            
            # Add sub-scores to tooltip
            score_labels = {
                'relief_score': 'Relief Score',
                'cognitive_load': 'Cognitive Load',
                'emotional_load': 'Emotional Load',
                'physical_load': 'Physical Load',
                'stress_level': 'Stress Level',
                'behavioral_score': 'Behavioral Score',
                'net_wellbeing_normalized': 'Net Wellbeing',
                'net_load': 'Net Load',
                'net_relief_proxy': 'Net Relief',
                'mental_energy_needed': 'Mental Energy',
                'task_difficulty': 'Task Difficulty',
                'historical_efficiency': 'Historical Efficiency',
                'duration_minutes': 'Duration (min)',
            }
            
            for key, label in score_labels.items():
                val = sub_scores.get(key)
                if val is not None:
                    try:
                        display_val = f"{float(val):.1f}"
                    except (ValueError, TypeError):
                        display_val = str(val)
                    tooltip_parts.append(f'<div><strong>{label}:</strong> {display_val}</div>')
            
            formatted_tooltip = ''.join(tooltip_parts)
            tooltip_id = f'tooltip-{rec_id}'
            tooltip_html = f'<div id="{tooltip_id}" class="recommendation-tooltip">{formatted_tooltip}</div>'
            
            # Add tooltip to body using the same method as task tooltips
            ui.add_body_html(tooltip_html)
    
    # Initialize tooltips after all cards are created (same pattern as task tooltips)
    ui.run_javascript('setTimeout(initRecommendationTooltips, 200);')