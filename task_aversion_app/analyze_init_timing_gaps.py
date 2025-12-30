#!/usr/bin/env python3
"""Analyze timing gaps in initialization log."""
import json
from datetime import datetime

log_file = 'data/logs/initialization_performance.log'

with open(log_file, 'r', encoding='utf-8') as f:
    data = [json.loads(line) for line in f if line.strip()]

# Find the initialization we care about
init_events = [d for d in data if d.get('message') == 'do_save_start']
if not init_events:
    print("No initialization events found")
    exit(1)

latest_init = init_events[-1]
instance_id = latest_init['data'].get('instance_id')

print("=" * 80)
print("TIMING GAP ANALYSIS")
print("=" * 80)
print(f"\nInstance ID: {instance_id}\n")

# Find all events related to this initialization
relevant_events = []
for d in data:
    data_dict = d.get('data', {})
    if (instance_id in str(data_dict.get('instance_id', '')) or 
        'initialize_task_page_load_start' in d.get('message', '') or
        'do_save_start' in d.get('message', '')):
        relevant_events.append(d)

# Parse timestamps and calculate gaps
print("KEY EVENTS WITH TIMING:")
print("-" * 80)

prev_time = None
for event in relevant_events:
    timestamp_str = event.get('timestamp', '')
    try:
        current_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
        
        if prev_time:
            gap = (current_time - prev_time).total_seconds() * 1000  # Convert to ms
            if gap > 10:  # Only show gaps > 10ms
                print(f"\n  GAP: {gap:.0f}ms")
        
        message = event.get('message', '')
        level = event.get('level', '')
        
        # Show important events
        if (level in ['EVENT', 'TIMING'] or 
            'page_load' in message or 
            'do_save' in message or
            'add_prediction' in message):
            print(f"  {timestamp_str} [{level}] {message}")
            if 'duration_ms' in event.get('data', {}):
                print(f"      Duration: {event['data']['duration_ms']:.2f}ms")
        
        prev_time = current_time
    except Exception as e:
        continue

# Calculate total time from page load start to save completion
page_load_starts = [d for d in relevant_events if 'initialize_task_page_load_start' in d.get('message', '')]
save_totals = [d for d in relevant_events if 'do_save_total' in d.get('message', '')]

if page_load_starts and save_totals:
    start_time = datetime.strptime(page_load_starts[-1]['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
    end_time = datetime.strptime(save_totals[-1]['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
    total_elapsed = (end_time - start_time).total_seconds() * 1000
    
    print("\n" + "=" * 80)
    print(f"TOTAL ELAPSED TIME (Page Load Start -> Save Complete): {total_elapsed:.0f}ms ({total_elapsed/1000:.2f}s)")
    print("=" * 80)
    
    # Breakdown
    page_load_time = page_load_starts[-1].get('data', {}).get('duration_ms', 0) if 'duration_ms' in page_load_starts[-1].get('data', {}) else 0
    save_time = save_totals[-1].get('data', {}).get('duration_ms', 0)
    
    print(f"\nMeasured operations: {page_load_time + save_time:.2f}ms")
    print(f"Unaccounted time: {total_elapsed - (page_load_time + save_time):.0f}ms ({((total_elapsed - (page_load_time + save_time)) / total_elapsed * 100):.1f}%)")
    print("\nThis unaccounted time likely includes:")
    print("  - UI rendering")
    print("  - Network round-trips")
    print("  - Browser processing")
    print("  - Navigation/redirect time")
    print("  - Dashboard refresh after initialization")
