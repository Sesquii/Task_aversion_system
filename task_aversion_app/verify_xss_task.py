#!/usr/bin/env python3
"""
Quick script to verify XSS task was created and find it.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.task_manager import TaskManager
from backend.auth import get_current_user

def verify_xss_task():
    """Check if the XSS task was created."""
    print("="*60)
    print("VERIFYING XSS TASK CREATION")
    print("="*60)
    
    tm = TaskManager()
    
    # Try to get current user (might be None if not logged in)
    try:
        user_id = get_current_user()
        print(f"Current user_id: {user_id}")
    except:
        user_id = None
        print("No user logged in (using None for user_id)")
    
    # Get all tasks
    print("\nFetching all tasks...")
    try:
        df = tm.get_all(user_id=user_id)
        if df is None or df.empty:
            print("[INFO] No tasks found in database")
            return
        
        print(f"[OK] Found {len(df)} task(s) in database\n")
        
        # Look for XSS task
        xss_tasks = df[df['name'].str.contains('script', case=False, na=False)]
        
        if len(xss_tasks) > 0:
            print("="*60)
            print("FOUND XSS TASK(S):")
            print("="*60)
            for idx, task in xss_tasks.iterrows():
                print(f"\nTask ID: {task.get('task_id')}")
                print(f"Name: {task.get('name')}")
                print(f"Description: {task.get('description', '')[:100]}...")
                print(f"User ID: {task.get('user_id')}")
                print(f"Created: {task.get('created_at')}")
                
                # Check if name is escaped
                name = task.get('name', '')
                if '&lt;' in name or '&gt;' in name:
                    print("[OK] Task name is ESCAPED (safe)")
                elif '<script>' in name.lower():
                    print("[WARNING] Task name contains unescaped <script> tag!")
        else:
            print("="*60)
            print("XSS TASK NOT FOUND")
            print("="*60)
            print("\nThe task might not have been created, or it has a different name.")
            print("\nAll tasks in database:")
            for idx, task in df.iterrows():
                print(f"  - {task.get('name')} (ID: {task.get('task_id')})")
        
        print("\n" + "="*60)
        print("HOW TO FIND IT IN DASHBOARD:")
        print("="*60)
        print("""
1. Go to dashboard (/)
2. Scroll to "Task Templates" section
3. Look for a task with escaped HTML (e.g., &lt;script&gt;...)
4. Or use the search box and search for "script" or "alert"
5. The task name should be displayed as TEXT, not executed

If you still can't find it:
- Try refreshing the page (F5)
- Check if you're logged in (task might be user-specific)
- Check browser console for any errors
        """)
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch tasks: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_xss_task()
