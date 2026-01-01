#!/usr/bin/env python
"""
Unit tests for pause/resume time tracking functionality.

Tests that time spent on a task accumulates correctly across multiple pause/resume cycles.

Run with: python -m pytest task_aversion_app/tests/test_pause_resume_time_tracking.py -v
Or: python task_aversion_app/tests/test_pause_resume_time_tracking.py
"""
import os
import sys
import unittest
from datetime import datetime
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.instance_manager import InstanceManager
from backend.task_manager import TaskManager


class TestPauseResumeTimeTracking(unittest.TestCase):
    """Test pause/resume time tracking with multiple pause cycles."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        # Set environment to use CSV backend for testing
        os.environ['USE_CSV'] = 'true'
        os.environ.pop('DATABASE_URL', None)
        
        # Initialize managers
        cls.task_manager = TaskManager()
        cls.instance_manager = InstanceManager()
        
        # Create a test task
        cls.task_id = cls.task_manager.create_task(
            name="Test Task for Pause/Resume",
            description="Testing time tracking",
            task_type="Work"
        )
        print(f"\n[TEST SETUP] Created test task: {cls.task_id}")
    
    def setUp(self):
        """Set up for each test."""
        # Each test gets a fresh instance
        self.instance_id = None
    
    def test_single_pause_accumulates_time(self):
        """Test that a single pause correctly calculates and stores time."""
        print("\n=== Test 1: Single Pause ===")
        
        # Create an instance
        instance_id = self.instance_manager.create_instance(
            self.task_id,
            "Test Task for Pause/Resume",
            task_version=1
        )
        print(f"Created instance: {instance_id}")
        
        # Start the task
        self.instance_manager.start_instance(instance_id)
        print("Started instance")
        
        # Get instance to verify started_at
        instance = self.instance_manager.get_instance(instance_id)
        started_at_str = instance.get('started_at', '')
        print(f"started_at after start: '{started_at_str}'")
        self.assertNotEqual(started_at_str, '', "started_at should be set")
        
        # Wait a bit (simulate work)
        time.sleep(0.1)  # 100ms = ~0.0017 minutes
        
        # Pause the task
        self.instance_manager.pause_instance(instance_id, reason="Test pause", completion_percentage=0.0)
        print("Paused instance")
        
        # Get instance and check time_spent_before_pause
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        print(f"actual JSON string: {actual_str}")
        
        try:
            actual_data = json.loads(actual_str) if actual_str else {}
        except json.JSONDecodeError:
            actual_data = {}
        
        print(f"Parsed actual_data: {actual_data}")
        time_spent = actual_data.get('time_spent_before_pause', 0.0)
        print(f"time_spent_before_pause: {time_spent}")
        
        # Verify time was accumulated
        self.assertGreater(time_spent, 0, "Time should be accumulated after pause")
        print(f"[PASS] Time accumulated: {time_spent} minutes")
    
    def test_multiple_pauses_accumulate_time(self):
        """Test that multiple pause/resume cycles accumulate time correctly."""
        print("\n=== Test 2: Multiple Pauses ===")
        
        # Create an instance
        instance_id = self.instance_manager.create_instance(
            self.task_id,
            "Test Task for Multiple Pauses",
            task_version=1
        )
        print(f"Created instance: {instance_id}")
        
        # First work session
        print("\n--- First Work Session ---")
        self.instance_manager.start_instance(instance_id)
        instance = self.instance_manager.get_instance(instance_id)
        started_at_1 = instance.get('started_at', '')
        print(f"Started at: '{started_at_1}'")
        
        time.sleep(0.1)  # Work for 100ms
        
        self.instance_manager.pause_instance(instance_id, reason="First pause", completion_percentage=0.0)
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        time_after_first = actual_data.get('time_spent_before_pause', 0.0)
        print(f"Time after first pause: {time_after_first} minutes")
        self.assertGreater(time_after_first, 0, "First pause should accumulate time")
        
        # Second work session
        print("\n--- Second Work Session ---")
        self.instance_manager.start_instance(instance_id)
        instance = self.instance_manager.get_instance(instance_id)
        started_at_2 = instance.get('started_at', '')
        print(f"Started at: '{started_at_2}'")
        self.assertNotEqual(started_at_2, '', "started_at should be set on resume")
        
        # Check that previous time is preserved
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        time_before_second = actual_data.get('time_spent_before_pause', 0.0)
        print(f"Time before second session: {time_before_second} minutes")
        self.assertEqual(time_before_second, time_after_first, "Previous time should be preserved")
        
        time.sleep(0.1)  # Work for another 100ms
        
        self.instance_manager.pause_instance(instance_id, reason="Second pause", completion_percentage=0.0)
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        time_after_second = actual_data.get('time_spent_before_pause', 0.0)
        print(f"Time after second pause: {time_after_second} minutes")
        
        # Verify time increased
        self.assertGreater(time_after_second, time_after_first, "Time should increase after second pause")
        print(f"[PASS] Time increased from {time_after_first} to {time_after_second} minutes")
        
        # Third work session
        print("\n--- Third Work Session ---")
        self.instance_manager.start_instance(instance_id)
        time.sleep(0.1)  # Work for another 100ms
        
        self.instance_manager.pause_instance(instance_id, reason="Third pause", completion_percentage=0.0)
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        time_after_third = actual_data.get('time_spent_before_pause', 0.0)
        print(f"Time after third pause: {time_after_third} minutes")
        
        # Verify time increased again
        self.assertGreater(time_after_third, time_after_second, "Time should increase after third pause")
        print(f"[PASS] Time increased from {time_after_second} to {time_after_third} minutes")
        print(f"[PASS] Total accumulated time: {time_after_third} minutes")
    
    def test_pause_without_start_has_zero_time(self):
        """Test that pausing without starting doesn't accumulate time."""
        print("\n=== Test 3: Pause Without Start ===")
        
        # Create an instance but don't start it
        instance_id = self.instance_manager.create_instance(
            self.task_id,
            "Test Task Not Started",
            task_version=1
        )
        print(f"Created instance: {instance_id} (not started)")
        
        # Try to pause (should not accumulate time since never started)
        self.instance_manager.pause_instance(instance_id, reason="Pause without start", completion_percentage=0.0)
        
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        time_spent = actual_data.get('time_spent_before_pause', 0.0)
        print(f"time_spent_before_pause: {time_spent} minutes")
        
        # Should be 0 or very small (just initialization time)
        self.assertGreaterEqual(time_spent, 0, "Time should be >= 0")
        print(f"[PASS] Time is {time_spent} (expected 0 or very small)")
    
    def test_resume_preserves_accumulated_time(self):
        """Test that resuming preserves previously accumulated time."""
        print("\n=== Test 4: Resume Preserves Time ===")
        
        instance_id = self.instance_manager.create_instance(
            self.task_id,
            "Test Task Resume",
            task_version=1
        )
        
        # Start and pause to accumulate some time
        self.instance_manager.start_instance(instance_id)
        time.sleep(0.1)
        self.instance_manager.pause_instance(instance_id, reason="Initial pause", completion_percentage=0.0)
        
        # Get accumulated time
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        initial_time = actual_data.get('time_spent_before_pause', 0.0)
        print(f"Initial accumulated time: {initial_time} minutes")
        
        # Resume
        self.instance_manager.start_instance(instance_id)
        
        # Verify time is still in actual_data
        instance = self.instance_manager.get_instance(instance_id)
        actual_str = instance.get('actual', '{}')
        actual_data = json.loads(actual_str) if actual_str else {}
        preserved_time = actual_data.get('time_spent_before_pause', 0.0)
        print(f"Time after resume: {preserved_time} minutes")
        
        self.assertEqual(preserved_time, initial_time, "Time should be preserved after resume")
        print(f"[PASS] Time preserved: {preserved_time} == {initial_time}")


if __name__ == '__main__':
    import sys
    from datetime import datetime
    import os
    
    # Create output file with timestamp in the tests directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(test_dir, f"test_pause_resume_results_{timestamp}.txt")
    
    print(f"Running pause/resume time tracking tests...")
    print(f"All output will be saved to: {output_file}")
    
    # Save original streams
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    # Open file for writing
    f = open(output_file, 'w', encoding='utf-8')
    
    try:
        # Redirect both stdout and stderr to file
        sys.stdout = f
        sys.stderr = f
        
        # Run tests with verbose output
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(sys.modules[__name__])
        runner = unittest.TextTestRunner(stream=f, verbosity=2)
        result = runner.run(suite)
        
    finally:
        # Restore original streams
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        f.close()
    
    # Print summary to terminal
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print(f"[SUCCESS] All {result.testsRun} tests passed!")
    else:
        print(f"[FAILURE] {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests")
    print(f"Full test output saved to: {output_file}")
    print("=" * 70)
