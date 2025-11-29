"""
Migration script to backfill missing attribute columns from JSON data.
Run this once to fix existing task_instances.csv data.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.instance_manager import InstanceManager

def main():
    print("Starting data migration: backfilling attributes from JSON...")
    im = InstanceManager()
    count = im.backfill_attributes_from_json()
    print(f"Migration complete! Updated {count} instances.")
    print("\nYou can now safely remove logs.csv and emotions.csv if desired.")
    print("All data is now consolidated in task_instances.csv")

if __name__ == "__main__":
    main()

