# app.py
from nicegui import ui
import time
from backend.task_manager import TaskManager
from backend.emotion_manager import EmotionManager
from backend.routine_scheduler import start_scheduler
from backend.bootup_logger import get_bootup_logger

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


# Initialize bootup logger
bootup_logger = get_bootup_logger()
bootup_logger.log_server_start()

# Initialize managers with logging
init_start = time.perf_counter()
task_manager = TaskManager()
init_duration = (time.perf_counter() - init_start) * 1000
bootup_logger.log_manager_initialization('TaskManager', init_duration)

init_start = time.perf_counter()
emotion_manager = EmotionManager()
init_duration = (time.perf_counter() - init_start) * 1000
bootup_logger.log_manager_initialization('EmotionManager', init_duration)


def register_pages():
    @ui.page('/')
    def index():
        from fastapi import Request
        request = ui.context.client.request if hasattr(ui.context, 'client') and hasattr(ui.context.client, 'request') else None
        path = request.url.path if request else '/'
        client_id = str(id(ui.context.client)) if hasattr(ui.context, 'client') else None
        
        page_start = time.perf_counter()
        bootup_logger.log_page_load_start(path, client_id)
        
        # Check for gap handling needs before showing dashboard
        if check_and_redirect_to_gap_handling():
            bootup_logger.log_page_render_complete(path, None, client_id)
            return
        try:
            build_dashboard(task_manager)
            page_duration = (time.perf_counter() - page_start) * 1000
            bootup_logger.log_page_render_complete(path, page_duration, client_id)
        except Exception as e:
            # Show user-friendly error page instead of crashing
            import traceback
            error_details = traceback.format_exc()
            print(f"[App] Error building dashboard: {error_details}")
            bootup_logger.log_error("Error building dashboard", e, {'path': path, 'client_id': client_id})
            
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
        path = '/gap-handling'
        client_id = str(id(ui.context.client)) if hasattr(ui.context, 'client') else None
        page_start = time.perf_counter()
        bootup_logger.log_page_load_start(path, client_id)
        gap_handling_page()
        page_duration = (time.perf_counter() - page_start) * 1000
        bootup_logger.log_page_render_complete(path, page_duration, client_id)
    
    # Log page registrations (pages registered via decorators are logged when register_pages() is called)
    bootup_logger.log_page_registration('/')
    bootup_logger.log_page_registration('/gap-handling')

    create_task_page(task_manager, emotion_manager)
    bootup_logger.log_page_registration('/create-task')
    initialize_task_page(task_manager, emotion_manager)
    bootup_logger.log_page_registration('/initialize-task')
    complete_task_page(task_manager, emotion_manager)
    bootup_logger.log_page_registration('/complete_task')
    cancel_task_page(task_manager, emotion_manager)
    bootup_logger.log_page_registration('/cancel_task')
    register_analytics_page()
    bootup_logger.log_page_registration('/analytics')
    register_analytics_glossary()
    bootup_logger.log_page_registration('/analytics/glossary')
    register_relief_comparison_page()
    bootup_logger.log_page_registration('/analytics/relief-comparison')
    register_formula_baseline_charts()
    bootup_logger.log_page_registration('/experimental/formula-baseline-charts')
    register_known_issues_page()
    bootup_logger.log_page_registration('/known-issues')
    bootup_logger.log_page_registration('/')
    bootup_logger.log_page_registration('/gap-handling')


if __name__ in {"__main__", "__mp_main__"}:
    register_pages()
    
    # Set up static file serving for graphic aids
    import os
    from fastapi.staticfiles import StaticFiles
    from nicegui import app
    from fastapi import Request
    
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    graphic_aids_dir = os.path.join(assets_dir, 'graphic_aids')
    os.makedirs(graphic_aids_dir, exist_ok=True)
    
    # Mount static files directory using FastAPI
    app.mount('/static/graphic_aids', StaticFiles(directory=graphic_aids_dir), name='graphic_aids')
    bootup_logger.log_static_mount('/static/graphic_aids', graphic_aids_dir)
    
    # Add HTTP request middleware to log all incoming requests
    # Use Starlette's BaseHTTPMiddleware for better compatibility
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response
    
    class HTTPRequestLoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: StarletteRequest, call_next):
            """Log all HTTP requests to track connection attempts."""
            start_time = time.perf_counter()
            path = request.url.path
            method = request.method
            client_host = request.client.host if request.client else None
            
            bootup_logger.log_page_request(path, method, str(client_host))
            
            try:
                response = await call_next(request)
                duration_ms = (time.perf_counter() - start_time) * 1000
                bootup_logger.log_browser_event('http_request_complete', {
                    'path': path,
                    'method': method,
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                    'client_host': client_host
                })
                return response
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                bootup_logger.log_error(f"HTTP request error: {path}", e, {
                    'method': method,
                    'duration_ms': round(duration_ms, 2),
                    'client_host': client_host
                })
                raise
    
    # Add the middleware
    app.add_middleware(HTTPRequestLoggingMiddleware)
    
    # Add endpoint for browser-side logging
    @app.post('/api/log-browser-event')
    async def log_browser_event(request: Request):
        """Endpoint for browser-side events to log."""
        try:
            data = await request.json()
            event_type = data.get('event_type', 'unknown')
            event_data = data.get('data', {})
            bootup_logger.log_browser_event(event_type, event_data)
            return {'status': 'ok'}
        except Exception as e:
            bootup_logger.log_error("Error logging browser event", e)
            return {'status': 'error', 'message': str(e)}
    
    # Use FastAPI startup event to log when server is actually ready
    # This fires after ui.run() starts the server and WebSocket handlers are initialized
    @app.on_event("startup")
    async def on_startup():
        """Log when server is actually ready after WebSocket initialization."""
        import asyncio
        # Small delay to allow WebSocket infrastructure to fully initialize
        await asyncio.sleep(0.5)
        host = os.getenv('NICEGUI_HOST', '127.0.0.1')
        bootup_logger.log_server_ready(host, 8080)
    
    # Start routine scheduler
    scheduler_start = time.perf_counter()
    start_scheduler()
    scheduler_duration = (time.perf_counter() - scheduler_start) * 1000
    bootup_logger.log_service_start('routine_scheduler')
    
    host = os.getenv('NICEGUI_HOST', '127.0.0.1')  # Default to localhost, use env var in Docker
    # Don't log server_ready here - it will be logged in the startup event
    # after WebSocket infrastructure is initialized
    ui.run(title='Task Aversion System', port=8080, host=host, reload=False)

