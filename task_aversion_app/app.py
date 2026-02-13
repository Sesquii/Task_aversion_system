# app.py
from nicegui import ui

# Instrument navigation/cache/analytics early (before any pages use ui.navigate)
try:
    from backend.instrumentation import (
        instrument_navigate,
        _log_cache_start,
        _log_analytics_start,
    )
    instrument_navigate(ui)
    _log_cache_start()
    _log_analytics_start()
except Exception as e:
    import sys
    print(f"[App] Instrumentation setup failed: {e}", file=sys.stderr)

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
        try:
            from backend.instrumentation import log_page_visit
            log_page_visit('/')
        except ImportError:
            pass
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
    
    
    # Diagnostic endpoint to check backend mode
    @ui.page('/diagnostic/backend')
    def backend_diagnostic():
        """Diagnostic page to check which backend is being used."""
        from backend.task_manager import TaskManager
        from backend.instance_manager import InstanceManager
        
        tm = TaskManager()
        im = InstanceManager()
        
        ui.label("Backend Diagnostic").classes("text-2xl font-bold mb-4")
        
        with ui.card().classes("w-full max-w-2xl p-4"):
            ui.label("TaskManager:").classes("text-lg font-semibold mb-2")
            ui.label(f"Using Database: {tm.use_db}").classes("mb-1")
            ui.label(f"Strict Mode: {tm.strict_mode}").classes("mb-1")
            
            if tm.use_db:
                try:
                    from backend.database import get_session, Task
                    with get_session() as session:
                        count = session.query(Task).count()
                        ui.label(f"Database tasks: {count}").classes("text-green-600 mb-1")
                except Exception as e:
                    ui.label(f"Database error: {e}").classes("text-red-600 mb-1")
            else:
                if hasattr(tm, 'tasks_file') and os.path.exists(tm.tasks_file):
                    import pandas as pd
                    try:
                        df = pd.read_csv(tm.tasks_file, dtype=str).fillna('')
                        ui.label(f"CSV tasks: {len(df)}").classes("text-yellow-600 mb-1")
                    except Exception as e:
                        ui.label(f"CSV error: {e}").classes("text-red-600 mb-1")
        
        with ui.card().classes("w-full max-w-2xl p-4 mt-4"):
            ui.label("InstanceManager:").classes("text-lg font-semibold mb-2")
            ui.label(f"Using Database: {im.use_db}").classes("mb-1")
            
            if im.use_db:
                try:
                    from backend.database import get_session, TaskInstance
                    with get_session() as session:
                        count = session.query(TaskInstance).count()
                        ui.label(f"Database instances: {count}").classes("text-green-600 mb-1")
                except Exception as e:
                    ui.label(f"Database error: {e}").classes("text-red-600 mb-1")
            else:
                if hasattr(im, 'file') and os.path.exists(im.file):
                    import pandas as pd
                    try:
                        df = pd.read_csv(im.file, dtype=str).fillna('')
                        ui.label(f"CSV instances: {len(df)}").classes("text-yellow-600 mb-1")
                    except Exception as e:
                        ui.label(f"CSV error: {e}").classes("text-red-600 mb-1")
        
        with ui.card().classes("w-full max-w-2xl p-4 mt-4"):
            ui.label("Environment:").classes("text-lg font-semibold mb-2")
            ui.label(f"USE_CSV: {os.getenv('USE_CSV', '(not set)')}").classes("mb-1")
            ui.label(f"DATABASE_URL: {os.getenv('DATABASE_URL', '(not set)')}").classes("mb-1")
            ui.label(f"DISABLE_CSV_FALLBACK: {os.getenv('DISABLE_CSV_FALLBACK', '(not set)')}").classes("mb-1")
        
        ui.button("Refresh", on_click=lambda: ui.navigate.reload()).classes("mt-4")


def _backend_label() -> str:
    """Return which storage backend is active (ASCII-safe for Windows console)."""
    use_csv = os.getenv('USE_CSV', '').strip().lower() in ('1', 'true', 'yes')
    if use_csv:
        return 'CSV (USE_CSV overrides DATABASE_URL)'
    url = os.getenv('DATABASE_URL', '').strip()
    if not url:
        return 'CSV (no DATABASE_URL set)'
    if url.lower().startswith('postgresql'):
        return 'PostgreSQL'
    if url.lower().startswith('sqlite'):
        return 'SQLite'
    return 'Database'


