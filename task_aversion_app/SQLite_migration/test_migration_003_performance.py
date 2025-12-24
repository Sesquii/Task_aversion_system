#!/usr/bin/env python
"""
Performance Test Script for Migration 003 (TaskInstance Table)

This script compares CSV vs Database performance for task instance queries.
It tests common operations like:
- Loading all instances
- Filtering by task_id
- Filtering by status
- Filtering by date range
- Counting completed instances

Run with: python SQLite_migration/test_migration_003_performance.py
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from backend.database import get_session, TaskInstance, engine
from backend.instance_manager import InstanceManager

def format_time(seconds):
    """Format time in readable format."""
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f} μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.3f} s"

def test_csv_load_all():
    """Test loading all instances from CSV."""
    print("  Testing CSV: Load all instances...")
    start = time.time()
    
    im = InstanceManager()
    # Force reload to get fresh data
    im._reload()
    df = im.df
    
    elapsed = time.time() - start
    print(f"    Loaded {len(df)} instances in {format_time(elapsed)}")
    return df, elapsed

def test_db_load_all():
    """Test loading all instances from database."""
    print("  Testing Database: Load all instances...")
    start = time.time()
    
    try:
        with get_session() as session:
            instances = session.query(TaskInstance).all()
            # Convert to list of dicts for fair comparison
            results = [inst.to_dict() for inst in instances]
        
        elapsed = time.time() - start
        print(f"    Loaded {len(results)} instances in {format_time(elapsed)}")
        return results, elapsed
    except Exception as e:
        print(f"    [ERROR] Database query failed: {e}")
        return [], 0

def test_csv_filter_by_task(csv_df, task_id):
    """Test filtering CSV by task_id."""
    print(f"  Testing CSV: Filter by task_id='{task_id}'...")
    start = time.time()
    
    filtered = csv_df[csv_df['task_id'] == task_id]
    
    elapsed = time.time() - start
    print(f"    Found {len(filtered)} instances in {format_time(elapsed)}")
    return elapsed

def test_db_filter_by_task(task_id):
    """Test filtering database by task_id."""
    print(f"  Testing Database: Filter by task_id='{task_id}'...")
    start = time.time()
    
    with get_session() as session:
        instances = session.query(TaskInstance).filter(
            TaskInstance.task_id == task_id
        ).all()
        count = len(instances)
    
    elapsed = time.time() - start
    print(f"    Found {count} instances in {format_time(elapsed)}")
    return elapsed

def test_csv_filter_by_status(csv_df, status):
    """Test filtering CSV by status."""
    print(f"  Testing CSV: Filter by status='{status}'...")
    start = time.time()
    
    filtered = csv_df[csv_df['status'] == status]
    
    elapsed = time.time() - start
    print(f"    Found {len(filtered)} instances in {format_time(elapsed)}")
    return elapsed

def test_db_filter_by_status(status):
    """Test filtering database by status."""
    print(f"  Testing Database: Filter by status='{status}'...")
    start = time.time()
    
    with get_session() as session:
        instances = session.query(TaskInstance).filter(
            TaskInstance.status == status
        ).all()
        count = len(instances)
    
    elapsed = time.time() - start
    print(f"    Found {count} instances in {format_time(elapsed)}")
    return elapsed

def test_csv_count_completed(csv_df):
    """Test counting completed instances in CSV."""
    print("  Testing CSV: Count completed instances...")
    start = time.time()
    
    completed = csv_df[csv_df['is_completed'] == 'True']
    count = len(completed)
    
    elapsed = time.time() - start
    print(f"    Found {count} completed instances in {format_time(elapsed)}")
    return elapsed

def test_db_count_completed():
    """Test counting completed instances in database."""
    print("  Testing Database: Count completed instances...")
    start = time.time()
    
    with get_session() as session:
        count = session.query(TaskInstance).filter(
            TaskInstance.is_completed == True
        ).count()
    
    elapsed = time.time() - start
    print(f"    Found {count} completed instances in {format_time(elapsed)}")
    return elapsed

def test_csv_date_range(csv_df, days_back=30):
    """Test filtering CSV by date range."""
    print(f"  Testing CSV: Filter by date range (last {days_back} days)...")
    start = time.time()
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    csv_df['created_at_parsed'] = pd.to_datetime(csv_df['created_at'], errors='coerce')
    filtered = csv_df[csv_df['created_at_parsed'] >= cutoff_date]
    
    elapsed = time.time() - start
    print(f"    Found {len(filtered)} instances in {format_time(elapsed)}")
    return elapsed

def test_db_date_range(days_back=30):
    """Test filtering database by date range."""
    print(f"  Testing Database: Filter by date range (last {days_back} days)...")
    start = time.time()
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    with get_session() as session:
        instances = session.query(TaskInstance).filter(
            TaskInstance.created_at >= cutoff_date
        ).all()
        count = len(instances)
    
    elapsed = time.time() - start
    print(f"    Found {count} instances in {format_time(elapsed)}")
    return elapsed

def main():
    print("=" * 70)
    print("Migration 003 Performance Test: CSV vs Database")
    print("=" * 70)
    print()
    
    # Check DATABASE_URL
    database_url = os.getenv('DATABASE_URL', '')
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set!")
        print("Please set it before running this test.")
        print("Example: export DATABASE_URL='sqlite:///data/task_aversion.db'")
        return
    
    print(f"Database: {database_url}")
    print()
    
    # Check if we have data
    try:
        im = InstanceManager()
        im._reload()
        csv_row_count = len(im.df)
    except Exception as e:
        print(f"[ERROR] Failed to load CSV data: {e}")
        csv_row_count = 0
    
    try:
        with get_session() as session:
            db_row_count = session.query(TaskInstance).count()
    except Exception as e:
        print(f"[ERROR] Failed to query database: {e}")
        db_row_count = 0
    
    print(f"Data counts:")
    print(f"  CSV: {csv_row_count} instances")
    print(f"  Database: {db_row_count} instances")
    print()
    
    if csv_row_count == 0 and db_row_count == 0:
        print("[NOTE] No data found. The performance test requires existing data.")
        print("You may want to:")
        print("  1. Run the app to create some task instances")
        print("  2. Or run migrate_csv_to_database.py to migrate existing CSV data")
        return
    
    results = {}
    
    # Test 1: Load all instances
    print("Test 1: Load All Instances")
    print("-" * 70)
    csv_df, csv_time = test_csv_load_all()
    db_results, db_time = test_db_load_all()
    results['load_all'] = {'csv': csv_time, 'db': db_time}
    
    if db_time > 0:
        speedup = csv_time / db_time
        print(f"  Speedup: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
    print()
    
    # Test 2: Filter by task_id (if we have data)
    if csv_row_count > 0:
        # Get a sample task_id
        sample_task_id = csv_df.iloc[0]['task_id'] if len(csv_df) > 0 else None
        if sample_task_id:
            print("Test 2: Filter by task_id")
            print("-" * 70)
            csv_time = test_csv_filter_by_task(csv_df, sample_task_id)
            db_time = test_db_filter_by_task(sample_task_id)
            results['filter_task'] = {'csv': csv_time, 'db': db_time}
            
            if db_time > 0:
                speedup = csv_time / db_time
                print(f"  Speedup: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
            print()
    
    # Test 3: Filter by status
    if csv_row_count > 0:
        print("Test 3: Filter by status='completed'")
        print("-" * 70)
        csv_time = test_csv_filter_by_status(csv_df, 'completed')
        db_time = test_db_filter_by_status('completed')
        results['filter_status'] = {'csv': csv_time, 'db': db_time}
        
        if db_time > 0:
            speedup = csv_time / db_time
            print(f"  Speedup: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
        print()
    
    # Test 4: Count completed
    print("Test 4: Count Completed Instances")
    print("-" * 70)
    csv_time = test_csv_count_completed(csv_df)
    db_time = test_db_count_completed()
    results['count_completed'] = {'csv': csv_time, 'db': db_time}
    
    if db_time > 0:
        speedup = csv_time / db_time
        print(f"  Speedup: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
    print()
    
    # Test 5: Date range filter
    if csv_row_count > 0:
        print("Test 5: Filter by Date Range")
        print("-" * 70)
        csv_time = test_csv_date_range(csv_df, days_back=30)
        db_time = test_db_date_range(days_back=30)
        results['filter_date'] = {'csv': csv_time, 'db': db_time}
        
        if db_time > 0:
            speedup = csv_time / db_time
            print(f"  Speedup: {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
        print()
    
    # Summary
    print("=" * 70)
    print("Performance Summary")
    print("=" * 70)
    print()
    print(f"{'Test':<25} {'CSV Time':<15} {'DB Time':<15} {'Speedup':<15}")
    print("-" * 70)
    
    for test_name, times in results.items():
        csv_time = times['csv']
        db_time = times['db']
        if db_time > 0:
            speedup = csv_time / db_time
            speedup_str = f"{speedup:.2f}x {'faster' if speedup > 1 else 'slower'}"
        else:
            speedup_str = "N/A"
        
        print(f"{test_name:<25} {format_time(csv_time):<15} {format_time(db_time):<15} {speedup_str:<15}")
    
    print()
    print("=" * 70)
    print("Notes:")
    print("- CSV times include file I/O and pandas DataFrame operations")
    print("- Database times include SQL query execution and ORM overhead")
    print("- Speedup > 1.0 means database is faster")
    print("- For small datasets, CSV may be faster due to overhead")
    print("- Database advantages become more apparent with:")
    print("  * Larger datasets (>1000 rows)")
    print("  * Complex queries (joins, aggregations)")
    print("  * Concurrent access")
    print("=" * 70)

if __name__ == "__main__":
    main()

