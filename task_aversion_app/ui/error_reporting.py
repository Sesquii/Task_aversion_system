# ui/error_reporting.py
"""
Error reporting UI component for user-friendly error handling.
Shows error ID and optional user reporting dialog.
"""
from nicegui import ui
from typing import Optional, Callable
from backend.security_utils import record_error_report
from backend.auth import get_current_user


def show_error_notification(
    error_id: str,
    user_message: str = None,
    show_report_button: bool = True
):
    """
    Show error notification with error ID and optional report button.
    
    Args:
        error_id: Error ID from handle_error()
        user_message: User-friendly error message (defaults to generic message)
        show_report_button: Whether to show "Report Issue" button
    """
    if user_message is None:
        user_message = (
            f"An error occurred. Error ID: {error_id}. "
            "Please try again or contact support with this ID."
        )
    
    # Show notification
    ui.notify(
        user_message,
        color='negative',
        timeout=10000  # 10 seconds
    )
    
    # Optionally show report button in a dialog
    if show_report_button:
        show_error_report_dialog(error_id)


def show_error_report_dialog(error_id: str):
    """
    Show non-blocking error report dialog.
    User can optionally describe what they were doing when error occurred.
    
    Args:
        error_id: Error ID from handle_error()
    """
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md p-6'):
        ui.label(f'Error ID: {error_id}').classes('text-lg font-bold mb-2')
        ui.label(
            'If you\'d like, you can help us fix this by describing what you were doing when the error occurred.'
        ).classes('text-sm text-gray-600 mb-4')
        
        context_input = ui.textarea(
            label='What were you doing? (optional)',
            placeholder='e.g., "Creating a new task called \'Review project proposal\'"'
        ).classes('w-full mb-4')
        
        with ui.row().classes('w-full justify-end gap-2'):
            def skip():
                dialog.close()
            
            def submit():
                user_id = get_current_user()
                user_context = context_input.value.strip() if context_input.value else None
                
                # Record error report
                success = record_error_report(error_id, user_id, user_context)
                
                if success:
                    ui.notify('Thank you for reporting this issue!', color='positive')
                else:
                    ui.notify('Failed to submit report. Error ID saved above.', color='warning')
                
                dialog.close()
            
            ui.button('Skip', on_click=skip).classes('px-4')
            ui.button('Submit Report', on_click=submit, color='primary').classes('px-4')
    
    # Show dialog (non-blocking)
    dialog.open()


def handle_error_with_ui(
    operation: str,
    error: Exception,
    user_id: Optional[int] = None,
    context: Optional[dict] = None,
    user_message: Optional[str] = None,
    show_report: bool = True
) -> str:
    """
    Handle error and show UI notification with error ID.
    Convenience function that combines handle_error() and show_error_notification().
    
    Args:
        operation: Name of operation that failed
        error: Exception that occurred
        user_id: Optional user ID (if authenticated)
        context: Optional additional context
        user_message: Optional user-friendly message (defaults to generic)
        show_report: Whether to show error report dialog
        
    Returns:
        Error ID string
    """
    from backend.security_utils import handle_error
    
    # Log error and get error ID
    error_id = handle_error(operation, error, user_id, context)
    
    # Show UI notification
    show_error_notification(error_id, user_message, show_report)
    
    return error_id
