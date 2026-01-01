#!/usr/bin/env python3
"""
Performance comparison script: CSV vs Database backend
Simulates realistic usage patterns and measures performance.
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
import random

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'task_aversion_app'))

def simulate_user_workload(im, user_id, num_instances=100):
    """Simulate a user creating, initializing, and completing instances."""
    task_ids = [f't{user_id}_{i}' for i in range(10)]  # 10 tasks per user
    instance_ids = []
    
    # Create instances
    for i in range(num_instances):
        task_id = random.choice(task_ids)
        task_name = f"Task {task_id}"
        predicted = {
            'expected_aversion': random.randint(20, 80),
            'expected_relief': random.randint(30, 90),
            'expected_mental_energy': random.randint(20, 70),
            'expected_difficulty': random.randint(10, 60),
            'time_estimate_minutes': random.randint(15, 120)
        }
        inst_id = im.create_instance(task_id, task_name, 1, predicted=predicted)
        instance_ids.append(inst_id)
    
    # Initialize some instances (80%)
    initialized_ids = random.sample(instance_ids, int(num_instances * 0.8))
    for inst_id in initialized_ids:
        im.add_prediction_to_instance(inst_id, {
            'expected_aversion': random.randint(20, 80),
            'expected_relief': random.randint(30, 90)
        })
        # Set initialized_at (only for database backend)
        if im.use_db:
            try:
                with im.db_session() as session:
                    instance = session.query(im.TaskInstance).filter(
                        im.TaskInstance.instance_id == inst_id
                    ).first()
                    if instance:
                        instance.initialized_at = datetime.now() - timedelta(days=random.randint(0, 30))
                        session.commit()
            except:
                pass
    
    # Start some instances (60% of initialized)
    started_ids = random.sample(initialized_ids, int(len(initialized_ids) * 0.6))
    for inst_id in started_ids:
        im.start_instance(inst_id)
        # Set started_at (only for database backend)
        if im.use_db:
            try:
                with im.db_session() as session:
                    instance = session.query(im.TaskInstance).filter(
                        im.TaskInstance.instance_id == inst_id
                    ).first()
                    if instance:
                        instance.started_at = datetime.now() - timedelta(hours=random.randint(1, 48))
                        session.commit()
            except:
                pass
    
    # Complete some instances (50% of started)
    completed_ids = random.sample(started_ids, int(len(started_ids) * 0.5))
    for inst_id in completed_ids:
        actual = {
            'time_actual_minutes': random.randint(10, 150),
            'actual_relief': random.randint(30, 90),
            'actual_cognitive': random.randint(20, 70),
            'actual_emotional': random.randint(10, 60),
            'actual_physical': random.randint(5, 50)
        }
        im.complete_instance(inst_id, actual)
    
    return instance_ids

def run_performance_test(backend_type, num_users=1, instances_per_user=100):
    """Run performance test with specified backend."""
    print(f"\n{'='*70}")
    print(f"Performance Test: {backend_type.upper()} Backend")
    print(f"Configuration: {num_users} user(s), {instances_per_user} instances per user")
    print(f"{'='*70}\n")
    
    # Set up backend
    if backend_type == 'database':
        os.environ['DATABASE_URL'] = f'sqlite:///test_perf_{backend_type}.db'
        os.environ.pop('DISABLE_CSV_FALLBACK', None)
    else:
        os.environ.pop('DATABASE_URL', None)
        os.environ.pop('DISABLE_CSV_FALLBACK', None)
    
    # Import after setting environment
    from backend.instance_manager import InstanceManager
    
    # Initialize
    start_time = time.time()
    im = InstanceManager()
    init_time = time.time() - start_time
    
    # Simulate workload
    all_instance_ids = []
    workload_start = time.time()
    
    for user_id in range(1, num_users + 1):
        print(f"  Simulating user {user_id}...", end=' ', flush=True)
        user_start = time.time()
        instance_ids = simulate_user_workload(im, user_id, instances_per_user)
        all_instance_ids.extend(instance_ids)
        user_time = time.time() - user_start
        print(f"({user_time:.2f}s)")
    
    workload_time = time.time() - workload_start
    
    # Test query operations
    query_start = time.time()
    
    # Test 1: Get instance
    if all_instance_ids:
        test_id = random.choice(all_instance_ids)
        im.get_instance(test_id)
    
    # Test 2: List active instances
    active = im.list_active_instances()
    
    # Test 3: List recent completed
    completed = im.list_recent_completed(limit=20)
    
    # Test 4: Get previous averages (if we have instances)
    if all_instance_ids:
        test_task_id = im.get_instance(all_instance_ids[0])['task_id']
        im.get_previous_task_averages(test_task_id)
        im.get_previous_actual_averages(test_task_id)
        im.get_baseline_aversion_robust(test_task_id)
    
    query_time = time.time() - query_start
    
    total_time = time.time() - start_time
    
    # Cleanup
    cleanup_start = time.time()
    for inst_id in all_instance_ids:
        try:
            im.delete_instance(inst_id)
        except:
            pass
    cleanup_time = time.time() - cleanup_start
    
    # Remove test database
    if backend_type == 'database':
        try:
            db_file = f'test_perf_{backend_type}.db'
            if os.path.exists(db_file):
                from sqlalchemy import create_engine
                engine = create_engine(os.environ['DATABASE_URL'])
                engine.dispose()
                time.sleep(0.1)
                if os.path.exists(db_file):
                    os.remove(db_file)
        except:
            pass
    
    return {
        'backend': backend_type,
        'num_users': num_users,
        'instances_per_user': instances_per_user,
        'total_instances': len(all_instance_ids),
        'init_time': init_time,
        'workload_time': workload_time,
        'query_time': query_time,
        'cleanup_time': cleanup_time,
        'total_time': total_time,
        'active_count': len(active),
        'completed_count': len(completed)
    }

def print_results(results_csv, results_db):
    """Print comparison results."""
    print(f"\n{'='*70}")
    print("PERFORMANCE COMPARISON RESULTS")
    print(f"{'='*70}\n")
    
    print(f"Configuration:")
    print(f"  Users: {results_csv['num_users']}")
    print(f"  Instances per user: {results_csv['instances_per_user']}")
    print(f"  Total instances: {results_csv['total_instances']}")
    print()
    
    print(f"{'Metric':<30} {'CSV':<20} {'Database':<20} {'Speedup':<15}")
    print(f"{'-'*30} {'-'*20} {'-'*20} {'-'*15}")
    
    metrics = [
        ('Initialization', 'init_time'),
        ('Workload (CRUD ops)', 'workload_time'),
        ('Query operations', 'query_time'),
        ('Cleanup', 'cleanup_time'),
        ('Total time', 'total_time')
    ]
    
    for metric_name, metric_key in metrics:
        csv_val = results_csv[metric_key]
        db_val = results_db[metric_key]
        speedup = csv_val / db_val if db_val > 0 else 0
        print(f"{metric_name:<30} {csv_val:>8.3f}s{'':<11} {db_val:>8.3f}s{'':<11} {speedup:>6.2f}x")
    
    print()
    print(f"Query Results:")
    print(f"  Active instances (CSV): {results_csv['active_count']}")
    print(f"  Active instances (DB): {results_db['active_count']}")
    print(f"  Completed instances (CSV): {results_csv['completed_count']}")
    print(f"  Completed instances (DB): {results_db['completed_count']}")
    print()
    
    # Performance assessment
    total_speedup = results_csv['total_time'] / results_db['total_time'] if results_db['total_time'] > 0 else 0
    print(f"{'='*70}")
    if total_speedup >= 2.0:
        print(f"[SUCCESS] Database backend is {total_speedup:.2f}x faster - Excellent performance!")
    elif total_speedup >= 1.5:
        print(f"[SUCCESS] Database backend is {total_speedup:.2f}x faster - Good performance improvement!")
    elif total_speedup >= 1.1:
        print(f"[INFO] Database backend is {total_speedup:.2f}x faster - Modest improvement")
    else:
        print(f"[WARNING] Database backend is {total_speedup:.2f}x faster - May need optimization")
    print(f"{'='*70}\n")

def main():
    """Run performance comparison tests."""
    print("="*70)
    print("InstanceManager Performance Comparison: CSV vs Database")
    print("="*70)
    
    # Test 1: Single user, 100 instances
    print("\n" + "="*70)
    print("TEST 1: Single User (100 instances)")
    print("="*70)
    
    results_csv_1 = run_performance_test('csv', num_users=1, instances_per_user=100)
    results_db_1 = run_performance_test('database', num_users=1, instances_per_user=100)
    print_results(results_csv_1, results_db_1)
    
    # Test 2: 5 users, 100 instances each
    print("\n" + "="*70)
    print("TEST 2: Five Users (100 instances each = 500 total)")
    print("="*70)
    
    results_csv_5 = run_performance_test('csv', num_users=5, instances_per_user=100)
    results_db_5 = run_performance_test('database', num_users=5, instances_per_user=100)
    print_results(results_csv_5, results_db_5)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nSingle User (100 instances):")
    print(f"  CSV: {results_csv_1['total_time']:.2f}s")
    print(f"  DB:  {results_db_1['total_time']:.2f}s")
    print(f"  Speedup: {results_csv_1['total_time']/results_db_1['total_time']:.2f}x")
    
    print(f"\nFive Users (500 instances):")
    print(f"  CSV: {results_csv_5['total_time']:.2f}s")
    print(f"  DB:  {results_db_5['total_time']:.2f}s")
    print(f"  Speedup: {results_csv_5['total_time']/results_db_5['total_time']:.2f}x")
    print()

if __name__ == '__main__':
    main()

