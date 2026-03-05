# backend/database_diagnostics.py
"""
Database diagnostics for future incident investigation.

Logs DB identity (server version, read-only status) and connection errors so you can
correlate "data missing" or stale reads with restarts, replicas, or connection issues.

Enable with env: ENABLE_DATABASE_DIAGNOSTICS=1 (default: 1 in production-style setups).
Log file: task_aversion_app/logs/database_diagnostics.log
"""
import logging
import os
from typing import Any, Optional

from sqlalchemy import text

# Log directory (same as query_logger uses for query_log.txt)
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
DIAG_LOG_FILE = os.path.join(LOG_DIR, 'database_diagnostics.log')

_logger: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    """Lazy-init logger for database diagnostics."""
    global _logger
    if _logger is not None:
        return _logger
    os.makedirs(LOG_DIR, exist_ok=True)
    _logger = logging.getLogger('database_diagnostics')
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        handler = logging.FileHandler(DIAG_LOG_FILE, encoding='utf-8')
        handler.setFormatter(
            logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        )
        _logger.addHandler(handler)
        _logger.propagate = False
    return _logger


def is_enabled() -> bool:
    """Whether database diagnostics logging is enabled (env: ENABLE_DATABASE_DIAGNOSTICS)."""
    return os.getenv('ENABLE_DATABASE_DIAGNOSTICS', '1').lower() in ('1', 'true', 'yes')


def log_connection_identity(engine: Any, database_url: str) -> None:
    """
    Log current DB identity (server version, in_recovery for PG) for later comparison.
    Call once at startup; if you ever see "data missing" you can check if identity changed.
    """
    if not is_enabled():
        return
    log = _get_logger()
    # Redact URL for logging (host only, no password)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        safe_url = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or ''}/{parsed.path or ''}"
    except Exception:
        safe_url = "(url parse failed)"
    log.info("DB identity check started url=%s", safe_url)
    try:
        with engine.connect() as conn:
            if database_url.startswith('postgresql'):
                row = conn.execute(
                    text(
                        "SELECT current_setting('server_version') AS version, "
                        "pg_is_in_recovery() AS in_recovery"
                    )
                ).fetchone()
                version = row[0] if row else "unknown"
                in_recovery = row[1] if row and len(row) > 1 else None
                log.info(
                    "DB identity postgres version=%s in_recovery=%s",
                    version,
                    in_recovery,
                )
            else:
                # SQLite: no server version, just confirm connect
                conn.execute(text("SELECT 1"))
                log.info("DB identity sqlite connected ok")
    except Exception as e:
        log.warning("DB identity check failed: %s", e, exc_info=True)


def log_connection_error(operation: str, error: Exception) -> None:
    """
    Log a database connection/operation error (e.g. OperationalError).
    Helps distinguish restarts, proxy drops, or network blips.
    """
    if not is_enabled():
        return
    log = _get_logger()
    log.warning(
        "DB connection error operation=%s error_type=%s message=%s",
        operation,
        type(error).__name__,
        str(error),
    )


def log_cache_invalidation(source: str, detail: Optional[str] = None) -> None:
    """
    Log when instance/task caches are invalidated so you can correlate
    "data back" with invalidation (e.g. after deploy or manual refresh).
    """
    if not is_enabled():
        return
    log = _get_logger()
    msg = f"cache_invalidation source={source}"
    if detail:
        msg += f" detail={detail}"
    log.info(msg)
