#!/usr/bin/env python
"""Generate large test dataset for Phase 2B edge case testing.

This script generates a large number of tasks and instances for a specific user_id
to test performance, data isolation, and edge cases with large datasets.

Usage:
    python scripts/generate_large_test_dataset.py --user-id 1 --tasks 1000 --instances 10000
    python scripts/generate_large_test_dataset.py --user-id 2 --tasks 500 --instances 5000 --completed-ratio 0.8
"""

import os
import sys
import argparse
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set database URL if not set
if not os.getenv('DATABASE_URL'):
    os.environ['DATABASE_URL'] = 'sqlite:///data/task_aversion.db'

from backend.database import get_session, init_db, Task, TaskInstance
from backend.task_manager import TaskManager
from backend.instance_manager import InstanceManager

# Sample data for realistic test data
TASK_NAMES = [
    "Review project proposal", "Update documentation", "Fix bug in module",
    "Write unit tests", "Code review", "Deploy to staging", "Update dependencies",
    "Refactor legacy code", "Design new feature", "Write API documentation",
    "Optimize database queries", "Fix security vulnerability", "Update user interface",
    "Implement authentication", "Add error handling", "Write integration tests",
    "Performance optimization", "Database migration", "Add logging", "Update config"
]

TASK_DESCRIPTIONS = [
    "Need to review and provide feedback",
    "Update outdated documentation",
    "Fix critical bug affecting users",
    "Add comprehensive test coverage",
    "Review code for quality and standards",
    "Deploy latest changes to staging environment",
    "Update third-party dependencies",
    "Improve code structure and maintainability",
    "Design and plan new feature implementation",
    "Document API endpoints and usage"
]

TASK_TYPES = ["one-time", "recurring"]
CATEGORIES_OPTIONS = [
    ["Work", "Development"],
    ["Work", "Documentation"],
    ["Work", "Testing"],
    ["Personal", "Health"],
    ["Personal", "Learning"],
    ["Work", "Meeting"],
    ["Personal", "Finance"]
]

def generate_task(user_id: int, task_id: str, name: str, description: str) -> Dict:
    """Generate a task dictionary."""
    task_type = random.choice(TASK_TYPES)
    categories = random.choice(CATEGORIES_OPTIONS)
    is_recurring = task_type == "recurring"
    
    return {
        'task_id': task_id,
        'name': name,
        'description': description,
        'type': task_type,
        'version': 1,
        'created_at': datetime.now() - timedelta(days=random.randint(0, 365)),
        'is_recurring': is_recurring,
        'categories': categories,
        'default_estimate_minutes': random.randint(15, 240),
        'task_type': categories[0],
        'default_initial_aversion': random.choice(['low', 'medium', 'high', '']),
        'user_id': user_id
    }

def generate_instance(
    user_id: int,
    instance_id: str,
    task_id: str,
    task_name: str,
    task_version: int,
    is_completed: bool = False
) -> Dict:
    """Generate a task instance dictionary."""
    base_time = datetime.now() - timedelta(days=random.randint(0, 180))
    created_at = base_time
    initialized_at = base_time + timedelta(minutes=random.randint(0, 60))
    started_at = initialized_at + timedelta(minutes=random.randint(0, 120))
    
    if is_completed:
        completed_at = started_at + timedelta(minutes=random.randint(15, 480))
        cancelled_at = None
        status = 'completed'
    else:
        # Some active, some cancelled
        if random.random() < 0.3:  # 30% cancelled
            cancelled_at = started_at + timedelta(minutes=random.randint(5, 120))
            completed_at = None
            status = 'cancelled'
        else:
            cancelled_at = None
            completed_at = None
            status = 'active'
    
    # Generate predicted data
    predicted = {
        'relief_score': random.randint(20, 90),
        'cognitive_load': random.randint(10, 80),
        'emotional_load': random.randint(5, 70),
        'expected_duration_minutes': random.randint(15, 240)
    }
    
    # Generate actual data (if completed)
    actual = {}
    if is_completed:
        actual = {
            'relief_score': random.randint(15, 95),
            'cognitive_load': random.randint(10, 85),
            'emotional_load': random.randint(5, 75),
            'duration_minutes': random.randint(10, 300),
            'environmental_effect': random.randint(-20, 20),
            'skills_improved': random.choice([True, False]),
            'behavioral_score': random.randint(0, 100)
        }
        actual['net_relief'] = actual['relief_score'] - predicted['relief_score']
    
    return {
        'instance_id': instance_id,
        'task_id': task_id,
        'task_name': task_name,
        'task_version': task_version,
        'created_at': created_at,
        'initialized_at': initialized_at,
        'started_at': started_at,
        'completed_at': completed_at,
        'cancelled_at': cancelled_at,
        'predicted': json.dumps(predicted),
        'actual': json.dumps(actual) if actual else '',
        'is_completed': is_completed,
        'is_deleted': False,
        'status': status,
        'delay_minutes': random.randint(0, 1440) if initialized_at else 0,
        'user_id': user_id
    }

