# backend/query_middleware.py
"""
FastAPI middleware for tracking database queries per request.
Integrates with query_logger to log query counts for each page load.
"""
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.query_logger import set_request_id, log_request_summary


class QueryLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to track database queries per request."""
    
    def _should_skip_request(self, request: Request) -> bool:
        """Check if this request should be skipped (WebSocket, static files, etc.)."""
        path = request.url.path
        headers = request.headers
        method = request.method
        
        # Skip WebSocket upgrade requests (critical - must be first check)
        # Check multiple headers and path patterns to catch all WebSocket requests
        upgrade_header = headers.get('upgrade', '').lower()
        connection_header = headers.get('connection', '').lower()
        sec_websocket_key = headers.get('sec-websocket-key', '')
        sec_websocket_version = headers.get('sec-websocket-version', '')
        
        if ('websocket' in upgrade_header or 
            'websocket' in connection_header or
            sec_websocket_key or
            sec_websocket_version or
            path.startswith('/_nicegui/ws') or
            '/ws' in path):
            return True
        
        # Skip static files and NiceGUI internal routes
        if (path.startswith('/static/') or 
            path.startswith('/_nicegui/') or
            path.startswith('/ws') or
            path.startswith('/api/') or
            path.endswith('.js') or
            path.endswith('.css') or
            path.endswith('.png') or
            path.endswith('.jpg') or
            path.endswith('.ico') or
            path.endswith('.svg') or
            path.endswith('.woff') or
            path.endswith('.woff2') or
            path.endswith('.ttf') or
            path.endswith('.eot')):
            return True
        
        # Skip non-GET requests (POST, PUT, DELETE, etc. - these are usually API calls)
        # BUT allow auth callback which might be GET
        if method != 'GET':
            return True
        
        # Only track actual page routes (paths that don't have file extensions)
        # This ensures we only track HTML page loads, not API or static file requests
        return False
    
    async def dispatch(self, request: Request, call_next):
        # Skip WebSocket and static file requests entirely
        if self._should_skip_request(request):
            return await call_next(request)
        
        # Generate unique request ID only for page requests
        request_id = str(uuid.uuid4())[:8]
        
        # Set request ID in context (must not fail)
        try:
            set_request_id(request_id)
        except Exception as e:
            # If setting request ID fails, just continue without logging
            print(f"[QueryMiddleware] Warning: Failed to set request ID: {e}")
            return await call_next(request)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log query summary after request completes (don't let logging break the request)
            try:
                path = request.url.path
                method = request.method
                log_request_summary(path, method)
            except Exception as log_error:
                # Logging failure should not break the request
                print(f"[QueryMiddleware] Warning: Failed to log query summary: {log_error}")
            
            return response
        except Exception as e:
            # Log even if request fails, but don't let logging break error handling
            try:
                path = request.url.path
                method = request.method
                log_request_summary(path, method)
            except Exception as log_error:
                print(f"[QueryMiddleware] Warning: Failed to log query summary on error: {log_error}")
            # Re-raise the original exception
            raise
