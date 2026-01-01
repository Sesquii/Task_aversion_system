"""
Reusable popup modal component for displaying popups with options and feedback.
"""
from nicegui import ui
from typing import Optional, Dict, Any, Callable


def show_popup_modal(popup_data: Dict[str, Any], 
                     on_response: Optional[Callable[[str, Optional[bool], Optional[str]], None]] = None) -> None:
    """
    Display a popup modal with title, message, options, and helpful toggle.
    
    Args:
        popup_data: Dict with 'title', 'message', 'options', 'trigger_id', etc.
        on_response: Callback function(response_value, helpful, comment) called when user responds
    """
    trigger_id = popup_data.get('trigger_id', 'unknown')
    title = popup_data.get('title', 'Notification')
    message = popup_data.get('message', '')
    options = popup_data.get('options', [])
    show_helpful = popup_data.get('show_helpful_toggle', True)
    
    # Create modal dialog
    with ui.dialog() as dialog, ui.card().classes('w-full max-w-md'):
        ui.label(title).classes('text-xl font-bold mb-4')
        ui.label(message).classes('text-sm mb-6 whitespace-pre-wrap')
        
        # Options buttons
        with ui.row().classes('w-full gap-2'):
            for option in options:
                option_value = option.get('value', '')
                option_label = option.get('label', option_value)
                option_color = option.get('color', 'primary')
                
                def make_handler(val):
                    def handler():
                        handle_response(val)
                    return handler
                
                ui.button(option_label, on_click=make_handler(option_value)).classes(f'flex-1').props(f'color={option_color}')
        
        # Helpful toggle and comment (optional)
        if show_helpful:
            ui.separator().classes('my-4')
            helpful_toggle = ui.checkbox('Helpful?', value=False)
            comment_input = ui.textarea(
                label='Feedback (optional)',
                placeholder='Any comments to help improve this popup?'
            ).classes('w-full mt-2')
            comment_input.set_visibility(False)
            
            def toggle_comment():
                comment_input.set_visibility(helpful_toggle.value)
            
            helpful_toggle.on('update:model-value', lambda e: toggle_comment())
        
        # Store references for response handler
        dialog.helpful_toggle = helpful_toggle if show_helpful else None
        dialog.comment_input = comment_input if show_helpful else None
        dialog.on_response = on_response
        dialog.trigger_id = trigger_id
    
    # Response handler
    def handle_response(response_value: str):
        helpful = None
        comment = None
        
        if show_helpful and hasattr(dialog, 'helpful_toggle') and dialog.helpful_toggle:
            helpful = dialog.helpful_toggle.value
            if hasattr(dialog, 'comment_input') and dialog.comment_input:
                comment = dialog.comment_input.value or None
        
        # Call callback if provided
        if on_response:
            on_response(response_value, helpful, comment)
        
        dialog.close()
    
    # Show modal
    dialog.open()
