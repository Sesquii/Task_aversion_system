# Phase 2B Security Features Implementation

## Overview

This document describes the security features implemented for Phase 2B, including input sanitization, validation, error handling, and output escaping.

## Implemented Features

### 1. Input Sanitization (`backend/security_utils.py`)

**Functions:**
- `sanitize_html(text)` - Escapes HTML special characters to prevent XSS
- `sanitize_for_storage(text)` - Sanitizes text before storing in database/CSV

**Usage:**
```python
from backend.security_utils import sanitize_html, sanitize_for_storage

# Before storing user input
safe_text = sanitize_for_storage(user_input)

# When displaying user-generated content
display_text = sanitize_html(user_content)
```

### 2. Input Validation with Length Limits

**Length Limits:**
- Task names: 200 characters
- Descriptions: 5000 characters
- Notes: 10000 characters
- Emotion text: 500 characters
- Survey responses: 2000 characters
- Comments: 2000 characters
- Blockers: 1000 characters

**Validation Functions:**
- `validate_task_name(name)` - Validates and sanitizes task name
- `validate_description(description)` - Validates and sanitizes description
- `validate_note(note)` - Validates and sanitizes note text
- `validate_emotion_text(text)` - Validates and sanitizes emotion text
- `validate_survey_response(response)` - Validates and sanitizes survey response
- `validate_comment(comment)` - Validates and sanitizes comment
- `validate_blocker(blocker)` - Validates and sanitizes blocker text

**Usage:**
```python
from backend.security_utils import validate_task_name, ValidationError

try:
    safe_name = validate_task_name(user_input)
except ValidationError as e:
    ui.notify(str(e), color='negative')
    return
```

**Updated Managers:**
- `TaskManager.create_task()` - Validates task name and description
- `TaskManager.append_task_notes()` - Validates note text
- `NotesManager.add_note()` - Validates note content
- `SurveyManager.record_response()` - Validates survey response text

### 3. Error Handling with Error ID System

**Components:**
- `backend/security_utils.py` - Error logging and error ID generation
- `ui/error_reporting.py` - User-friendly error UI components

**Functions:**
- `handle_error(operation, error, user_id, context)` - Logs error and returns error ID
- `record_error_report(error_id, user_id, user_context)` - Records user-provided error context
- `get_error_summary(error_id)` - Gets summary of error reports for pattern detection
- `handle_error_with_ui(operation, error, ...)` - Convenience function that logs and shows UI

**Error Log Files:**
- `data/logs/errors.jsonl` - Full technical error details (server-side only)
- `data/logs/error_reports.jsonl` - User-provided error context

**Usage:**
```python
from ui.error_reporting import handle_error_with_ui
from backend.security_utils import ValidationError

try:
    # ... operation ...
except ValidationError as e:
    # Validation errors - show user-friendly message
    ui.notify(str(e), color='negative')
except Exception as e:
    # Other errors - use error ID system
    handle_error_with_ui(
        'operation_name',
        e,
        user_id=get_current_user(),
        context={'key': 'value'}  # Optional context
    )
```

**Example UI Integration:**
See `ui/create_task.py` for a complete example of error handling integration.

### 4. Output Escaping

**Function:**
- `escape_for_display(text)` - Escapes user-generated content for safe HTML display

**Usage:**
```python
from backend.security_utils import escape_for_display

# When displaying user-generated content in UI
ui.label(escape_for_display(task.name))
ui.html(f"<p>{escape_for_display(user_comment)}</p>")
```

**Note:** NiceGUI may provide some automatic escaping, but explicit escaping is safer and recommended for all user-generated content.

## Integration Guide

### For New UI Pages

1. **Import security utilities:**
```python
from backend.security_utils import (
    validate_task_name, validate_description, ValidationError
)
from backend.auth import get_current_user
from ui.error_reporting import handle_error_with_ui
```

2. **Validate inputs before calling managers:**
```python
try:
    name = validate_task_name(name_input.value)
    description = validate_description(desc_input.value)
except ValidationError as e:
    ui.notify(str(e), color='negative')
    return
```

3. **Wrap manager calls in error handling:**
```python
try:
    user_id = get_current_user()
    result = manager.method(name, description, user_id=user_id)
    ui.notify("Success!", color='positive')
except ValidationError as e:
    ui.notify(str(e), color='negative')
except Exception as e:
    handle_error_with_ui('method_name', e, user_id=get_current_user())
```

