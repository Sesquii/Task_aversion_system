# Security Features Testing Guide

## Overview

This guide explains how to test and verify that Phase 2B security features work correctly, especially critical features like HTML escaping/XSS prevention.

## Quick Test

Run the automated test script:

```bash
cd task_aversion_app
python test_security_features.py
```

This will test:
- HTML escaping (XSS prevention)
- Input validation (length limits)
- XSS sanitization in validation
- Error handling system
- Output escaping
- Sanitize for storage

## Manual Testing

### 1. HTML Escaping / XSS Prevention

**Test in the UI:**

1. **Create a task with XSS payload:**
   - Go to `/create_task`
   - Try entering: `<script>alert('XSS')</script>` as task name
   - Try entering: `<img src=x onerror=alert('XSS')>` as description
   - Save the task

2. **Verify:**
   - Task should be created (validation should pass)
   - When viewing the task in dashboard, the script tags should be **escaped** (displayed as text, not executed)
   - Check browser console - no JavaScript should execute
   - View page source - HTML should be escaped (e.g., `&lt;script&gt;`)

3. **Test XSS payloads:**
   ```
   <script>alert('XSS')</script>
   <img src=x onerror=alert('XSS')>
   javascript:alert('XSS')
   <div onclick='alert(1)'>Click</div>
   <svg><script>alert('XSS')</script></svg>
   ```

**Expected Result:** All payloads should be escaped and displayed as text, not executed.

### 2. Input Validation (Length Limits)

**Test in the UI:**

1. **Task name length:**
   - Go to `/create_task`
   - Enter a task name with 201+ characters
   - Try to save
   - **Expected:** Error message: "Task name too long (max 200 characters)"

2. **Description length:**
   - Enter a description with 5001+ characters
   - Try to save
   - **Expected:** Error message: "Description too long (max 5000 characters)"

3. **Note length:**
   - Try to add a note with 10001+ characters
   - **Expected:** Error message: "Note too long (max 10000 characters)"

**Test with Python:**
```python
from backend.security_utils import validate_task_name, ValidationError

# Should pass
try:
    result = validate_task_name("a" * 200)
    print("PASS: Max length accepted")
except ValidationError as e:
    print(f"FAIL: {e}")

# Should fail
try:
    result = validate_task_name("a" * 201)
    print("FAIL: Should have rejected")
except ValidationError as e:
    print(f"PASS: Correctly rejected - {e}")
```

### 3. Error Handling System

**Test in the UI:**

1. **Trigger an error:**
   - Create a task with invalid data (e.g., very long name)
   - Or simulate a database error

2. **Verify:**
   - Error notification shows with error ID (e.g., "Error ID: a1b2c3d4")
   - Error report dialog appears (optional)
   - User can submit error report with context

3. **Check error logs:**
   - Look in `data/logs/errors.jsonl`
   - Should contain full error details with error ID
   - Check `data/logs/error_reports.jsonl` for user reports

**Test with Python:**
```python
from backend.security_utils import handle_error, record_error_report

# Generate error ID
error_id = handle_error("test_operation", ValueError("Test error"), user_id=1)
print(f"Error ID: {error_id}")

# Record user report
success = record_error_report(error_id, user_id=1, user_context="User was testing")
print(f"Report recorded: {success}")
```

### 4. Output Escaping

**Test in the UI:**

1. **Create task with special characters:**
   - Task name: `Task with <script> tags`
   - Description: `Description with "quotes" and 'apostrophes'`

2. **View task in dashboard:**
   - Check that `<script>` is displayed as text (not executed)
   - Check that quotes are properly escaped
   - View page source to verify HTML escaping

**Test with Python:**
```python
from backend.security_utils import escape_for_display

# Test escaping
result = escape_for_display("<script>alert('XSS')</script>")
print(result)  # Should be: &lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;

# Verify no script tags
assert "<script>" not in result
assert "onerror" not in result.lower()
```

## Browser Testing

### Chrome DevTools Testing

1. **Open DevTools (F12)**
2. **Console tab:**
   - Enter XSS payload in form
   - Check console for any JavaScript errors or alerts
   - **Expected:** No alerts should appear

