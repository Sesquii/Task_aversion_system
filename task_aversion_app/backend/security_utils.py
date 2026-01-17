# backend/security_utils.py
"""
Security utilities for input sanitization, validation, and error handling.
Implements Phase 2B security features: HTML escaping, input validation, error ID system.
"""
import os
import html
import uuid
import json
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from pathlib import Path


# ============================================================================
# Input Length Limits (DoS Protection)
# ============================================================================

MAX_TASK_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_NOTE_LENGTH = 10000
MAX_EMOTION_TEXT_LENGTH = 500
MAX_SURVEY_RESPONSE_LENGTH = 2000
MAX_COMMENT_LENGTH = 2000
MAX_BLOCKER_LENGTH = 1000


# ============================================================================
# Input Sanitization (XSS Prevention)
# ============================================================================

def sanitize_html(text: Optional[str]) -> str:
    """
    Escape HTML special characters to prevent XSS attacks.
    
    Args:
        text: Input text that may contain HTML
        
    Returns:
        Escaped text safe for HTML display
    """
    if text is None:
        return ''
    if not isinstance(text, str):
        text = str(text)
    return html.escape(text, quote=True)


def sanitize_for_storage(text: Optional[str]) -> str:
    """
    Sanitize text before storing in database/CSV.
    Escapes HTML and strips excessive whitespace.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text safe for storage
    """
    if text is None:
        return ''
    if not isinstance(text, str):
        text = str(text)
    # Strip leading/trailing whitespace
    text = text.strip()
    # Escape HTML (prevents XSS if text is later displayed)
    return sanitize_html(text)


# ============================================================================
# Input Validation
# ============================================================================

class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_task_name(name: Optional[str]) -> str:
    """
    Validate and sanitize task name.
    
    Args:
        name: Task name to validate
        
    Returns:
        Validated and sanitized task name
        
    Raises:
        ValidationError: If validation fails
    """
    if not name or not name.strip():
        raise ValidationError("Task name is required")
    
    name = name.strip()
    
    if len(name) > MAX_TASK_NAME_LENGTH:
        raise ValidationError(
            f"Task name too long (max {MAX_TASK_NAME_LENGTH} characters)"
        )
    
    return sanitize_for_storage(name)


def validate_description(description: Optional[str]) -> str:
    """
    Validate and sanitize task description.
    
    Args:
        description: Description to validate
        
    Returns:
        Validated and sanitized description
    """
    if not description:
        return ''
    
    description = description.strip()
    
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(
            f"Description too long (max {MAX_DESCRIPTION_LENGTH} characters)"
        )
    
    return sanitize_for_storage(description)


def validate_note(note: Optional[str]) -> str:
    """
    Validate and sanitize note text.
    
    Args:
        note: Note text to validate
        
    Returns:
        Validated and sanitized note
    """
    if not note:
        return ''
    
    note = note.strip()
    
    if len(note) > MAX_NOTE_LENGTH:
        raise ValidationError(
            f"Note too long (max {MAX_NOTE_LENGTH} characters)"
        )
    
    return sanitize_for_storage(note)


def validate_emotion_text(text: Optional[str]) -> str:
    """
    Validate and sanitize emotion text.
    
    Args:
        text: Emotion text to validate
        
    Returns:
        Validated and sanitized emotion text
    """
    if not text:
        return ''
    
    text = text.strip()
    
    if len(text) > MAX_EMOTION_TEXT_LENGTH:
        raise ValidationError(
            f"Emotion text too long (max {MAX_EMOTION_TEXT_LENGTH} characters)"
        )
    
    return sanitize_for_storage(text)


def validate_survey_response(response: Optional[str]) -> str:
    """
    Validate and sanitize survey response text.
    
    Args:
        response: Survey response to validate
        
    Returns:
        Validated and sanitized response
    """
    if not response:
        return ''
    
    response = response.strip()
    
    if len(response) > MAX_SURVEY_RESPONSE_LENGTH:
        raise ValidationError(
            f"Survey response too long (max {MAX_SURVEY_RESPONSE_LENGTH} characters)"
        )
    
    return sanitize_for_storage(response)


