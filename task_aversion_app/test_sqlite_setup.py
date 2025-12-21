#!/usr/bin/env python
"""Quick test to verify SQLite setup works."""
import os
import sys

# Set DATABASE_URL
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.task_manager import TaskManager
from backend.database import init_db

print("=" * 60)
print("Testing SQLite Setup")
print("=" * 60)

# Initialize database
print("\n1. Initializing database...")
init_db()
print("   [OK] Database initialized")

# Create TaskManager
print("\n2. Creating TaskManager...")
tm = TaskManager()
if tm.use_db:
    print("   [OK] TaskManager using database backend")
else:
    print("   [FAIL] TaskManager fell back to CSV")
    sys.exit(1)

# Test creating a task
print("\n3. Creating a test task...")
task_id = tm.create_task(
    name="Test SQLite Task",
    description="Testing database connection",
    ttype="one-time"
)
print(f"   [OK] Created task: {task_id}")

# Test retrieving the task
print("\n4. Retrieving the task...")
task = tm.get_task(task_id)
if task and task['name'] == "Test SQLite Task":
    print(f"   [OK] Retrieved: {task['name']}")
else:
    print("   [FAIL] Could not retrieve task")
    sys.exit(1)

# Clean up - delete test task
print("\n5. Cleaning up test task...")
tm.delete_by_id(task_id)
print("   [OK] Test task deleted")

print("\n" + "=" * 60)
print("All tests passed! SQLite is working correctly.")
print("=" * 60)
print("\nYou can now start the app with:")
print("  PowerShell: .\\start_with_sqlite.ps1")
print("  Or: $env:DATABASE_URL = 'sqlite:///data/task_aversion.db'; python app.py")

