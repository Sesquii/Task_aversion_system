#!/usr/bin/env python
"""Quick performance check: Read operations only (no writes to avoid conflicts)."""
import os
import sys
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("Quick Performance Check: Database vs CSV (Read Operations)")
print("=" * 70)

# Test Database reads
print("\n1. Testing DATABASE read performance...")
os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

from backend.task_manager import TaskManager
tm_db = TaskManager()

if not tm_db.use_db:
    print("   [ERROR] Not using database!")
    sys.exit(1)

# Time listing all tasks
start = time.time()
tasks_list = tm_db.list_tasks()
list_time = time.time() - start

# Time getting all tasks
start = time.time()
all_tasks = tm_db.get_all()
get_all_time = time.time() - start

# Time getting individual tasks (sample of 5)
start = time.time()
sample_ids = all_tasks['task_id'].head(5).tolist() if not all_tasks.empty else []
for task_id in sample_ids:
    task = tm_db.get_task(task_id)
get_individual_time = time.time() - start

db_total = list_time + get_all_time + get_individual_time

print(f"   List tasks:        {list_time:.4f}s ({len(tasks_list)} tasks)")
print(f"   Get all tasks:     {get_all_time:.4f}s")
print(f"   Get 5 individual:  {get_individual_time:.4f}s")
print(f"   Total:             {db_total:.4f}s")

# Test CSV reads
print("\n2. Testing CSV read performance...")
if 'DATABASE_URL' in os.environ:
    del os.environ['DATABASE_URL']

tm_csv = TaskManager()

if tm_csv.use_db:
    print("   [ERROR] Still using database!")
    sys.exit(1)

# Time listing all tasks
start = time.time()
tasks_list = tm_csv.list_tasks()
list_time = time.time() - start

# Time getting all tasks
start = time.time()
all_tasks = tm_csv.get_all()
get_all_time = time.time() - start

# Time getting individual tasks (sample of 5)
start = time.time()
sample_ids = all_tasks['task_id'].head(5).tolist() if not all_tasks.empty else []
for task_id in sample_ids:
    task = tm_csv.get_task(task_id)
get_individual_time = time.time() - start

csv_total = list_time + get_all_time + get_individual_time

print(f"   List tasks:        {list_time:.4f}s ({len(tasks_list)} tasks)")
print(f"   Get all tasks:     {get_all_time:.4f}s")
print(f"   Get 5 individual:  {get_individual_time:.4f}s")
print(f"   Total:             {csv_total:.4f}s")

# Comparison
print("\n" + "=" * 70)
print("Performance Comparison")
print("=" * 70)

if csv_total > 0:
    speedup = csv_total / db_total if db_total > 0 else 0
    if speedup > 1:
        print(f"\nDatabase is {speedup:.2f}x FASTER for read operations")
    elif speedup < 1:
        print(f"\nDatabase is {1/speedup:.2f}x SLOWER for read operations")
    else:
        print(f"\nPerformance is similar")
    
    time_saved = csv_total - db_total
    if time_saved > 0:
        print(f"Time saved: {time_saved:.4f}s per operation")
    else:
        print(f"Time difference: {abs(time_saved):.4f}s")

print("\nNote: This test only measures read operations.")
print("Database performance advantage increases with:")
print("  - Larger datasets")
print("  - More complex queries")
print("  - Concurrent operations")
print("  - No file locking issues (CSV can be locked by Excel/OneDrive)")

print("\n" + "=" * 70)

