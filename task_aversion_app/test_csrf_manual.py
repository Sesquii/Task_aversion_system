#!/usr/bin/env python3
"""
Manual CSRF Testing Helper
This script helps you test CSRF protection by showing you what to look for.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_csrf_testing_guide():
    """Print a guide for manually testing CSRF protection."""
    print("\n" + "="*70)
    print("CSRF PROTECTION TESTING GUIDE")
    print("="*70)
    
    print("\n1. START THE APP:")
    print("   python app.py")
    
    print("\n2. OPEN BROWSER:")
    print("   - Go to: http://localhost:8080/login")
    print("   - Open DevTools (F12) -> Network tab")
    
    print("\n3. START OAUTH FLOW:")
    print("   - Click 'Login with Google'")
    print("   - Complete Google authentication")
    
    print("\n4. INTERCEPT THE CALLBACK URL:")
    print("   After Google redirects, you'll see a URL like:")
    print("   " + "-"*70)
    print("   http://localhost:8080/auth/callback?code=4/0A...&state=abc123-def456-ghi789...")
    print("   " + "-"*70)
    
    print("\n5. MODIFY THE STATE PARAMETER:")
    print("   In the browser address bar, find the 'state=' parameter.")
    print("   The state value is a UUID (36 characters with dashes).")
    print("   ")
    print("   Example original state:")
    print("   state=550e8400-e29b-41d4-a716-446655440000")
    print("   ")
    print("   Modify it to one of these:")
    print("   ")
    print("   Option A - Change to random value:")
    print("   state=INVALID_STATE_12345")
    print("   ")
    print("   Option B - Change one character:")
    print("   state=550e8400-e29b-41d4-a716-44665544000X")
    print("   ")
    print("   Option C - Remove entirely:")
    print("   state=")
    print("   ")
    print("   Then press Enter to load the modified URL.")
    
    print("\n6. EXPECTED RESULT:")
    print("   You should see a RED ERROR PAGE with:")
    print("   - Security icon")
    print("   - Title: 'Invalid authentication state'")
    print("   - Message: 'Your session has been cleared for security'")
    print("   - 'Go to Login' button")
    print("   ")
    print("   You should NOT see:")
    print("   - Successful login")
    print("   - Dashboard (if you try to go to /, it should redirect to /login)")
    print("   - Just a notification (error should be on full page)")
    print("   ")
    print("   IMPORTANT SECURITY CHECK:")
    print("   - Try navigating to http://localhost:8080/ (dashboard)")
    print("   - You should be REDIRECTED to /login (not see dashboard)")
    print("   - This confirms your session was cleared")
    
    print("\n7. CHECK SERVER LOGS:")
    print("   In the terminal where app.py is running, you should see:")
    print("   [Auth] CSRF: Invalid state parameter. State not found.")
    print("   OR")
    print("   [Auth] CSRF: State value mismatch.")
    
    print("\n" + "="*70)
    print("ALTERNATIVE: Test with Browser Extension")
    print("="*70)
    print("\nYou can also use a browser extension like 'Requestly' or 'ModHeader'")
    print("to intercept and modify the OAuth callback request.")
    
    print("\n" + "="*70)
    print("TROUBLESHOOTING")
    print("="*70)
    print("\nIf you don't see the error page:")
    print("  1. Make sure you're modifying the 'state' parameter, not 'code'")
    print("  2. The URL should be: /auth/callback?code=...&state=...")
    print("  3. Try changing the state to a completely different value")
    print("  4. Check server logs for CSRF messages")
    print("  5. Make sure the app is running and you're testing the callback URL")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    print_csrf_testing_guide()