def validate_comment(comment: Optional[str]) -> str:
    """
    Validate and sanitize comment text.
    
    Args:
        comment: Comment text to validate
        
    Returns:
        Validated and sanitized comment
    """
    if not comment:
        return ''
    
    comment = comment.strip()
    
    if len(comment) > MAX_COMMENT_LENGTH:
        raise ValidationError(
            f"Comment too long (max {MAX_COMMENT_LENGTH} characters)"
        )
    
    return sanitize_for_storage(comment)


def validate_blocker(blocker: Optional[str]) -> str:
    """
    Validate and sanitize blocker text.
    
    Args:
        blocker: Blocker text to validate
        
    Returns:
        Validated and sanitized blocker
    """
    if not blocker:
        return ''
    
    blocker = blocker.strip()
    
    if len(blocker) > MAX_BLOCKER_LENGTH:
        raise ValidationError(
            f"Blocker text too long (max {MAX_BLOCKER_LENGTH} characters)"
        )
    
    return sanitize_for_storage(blocker)


# ============================================================================
# Database Identifier Validation (SQL Injection Prevention)
# ============================================================================

def validate_task_id(task_id: Optional[str]) -> str:
    """
    Validate task ID format to prevent SQL injection.
    
    Task IDs should match pattern: t{timestamp} (e.g., "t1234567890")
    or be empty string for new tasks.
    
    Args:
        task_id: Task ID to validate
        
    Returns:
        Validated task ID
        
    Raises:
        ValidationError: If task_id format is invalid
    """
    if not task_id:
        return ''
    
    task_id = str(task_id).strip()
    
    # Allow empty string (for new tasks)
    if not task_id:
        return ''
    
    # Task ID format: t{timestamp} (e.g., "t1234567890")
    # Must start with 't' followed by digits only
    if not task_id.startswith('t'):
        raise ValidationError(f"Invalid task_id format: must start with 't'")
    
    # Check that after 't' there are only digits
    numeric_part = task_id[1:]
    if not numeric_part.isdigit():
        raise ValidationError(f"Invalid task_id format: must be 't' followed by digits only")
    
    # Length check (reasonable limit)
    if len(task_id) > 50:
        raise ValidationError(f"Task ID too long (max 50 characters)")
    
    return task_id


def validate_instance_id(instance_id: Optional[str]) -> str:
    """
    Validate instance ID format to prevent SQL injection.
    
    Instance IDs should match pattern: i{timestamp} (e.g., "i1234567890")
    or be empty string for new instances.
    
    Args:
        instance_id: Instance ID to validate
        
    Returns:
        Validated instance ID
        
    Raises:
        ValidationError: If instance_id format is invalid
    """
    if not instance_id:
        return ''
    
    instance_id = str(instance_id).strip()
    
    # Allow empty string (for new instances)
    if not instance_id:
        return ''
    
    # Instance ID format: i{timestamp} (e.g., "i1234567890")
    # Must start with 'i' followed by digits only
    if not instance_id.startswith('i'):
        raise ValidationError(f"Invalid instance_id format: must start with 'i'")
    
    # Check that after 'i' there are only digits
    numeric_part = instance_id[1:]
    if not numeric_part.isdigit():
        raise ValidationError(f"Invalid instance_id format: must be 'i' followed by digits only")
    
    # Length check (reasonable limit)
    if len(instance_id) > 50:
        raise ValidationError(f"Instance ID too long (max 50 characters)")
    
    return instance_id


def validate_user_id(user_id: Optional[int]) -> int:
    """
    Validate user ID to prevent SQL injection.
    
    User IDs should be positive integers.
    
    Args:
        user_id: User ID to validate
        
    Returns:
        Validated user ID
        
    Raises:
        ValidationError: If user_id is invalid
    """
    if user_id is None:
        raise ValidationError("user_id is required")
    
    if not isinstance(user_id, int):
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid user_id: must be an integer")
    
    if user_id < 1:
        raise ValidationError(f"Invalid user_id: must be a positive integer")
    
    return user_id


