#!/usr/bin/env python
"""
Performance test: Compare CSV vs Database performance.
This helps verify the app works without CSV and shows speed improvements.
"""
import os
import sys
import time
import pandas as pd

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_csv_performance():
    """Test CSV read/write performance."""
    print("Testing CSV Performance...")
    
    # Remove DATABASE_URL to force CSV mode
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    
    from backend.task_manager import TaskManager
    
    tm = TaskManager()
    if tm.use_db:
        print("  [WARNING] Still using database! CSV test invalid.")
        return None
    
    # Test creating multiple tasks
    start_time = time.time()
    task_ids = []
    for i in range(10):
        task_id = tm.create_task(
            name=f"CSV Test Task {i}",
            description=f"Test task {i} for performance",
            ttype="one-time"
        )
        task_ids.append(task_id)
    create_time = time.time() - start_time
    
    # Test reading tasks
    start_time = time.time()
    for task_id in task_ids:
        task = tm.get_task(task_id)
    read_time = time.time() - start_time
    
    # Test listing tasks
    start_time = time.time()
    tasks = tm.list_tasks()
    list_time = time.time() - start_time
    
    # Cleanup
    for task_id in task_ids:
        tm.delete_by_id(task_id)
    
    return {
        'create_time': create_time,
        'read_time': read_time,
        'list_time': list_time,
        'total_time': create_time + read_time + list_time
    }

def test_database_performance():
    """Test Database read/write performance."""
    print("Testing Database Performance...")
    
    # Set DATABASE_URL to use SQLite
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion_perf_test.db'
    
    from backend.task_manager import TaskManager
    from backend.database import init_db
    
    # Initialize fresh database
    init_db()
    
    tm = TaskManager()
    if not tm.use_db:
        print("  [WARNING] Not using database! Database test invalid.")
        return None
    
    # Test creating multiple tasks
    start_time = time.time()
    task_ids = []
    for i in range(10):
        task_id = tm.create_task(
            name=f"DB Test Task {i}",
            description=f"Test task {i} for performance",
            ttype="one-time"
        )
        task_ids.append(task_id)
    create_time = time.time() - start_time
    
    # Test reading tasks
    start_time = time.time()
    for task_id in task_ids:
        task = tm.get_task(task_id)
    read_time = time.time() - start_time
    
    # Test listing tasks
    start_time = time.time()
    tasks = tm.list_tasks()
    list_time = time.time() - start_time
    
    # Cleanup
    for task_id in task_ids:
        tm.delete_by_id(task_id)
    
    # Clean up test database
    db_file = 'data/task_aversion_perf_test.db'
    if os.path.exists(db_file):
        os.remove(db_file)
    
    return {
        'create_time': create_time,
        'read_time': read_time,
        'list_time': list_time,
        'total_time': create_time + read_time + list_time
    }

def main():
    print("=" * 60)
    print("Performance Test: CSV vs Database")
    print("=" * 60)
    print("\nThis test creates 10 tasks, reads them, and lists them.")
    print("Comparing CSV file operations vs SQLite database operations.\n")
    
    # Test CSV
    csv_results = test_csv_performance()
    
    print("\n" + "-" * 60 + "\n")
    
    # Test Database
    db_results = test_database_performance()
    
    # Compare results
    print("\n" + "=" * 60)
    print("Performance Comparison")
    print("=" * 60)
    
    if csv_results and db_results:
        print(f"\nCSV Results:")
        print(f"  Create 10 tasks: {csv_results['create_time']:.4f}s")
        print(f"  Read 10 tasks:    {csv_results['read_time']:.4f}s")
        print(f"  List tasks:       {csv_results['list_time']:.4f}s")
        print(f"  Total time:       {csv_results['total_time']:.4f}s")
        
        print(f"\nDatabase Results:")
        print(f"  Create 10 tasks: {db_results['create_time']:.4f}s")
        print(f"  Read 10 tasks:    {db_results['read_time']:.4f}s")
        print(f"  List tasks:       {db_results['list_time']:.4f}s")
        print(f"  Total time:       {db_results['total_time']:.4f}s")
        
        print(f"\nSpeed Improvement:")
        speedup = csv_results['total_time'] / db_results['total_time']
        if speedup > 1:
            print(f"  Database is {speedup:.2f}x FASTER")
        else:
            print(f"  Database is {1/speedup:.2f}x SLOWER")
        
        print(f"\nTime Saved: {csv_results['total_time'] - db_results['total_time']:.4f}s")
    else:
        print("\n[ERROR] Could not complete performance test")
        if not csv_results:
            print("  CSV test failed")
        if not db_results:
            print("  Database test failed")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\nNote: Database performance improves more with larger datasets.")
    print("For small datasets, the difference may be minimal.")

if __name__ == "__main__":
    main()