if __name__ in {"__main__", "__mp_main__"}:
    import os
    import sys

    # Optional: redirect stdout/stderr to a log file to avoid flooding the terminal
    _log_file = None
    _log_path = os.getenv("APP_LOG_FILE", "").strip() or (os.path.join(
        os.path.dirname(__file__), "logs", "app.log"
    ) if os.getenv("LOG_TO_FILE", "").lower() in ("1", "true", "yes") else "")
    if _log_path:
        try:
            _log_dir = os.path.dirname(_log_path)
            if _log_dir:
                os.makedirs(_log_dir, exist_ok=True)
            _log_file = open(_log_path, "a", encoding="utf-8")
            _tee = os.getenv("LOG_TEE", "").lower() in ("1", "true", "yes")
            _orig_stdout, _orig_stderr = sys.stdout, sys.stderr

            class _LogStream:
                def __init__(self, file, original, tee_mode):
                    self._file = file
                    self._orig = original
                    self._tee = tee_mode
                def write(self, data):
                    try:
                        self._file.write(data)
                        self._file.flush()
                    except OSError:
                        pass
                    if self._tee and self._orig:
                        try:
                            self._orig.write(data)
                            self._orig.flush()
                        except OSError:
                            pass
                def flush(self):
                    try:
                        self._file.flush()
                    except OSError:
                        pass
                    if self._orig:
                        try:
                            self._orig.flush()
                        except OSError:
                            pass
                def fileno(self):
                    return self._orig.fileno() if self._orig else -1
                def isatty(self):
                    return self._orig.isatty() if self._orig else False
                def writable(self):
                    return True

            sys.stdout = _LogStream(_log_file, _orig_stdout if _tee else None, _tee)
            sys.stderr = _LogStream(_log_file, _orig_stderr if _tee else None, _tee)

            # Log uncaught exceptions to app.log (e.g. KeyError in analytics)
            _log_path_final = _log_path
            def _excepthook(exc_type, exc_value, exc_tb):
                import traceback
                try:
                    with open(_log_path_final, "a", encoding="utf-8") as f:
                        f.write("[Uncaught] ")
                        f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
                        f.write("\n")
                except OSError:
                    pass
                # Chain to default so process still exits / shows in console
                sys.__excepthook__(exc_type, exc_value, exc_tb)
            sys.excepthook = _excepthook

            # So user always sees this in the terminal even when not teeing
            try:
                _orig_stdout.write(f"[App] Stdout/stderr logging to: {_log_path}\n")
                _orig_stdout.write("[App] Server will start below; open http://127.0.0.1:8080\n")
                _orig_stdout.flush()
            except OSError:
                pass
            print(f"[App] Logging to file: {_log_path}")
        except OSError as e:
            print(f"[App] Could not open log file {_log_path}: {e}", file=sys.__stderr__)

    # Terminal notification: which database is in use (separate line, ASCII-safe)
    print("")
    print("[Backend] Storage: " + _backend_label())
    print("")
    register_pages()
    
    # Set up static file serving for graphic aids
    from fastapi.staticfiles import StaticFiles
    from nicegui import app
    
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    graphic_aids_dir = os.path.join(assets_dir, 'graphic_aids')
    os.makedirs(graphic_aids_dir, exist_ok=True)
    
    # Mount static files directory using FastAPI
    app.mount('/static/graphic_aids', StaticFiles(directory=graphic_aids_dir), name='graphic_aids')
    
    # Simple version check endpoint (no UI, just returns version info)
    @app.get('/api/version')
    async def version_check():
        """Simple endpoint to check if server is running latest code."""
        import time
        return {
            "version": "1.0.0",
            "timestamp": time.time(),
            "message": "Server is running. If you see this, the server has the latest code."
        }
    
    # Add query logging middleware (lightweight, can be disabled via env var)
    if os.getenv('ENABLE_QUERY_LOGGING', '1').lower() in ('1', 'true', 'yes'):
        try:
            from backend.query_middleware import QueryLoggingMiddleware
            app.add_middleware(QueryLoggingMiddleware)
            print("[App] Query logging middleware enabled")
        except Exception as e:
            print(f"[App] Warning: Failed to set up query logging middleware: {e}")
    
    # Start routine scheduler
    start_scheduler()
    host = os.getenv('NICEGUI_HOST', '127.0.0.1')  # Default to localhost, use env var in Docker
    # Storage secret for browser storage (required for OAuth session management)
    # Use environment variable or generate a default (not secure for production)
    storage_secret = os.getenv('STORAGE_SECRET', 'dev-secret-change-in-production')
    
    # Add cache-busting headers to prevent browser caching issues
    # NOTE: Temporarily disabled if causing Chrome/Edge loading issues
    # Set ENABLE_CACHE_BUSTING=1 to enable
    if os.getenv('ENABLE_CACHE_BUSTING', '0').lower() in ('1', 'true', 'yes'):
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        
        class NoCacheMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                response = await call_next(request)
                # Only add no-cache headers to specific routes, not WebSocket or NiceGUI internal routes
                path = request.url.path
                upgrade_header = request.headers.get('upgrade', '').lower()
                
                # Skip WebSocket connections and NiceGUI internal routes completely
                if (path.startswith('/_nicegui') or 
                    path.startswith('/ws') or
                    'websocket' in upgrade_header):
                    return response
                
                # Only apply cache-busting to specific HTML pages and API endpoints
                if (path == '/' or 
                    path.startswith('/diagnostic') or
                    path.startswith('/api/')):
                    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                    response.headers["Pragma"] = "no-cache"
                    response.headers["Expires"] = "0"
                
                return response
        
        # Add middleware AFTER all routes are registered but BEFORE ui.run()
        try:
            app.add_middleware(NoCacheMiddleware)
            print("[App] Cache-busting middleware enabled")
        except Exception as e:
            print(f"[App] Warning: Could not add cache-busting middleware: {e}")
    else:
        print("[App] Cache-busting middleware disabled (set ENABLE_CACHE_BUSTING=1 to enable)")
    
    # Show backend again right before server starts (restart app after changing .env)
    print("")
    print("---")
    print("[Backend] Storage: " + _backend_label())
    print("---")
    print("")
    ui.run(title='Task Aversion System', port=8080, host=host, reload=False, storage_secret=storage_secret)

