#!/usr/bin/env python3
"""
Test XSS Escaping in Actual App Context
This script tests that XSS payloads are properly escaped when displayed in the UI.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.security_utils import escape_for_display, sanitize_html
from backend.task_manager import TaskManager
from backend.auth import get_current_user


def test_xss_escaping_in_context():
    """
    Test that XSS payloads are escaped when used in actual app context.
    This simulates what happens when user input is displayed.
    """
    print("\n" + "="*60)
    print("XSS ESCAPING TEST - App Context")
    print("="*60)
    
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<div onclick='alert(1)'>Click</div>",
        "<svg><script>alert('XSS')</script></svg>",
        "<iframe src='javascript:alert(\"XSS\")'></iframe>",
    ]
    
    print("\nTesting what happens if escaping IS working:")
    print("-" * 60)
    
    for payload in xss_payloads:
        # Simulate what happens when user enters XSS payload
        escaped = escape_for_display(payload)
        
        # Check if it's safe (no unescaped HTML tags)
        is_safe = (
            "<script>" not in escaped and
            "<img" not in escaped and
            "<div" not in escaped and
            "<svg" not in escaped and
            "<iframe" not in escaped and
            "onerror" not in escaped.lower() and
            "onclick" not in escaped.lower()
        )
        
        if is_safe:
            print(f"[SAFE] '{payload[:40]}...'")
            print(f"        Escaped: '{escaped[:60]}...'")
        else:
            print(f"[UNSAFE] '{payload[:40]}...'")
            print(f"          Escaped: '{escaped[:60]}...'")
            print(f"          [WARNING] Contains unescaped HTML!")
    
    print("\n" + "="*60)
    print("WHAT HAPPENS IF ESCAPING IS NOT WORKING:")
    print("="*60)
    print("""
If escaping is NOT working, when you enter:
  <script>alert('XSS')</script>

And it's displayed in the UI without escaping, the browser will:
  1. Parse it as actual HTML/JavaScript
  2. Execute the alert('XSS') code
  3. Show an alert popup
  4. Potentially allow attacker to:
     - Steal session tokens
     - Access user data
     - Perform actions as the user
     - Redirect to malicious sites

This is a CRITICAL security vulnerability!
    """)
    
    print("\n" + "="*60)
    print("HOW TO VERIFY ESCAPING IS WORKING:")
    print("="*60)
    print("""
1. Start your app: python app.py

2. Create a task with XSS payload:
   - Go to /create_task
   - Task name: <script>alert('XSS')</script>
   - Description: <img src=x onerror=alert('XSS')>
   - Click "Create Task"

3. View the task in dashboard

4. Check browser:
   a) Open DevTools (F12)
   b) Console tab - NO alerts should appear
   c) Elements tab - Inspect task name/description
      - Should see: &lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;
      - NOT: <script>alert('XSS')</script>
   d) View page source (Ctrl+U)
      - Search for your task name
      - Should see escaped HTML, not raw HTML

5. If you see an alert popup:
   [WARNING] ESCAPING IS NOT WORKING - CRITICAL SECURITY ISSUE!
   - Check that escape_for_display() is called when displaying
   - Check that sanitize_for_storage() is called when saving
   - Review backend/security_utils.py
    """)


def test_what_happens_without_escaping():
    """Demonstrate what happens if escaping is NOT applied."""
    print("\n" + "="*60)
    print("DEMONSTRATION: What Happens WITHOUT Escaping")
    print("="*60)
    
    payload = "<script>alert('XSS Attack!')</script>"
    
    print(f"\nOriginal payload: {payload}")
    print(f"Without escaping: {payload}  ← Browser would execute this!")
    print(f"With escaping:    {escape_for_display(payload)}  ← Safe, displayed as text")
    
    print("\n" + "-"*60)
    print("If displayed WITHOUT escaping in HTML:")
    print("-"*60)
    print(f"""
    <div>{payload}</div>
    
    Browser interprets this as:
    - <script> tag starts
    - JavaScript code: alert('XSS Attack!')
    - </script> tag ends
    - Result: Alert popup appears! [CRITICAL]
    """)
    
    print("\n" + "-"*60)
    print("If displayed WITH escaping:")
    print("-"*60)
    escaped = escape_for_display(payload)
    print(f"""
    <div>{escaped}</div>
    
    Browser interprets this as:
    - Text: &lt;script&gt;alert(&#x27;XSS Attack!&#x27;)&lt;/script&gt;
    - No <script> tag (it's escaped)
    - Result: Safe, displayed as plain text [OK]
    """)


def check_actual_usage():
    """Check if escaping is actually used in key places."""
    print("\n" + "="*60)
    print("CHECKING ACTUAL USAGE IN CODEBASE")
    print("="*60)
    
    # Check if escape_for_display is imported/used
    import os
    import re
    
    ui_files = []
    for root, dirs, files in os.walk('ui'):
        for file in files:
            if file.endswith('.py'):
                ui_files.append(os.path.join(root, file))
    
    uses_escaping = []
    missing_escaping = []
    
    for file_path in ui_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for places where user data might be displayed
                # Check if escape_for_display is used
                if 'escape_for_display' in content:
                    uses_escaping.append(file_path)
                elif any(pattern in content for pattern in [
                    'task[\'name\']', 'task["name"]',
                    'task[\'description\']', 'task["description"]',
                    'instance[\'task_name\']', 'instance["task_name"]',
                    'ui.label(', 'ui.html('
                ]):
                    # Potential place where user data is displayed
                    if 'escape_for_display' not in content:
                        missing_escaping.append(file_path)
        except Exception as e:
            pass
    
    print("\nFiles that USE escaping:")
    for f in uses_escaping:
        print(f"  [OK] {f}")
    
    if missing_escaping:
        print("\n[WARNING] Files that might need escaping (manual review needed):")
        for f in missing_escaping[:5]:  # Show first 5
            print(f"  [CHECK] {f}")
        if len(missing_escaping) > 5:
            print(f"  ... and {len(missing_escaping) - 5} more")
    else:
        print("\n[OK] No obvious missing escaping found (but manual review still recommended)")


if __name__ == "__main__":
    test_xss_escaping_in_context()
    test_what_happens_without_escaping()
    check_actual_usage()
    
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    print("""
Always test XSS escaping in the actual running app:
1. Enter XSS payload in UI
2. View it in dashboard
3. Check browser DevTools
4. Verify NO JavaScript executes

If you see alerts or JavaScript executing:
  [CRITICAL] Escaping is not working!
  -> Fix immediately before deploying
    """)
