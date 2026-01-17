#!/usr/bin/env python3
"""
Check which backend (database vs CSV) the app is using and what data sources exist.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("BACKEND MODE DIAGNOSTIC")
print("=" * 80)
print()

# Check environment variables
print("ENVIRONMENT VARIABLES:")
print("-" * 80)
use_csv = os.getenv('USE_CSV', '')
disable_fallback = os.getenv('DISABLE_CSV_FALLBACK', '')
database_url = os.getenv('DATABASE_URL', '')
print(f"  USE_CSV: {use_csv or '(not set)'}")
print(f"  DISABLE_CSV_FALLBACK: {disable_fallback or '(not set)'}")
print(f"  DATABASE_URL: {database_url or '(not set)'}")
print()

# Check what TaskManager would use
print("TASKMANAGER BACKEND:")
print("-" * 80)
from backend.task_manager import TaskManager
tm = TaskManager()
print(f"  use_db: {tm.use_db}")
print(f"  strict_mode: {tm.strict_mode}")
if hasattr(tm, 'tasks_file'):
    print(f"  CSV file: {tm.tasks_file}")
    if os.path.exists(tm.tasks_file):
        import pandas as pd
        try:
            df = pd.read_csv(tm.tasks_file, dtype=str).fillna('')
            print(f"  CSV tasks count: {len(df)}")
            if len(df) > 0:
                print(f"  CSV has user_id column: {'user_id' in df.columns}")
                if 'user_id' in df.columns:
                    null_count = df['user_id'].isna().sum() + (df['user_id'] == '').sum()
                    print(f"  CSV tasks with NULL/empty user_id: {null_count}")
        except Exception as e:
            print(f"  Error reading CSV: {e}")
    else:
        print(f"  CSV file does not exist")
print()

# Check what InstanceManager would use
print("INSTANCEMANAGER BACKEND:")
print("-" * 80)
from backend.instance_manager import InstanceManager
im = InstanceManager()
print(f"  use_db: {im.use_db}")
if hasattr(im, 'file'):
    print(f"  CSV file: {im.file}")
    if os.path.exists(im.file):
        import pandas as pd
        try:
            df = pd.read_csv(im.file, dtype=str).fillna('')
            print(f"  CSV instances count: {len(df)}")
            if len(df) > 0:
                print(f"  CSV has user_id column: {'user_id' in df.columns}")
                if 'user_id' in df.columns:
                    null_count = df['user_id'].isna().sum() + (df['user_id'] == '').sum()
                    print(f"  CSV instances with NULL/empty user_id: {null_count}")
        except Exception as e:
            print(f"  Error reading CSV: {e}")
    else:
        print(f"  CSV file does not exist")
print()

# Check database
print("DATABASE STATUS:")
print("-" * 80)
try:
    from backend.database import get_session, Task, TaskInstance, init_db
    init_db()
    with get_session() as session:
        task_count = session.query(Task).count()
        instance_count = session.query(TaskInstance).count()
        print(f"  Database tasks: {task_count}")
        print(f"  Database instances: {instance_count}")
except Exception as e:
    print(f"  Error accessing database: {e}")
print()

# Check CSV files in data directory
print("CSV FILES IN DATA DIRECTORY:")
print("-" * 80)
data_dir = Path(__file__).parent / 'data'
if data_dir.exists():
    csv_files = list(data_dir.glob('*.csv'))
    for csv_file in csv_files:
        print(f"  {csv_file.name}: {csv_file.stat().st_size} bytes")
        if csv_file.name in ['tasks.csv', 'task_instances.csv']:
            import pandas as pd
            try:
                df = pd.read_csv(csv_file, dtype=str).fillna('')
                print(f"    Rows: {len(df)}")
                if 'user_id' in df.columns:
                    null_count = df['user_id'].isna().sum() + (df['user_id'] == '').sum()
                    print(f"    NULL/empty user_id: {null_count}")
            except Exception as e:
                print(f"    Error reading: {e}")
else:
    print("  Data directory does not exist")
print()

print("=" * 80)
print("RECOMMENDATION:")
print("-" * 80)
if tm.use_db and im.use_db:
    print("  App is using DATABASE backend - data should be in database")
    print("  If Edge shows data not in database, it may be:")
    print("    1. Using cached JavaScript/UI")
    print("    2. Reading from CSV files (fallback mode)")
    print("    3. Using a different database file")
else:
    print("  App is using CSV backend - data is in CSV files")
    print("  This explains why data isn't in the database!")
print()
