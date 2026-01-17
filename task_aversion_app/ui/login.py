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
            
            # Onboarding message
            with ui.card().classes('w-full p-8 mt-6'):
                ui.label('Welcome to the Task Aversion System').classes('text-2xl font-bold mb-4')
                
                ui.html('''
                    <div style="line-height: 1.6; color: #374151;">
                        <p style="margin-bottom: 1rem;">
                            The Task Aversion System is a productivity application designed to help you overcome task avoidance and increase your daily functioning through comprehensive tracking of emotions, cognitive load, motivation, and task performance metrics. Unlike simple to-do lists, this system incorporates psychological and behavioral tracking to help you understand and overcome task avoidance patterns.
                        </p>
                        
                        <p style="margin-bottom: 1rem;">
                            <strong>What is Task Aversion?</strong> Task aversion is the feeling of resistance or avoidance you experience when facing certain tasks. This system helps you quantify and understand these feelings by tracking how you feel about tasks before, during, and after completion. By measuring aversion, stress, relief, and other psychological factors alongside task completion, you can identify patterns and make data-driven decisions about which tasks to tackle and when.
                        </p>
                        
                        <p style="margin-bottom: 1rem;">
                            <strong>What Does It Track?</strong> The system tracks a comprehensive set of psychological and performance metrics. Before starting a task, you record your initial emotions, stress levels (cognitive, emotional, and physical load), and your level of aversion. During task completion, the system tracks time spent, pauses, and completion percentage. After finishing, you record the actual relief you felt, final emotions, and any factors that affected your experience. The system then calculates over a dozen performance metrics including Execution Score, Productivity Score, Grit Score, Stress Efficiency, Net Wellbeing, and more.
                        </p>
                        
                        <p style="margin-bottom: 1rem;">
                            <strong>What Insights Does It Provide?</strong> The analytics dashboard provides interactive visualizations showing trends in relief scores, stress levels, and performance metrics over time. You can explore correlations between different factors, see which tasks provide the most relief relative to stress, and identify patterns in your task completion behavior. The system also provides intelligent task recommendations based on your historical data, helping you choose tasks that are likely to be manageable and rewarding.
                        </p>
                        
                        <p style="margin-bottom: 1rem;">
                            <strong>How Does It Work?</strong> You start by creating task templates for recurring activities. When you're ready to work on a task, you initialize an instance and record your initial state. As you work, you can pause and resume tasks with time tracking that persists. When you complete a task, you record your final metrics. The system automatically calculates performance scores and stores this data for analysis. Over time, as you complete more tasks, the system builds a comprehensive picture of your patterns and preferences.
                        </p>
                        
                        <p style="margin-bottom: 0;">
                            <strong>Getting Started:</strong> After signing in, you'll be taken to the dashboard where you can create your first task template. Start with a few common tasks you do regularly. When you're ready to work on one, click "Initialize" to begin tracking. The more you use the system, the more valuable the insights become. Regular daily use provides the most meaningful data for understanding your patterns and improving your productivity.
                        </p>
                    </div>
                ''', sanitize=False).classes('text-gray-700')


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
        
        # Clear localStorage via JavaScript and force full page reload
        ui.run_javascript('''
            try {
                if (window.localStorage) {
                    localStorage.removeItem('session_token');
                    localStorage.removeItem('tas_user_id');
                    localStorage.removeItem('user_id');
                    localStorage.removeItem('login_redirect');
                }
            } catch(e) {
                console.log('Error clearing localStorage:', e);
            }
            window.location.href = "/login";
        ''')
    except Exception as e:
        handle_error_with_ui(
            "logout",
            e,
            user_id=current_user_id
        )
        # Still try to redirect even if logout failed
        ui.run_javascript('window.location.href = "/login";')
