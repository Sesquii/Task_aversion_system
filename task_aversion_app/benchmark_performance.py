#!/usr/bin/env python3
"""
Performance Benchmarking Script

Measures load times for dashboard and analytics pages to track performance improvements.
Run this before and after optimizations to measure impact.

Usage:
    python benchmark_performance.py
    python benchmark_performance.py --output results.json
    python benchmark_performance.py --warmup 3 --iterations 5
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Tuple
import traceback
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set to use CSV mode for benchmark script (data isolation not required)
os.environ['USE_CSV'] = 'true'
os.environ.pop('DATABASE_URL', None)

from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager
from backend.analytics import Analytics


class PerformanceBenchmark:
    """Benchmark dashboard and analytics page load times."""
    
    def __init__(self, warmup_runs: int = 1, iterations: int = 3):
        """
        Initialize benchmark.
        
        Args:
            warmup_runs: Number of warmup runs to perform (to warm caches, etc.)
            iterations: Number of measurement iterations to average
        """
        self.warmup_runs = warmup_runs
        self.iterations = iterations
        self.results: Dict[str, Any] = {
            'timestamp': datetime.now().isoformat(),
            'warmup_runs': warmup_runs,
            'iterations': iterations,
            'dashboard': {},
            'analytics': {},
            'individual_operations': {},
            'summary': {}
        }
        
        # Initialize managers
        print("[Benchmark] Initializing managers...")
        self.tm = TaskManager()
        self.im = InstanceManager()
        self.analytics = Analytics()
        print("[Benchmark] Managers initialized")
    
    def measure_time(self, func, *args, **kwargs) -> Tuple[float, Any]:
        """
        Measure execution time of a function.
        
        Returns:
            (duration_ms, result)
        """
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = (time.perf_counter() - start) * 1000  # Convert to milliseconds
            return duration, result
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            print(f"[ERROR] {func.__name__} failed: {e}")
            traceback.print_exc()
            return duration, None
    
    def benchmark_operation(self, name: str, func, *args, **kwargs) -> List[float]:
        """
        Benchmark an operation multiple times and return list of durations.
        
        Args:
            name: Operation name for logging
            func: Function to benchmark
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            List of durations in milliseconds
        """
        durations = []
        
        # Warmup runs
        print(f"[Benchmark] Warming up: {name} ({self.warmup_runs} runs)")
        for i in range(self.warmup_runs):
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"[WARNING] Warmup {i+1} failed for {name}: {e}")
        
        # Measurement runs
        print(f"[Benchmark] Measuring: {name} ({self.iterations} iterations)")
        for i in range(self.iterations):
            duration, result = self.measure_time(func, *args, **kwargs)
            if result is not None:
                durations.append(duration)
                print(f"  Run {i+1}: {duration:.2f}ms")
            else:
                print(f"  Run {i+1}: FAILED")
        
        return durations
    
    def benchmark_dashboard_operations(self):
        """Benchmark key dashboard operations."""
        print("\n" + "="*60)
        print("BENCHMARKING DASHBOARD OPERATIONS")
        print("="*60)
        
        dashboard_ops = {
            'list_tasks': lambda: self.tm.list_tasks(user_id=None),  # Benchmark script: intentionally use user_id=None
            'list_active_instances': lambda: self.im.list_active_instances(user_id=None),  # CSV mode allows None
            'get_relief_summary': lambda: self.analytics.get_relief_summary(),
            'get_dashboard_metrics': lambda: self.analytics.get_dashboard_metrics(),
        }
        
        for op_name, op_func in dashboard_ops.items():
            durations = self.benchmark_operation(op_name, op_func)
            if durations:
                avg = sum(durations) / len(durations)
                min_dur = min(durations)
                max_dur = max(durations)
                
                self.results['individual_operations'][op_name] = {
                    'durations_ms': durations,
                    'avg_ms': avg,
                    'min_ms': min_dur,
                    'max_ms': max_dur,
                    'count': len(durations)
                }
                print(f"[RESULT] {op_name}: avg={avg:.2f}ms, min={min_dur:.2f}ms, max={max_dur:.2f}ms")
    
    def benchmark_analytics_operations(self):
        """Benchmark key analytics operations."""
        print("\n" + "="*60)
        print("BENCHMARKING ANALYTICS OPERATIONS")
        print("="*60)
        
        # Benchmark script: intentionally use user_id=None to load all instances across all users
        analytics_ops = {
            'load_instances_all': lambda: self.analytics._load_instances(completed_only=False, user_id=None),
            'load_instances_completed': lambda: self.analytics._load_instances(completed_only=True, user_id=None),
            'get_all_scores_for_composite': lambda: self.analytics.get_all_scores_for_composite(days=7),
            'calculate_time_tracking_consistency': lambda: self.analytics.calculate_time_tracking_consistency_score(days=7),
        }
        
        for op_name, op_func in analytics_ops.items():
            durations = self.benchmark_operation(op_name, op_func)
            if durations:
                avg = sum(durations) / len(durations)
                min_dur = min(durations)
                max_dur = max(durations)
                
                self.results['individual_operations'][op_name] = {
                    'durations_ms': durations,
                    'avg_ms': avg,
                    'min_ms': min_dur,
                    'max_ms': max_dur,
                    'count': len(durations)
                }
                print(f"[RESULT] {op_name}: avg={avg:.2f}ms, min={min_dur:.2f}ms, max={max_dur:.2f}ms")
    
    def simulate_dashboard_load(self):
        """Simulate a full dashboard page load."""
        print("\n" + "="*60)
        print("SIMULATING DASHBOARD PAGE LOAD")
        print("="*60)
        
        def simulate_load():
            """Simulate what happens when dashboard loads."""
            # These are the key operations that happen on dashboard load
            self.tm.list_tasks(user_id=None)  # Benchmark script: intentionally use user_id=None
            self.im.list_active_instances(user_id=None)  # CSV mode allows None
            self.analytics.get_relief_summary()
            self.analytics.get_dashboard_metrics()
        
        durations = self.benchmark_operation('dashboard_page_load', simulate_load)
        
        if durations:
            avg = sum(durations) / len(durations)
            min_dur = min(durations)
            max_dur = max(durations)
            
            self.results['dashboard'] = {
                'durations_ms': durations,
                'avg_ms': avg,
                'min_ms': min_dur,
                'max_ms': max_dur,
                'count': len(durations)
            }
            print(f"\n[RESULT] Dashboard page load: avg={avg:.2f}ms, min={min_dur:.2f}ms, max={max_dur:.2f}ms")
    
    def simulate_analytics_load(self):
        """Simulate a full analytics page load."""
        print("\n" + "="*60)
        print("SIMULATING ANALYTICS PAGE LOAD")
        print("="*60)
        
        def simulate_load():
            """Simulate what happens when analytics page loads."""
            # These are the key operations that happen on analytics page load
            self.analytics.get_dashboard_metrics()
            self.analytics.get_relief_summary()
            self.analytics.get_all_scores_for_composite(days=7)
            self.analytics.calculate_time_tracking_consistency_score(days=7)
            # Note: calculate_composite_score is called with results from get_all_scores_for_composite
            # but we'll measure that separately
        
        durations = self.benchmark_operation('analytics_page_load', simulate_load)
        
        if durations:
            avg = sum(durations) / len(durations)
            min_dur = min(durations)
            max_dur = max(durations)
            
            self.results['analytics'] = {
                'durations_ms': durations,
                'avg_ms': avg,
                'min_ms': min_dur,
                'max_ms': max_dur,
                'count': len(durations)
            }
            print(f"\n[RESULT] Analytics page load: avg={avg:.2f}ms, min={min_dur:.2f}ms, max={max_dur:.2f}ms")
    
    def get_data_stats(self):
        """Get statistics about the dataset size."""
        print("\n" + "="*60)
        print("COLLECTING DATA STATISTICS")
        print("="*60)
        
        try:
            # Benchmark script: intentionally use user_id=None to analyze data across all users
            tasks = self.tm.list_tasks(user_id=None)
            active_instances = self.im.list_active_instances(user_id=None)
            
            # Load instances DataFrame to get comprehensive stats
            try:
                # Benchmark script: intentionally use user_id=None to load all instances across all users
                df = self.analytics._load_instances(completed_only=False, user_id=None)
                total_instances = len(df)
                completed_instances = len(df[df.get('is_completed', pd.Series([False]*len(df))) == True]) if 'is_completed' in df.columns else 0
                active_count = len(df[df.get('status', pd.Series(['']*len(df))) == 'active']) if 'status' in df.columns else len(active_instances)
                
                stats = {
                    'total_tasks': len(tasks),
                    'total_instances': total_instances,
                    'completed_instances': completed_instances,
                    'active_instances': active_count,
                    'instances_dataframe_rows': total_instances,
                    'instances_dataframe_columns': len(df.columns) if not df.empty else 0
                }
            except Exception as e:
                print(f"[WARNING] Could not load instances DataFrame: {e}")
                # Fallback: use active instances count
                stats = {
                    'total_tasks': len(tasks),
                    'total_instances': len(active_instances),  # Approximate
                    'completed_instances': None,
                    'active_instances': len(active_instances),
                    'instances_dataframe_rows': None,
                    'instances_dataframe_columns': None
                }
            
            self.results['data_stats'] = stats
            
            print(f"[STATS] Total tasks: {stats['total_tasks']}")
            print(f"[STATS] Total instances: {stats['total_instances']}")
            if stats['completed_instances'] is not None:
                print(f"[STATS] Completed instances: {stats['completed_instances']}")
            print(f"[STATS] Active instances: {stats['active_instances']}")
            if stats['instances_dataframe_rows'] is not None:
                print(f"[STATS] DataFrame rows: {stats['instances_dataframe_rows']}")
                print(f"[STATS] DataFrame columns: {stats['instances_dataframe_columns']}")
        
        except Exception as e:
            print(f"[ERROR] Failed to collect data stats: {e}")
            traceback.print_exc()
            self.results['data_stats'] = {'error': str(e)}
    
    def generate_summary(self):
        """Generate a summary of results."""
        print("\n" + "="*60)
        print("PERFORMANCE SUMMARY")
        print("="*60)
        
        summary = {}
        
        # Dashboard summary
        if 'dashboard' in self.results and self.results['dashboard']:
            dashboard = self.results['dashboard']
            summary['dashboard_avg_ms'] = dashboard.get('avg_ms', 0)
            summary['dashboard_min_ms'] = dashboard.get('min_ms', 0)
            summary['dashboard_max_ms'] = dashboard.get('max_ms', 0)
        
        # Analytics summary
        if 'analytics' in self.results and self.results['analytics']:
            analytics = self.results['analytics']
            summary['analytics_avg_ms'] = analytics.get('avg_ms', 0)
            summary['analytics_min_ms'] = analytics.get('min_ms', 0)
            summary['analytics_max_ms'] = analytics.get('max_ms', 0)
        
        # Find slowest operations
        if 'individual_operations' in self.results:
            ops = self.results['individual_operations']
            if ops:
                sorted_ops = sorted(ops.items(), key=lambda x: x[1].get('avg_ms', 0), reverse=True)
                summary['slowest_operations'] = [
                    {'name': name, 'avg_ms': data.get('avg_ms', 0)}
                    for name, data in sorted_ops[:5]  # Top 5 slowest
                ]
        
        self.results['summary'] = summary
        
        # Print summary
        print(f"\nDashboard Page Load:")
        if 'dashboard_avg_ms' in summary:
            print(f"  Average: {summary['dashboard_avg_ms']:.2f}ms")
            print(f"  Range: {summary['dashboard_min_ms']:.2f}ms - {summary['dashboard_max_ms']:.2f}ms")
        
        print(f"\nAnalytics Page Load:")
        if 'analytics_avg_ms' in summary:
            print(f"  Average: {summary['analytics_avg_ms']:.2f}ms")
            print(f"  Range: {summary['analytics_min_ms']:.2f}ms - {summary['analytics_max_ms']:.2f}ms")
        
        if 'slowest_operations' in summary:
            print(f"\nSlowest Operations:")
            for op in summary['slowest_operations']:
                print(f"  {op['name']}: {op['avg_ms']:.2f}ms")
    
    def run_all(self):
        """Run all benchmarks."""
        print("\n" + "="*60)
        print("PERFORMANCE BENCHMARK")
        print("="*60)
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Warmup runs: {self.warmup_runs}")
        print(f"Measurement iterations: {self.iterations}")
        
        # Collect data stats first
        self.get_data_stats()
        
        # Benchmark individual operations
        self.benchmark_dashboard_operations()
        self.benchmark_analytics_operations()
        
        # Simulate full page loads
        self.simulate_dashboard_load()
        self.simulate_analytics_load()
        
        # Generate summary
        self.generate_summary()
        
        return self.results
    
    def save_results(self, output_file: str = None):
        """Save results to file."""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"benchmark_results_{timestamp}.json"
        
        output_path = os.path.join(os.path.dirname(__file__), output_file)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2)
            print(f"\n[SUCCESS] Results saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"\n[ERROR] Failed to save results: {e}")
            return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Benchmark dashboard and analytics page performance')
    parser.add_argument('--warmup', type=int, default=1, help='Number of warmup runs (default: 1)')
    parser.add_argument('--iterations', type=int, default=3, help='Number of measurement iterations (default: 3)')
    parser.add_argument('--output', type=str, default=None, help='Output file path (default: benchmark_results_TIMESTAMP.json)')
    
    args = parser.parse_args()
    
    # Run benchmark
    benchmark = PerformanceBenchmark(warmup_runs=args.warmup, iterations=args.iterations)
    results = benchmark.run_all()
    
    # Save results
    output_path = benchmark.save_results(args.output)
    
    print("\n" + "="*60)
    print("BENCHMARK COMPLETE")
    print("="*60)
    if output_path:
        print(f"Results saved to: {output_path}")
    print("\nRun this script again after optimizations to compare results.")


if __name__ == '__main__':
    main()