3. **Elements tab:**
   - Inspect the task name/description in dashboard
   - Check HTML - should be escaped
   - Example: `<div>Task: &lt;script&gt;alert('XSS')&lt;/script&gt;</div>`

4. **Network tab:**
   - Create task with XSS payload
   - Check request payload - should contain escaped HTML
   - Check response - should contain escaped HTML

### Firefox Testing

Same as Chrome, but also check:
- **View Page Source** (Ctrl+U)
- Verify HTML is escaped in source

## Automated Testing

### Run Test Script

```bash
cd task_aversion_app
python test_security_features.py
```

### Expected Output

```
============================================================
SECURITY FEATURES TEST SUITE
============================================================

============================================================
TEST 1: HTML Escaping (XSS Prevention)
============================================================
[PASS] Script tag: '<script>alert('XSS')</script>' -> '&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;'
[PASS] Image with onerror: '<img src=x onerror=alert('XSS')>' -> '&lt;img src=x onerror=alert(&#x27;XSS&#x27;)&gt;'
...

============================================================
TEST SUMMARY
============================================================
[PASS] HTML Escaping
[PASS] Input Validation
[PASS] XSS in Validation
[PASS] Error Handling
[PASS] Output Escaping
[PASS] Sanitize for Storage

Total: 6/6 tests passed

[SUCCESS] All security tests passed!
```

## Integration Testing

### Test Full Flow

1. **Create task with XSS:**
   ```python
   # In Python console or test script
   from backend.task_manager import TaskManager
   from backend.security_utils import ValidationError
   
   tm = TaskManager()
   try:
       # This should work (XSS is sanitized)
       task_id = tm.create_task(
           "<script>alert('XSS')</script>",
           description="<img src=x onerror=alert('XSS')>",
           user_id=1
       )
       print(f"Task created: {task_id}")
   except ValidationError as e:
       print(f"Validation error: {e}")
   ```

2. **Retrieve and verify:**
   ```python
   task = tm.get_task(task_id, user_id=1)
   print(f"Name: {task['name']}")
   # Should be escaped: &lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;
   ```

3. **Display in UI:**
   - View task in dashboard
   - Verify XSS is escaped (not executed)

## Common Issues

### Issue: XSS Still Executes

**Symptoms:** JavaScript alerts appear when viewing task with XSS payload

**Solution:**
1. Check that `escape_for_display()` is called when displaying user content
2. Verify `sanitize_for_storage()` is called before saving
3. Check that NiceGUI isn't auto-escaping (should still use explicit escaping)

### Issue: Validation Not Working

**Symptoms:** Very long inputs are accepted

**Solution:**
1. Check that validation functions are called in manager methods
2. Verify `ValidationError` is raised for invalid inputs
3. Check UI error handling catches `ValidationError`

### Issue: Error ID Not Showing

**Symptoms:** Generic error messages without error ID

**Solution:**
1. Check that `handle_error_with_ui()` is called in exception handlers
2. Verify error log directory exists: `data/logs/`
3. Check file permissions (should be writable)

## Verification Checklist

- [ ] HTML escaping prevents XSS (test with `<script>` tags)
- [ ] Input validation enforces length limits
- [ ] Error handling shows error IDs
- [ ] Error reports can be submitted
- [ ] Output escaping works when displaying user content
- [ ] All test cases in `test_security_features.py` pass
- [ ] Manual UI testing confirms security features work
- [ ] Browser DevTools shows no JavaScript execution from XSS payloads

## Next Steps

1. **Run automated tests:** `python test_security_features.py`
2. **Manual UI testing:** Follow manual testing steps above
3. **Browser testing:** Use DevTools to verify escaping
4. **Integration testing:** Test full create/view flow with XSS payloads
5. **Review error logs:** Check `data/logs/errors.jsonl` for proper logging

## Additional Resources

- See `docs/phase2b_security_implementation.md` for implementation details
- See `backend/security_utils.py` for security utility functions
- See `ui/error_reporting.py` for error UI components
