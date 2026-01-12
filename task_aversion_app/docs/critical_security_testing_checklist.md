# Critical Security Features Testing Checklist

## Overview

This checklist covers all critical security features that need testing beyond basic XSS prevention.

## Automated Tests

Run the automated test suite:

```bash
cd task_aversion_app
python test_critical_security.py
```

This tests:

- CSRF protection implementation
- Session security features
- Data isolation implementation
- SQL injection prevention
- Authentication requirements
- Input validation coverage
- Error sanitization

## Manual Testing Checklist

### 1. CSRF Protection (OAuth)

**Test:** OAuth state parameter validation

**Steps:**

1. Start app: `python app.py`
2. Go to `/login`
3. Open browser DevTools (F12) → Network tab
4. Click "Login with Google"
5. **Intercept the OAuth callback:**
  
   **Method 1: Modify URL in address bar (Easiest)**
   - After Google redirects back, you'll see a URL in the address bar like:
     ```
     http://localhost:8080/auth/callback?code=4/0A...&state=abc123-def456-ghi789...
     ```
   - **Find the `state=` parameter** (it's a UUID, 36 characters with dashes)
   - **Modify the value after `state=`**:
     - Change to random: `state=INVALID_STATE_12345`
     - Or remove: `state=`
     - Or change one char: `state=abc123-def456-ghi78X`
   - Press Enter to load the modified URL
   
   **Method 2: Use DevTools to pause (More reliable)**
   - In DevTools → Sources tab → Enable "Pause on exceptions"
   - Or use Network tab → Right-click the `/auth/callback` request → "Edit and Resend"
   - Modify the `state` parameter in the URL
   - Send the modified request

**Expected Result:**

- ❌ OAuth callback should **reject** invalid state
- ❌ User should see a **red error page** with:
  - Title: "Invalid authentication state" or "Authentication state expired"
  - Clear error message explaining the security issue
  - Message: "Your session has been cleared for security"
  - "Go to Login" button to retry
- ❌ **No session should be created** (new login attempt failed)
- ❌ **Any existing session should be cleared** (security measure)
- ❌ **User cannot access dashboard or other protected routes** (will redirect to login)
- ✅ State parameter should be cleared after validation

**Verify:**

- Check server logs for "CSRF: Invalid state parameter" or "CSRF: State expired" message
- Error page is displayed (not just a notification)
- No user session created in storage
- Can click "Go to Login" button to retry

### 2. Data Isolation (User Data Separation)

**Test:** Users can only access their own data

**Steps:**

1. **As User A:**
  - Login with Google account A
  - Create a task: "User A Private Task"
  - Note the task ID from browser DevTools or database
2. **As User B:**
  - Logout
  - Login with Google account B (different account)
  - Go to dashboard

**Expected Result:**

- ✅ User B should **NOT** see "User A Private Task"
- ✅ User B can only see their own tasks
- ✅ User B cannot access User A's task by ID

**Verify:**

- Check database: `SELECT * FROM tasks WHERE user_id = 1` (User A)
- Check database: `SELECT * FROM tasks WHERE user_id = 2` (User B)
- Verify tasks are properly isolated

**Test SQL Query Filtering:**

```python
# In Python console
from backend.task_manager import TaskManager
tm = TaskManager()

# As User 1
tasks_user1 = tm.get_all(user_id=1)
print(f"User 1 tasks: {len(tasks_user1)}")

# As User 2
tasks_user2 = tm.get_all(user_id=2)
print(f"User 2 tasks: {len(tasks_user2)}")

# Verify no overlap
user1_ids = set(tasks_user1['task_id'].tolist())
user2_ids = set(tasks_user2['task_id'].tolist())
overlap = user1_ids & user2_ids
assert len(overlap) == 0, f"Data leak! Shared tasks: {overlap}"
```

### 3. Authentication Requirements

**Test:** Protected routes require authentication

**Steps:**

1. **Without login:**
  - Open browser in incognito/private mode
  - Go directly to: `http://localhost:8080/`
  - Go directly to: `http://localhost:8080/create_task`
  - Go directly to: `http://localhost:8080/dashboard`

**Expected Result:**

- ✅ All routes should redirect to `/login`
- ✅ No data should be accessible
- ✅ User should be prompted to login

**Verify:**

- Check browser console for redirects
- Verify no data is loaded before authentication

### 4. Session Security

**Test:** Session persistence and expiration

**Steps:**

1. **Login:**
  - Login with Google
  - Verify session token in browser storage (DevTools → Application → Local Storage)
  - Note the session token
2. **Session Persistence:**
  - Close browser tab
  - Open new tab, go to `http://localhost:8080/`
  - Verify still logged in (same session token)
3. **Session Expiration:**
  - Manually expire session in storage (modify expires_at to past date)
  - Refresh page
  - Verify redirect to `/login`
4. **Logout:**
  - Click logout
  - Verify session token removed from storage
  - Verify redirect to `/login`

**Expected Result:**

- ✅ Session persists across tabs (same browser)
- ✅ Session expires after configured time (30 days default)
- ✅ Logout clears session completely
- ✅ Expired sessions trigger re-login

**Verify:**

- Check `app.storage.general` for session data
- Check `app.storage.browser` for session token
- Verify session cleanup on expiration

### 5. SQL Injection Prevention

**Test:** SQL injection attempts are blocked

**Steps:**

1. **Test in Task Name:**
  - Try creating task with name: `'; DROP TABLE tasks; --`
  - Try creating task with name: `1' OR '1'='1`

**Expected Result:**

- ✅ Task name is sanitized (HTML escaped)
- ✅ SQL injection attempt is stored as text, not executed
- ✅ No SQL errors or table drops
- ✅ Database remains intact

**Verify:**

- Check database: Task should be created with escaped name
- Check database schema: Tables should still exist
- No SQL errors in logs

**Note:** SQLAlchemy ORM automatically prevents SQL injection, but verify behavior.

### 6. Input Validation (Length Limits)

**Test:** DoS protection via long inputs

**Steps:**

1. **Task Name:**
  - Try creating task with 201+ characters
  - Expected: Error "Task name too long (max 200 characters)"
2. **Description:**
  - Try creating task with 5001+ characters
  - Expected: Error "Description too long (max 5000 characters)"
3. **Note:**
  - Try adding note with 10001+ characters
  - Expected: Error "Note too long (max 10000 characters)"

**Expected Result:**

- ✅ All length limits enforced
- ✅ User-friendly error messages
- ✅ No server crashes or performance issues

### 7. Error Message Sanitization

**Test:** Sensitive information not exposed in errors

**Steps:**

1. **Trigger an error:**
  - Create task with invalid data
  - Or simulate database error (temporarily break connection)
2. **Check error display:**
  - Verify error ID is shown (e.g., "Error ID: a1b2c3d4")
  - Verify NO sensitive info shown:
    - ❌ No file paths
    - ❌ No database connection strings
    - ❌ No stack traces (in production)
    - ❌ No internal error messages
3. **Check error logs:**
  - Look in `data/logs/errors.jsonl`
  - Verify full details are logged server-side
  - Verify error ID matches

**Expected Result:**

- ✅ Generic error message to user
- ✅ Error ID for reporting
- ✅ Full details in server logs only
- ✅ User reporting dialog available

### 8. Output Escaping (Display Safety)

**Test:** User-generated content is escaped when displayed

**Steps:**

1. **Create task with XSS:**
  - Task name: `<script>alert('XSS')</script>`
  - Description: `<img src=x onerror=alert('XSS')>`
2. **View in dashboard:**
  - Check browser console: NO alerts
  - View page source: HTML should be escaped
  - Check DevTools Elements: Should see `&lt;script&gt;`

**Expected Result:**

- ✅ XSS payloads displayed as text
- ✅ No JavaScript execution
- ✅ HTML properly escaped

## Security Testing Summary

### ✅ Automated Tests

- HTML escaping (XSS prevention)
- Input validation (length limits)
- Error handling system
- Output escaping
- CSRF protection (implementation check)
- Session security (implementation check)
- Data isolation (implementation check)
- SQL injection prevention (implementation check)

### ⚠️ Manual Tests Required

- ✅ CSRF protection (OAuth state validation) - **COMPLETE**
- Data isolation (multi-user testing)
- Authentication requirements (route protection)
- Session security (persistence, expiration)
- SQL injection (attempt injection)
- Error sanitization (trigger errors)
- Output escaping (XSS in UI)

## Quick Test Commands

```bash
# Run all automated security tests
python test_security_features.py
python test_critical_security.py

# Verify XSS task was created
python verify_xss_task.py

# Test XSS in app context
python test_xss_in_app.py
```

## Critical Issues to Watch For

1. **Data Leakage:**
  - Users can see other users' tasks
  - Users can modify other users' data
  - **Severity:** CRITICAL
2. **Authentication Bypass:**
  - Can access protected routes without login
  - Can access data without authentication
  - **Severity:** CRITICAL
3. **CSRF Attacks:**
  - OAuth state not validated
  - Can hijack OAuth flow
  - **Severity:** HIGH
4. **Session Hijacking:**
  - Session tokens predictable
  - Sessions not expired
  - **Severity:** HIGH
5. **SQL Injection:**
  - Raw SQL with user input
  - Database compromise possible
  - **Severity:** CRITICAL
6. **Information Disclosure:**
  - Error messages expose sensitive info
  - Stack traces shown to users
  - **Severity:** MEDIUM

## Next Steps

1. ✅ Run automated tests
2. ⚠️ Perform manual testing (follow checklist above)
3. ⚠️ Test with multiple user accounts
4. ⚠️ Test OAuth flow end-to-end
5. ⚠️ Review error logs for sensitive info
6. ⚠️ Test session expiration
7. ⚠️ Verify data isolation with real users

## Resources

- `test_security_features.py` - Basic security tests (XSS, validation)
- `test_critical_security.py` - Critical security tests (CSRF, isolation, auth)
- `docs/phase2b_security_implementation.md` - Implementation details
- `docs/security_testing_guide.md` - Testing guide
- `docs/xss_attack_simulation.md` - XSS testing guide

