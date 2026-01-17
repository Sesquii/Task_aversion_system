# Error Handling Testing Guide

This guide covers both automated and manual testing for the error handling implementation.

## Automated Testing

### Running the Test Suite

The automated test suite verifies all core error handling functionality:

```bash
cd task_aversion_app
python test_error_handling.py
```

### What the Automated Tests Cover

1. **Error ID Generation** (Test 1)
   - ✅ Error IDs are 8 characters long
   - ✅ Error IDs are in valid format (hexadecimal)
   - ✅ Error IDs are unique

2. **Error Logging** (Test 2)
   - ✅ Error log file (`data/logs/errors.jsonl`) is created
   - ✅ Errors are logged with all required fields
   - ✅ Timestamps are in valid ISO format
   - ✅ All error IDs appear in log file

3. **Error Message Sanitization** (Test 3)
   - ✅ Sensitive data is only logged server-side (not exposed to users)
   - ✅ Error messages don't leak sensitive information

4. **Error Report Recording** (Test 4)
   - ✅ Error reports can be recorded
   - ✅ Error reports file (`data/logs/error_reports.jsonl`) is created
   - ✅ User context is correctly stored
   - ✅ Report structure is correct

5. **Error Summary Function** (Test 5)
   - ✅ `get_error_summary()` retrieves error summaries
   - ✅ Report counts are accurate
   - ✅ Returns None for non-existent errors

6. **Context Handling** (Test 6)
   - ✅ Context data is correctly logged with errors
   - ✅ Context structure is preserved

### Test Results

The test suite should show:
- **35 tests passed**
- **0 tests failed**
- **100% success rate**

Test entries are appended to existing log files (they are not cleared).

---

## Manual Testing Guide

While automated tests verify the backend functionality, manual testing verifies the UI components and user experience.

### Prerequisites

1. Start the application:
   ```bash
   cd task_aversion_app
   python app.py
   ```

2. Log in to the application

3. Have the browser developer console open (F12) to see any console errors

### Test Scenarios

#### 1. Test Error ID Display

**Goal**: Verify error IDs are shown to users

**Steps**:
1. Trigger an error (see "How to Trigger Errors" below)
2. Check that an error notification appears
3. Verify the error notification shows an error ID (8 characters)
4. Verify the error message is user-friendly (not a stack trace)

**Expected Result**:
- Error notification shows: "An error occurred. Error ID: [8-char-id]. Please try again or contact support with this ID."
- No sensitive information is exposed
- No stack traces are shown to the user

---

#### 2. Test Error Report Dialog

**Goal**: Verify users can report errors with context

**Steps**:
1. Trigger an error
2. Wait for error notification
3. Check if "Report Issue" button appears (or dialog opens automatically)
4. Click "Report Issue" or interact with the dialog
5. Enter a description of what you were doing (e.g., "Creating a new task")
6. Submit the report

**Expected Result**:
- Error report dialog appears
- User can enter context about what they were doing
- Report submission shows success message
- Report is saved to `data/logs/error_reports.jsonl`

**Verify in Log File**:
```bash
# Check error_reports.jsonl
cat data/logs/error_reports.jsonl | tail -1 | python -m json.tool
```

Should show:
- `error_id`: The error ID from the notification
- `user_id`: Your user ID
- `user_context`: The description you entered
- `timestamp`: When the report was submitted

---

#### 3. Test Error Logging

**Goal**: Verify errors are logged server-side with full details

**Steps**:
1. Trigger an error
2. Note the error ID from the notification
3. Check the error log file

**Verify in Log File**:
```bash
# Check errors.jsonl for the error ID
grep "error_id" data/logs/errors.jsonl | tail -1 | python -m json.tool
```

**Expected Result**:
Log entry contains:
- `error_id`: Matches the ID shown to user
- `timestamp`: ISO format timestamp
- `operation`: Name of operation that failed
- `user_id`: Your user ID
- `error_type`: Type of exception (e.g., "ValueError")
- `error_message`: Full error message
- `traceback`: Full stack trace (for debugging)
- `context`: Any additional context provided

**Important**: Full error details (including stack traces) should be in the log file, but NOT shown to users.

---

#### 4. Test Different Error Types

