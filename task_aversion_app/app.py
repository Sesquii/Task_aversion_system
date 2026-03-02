# app.py
import os
from pathlib import Path

from nicegui import ui, app

# Load .env early so DATABASE_URL etc. are set before backend/migration check
try:
    from dotenv import load_dotenv
    _app_dir = Path(__file__).resolve().parent
    load_dotenv(_app_dir / ".env")
    load_dotenv()
    if not os.getenv("DATABASE_URL"):
        load_dotenv(_app_dir / ".env.production")
except ImportError:
    pass

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

from ui.dashboard import build_dashboard, build_dashboard_mobile_b
from ui.create_task import create_task_page
from ui.initialize_task import initialize_task_page
from ui.job_task_selection import register_job_task_selection_page
from ui.assign_tasks_to_jobs import register_assign_tasks_to_jobs_page
from ui.create_job import register_create_job_page
from ui.jobs_page import register_jobs_page
from ui.complete_task import complete_task_page
from ui.cancel_task import cancel_task_page
from ui.analytics_page import register_analytics_page
from ui.analytics_glossary import register_analytics_glossary
from ui.relief_comparison_analytics import register_relief_comparison_page
from ui.gap_handling import gap_handling_page, check_and_redirect_to_gap_handling
# Import pages - these will auto-register via @ui.page() decorators
# Import order matters - login page should be imported first
# These imports are for side effects (route registration via @ui.page)
from ui.login import login_page  # noqa: F401  (registers /login)
from ui import choose_experience  # noqa: F401  (registers /choose-experience)
# import submodules without rebinding the nicegui `ui` object
from ui import survey_page  # noqa: F401  (registers /survey)
from ui import settings_page  # noqa: F401  (registers /settings)
from ui import cancelled_tasks_page  # noqa: F401  (registers /cancelled-tasks)
from ui import task_editing_manager  # noqa: F401  (registers /task-editing-manager)
from ui import composite_score_weights_page  # noqa: F401  (registers /settings/composite-score-weights)
from ui import cancellation_penalties_page  # noqa: F401  (registers /settings/cancellation-penalties)
from ui import productivity_settings_page  # noqa: F401  (registers /settings/productivity-settings)
# from ui import data_guide_page  # registers /data-guide - TODO: Re-enable when data guide is updated for local setup
from ui import composite_score_page  # noqa: F401  (registers /composite-score)
from ui import summary_page  # noqa: F401  (registers /summary)
from ui import notes_page  # noqa: F401  (registers /notes)
from ui import productivity_goals_experimental  # noqa: F401  (registers /goals/productivity-hours)
from ui import goals_page  # noqa: F401  (registers /goals)
from ui import productivity_module  # noqa: F401  (registers /productivity-module) - flagged for removal after review
from ui import experimental_landing  # noqa: F401  (registers /experimental)
from ui.formula_baseline_charts import register_formula_baseline_charts  # registers /experimental/formula-baseline-charts
from ui import formula_control_system  # noqa: F401  (registers /experimental/formula-control-system/productivity-score)
from ui import coursera_analysis  # noqa: F401  (registers /experimental/coursera-analysis)
from ui import productivity_grit_tradeoff  # noqa: F401  (registers /experimental/productivity-grit-tradeoff)
from ui import task_distribution  # noqa: F401  (registers /experimental/task-distribution)


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
    def index(request: Request):
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

        # Per-device UI mode: allow query param from choose-experience or settings (avoids storage sync race)
        ui_mode = request.query_params.get('ui_mode')
        if ui_mode in ('mobile', 'desktop'):
            app.storage.browser['ui_mode'] = ui_mode
        else:
            ui_mode = app.storage.browser.get('ui_mode')

        if not ui_mode or ui_mode not in ('mobile', 'desktop'):
            ui.navigate.to('/choose-experience')
            return

        # Check for gap handling needs before showing dashboard
        if check_and_redirect_to_gap_handling():
            return
        try:
            if ui_mode == 'mobile':
                build_dashboard_mobile_b(task_manager, user_id=user_id)
            else:
                build_dashboard(task_manager, user_id=user_id)
        except Exception:
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
    register_job_task_selection_page(task_manager)
    register_assign_tasks_to_jobs_page(task_manager)
    register_create_job_page()
    register_jobs_page()
    complete_task_page(task_manager, emotion_manager)
    cancel_task_page(task_manager, emotion_manager)
    register_analytics_page()
    register_analytics_glossary()
    register_relief_comparison_page()
    register_formula_baseline_charts()

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

    # Check migration status once at startup (used by health route and redirect)
    from backend.migration_status import get_migration_status
    _migration_status = get_migration_status()
    if hasattr(app, "state"):
        app.state.migration_status = _migration_status
    if not _migration_status.ok:
        print("[App] Migrations behind - app will show 'Run migrations' until applied.")
    
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

    # Health/readiness: report migration status (503 if migrations behind)
    @app.get('/api/health')
    async def health():
        """Health check; returns 503 if migrations are behind."""
        status = getattr(app.state, "migration_status", None)
        if status is None:
            from backend.migration_status import get_migration_status
            status = get_migration_status()
        if status.ok:
            return {"status": "ok", "migrations_ok": True}
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={
                "status": "migrations_required",
                "migrations_ok": False,
                "message": status.message,
                "command": status.command,
                "details": status.details,
            },
        )

    # Migrations-required page: shown when DB is behind (blocking screen)
    @ui.page('/migrations-required')
    def migrations_required_page():
        status = getattr(app.state, "migration_status", None)
        if status is None:
            from backend.migration_status import get_migration_status
            status = get_migration_status()
        ui.html('<meta name="viewport" content="width=device-width, initial-scale=1">')
        ui.label("Database migrations required").classes(
            "text-2xl font-bold text-amber-700 mt-8"
        )
        ui.label(status.message or "Migrations are behind. Apply them to continue.").classes(
            "text-lg text-gray-700 mt-2"
        )
        with ui.card().classes("w-full max-w-2xl mt-6 p-6 bg-amber-50 border border-amber-200"):
            ui.label("Run this command in the app directory (task_aversion_app):").classes(
                "font-semibold text-gray-800"
            )
            ui.code(status.command).classes(
                "block mt-2 p-4 bg-gray-900 text-green-300 rounded text-sm font-mono"
            )
            if status.details:
                with ui.expansion("Details", icon="info").classes("w-full mt-4"):
                    for d in status.details:
                        ui.label(d).classes("text-sm text-gray-700")
        ui.label(
            "After running migrations, reload this page or restart the app."
        ).classes("text-sm text-gray-600 mt-4")
        ui.button("Reload page", on_click=lambda: ui.navigate.reload()).classes("mt-4")

    # Timezone: store browser-detected timezone for the current user (so "Use my device" works)
    from fastapi import Request, Response
    @app.post('/api/detected-timezone')
    async def api_detected_timezone(request: Request):
        """Accept browser timezone. Body: { timezone: string, use_auto?: boolean }."""
        user_id = get_current_user()
        if user_id is None:
            return Response(status_code=401)
        try:
            body = await request.json()
            tz = (body.get('timezone') or '').strip()
            if not tz:
                return Response(status_code=400)
            from backend.user_state import UserStateManager
            um = UserStateManager()
            um.set_detected_timezone(str(user_id), tz)
            if body.get('use_auto') is True:
                um.set_timezone(str(user_id), 'auto')
            return Response(status_code=200)
        except Exception:
            return Response(status_code=500)

    # Redirect to migrations-required when DB is behind (skip API/static/NiceGUI)
    _skip_migration_redirect_paths = (
        '/api/health', '/api/version', '/api/detected-timezone',
        '/migrations-required', '/auth/callback',
    )

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import RedirectResponse

    class MigrationRedirectMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if getattr(app.state, "migration_status", None) and not app.state.migration_status.ok:
                path = request.url.path
                if path in _skip_migration_redirect_paths:
                    pass
                elif path.startswith(('/static/', '/_nicegui/', '/api/')):
                    pass
                else:
                    return RedirectResponse(url='/migrations-required', status_code=302)
            return await call_next(request)

    app.add_middleware(MigrationRedirectMiddleware)

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
    # timeout_keep_alive=30: allow time for server to send keepalives during heavy UI updates.
    # reconnect_timeout=60: keep Client alive when connection drops so browser can reconnect to same
    # session instead of server destroying client (default 3s) and forcing full page re-execution on "reconnect".
    ui.run(
        title='Task Aversion System',
        port=8080,
        host=host,
        reload=False,
        storage_secret=storage_secret,
        timeout_keep_alive=30,
        reconnect_timeout=60,
    )

