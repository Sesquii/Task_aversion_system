#!/usr/bin/env python3
"""Standalone script to backfill task_instances.csv"""
import sys
import os

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.instance_manager import InstanceManager

if __name__ == "__main__":
    print("=" * 60)
    print("Task Instances Data Backfill")
    print("=" * 60)
    print()
    
    im = InstanceManager()
    print(f"Loaded {len(im.df)} instances from CSV")
    print()
    
    print("Running backfill...")
    count = im.backfill_attributes_from_json()
    print()
    
    print(f"✓ Backfilled {count} instances")
    print()
    print("Data has been updated in task_instances.csv")
    print("=" * 60)