**Goal**: Verify different types of errors are handled correctly

**Test Cases**:

**A. Validation Errors** (should show user-friendly message):
- Try creating a task with empty name
- Try creating a task with name > 200 characters
- Try entering invalid data in forms

**Expected**: Validation errors should show directly (not use error ID system)

**B. System Errors** (should use error ID system):
- Database connection errors
- File I/O errors
- Unexpected exceptions

**Expected**: System errors should show error ID and generic message

---

#### 5. Test Error Handling in Different Pages

**Goal**: Verify error handling works across all pages

**Pages to Test** (from `error_handling_implementation.md`):

**Core Task Management**:
- [ ] Dashboard - Pause task, update pause info, save metrics config, add note
- [ ] Complete Task - Complete task operation
- [ ] Initialize Task - Save initialization
- [ ] Create Task - Create task
- [ ] Cancel Task - Cancel task

**Notes and Data**:
- [ ] Notes Page - Save note, delete note

**Analytics**:
- [ ] Analytics Page - Data loading
- [ ] Analytics Glossary - Chart rendering
- [ ] Coursera Analysis - Data loading
- [ ] Productivity Grit Tradeoff - Analysis data loading
- [ ] Factors Comparison - Chart rendering
- [ ] Relief Comparison - Data loading
- [ ] Task Distribution - Database retrieval
- [ ] Summary Page - Data loading

**Settings**:
- [ ] Settings Page - Import/export
- [ ] Productivity Settings - Save settings, load config
- [ ] Composite Score Weights - Save weights
- [ ] Cancellation Penalties - Save penalty
- [ ] Productivity Goals - Save goals

**Other**:
- [ ] Login - Logout operation
- [ ] Survey Page - Load questions
- [ ] Tutorial - Load steps, mark completed
- [ ] Gap Handling - Get gap summary, set preferences

**For Each Page**:
1. Navigate to the page
2. Trigger an error (see "How to Trigger Errors" below)
3. Verify error notification appears with error ID
4. Verify error is logged to `errors.jsonl`
5. Optionally test error report dialog

---

### How to Trigger Errors for Testing

#### Method 1: Invalid Input (Validation Errors)
- Create task with empty name
- Enter text > max length in forms
- Enter invalid data types

#### Method 2: Database Errors (System Errors)
- Temporarily rename `data/task_aversion.db` to cause database errors
- Or modify database permissions to cause access errors

#### Method 3: File I/O Errors (System Errors)
- Temporarily remove read permissions from data files
- Or rename required files to cause file not found errors

#### Method 4: Network Errors (if applicable)
- Disconnect from network
- Or block network access in firewall

#### Method 5: Code Injection (for testing)
Add temporary code to trigger errors:
```python
# In any UI page, add:
raise ValueError("Test error for error handling verification")
```

**Note**: Remove test code after testing!

---

### Verification Checklist

After manual testing, verify:

- [ ] Error IDs are 8 characters and shown to users
- [ ] Error notifications are user-friendly (no stack traces)
- [ ] Error report dialog works and saves reports
- [ ] Errors are logged to `data/logs/errors.jsonl`
- [ ] Error reports are logged to `data/logs/error_reports.jsonl`
- [ ] Full error details are in log files (for debugging)
- [ ] No sensitive information is exposed to users
- [ ] Error handling works on all major pages
- [ ] Validation errors show directly (not via error ID system)
- [ ] System errors use error ID system

---

## Troubleshooting

### Error log file not created
- Check that `data/logs/` directory exists
- Check file permissions
- Verify `ERROR_LOG_DIR` path in `backend/security_utils.py`

### Error report dialog doesn't appear
- Check browser console for JavaScript errors
- Verify `show_report=True` in `handle_error_with_ui()` call
- Check that NiceGUI dialog system is working

### Error IDs not unique
- This should not happen (UUID-based)
- If it does, check `handle_error()` function in `security_utils.py`

### Errors not logged
- Check file permissions on `data/logs/` directory
- Check disk space
- Verify error logging code path is executed

---

## Summary

**Automated Testing**: Run `python test_error_handling.py` - verifies backend functionality

**Manual Testing**: Test UI components and user experience across all pages

**Both are important**: Automated tests verify correctness, manual tests verify user experience.