def generate_tasks(user_id: int, num_tasks: int) -> List[Dict]:
    """Generate a list of task dictionaries."""
    tasks = []
    for i in range(num_tasks):
        task_id = f"test_task_{user_id}_{i+1:06d}"
        name = random.choice(TASK_NAMES) + f" {i+1}"
        description = random.choice(TASK_DESCRIPTIONS)
        task = generate_task(user_id, task_id, name, description)
        tasks.append(task)
    return tasks

def generate_instances(
    user_id: int,
    tasks: List[Dict],
    num_instances: int,
    completed_ratio: float = 0.7
) -> List[Dict]:
    """Generate a list of instance dictionaries."""
    instances = []
    num_completed = int(num_instances * completed_ratio)
    
    if not tasks:
        raise ValueError("Cannot generate instances without tasks")
    
    for i in range(num_instances):
        # Select a random task
        task = random.choice(tasks)
        task_id = task.get('task_id')
        task_name = task.get('name', 'Unknown Task')
        task_version = task.get('version', 1)
        
        # Validate required fields
        if not task_id:
            print(f"  [WARNING] Task at index {tasks.index(task)} has no task_id, skipping")
            continue
        
        instance_id = f"test_instance_{user_id}_{i+1:08d}"
        is_completed = i < num_completed
        
        instance = generate_instance(
            user_id=user_id,
            instance_id=instance_id,
            task_id=task_id,
            task_name=task_name,
            task_version=task_version,
            is_completed=is_completed
        )
        
        # Validate instance has task_id before appending
        if 'task_id' not in instance or not instance['task_id']:
            print(f"  [ERROR] Generated instance {instance_id} is missing task_id!")
            continue
        
        instances.append(instance)
    
    return instances

def insert_tasks_to_db(tasks: List[Dict], batch_size: int = 100):
    """Insert tasks into database in batches."""
    print(f"Inserting {len(tasks)} tasks into database...")
    with get_session() as session:
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            db_tasks = []
            for task_dict in batch:
                task = Task(**task_dict)
                db_tasks.append(task)
            session.bulk_save_objects(db_tasks)
            session.commit()
            print(f"  Inserted batch {i//batch_size + 1}/{(len(tasks)-1)//batch_size + 1} ({len(batch)} tasks)")

def insert_instances_to_db(instances: List[Dict], batch_size: int = 100):
    """Insert instances into database in batches."""
    print(f"Inserting {len(instances)} instances into database...")
    with get_session() as session:
        for i in range(0, len(instances), batch_size):
            batch = instances[i:i+batch_size]
            for instance_dict in batch:
                # Ensure all required fields are present
                # Parse JSON fields if they're strings
                if 'predicted' in instance_dict and isinstance(instance_dict['predicted'], str):
                    try:
                        instance_dict['predicted'] = json.loads(instance_dict['predicted']) if instance_dict['predicted'] else {}
                    except (json.JSONDecodeError, TypeError):
                        instance_dict['predicted'] = {}
                if 'actual' in instance_dict and isinstance(instance_dict['actual'], str):
                    try:
                        instance_dict['actual'] = json.loads(instance_dict['actual']) if instance_dict['actual'] else {}
                    except (json.JSONDecodeError, TypeError):
                        instance_dict['actual'] = {}
                
                # Convert boolean strings to booleans
                if 'is_completed' in instance_dict and isinstance(instance_dict['is_completed'], str):
                    instance_dict['is_completed'] = instance_dict['is_completed'].lower() in ('true', '1', 'yes')
                if 'is_deleted' in instance_dict and isinstance(instance_dict['is_deleted'], str):
                    instance_dict['is_deleted'] = instance_dict['is_deleted'].lower() in ('true', '1', 'yes')
                
                # Ensure task_id is present (required field)
                if 'task_id' not in instance_dict or not instance_dict['task_id']:
                    print(f"  [WARNING] Skipping instance {instance_dict.get('instance_id', 'unknown')} - missing task_id")
                    continue
                
                instance = TaskInstance(**instance_dict)
                session.add(instance)
            
            session.commit()
            print(f"  Inserted batch {i//batch_size + 1}/{(len(instances)-1)//batch_size + 1} ({len(batch)} instances)")

