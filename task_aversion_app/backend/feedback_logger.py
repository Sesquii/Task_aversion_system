# backend/feedback_logger.py
"""
File logging for user feedback submissions.

Logs submission success/failure and metadata (filename, length) to data/logs/
for auditing and support. Does not log feedback content (stored in data/feedback/).
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Setup logging directory (same as other app logs)
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'logs')
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

FEEDBACK_LOG_FILE = os.path.join(LOG_DIR, 'feedback.log')
FEEDBACK_EVENTS_JSONL = os.path.join(LOG_DIR, 'feedback_events.jsonl')

_logger: Optional[logging.Logger] = None


def _get_logger() -> logging.Logger:
    """Lazy-init file logger for feedback events."""
    global _logger
    if _logger is not None:
        return _logger
    _logger = logging.getLogger('feedback_logger')
    _logger.setLevel(logging.INFO)
    _logger.handlers.clear()
    try:
        handler = logging.FileHandler(FEEDBACK_LOG_FILE, mode='a', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        _logger.addHandler(handler)
        _logger.propagate = False
    except OSError:
        _logger.addHandler(logging.NullHandler())
    return _logger


def _append_jsonl(record: dict[str, Any]) -> None:
    """Append one JSON object as a line to the events JSONL file."""
    try:
        with open(FEEDBACK_EVENTS_JSONL, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except OSError:
        pass


def log_feedback_submitted(
    filename: str,
    char_count: int,
    filepath: Optional[str] = None,
) -> None:
    """Log successful feedback submission (no content; content is in data/feedback/)."""
    logger = _get_logger()
    msg = f"Feedback submitted: file={filename} chars={char_count}"
    if filepath:
        msg += f" path={filepath}"
    logger.info(msg)
    _append_jsonl({
        'event': 'feedback_submitted',
        'timestamp': datetime.now().isoformat(),
        'filename': filename,
        'char_count': char_count,
        'filepath': filepath,
    })


def log_feedback_error(
    message: str,
    context: Optional[dict[str, Any]] = None,
) -> None:
    """Log feedback submission error (e.g. write failure, exception)."""
    logger = _get_logger()
    logger.error(message)
    record: dict[str, Any] = {
        'event': 'feedback_error',
        'timestamp': datetime.now().isoformat(),
        'message': message,
    }
    if context:
        record['context'] = context
    _append_jsonl(record)
