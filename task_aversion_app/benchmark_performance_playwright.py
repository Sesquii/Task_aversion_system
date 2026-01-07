#!/usr/bin/env python3
"""
End-to-End Performance Benchmarking with Playwright

Measures actual user experience by testing the web application through a browser.
This complements benchmark_performance.py which measures backend operations.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    python benchmark_performance_playwright.py
    python benchmark_performance_playwright.py --url http://localhost:8080
    python benchmark_performance_playwright.py --iterations 5
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback

try:
    from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
except ImportError:
    print("[ERROR] Playwright not installed. Install with:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)


class PlaywrightPerformanceBenchmark:
    """Benchmark web application performance using Playwright."""
    
    def __init__(self, base_url: str = "http://localhost:8080", iterations: int = 3):
        """
        Initialize benchmark.
        
        Args:
            base_url: Base URL of the running application
            iterations: Number of measurement iterations to average
        """
        self.base_url = base_url.rstrip('/')
        self.iterations = iterations
        self.results: Dict[str, Any] = {
            'timestamp': datetime.now().isoformat(),
            'base_url': base_url,
            'iterations': iterations,
            'dashboard': {},
            'analytics': {},
            'navigation': {},
            'summary': {}
        }
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
    
    def setup_browser(self):
        """Set up Playwright browser."""
        print("[Benchmark] Setting up browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        print("[Benchmark] Browser ready")
    
    def teardown_browser(self):
        """Close browser."""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def measure_page_load(self, page: Page, url: str, wait_selector: Optional[str] = None) -> Dict[str, float]:
        """
        Measure page load performance metrics.
        
        Args:
            page: Playwright page object
            url: URL to load
            wait_selector: Optional CSS selector to wait for (e.g., specific element that indicates page is ready)
            
        Returns:
            Dictionary with performance metrics in milliseconds
        """
        metrics = {}
        
        # Navigate and measure
        start_time = time.perf_counter()
        
        # Use Playwright's built-in performance timing
        response = page.goto(url, wait_until='networkidle', timeout=60000)
        
        # Wait for specific selector if provided (e.g., main content loaded)
        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=30000)
            except Exception as e:
                print(f"[WARNING] Could not wait for selector {wait_selector}: {e}")
        
        load_time = (time.perf_counter() - start_time) * 1000
        
        # Get navigation timing from browser
        try:
            timing = page.evaluate("""
                () => {
                    const perf = performance.timing;
                    const nav = performance.getEntriesByType('navigation')[0];
                    return {
                        dns: nav.domainLookupEnd - nav.domainLookupStart,
                        connect: nav.connectEnd - nav.connectStart,
                        ttfb: nav.responseStart - nav.requestStart,
                        download: nav.responseEnd - nav.responseStart,
                        domContentLoaded: nav.domContentLoadedEventEnd - nav.domContentLoadedEventStart,
                        load: nav.loadEventEnd - nav.loadEventStart,
                        total: nav.loadEventEnd - nav.fetchStart
                    };
                }
            """)
            metrics.update(timing)
        except Exception as e:
            print(f"[WARNING] Could not get browser timing: {e}")
            metrics['total'] = load_time
        
        # Get resource timing
        try:
            resources = page.evaluate("""
                () => {
                    const entries = performance.getEntriesByType('resource');
                    return {
                        total_resources: entries.length,
                        total_size: entries.reduce((sum, e) => sum + (e.transferSize || 0), 0),
                        js_resources: entries.filter(e => e.name.endsWith('.js')).length,
                        css_resources: entries.filter(e => e.name.endsWith('.css')).length
                    };
                }
            """)
            metrics.update(resources)
        except Exception as e:
            print(f"[WARNING] Could not get resource timing: {e}")
        
        metrics['manual_load_time'] = load_time
        
        return metrics
    
    def benchmark_dashboard(self):
        """Benchmark dashboard page load."""
        print("\n" + "="*60)
        print("BENCHMARKING DASHBOARD PAGE (E2E)")
        print("="*60)
        
        all_metrics = []
        
        for i in range(self.iterations):
            print(f"\n[Run {i+1}/{self.iterations}]")
            page = self.context.new_page()
            
            try:
                # Measure dashboard load
                metrics = self.measure_page_load(
                    page, 
                    f"{self.base_url}/",
                    wait_selector="[data-testid='dashboard']"  # Adjust based on your actual dashboard structure
                )
                
                all_metrics.append(metrics)
                print(f"  Total load: {metrics.get('total', metrics.get('manual_load_time', 0)):.2f}ms")
                print(f"  TTFB: {metrics.get('ttfb', 0):.2f}ms")
                print(f"  DOMContentLoaded: {metrics.get('domContentLoaded', 0):.2f}ms")
                
                # Wait a bit before next iteration
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Dashboard benchmark failed: {e}")
                traceback.print_exc()
            finally:
                page.close()
        
        if all_metrics:
            # Calculate averages
            avg_metrics = {}
            for key in all_metrics[0].keys():
                values = [m.get(key, 0) for m in all_metrics if key in m]
                if values:
                    avg_metrics[f'avg_{key}'] = sum(values) / len(values)
                    avg_metrics[f'min_{key}'] = min(values)
                    avg_metrics[f'max_{key}'] = max(values)
            
            self.results['dashboard'] = {
                'all_runs': all_metrics,
                **avg_metrics
            }
            
            print(f"\n[RESULT] Dashboard E2E Load:")
            print(f"  Average total: {avg_metrics.get('avg_total', avg_metrics.get('avg_manual_load_time', 0)):.2f}ms")
            print(f"  Average TTFB: {avg_metrics.get('avg_ttfb', 0):.2f}ms")
    
    def benchmark_analytics(self):
        """Benchmark analytics page load."""
        print("\n" + "="*60)
        print("BENCHMARKING ANALYTICS PAGE (E2E)")
        print("="*60)
        
        all_metrics = []
        
        for i in range(self.iterations):
            print(f"\n[Run {i+1}/{self.iterations}]")
            page = self.context.new_page()
            
            try:
                # Measure analytics page load
                metrics = self.measure_page_load(
                    page,
                    f"{self.base_url}/analytics",
                    wait_selector="text=Analytics Studio"  # Adjust based on your actual analytics page structure
                )
                
                all_metrics.append(metrics)
                print(f"  Total load: {metrics.get('total', metrics.get('manual_load_time', 0)):.2f}ms")
                print(f"  TTFB: {metrics.get('ttfb', 0):.2f}ms")
                print(f"  DOMContentLoaded: {metrics.get('domContentLoaded', 0):.2f}ms")
                
                # Wait a bit before next iteration
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Analytics benchmark failed: {e}")
                traceback.print_exc()
            finally:
                page.close()
        
        if all_metrics:
            # Calculate averages
            avg_metrics = {}
            for key in all_metrics[0].keys():
                values = [m.get(key, 0) for m in all_metrics if key in m]
                if values:
                    avg_metrics[f'avg_{key}'] = sum(values) / len(values)
                    avg_metrics[f'min_{key}'] = min(values)
                    avg_metrics[f'max_{key}'] = max(values)
            
            self.results['analytics'] = {
                'all_runs': all_metrics,
                **avg_metrics
            }
            
            print(f"\n[RESULT] Analytics E2E Load:")
            print(f"  Average total: {avg_metrics.get('avg_total', avg_metrics.get('avg_manual_load_time', 0)):.2f}ms")
            print(f"  Average TTFB: {avg_metrics.get('avg_ttfb', 0):.2f}ms")
    
    def benchmark_navigation(self):
        """Benchmark navigation between pages."""
        print("\n" + "="*60)
        print("BENCHMARKING NAVIGATION")
        print("="*60)
        
        page = self.context.new_page()
        
        try:
            # Load dashboard first
            page.goto(f"{self.base_url}/", wait_until='networkidle')
            time.sleep(1)
            
            # Measure navigation to analytics
            nav_times = []
            for i in range(self.iterations):
                start = time.perf_counter()
                page.goto(f"{self.base_url}/analytics", wait_until='networkidle')
                nav_time = (time.perf_counter() - start) * 1000
                nav_times.append(nav_time)
                print(f"  Navigation {i+1}: {nav_time:.2f}ms")
                time.sleep(0.5)
            
            if nav_times:
                self.results['navigation'] = {
                    'durations_ms': nav_times,
                    'avg_ms': sum(nav_times) / len(nav_times),
                    'min_ms': min(nav_times),
                    'max_ms': max(nav_times)
                }
                print(f"\n[RESULT] Navigation: avg={self.results['navigation']['avg_ms']:.2f}ms")
        except Exception as e:
            print(f"[ERROR] Navigation benchmark failed: {e}")
            traceback.print_exc()
        finally:
            page.close()
    
    def generate_summary(self):
        """Generate summary of results."""
        print("\n" + "="*60)
        print("E2E PERFORMANCE SUMMARY")
        print("="*60)
        
        summary = {}
        
        if 'dashboard' in self.results and self.results['dashboard']:
            dashboard = self.results['dashboard']
            summary['dashboard_avg_total_ms'] = dashboard.get('avg_total', dashboard.get('avg_manual_load_time', 0))
            summary['dashboard_avg_ttfb_ms'] = dashboard.get('avg_ttfb', 0)
        
        if 'analytics' in self.results and self.results['analytics']:
            analytics = self.results['analytics']
            summary['analytics_avg_total_ms'] = analytics.get('avg_total', analytics.get('avg_manual_load_time', 0))
            summary['analytics_avg_ttfb_ms'] = analytics.get('avg_ttfb', 0)
        
        if 'navigation' in self.results and self.results['navigation']:
            summary['navigation_avg_ms'] = self.results['navigation'].get('avg_ms', 0)
        
        self.results['summary'] = summary
        
        # Print summary
        print(f"\nDashboard Page (E2E):")
        if 'dashboard_avg_total_ms' in summary:
            print(f"  Average total load: {summary['dashboard_avg_total_ms']:.2f}ms")
            print(f"  Average TTFB: {summary['dashboard_avg_ttfb_ms']:.2f}ms")
        
        print(f"\nAnalytics Page (E2E):")
        if 'analytics_avg_total_ms' in summary:
            print(f"  Average total load: {summary['analytics_avg_total_ms']:.2f}ms")
            print(f"  Average TTFB: {summary['analytics_avg_ttfb_ms']:.2f}ms")
        
        if 'navigation_avg_ms' in summary:
            print(f"\nNavigation:")
            print(f"  Average: {summary['navigation_avg_ms']:.2f}ms")
    
    def run_all(self):
        """Run all benchmarks."""
        print("\n" + "="*60)
        print("E2E PERFORMANCE BENCHMARK (PLAYWRIGHT)")
        print("="*60)
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Base URL: {self.base_url}")
        print(f"Iterations: {self.iterations}")
        print("\n[NOTE] Make sure the application is running before starting benchmarks!")
        
        try:
            self.setup_browser()
            
            # Run benchmarks
            self.benchmark_dashboard()
            self.benchmark_analytics()
            self.benchmark_navigation()
            
            # Generate summary
            self.generate_summary()
            
            return self.results
        finally:
            self.teardown_browser()
    
    def save_results(self, output_file: str = None):
        """Save results to file."""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"benchmark_e2e_results_{timestamp}.json"
        
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
    parser = argparse.ArgumentParser(description='Benchmark web application performance using Playwright')
    parser.add_argument('--url', type=str, default='http://localhost:8080', 
                       help='Base URL of the application (default: http://localhost:8080)')
    parser.add_argument('--iterations', type=int, default=3, 
                       help='Number of measurement iterations (default: 3)')
    parser.add_argument('--output', type=str, default=None, 
                       help='Output file path (default: benchmark_e2e_results_TIMESTAMP.json)')
    
    args = parser.parse_args()
    
    # Check if app is running
    import urllib.request
    try:
        urllib.request.urlopen(args.url, timeout=2)
    except Exception:
        print(f"[ERROR] Could not connect to {args.url}")
        print("Make sure the application is running before starting benchmarks!")
        print("\nTo start the app:")
        print("  cd task_aversion_app")
        print("  python app.py")
        sys.exit(1)
    
    # Run benchmark
    benchmark = PlaywrightPerformanceBenchmark(base_url=args.url, iterations=args.iterations)
    results = benchmark.run_all()
    
    # Save results
    output_path = benchmark.save_results(args.output)
    
    print("\n" + "="*60)
    print("E2E BENCHMARK COMPLETE")
    print("="*60)
    if output_path:
        print(f"Results saved to: {output_path}")
    print("\nCompare with backend benchmark results to see full-stack performance.")


if __name__ == '__main__':
    main()