# ============================================================================
# Output Escaping (Display Safety)
# ============================================================================

def escape_for_display(text: Optional[str]) -> str:
    """
    Escape user-generated content for safe HTML display.
    Use this when displaying user input in UI.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for HTML display
    """
    return sanitize_html(text)


# ============================================================================
# Error Handling with Error ID System
# ============================================================================

# Error log directory
ERROR_LOG_DIR = Path(__file__).parent.parent / 'data' / 'logs'
ERROR_LOG_FILE = ERROR_LOG_DIR / 'errors.jsonl'
ERROR_REPORTS_FILE = ERROR_LOG_DIR / 'error_reports.jsonl'

# Ensure log directory exists
ERROR_LOG_DIR.mkdir(parents=True, exist_ok=True)


def handle_error(
    operation: str,
    error: Exception,
    user_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Handle error: log full details server-side, return safe error ID to user.
    
    Args:
        operation: Name of operation that failed (e.g., 'create_task', 'save_instance')
        error: Exception that occurred
        user_id: Optional user ID (if authenticated)
        context: Optional additional context (dict of key-value pairs)
        
    Returns:
        Error ID string (8 characters) for user reporting
    """
    error_id = str(uuid.uuid4())[:8]  # Short ID for user reporting
    timestamp = datetime.utcnow().isoformat()
    
    # Log full details server-side (for debugging)
    error_details = {
        'error_id': error_id,
        'timestamp': timestamp,
        'operation': operation,
        'user_id': user_id,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'context': context or {}
    }
    
    # Write to error log file (JSON Lines format)
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(error_details) + '\n')
    except Exception as log_error:
        # If logging fails, at least print to console
        print(f"[Security] Failed to write error log: {log_error}")
    
    # Also print to console for development
    print(f"[ERROR {error_id}] {operation}: {error}")
    if os.getenv('ENVIRONMENT', 'development') != 'production':
        print(traceback.format_exc())
    
    return error_id


def record_error_report(
    error_id: str,
    user_id: Optional[int] = None,
    user_context: Optional[str] = None
) -> bool:
    """
    Record user-provided error report (what they were doing when error occurred).
    
    Args:
        error_id: Error ID from handle_error()
        user_id: Optional user ID (if authenticated)
        user_context: User-provided description of what they were doing
        
    Returns:
        True if report was recorded successfully
    """
    timestamp = datetime.utcnow().isoformat()
    
    report = {
        'error_id': error_id,
        'timestamp': timestamp,
        'user_id': user_id,
        'user_context': sanitize_for_storage(user_context) if user_context else None
    }
    
    try:
        with open(ERROR_REPORTS_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(report) + '\n')
        return True
    except Exception as e:
        print(f"[Security] Failed to write error report: {e}")
        return False


def get_error_summary(error_id: str) -> Optional[Dict[str, Any]]:
    """
    Get summary of error reports for a specific error ID.
    Useful for pattern detection (same error reported by multiple users).
    
    Args:
        error_id: Error ID to look up
        
    Returns:
        Dict with error_id, report_count, first_seen, last_seen, sample_contexts
        or None if error_id not found
    """
    if not ERROR_REPORTS_FILE.exists():
        return None
    
    reports = []
    try:
        with open(ERROR_REPORTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    report = json.loads(line)
                    if report.get('error_id') == error_id:
                        reports.append(report)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[Security] Failed to read error reports: {e}")
        return None
    
    if not reports:
        return None
    
    # Sort by timestamp
    reports.sort(key=lambda x: x.get('timestamp', ''))
    
    return {
        'error_id': error_id,
        'report_count': len(reports),
        'first_seen': reports[0].get('timestamp'),
        'last_seen': reports[-1].get('timestamp'),
        'sample_contexts': [
            r.get('user_context') for r in reports[:5] if r.get('user_context')
        ]
    }
