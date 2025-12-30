#!/usr/bin/env python3
"""Analyze initialization performance log."""
import json
import sys

log_file = 'data/logs/initialization_performance.log'

try:
    with open(log_file, 'r', encoding='utf-8') as f:
        data = [json.loads(line) for line in f if line.strip()]
except FileNotFoundError:
    print(f"Log file not found: {log_file}")
    sys.exit(1)

# Find the most recent initialization (last instance_id in do_save_start)
init_events = [d for d in data if d.get('message') == 'do_save_start']
if not init_events:
    print("No initialization events found in log")
    sys.exit(1)

latest_init = init_events[-1]
instance_id = latest_init['data'].get('instance_id')
task_id = latest_init['data'].get('task_id')

print("=" * 60)
print("INITIALIZATION PERFORMANCE ANALYSIS")
print("=" * 60)
print(f"\nInstance ID: {instance_id}")
print(f"Task ID: {task_id}\n")

# Find all operations related to this initialization
init_ops = []
for d in data:
    data_dict = d.get('data', {})
    if (instance_id in str(data_dict.get('instance_id', '')) or 
        task_id in str(data_dict.get('task_id', ''))):
        init_ops.append(d)

# Page load operations
print("PAGE LOAD OPERATIONS:")
print("-" * 60)
page_load_total = [d for d in init_ops if 'initialize_task_page_load_total' in d.get('message', '')]
if page_load_total:
    print(f"  Total page load: {page_load_total[0]['data'].get('duration_ms', 0):.2f}ms")

page_load_ops = [d for d in init_ops if d.get('level') == 'END' and 
                 ('get_instance' in d.get('message', '') or 
                  'get_task' in d.get('message', '') or 
                  'get_previous_task_averages' in d.get('message', '') or
                  'get_initial_aversion' in d.get('message', '') or
                  'has_completed_task' in d.get('message', ''))]

for op in page_load_ops:
    msg = op.get('message', '').replace(' completed', '')
    duration = op['data'].get('duration_ms', 0)
    print(f"  {msg}: {duration:.2f}ms")

# Save operations
print("\nSAVE OPERATIONS:")
print("-" * 60)
save_total = [d for d in init_ops if 'do_save_total' in d.get('message', '')]
if save_total:
    print(f"  Total save: {save_total[0]['data'].get('duration_ms', 0):.2f}ms")

save_ops = [d for d in init_ops if d.get('level') == 'END' and 
            ('add_prediction_to_instance' in d.get('message', '') or 
             'save_initialization_entry' in d.get('message', '') or
             'set_persistent_emotions' in d.get('message', ''))]

for op in save_ops:
    msg = op.get('message', '').replace(' completed', '')
    duration = op['data'].get('duration_ms', 0)
    print(f"  {msg}: {duration:.2f}ms")

# Check for previous averages query performance
print("\nPREVIOUS AVERAGES QUERY:")
print("-" * 60)
avg_events = [d for d in init_ops if '_get_previous_task_averages_db_filtered' in d.get('message', '')]
if avg_events:
    for event in avg_events:
        count = event['data'].get('initialized_count', 0)
        print(f"  Processed {count} initialized instances for averages")

# Summary
print("\n" + "=" * 60)
print("PERFORMANCE SUMMARY")
print("=" * 60)
if page_load_total and save_total:
    total_time = page_load_total[0]['data'].get('duration_ms', 0) + save_total[0]['data'].get('duration_ms', 0)
    print(f"Total initialization time: {total_time:.2f}ms")
    print(f"  - Page load: {page_load_total[0]['data'].get('duration_ms', 0):.2f}ms")
    print(f"  - Save: {save_total[0]['data'].get('duration_ms', 0):.2f}ms")
    
    # Performance assessment
    print("\nPerformance Assessment:")
    if total_time < 50:
        print("  [EXCELLENT] Total time under 50ms")
    elif total_time < 100:
        print("  [GOOD] Total time under 100ms")
    elif total_time < 200:
        print("  [ACCEPTABLE] Total time under 200ms")
    else:
        print("  [NEEDS OPTIMIZATION] Total time over 200ms")