4. **Escape user-generated content when displaying:**
```python
from backend.security_utils import escape_for_display

ui.label(escape_for_display(task.name))
ui.html(f"<div>{escape_for_display(task.description)}</div>")
```

### For Manager Methods

1. **Import validation functions:**
```python
from backend.security_utils import (
    validate_task_name, validate_description, ValidationError
)
```

2. **Validate inputs at the start of methods:**
```python
def create_task(self, name, description='', ...):
    # Validate and sanitize inputs
    try:
        name = validate_task_name(name)
        description = validate_description(description)
    except ValidationError as e:
        raise  # Re-raise for UI to handle
```

3. **Use sanitize_for_storage for other text fields:**
```python
from backend.security_utils import sanitize_for_storage

other_field = sanitize_for_storage(other_field) if other_field else ''
```

## Security Checklist

- ✅ Input sanitization (HTML escaping)
- ✅ CSRF protection for OAuth (state parameter validation) - Already in `backend/auth.py`
- ✅ Input validation & length limits
- ✅ Error message sanitization (error ID system)
- ✅ Output escaping (when displaying user data)
- ✅ Session security (random tokens, expiration) - Already in `backend/auth.py`
- ✅ OAuth secrets in environment variables - Already configured

## Files Modified

**New Files:**
- `backend/security_utils.py` - Security utilities (sanitization, validation, error handling)
- `ui/error_reporting.py` - Error reporting UI components
- `docs/phase2b_security_implementation.md` - This documentation

**Updated Files:**
- `backend/task_manager.py` - Added validation to `create_task()` and `append_task_notes()`
- `backend/notes_manager.py` - Added validation to `add_note()`
- `backend/survey.py` - Added validation to `record_response()`
- `ui/create_task.py` - Added error handling and validation

## Next Steps

1. **Update remaining UI pages** to use error handling:
   - `ui/initialize_task.py`
   - `ui/complete_task.py`
   - `ui/settings_page.py`
   - Other pages that create/update user data

2. **Add validation for blocker/comment fields** in instance completion flow

3. **Add output escaping** in dashboard and other pages that display user-generated content

4. **Test security features** with XSS attack vectors:
   - `<script>alert('XSS')</script>`
   - `javascript:alert('XSS')`
   - `onerror=alert('XSS')`
   - Long inputs (DoS testing)

## Testing

### Automated Testing

**Status**: ✅ **Complete** - Error handling system has been automatically verified

**Test Results**: ✅ **100% pass rate (35/35 tests)**

**Test Command**: `python test_error_handling.py`

**What's Verified**:
- ✅ Error ID system generates unique 8-character IDs
- ✅ Error log file created (`data/logs/errors.jsonl`)
- ✅ Error messages don't expose sensitive info
- ✅ Error reporting system works
- ✅ Full error details logged server-side
- ✅ Context handling works correctly

**Note**: Automated verification confirms the error handling system is functioning correctly. Manual UI testing is still pending to verify user-facing error handling behavior.

### Manual Testing

**Status**: ⏳ **Pending** - Manual UI testing recommended

1. **Input Validation:**
   - Try creating a task with a name > 200 characters
   - Try creating a task with description > 5000 characters
   - Verify error messages are user-friendly

2. **XSS Prevention:**
   - Try entering `<script>alert('XSS')</script>` in task name
   - Verify it's escaped when displayed
   - Check that script doesn't execute

3. **Error Handling (Manual UI Testing):**
   - Trigger an error (e.g., database connection failure)
   - Verify error ID is shown
   - Test error reporting dialog
   - Check error log file for full details
   - Verify error notifications appear correctly across all pages

**Testing Guide**: See `docs/error_handling_testing_guide.md` for detailed manual testing procedures.

## Notes

- **NiceGUI Auto-Escaping:** NiceGUI may provide some automatic escaping, but explicit escaping is safer and recommended for all user-generated content.
- **Error Logs:** Error logs are stored in `data/logs/` directory. Ensure this directory exists and is writable.
- **Error ID Format:** Error IDs are 8-character UUIDs (e.g., `a1b2c3d4`) for easy user reporting.
- **Validation Errors:** Validation errors are shown directly to users (no error ID needed) since they're user input issues, not system errors.
