# ui/login.py
"""
Login page with Google OAuth authentication.
"""
from nicegui import ui
from backend.auth import get_current_user, login_with_google, logout
from backend.security_utils import escape_for_display
from ui.error_reporting import handle_error_with_ui


@ui.page('/login')
def login_page():
    """Login page with Google OAuth button."""
    user_id = get_current_user()
    
    if user_id:
        # User is already logged in
        with ui.column().classes('w-full max-w-md mx-auto mt-8 gap-4'):
            ui.label('You are already logged in').classes('text-2xl font-bold text-center')
            
            with ui.card().classes('w-full p-6'):
                ui.label('Current Session').classes('text-lg font-semibold mb-4')
                
                # Get user email from session (stored in session data)
                from nicegui import app
                session_token = app.storage.browser.get('session_token')
                if session_token:
                    session_data = app.storage.general.get(f'session:{session_token}')
                    if session_data:
                        email = session_data.get('email', 'Unknown')
                        ui.label(f'Email: {escape_for_display(email)}').classes('mb-2')
                
                with ui.row().classes('gap-2 mt-4'):
                    ui.button('Go to Dashboard', on_click=lambda: ui.navigate.to('/')).classes('flex-1')
                    ui.button('Logout', on_click=lambda: handle_logout_and_reload()).classes('flex-1')
    else:
        # Show login form
        with ui.column().classes('w-full max-w-md mx-auto mt-16 gap-6'):
            ui.label('Task Aversion System').classes('text-3xl font-bold text-center')
            ui.label('Sign in to continue').classes('text-lg text-gray-600 text-center mb-4')
            
            with ui.card().classes('w-full p-8'):
                ui.label('Authentication').classes('text-xl font-semibold mb-6')
                
                ui.label(
                    'Sign in with your Google account to access your tasks and data.'
                ).classes('text-gray-700 mb-6')
                
                ui.button(
                    'Sign in with Google',
                    on_click=login_with_google,
                    icon='login'
                ).classes('w-full bg-blue-600 hover:bg-blue-700 text-white text-lg py-3')
                
                ui.separator().classes('my-6')
                
                with ui.expansion('Why do I need to sign in?', icon='info').classes('w-full'):
                    ui.label(
                        'Signing in allows you to:\n'
                        '• Access your tasks from any device\n'
                        '• Keep your data secure and private\n'
                        '• Sync your preferences across sessions\n'
                        '• Migrate your existing anonymous data'
                    ).classes('text-sm text-gray-600 whitespace-pre-line p-4')


def handle_logout():
    """Handle logout action."""
    logout()
    ui.notify('Logged out successfully', color='positive')
    # Force a full page reload to clear any cached session state
    ui.run_javascript('window.location.href = "/login";')

def handle_logout_and_reload():
    """Handle logout and force page reload to clear session state."""
    current_user_id = get_current_user()
    try:
        # Clear session
        success = logout()
        if success:
            ui.notify('Logged out successfully', color='positive')
        else:
            ui.notify('Error during logout', color='negative')
        
        # Use a small delay to ensure logout completes, then force full page reload
        def do_redirect():
            # Force a full page reload to clear any cached session state
            ui.run_javascript('window.location.href = "/login";')
        
        # Small delay to ensure storage operations complete
        ui.timer(0.1, do_redirect, once=True)
    except Exception as e:
        handle_error_with_ui(
            "logout",
            e,
            user_id=current_user_id
        )
        # Still try to redirect even if logout failed
        ui.run_javascript('window.location.href = "/login";')
