# backend/bootup_logger.py
"""
Bootup and page load logging utility for tracking server startup and browser page loading.
Logs server initialization, page registrations, and browser-side events to help debug startup issues.
"""
import os
import time
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
LOG_DIR = os.path.join(DATA_DIR, 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'bootup_page_load.log')


class BootupLogger:
    """Logger for tracking server bootup and page load events."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or LOG_FILE
        self._ensure_log_dir()
        self._setup_logger()
        self._server_start_time = time.perf_counter()
        self._bootup_stage = 'initialization'
    
    def _ensure_log_dir(self):
        """Ensure log directory exists."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def _setup_logger(self):
        """Setup Python logging handler for bootup events."""
        self.logger = logging.getLogger('bootup_logger')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()  # Prevent duplicate handlers
        
        handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        
        # Custom formatter with microseconds
        class MicrosecondFormatter(logging.Formatter):
            def formatTime(self, record, datefmt=None):
                dt = datetime.fromtimestamp(record.created)
                return dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        
        formatter = MicrosecondFormatter('%(asctime)s [%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False  # Prevent propagation to root logger
    
    def _get_elapsed_ms(self) -> float:
        """Get elapsed time since server start in milliseconds."""
        elapsed = time.perf_counter() - self._server_start_time
        return elapsed * 1000
    
    def _log(self, level: str, message: str, data: Optional[Dict[str, Any]] = None, source: str = 'server'):
        """Write a log entry with timestamp and source."""
        elapsed_ms = self._get_elapsed_ms()
        log_data = {
            'source': source,
            'stage': self._bootup_stage,
            'elapsed_ms': round(elapsed_ms, 2),
            **(data or {})
        }
        
        log_message = f"[{source.upper()}] {message}"
        if log_data:
            log_message += f" | Data: {json.dumps(log_data)}"
        
        if level == 'DEBUG':
            self.logger.debug(log_message)
        elif level == 'INFO':
            self.logger.info(log_message)
        elif level == 'WARNING':
            self.logger.warning(log_message)
        elif level == 'ERROR':
            self.logger.error(log_message)
    
    def log_server_start(self):
        """Log server startup beginning."""
        self._bootup_stage = 'server_start'
        import sys
        self._log('INFO', 'Server startup initiated', {
            'python_version': sys.version,
            'working_directory': os.getcwd()
        })
    
    def log_module_import(self, module_name: str):
        """Log module import during startup."""
        self._log('DEBUG', f'Module imported: {module_name}')
    
    def log_manager_initialization(self, manager_name: str, duration_ms: Optional[float] = None):
        """Log manager class initialization (TaskManager, EmotionManager, etc.)."""
        data = {'manager': manager_name}
        if duration_ms:
            data['duration_ms'] = duration_ms
        self._log('INFO', f'Manager initialized: {manager_name}', data)
    
    def log_page_registration(self, page_path: str):
        """Log page route registration."""
        self._bootup_stage = 'page_registration'
        self._log('INFO', f'Page registered: {page_path}')
    
    def log_static_mount(self, mount_path: str, directory: str):
        """Log static file directory mount."""
        self._log('INFO', f'Static mount: {mount_path} -> {directory}')
    
    def log_service_start(self, service_name: str):
        """Log service startup (scheduler, etc.)."""
        self._log('INFO', f'Service started: {service_name}')
    
    def log_server_ready(self, host: str, port: int):
        """Log when server is ready to accept connections."""
        self._bootup_stage = 'ready'
        elapsed_ms = self._get_elapsed_ms()
        self._log('INFO', 'Server ready to accept connections', {
            'host': host,
            'port': port,
            'total_startup_time_ms': round(elapsed_ms, 2)
        })
    
    def log_page_request(self, path: str, method: str = 'GET', client_id: Optional[str] = None):
        """Log incoming page request from browser."""
        self._log('INFO', f'Page request: {method} {path}', {
            'client_id': client_id
        }, source='server')
    
    def log_page_load_start(self, path: str, client_id: Optional[str] = None):
        """Log when page load begins (server-side)."""
        self._log('INFO', f'Page load started: {path}', {
            'client_id': client_id
        }, source='server')
    
    def log_page_render_complete(self, path: str, duration_ms: Optional[float] = None, client_id: Optional[str] = None):
        """Log when page rendering completes (server-side)."""
        data = {'client_id': client_id}
        if duration_ms:
            data['render_duration_ms'] = duration_ms
        self._log('INFO', f'Page render complete: {path}', data, source='server')
    
    def log_browser_event(self, event_type: str, event_data: Dict[str, Any]):
        """Log browser-side event (page load, refresh, timer, etc.)."""
        # This will be called from JavaScript via an endpoint
        self._log('INFO', f'Browser event: {event_type}', event_data, source='browser')
    
    def log_reload(self, path: str, reason: Optional[str] = None, client_id: Optional[str] = None):
        """Log page reload event."""
        data = {'reason': reason, 'client_id': client_id}
        self._log('WARNING', f'Page reload detected: {path}', data, source='browser')
    
    def log_error(self, message: str, exception: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None):
        """Log an error during bootup or page load."""
        error_data = context or {}
        if exception:
            error_data['exception_type'] = type(exception).__name__
            error_data['exception_message'] = str(exception)
        self._log('ERROR', message, error_data)
    
    def log_timer_creation(self, timer_id: str, interval_seconds: float, path: str):
        """Log timer creation."""
        self._log('DEBUG', f'Timer created: {timer_id}', {
            'interval_seconds': interval_seconds,
            'path': path
        }, source='server')


# Global logger instance
_bootup_logger = None


def get_bootup_logger() -> BootupLogger:
    """Get or create the global bootup logger instance."""
    global _bootup_logger
    if _bootup_logger is None:
        _bootup_logger = BootupLogger()
    return _bootup_logger
