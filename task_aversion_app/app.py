# app.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.emotion_manager import EmotionManager
from backend.routine_scheduler import start_scheduler
from backend.auth import get_current_user, oauth_callback

from ui.dashboard import build_dashboard
from ui.create_task import create_task_page
from ui.initialize_task import initialize_task_page
from ui.complete_task import complete_task_page
from ui.cancel_task import cancel_task_page
from ui.analytics_page import register_analytics_page
from ui.analytics_glossary import register_analytics_glossary
from ui.relief_comparison_analytics import register_relief_comparison_page
from ui.known_issues_page import register_known_issues_page
from ui.gap_handling import gap_handling_page, check_and_redirect_to_gap_handling
# Import pages - these will auto-register via @ui.page() decorators
# Import order matters - login page should be imported first
from ui.login import login_page  # registers /login
# import submodules without rebinding the nicegui `ui` object
from ui import survey_page  # registers /survey
from ui import settings_page  # registers /settings
from ui import cancelled_tasks_page  # registers /cancelled-tasks
from ui import task_editing_manager  # registers /task-editing-manager
from ui import composite_score_weights_page  # registers /settings/composite-score-weights
from ui import cancellation_penalties_page  # registers /settings/cancellation-penalties
from ui import productivity_settings_page  # registers /settings/productivity-settings
# from ui import data_guide_page  # registers /data-guide - TODO: Re-enable when data guide is updated for local setup
from ui import composite_score_page  # registers /composite-score
from ui import summary_page  # registers /summary
from ui import notes_page  # registers /notes
from ui import productivity_goals_experimental  # registers /goals/productivity-hours
from ui import goals_page  # registers /goals
from ui import productivity_module  # registers /productivity-module - ⚠️ FLAGGED FOR REMOVAL AFTER REVIEW
from ui import experimental_landing  # registers /experimental
from ui.formula_baseline_charts import register_formula_baseline_charts  # registers /experimental/formula-baseline-charts
from ui import formula_control_system  # registers /experimental/formula-control-system/productivity-score
from ui import coursera_analysis  # registers /experimental/coursera-analysis
from ui import productivity_grit_tradeoff  # registers /experimental/productivity-grit-tradeoff
from ui import task_distribution  # registers /experimental/task-distribution


task_manager = TaskManager()
emotion_manager = EmotionManager()


def register_pages():
    # OAuth callback route (must be registered before other routes)
    from fastapi import Request
    
    @ui.page('/auth/callback')
    async def auth_callback(request: Request):
        # request is automatically injected by NiceGUI when page function has request parameter
        await oauth_callback(request)
    
    # Note: login_page is already registered via @ui.page() decorator when imported
    # No need to call it again
    
    @ui.page('/')
    def index():
        # Check authentication
        user_id = get_current_user()
        if user_id is None:
            ui.navigate.to('/login')
            return
        
        # Check for gap handling needs before showing dashboard
        if check_and_redirect_to_gap_handling():
            return
        try:
            # Pass user_id to dashboard
            build_dashboard(task_manager, user_id=user_id)
        except Exception as e:
            # Show user-friendly error page instead of crashing
            import traceback
            error_details = traceback.format_exc()
            print(f"[App] Error building dashboard: {error_details}")
            
            ui.label("⚠️ Dashboard Error").classes("text-2xl font-bold text-red-600 mb-4")
            
            with ui.card().classes("w-full max-w-2xl p-6 bg-red-50 border border-red-200"):
                ui.label("Unable to load the dashboard.").classes("text-lg font-semibold text-red-700 mb-2")
                ui.label(
                    "This may be caused by:\n"
                    "• Data file is open in Excel or another program\n"
                    "• OneDrive sync is in progress\n"
                    "• File permissions issue\n"
                    "• Data corruption"
                ).classes("text-sm text-red-600 mb-4 whitespace-pre-line")
                
                with ui.expansion("Technical Details", icon="info").classes("w-full"):
                    ui.code(error_details).classes("text-xs")
                
                ui.button("Retry", on_click=lambda: ui.navigate.to('/')).classes("mt-4")
                ui.button("Go to Settings", on_click=lambda: ui.navigate.to('/settings')).classes("mt-2")
    
    @ui.page('/gap-handling')
    def gap_handling():
        # Check authentication
        user_id = get_current_user()
        if user_id is None:
            ui.navigate.to('/login')
            return
        gap_handling_page()

    create_task_page(task_manager, emotion_manager)
    initialize_task_page(task_manager, emotion_manager)
    complete_task_page(task_manager, emotion_manager)
    cancel_task_page(task_manager, emotion_manager)
    register_analytics_page()
    register_analytics_glossary()
    register_relief_comparison_page()
    register_formula_baseline_charts()
    register_known_issues_page()


if __name__ in {"__main__", "__mp_main__"}:
    register_pages()
    
    # Set up static file serving for graphic aids
    import os
    from fastapi.staticfiles import StaticFiles
    from nicegui import app
    
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    graphic_aids_dir = os.path.join(assets_dir, 'graphic_aids')
    os.makedirs(graphic_aids_dir, exist_ok=True)
    
    # Mount static files directory using FastAPI
    app.mount('/static/graphic_aids', StaticFiles(directory=graphic_aids_dir), name='graphic_aids')
    
    # Start routine scheduler
    start_scheduler()
    host = os.getenv('NICEGUI_HOST', '127.0.0.1')  # Default to localhost, use env var in Docker
    # Storage secret for browser storage (required for OAuth session management)
    # Use environment variable or generate a default (not secure for production)
    storage_secret = os.getenv('STORAGE_SECRET', 'dev-secret-change-in-production')
    ui.run(title='Task Aversion System', port=8080, host=host, reload=False, storage_secret=storage_secret)

