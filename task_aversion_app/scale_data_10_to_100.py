#!/usr/bin/env python3
"""
Migration script to scale existing data from 0-10 range to 0-100 range.
This ensures consistency with the new slider range.

Run this once to update existing task_instances.csv data.
"""
import sys
import os

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.instance_manager import InstanceManager

if __name__ == "__main__":
    print("=" * 60)
    print("Scale Data: 0-10 to 0-100 Range")
    print("=" * 60)
    print()
    print("This script will scale all values from 0-10 to 0-100 range.")
    print("Only values <= 10 will be scaled (to avoid double-scaling).")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Cancelled.")
        sys.exit(0)
    
    print()
    im = InstanceManager()
    print(f"Loaded {len(im.df)} instances from CSV")
    print()
    
    print("Scaling values...")
    count = im.scale_values_10_to_100()
    print()
    
    print(f"✓ Scaled {count} instances")
    print()
    print("Data has been updated in task_instances.csv")
    print("=" * 60)