def main():
    parser = argparse.ArgumentParser(
        description='Generate large test dataset for Phase 2B stress testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stress test: 1500 tasks (realistic extreme)
  python scripts/generate_large_test_dataset.py --user-id 2 --tasks 1500

  # Extreme stress test: 3000 tasks (makes app nonfunctional)
  python scripts/generate_large_test_dataset.py --user-id 2 --tasks 3000 --stress-test

  # Custom: 2000 tasks with 80% completed
  python scripts/generate_large_test_dataset.py --user-id 2 --tasks 2000 --completed-ratio 0.8
        """
    )
    parser.add_argument('--user-id', type=int, required=True, help='User ID to generate data for')
    parser.add_argument('--tasks', type=int, default=1500, help='Number of tasks to generate (default: 1500 for stress test)')
    parser.add_argument('--instances', type=int, help='Number of instances to generate (default: tasks * 10, or tasks * 20 for stress-test)')
    parser.add_argument('--completed-ratio', type=float, default=0.7, help='Ratio of completed instances (default: 0.7)')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for database inserts (default: 100)')
    parser.add_argument('--stress-test', action='store_true', help='Extreme stress test mode (tasks * 20 instances, makes app nonfunctional)')
    
    args = parser.parse_args()
    
    # Calculate instances if not provided
    if args.instances is None:
        if args.stress_test:
            args.instances = args.tasks * 20  # Extreme: 20 instances per task
        else:
            args.instances = args.tasks * 10  # Standard: 10 instances per task
    
    print("=" * 70)
    print("Large Test Dataset Generator for Phase 2B")
    print("=" * 70)
    print(f"User ID: {args.user_id}")
    print(f"Tasks: {args.tasks}")
    print(f"Instances: {args.instances} ({args.instances // args.tasks} per task)")
    print(f"Completed Ratio: {args.completed_ratio:.1%}")
    print(f"Batch Size: {args.batch_size}")
    if args.stress_test:
        print("⚠️  STRESS TEST MODE: This will make the app nonfunctional!")
    print()
    
    # Initialize database
    print("1. Initializing database...")
    init_db()
    print("   [OK] Database initialized")
    
    # Generate tasks
    print(f"\n2. Generating {args.tasks} tasks...")
    tasks = generate_tasks(args.user_id, args.tasks)
    print(f"   [OK] Generated {len(tasks)} tasks")
    
    # Insert tasks
    print(f"\n3. Inserting tasks into database...")
    insert_tasks_to_db(tasks, args.batch_size)
    print(f"   [OK] All tasks inserted")
    
    # Generate instances
    print(f"\n4. Generating {args.instances} instances...")
    instances = generate_instances(args.user_id, tasks, args.instances, args.completed_ratio)
    print(f"   [OK] Generated {len(instances)} instances")
    print(f"   - Completed: {sum(1 for i in instances if i['is_completed'])}")
    print(f"   - Active: {sum(1 for i in instances if i['status'] == 'active')}")
    print(f"   - Cancelled: {sum(1 for i in instances if i['status'] == 'cancelled')}")
    
    # Insert instances
    print(f"\n5. Inserting instances into database...")
    insert_instances_to_db(instances, args.batch_size)
    print(f"   [OK] All instances inserted")
    
    # Verify
    print(f"\n6. Verifying data...")
    with get_session() as session:
        task_count = session.query(Task).filter(Task.user_id == args.user_id).count()
        instance_count = session.query(TaskInstance).filter(TaskInstance.user_id == args.user_id).count()
        print(f"   Tasks in database: {task_count}")
        print(f"   Instances in database: {instance_count}")
    
    print("\n" + "=" * 70)
    print("[SUCCESS] Large test dataset generated successfully!")
    print("=" * 70)
    print(f"\nYou can now test the application with user_id={args.user_id}")
    print("Test scenarios:")
    print("  - Dashboard load time with large dataset")
    print("  - Analytics calculations with many instances")
    print("  - Data isolation (verify other users don't see this data)")
    print("  - Query performance")
    print("  - Memory usage with large datasets")
    print()
    print("To cleanup this test data:")
    print(f"  python scripts/cleanup_test_data.py --user-id {args.user_id}")

if __name__ == '__main__':
    main()
