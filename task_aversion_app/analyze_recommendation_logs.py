#!/usr/bin/env python
"""
Analyze recommendation logs to understand recommendation effectiveness.

Reads JSONL log files from data/logs/recommendations_*.jsonl and provides insights.
"""
import os
import json
import glob
from datetime import datetime
from collections import defaultdict, Counter
from typing import List, Dict, Any

LOG_DIR = os.path.join(os.path.dirname(__file__), 'data', 'logs')

def load_recommendation_logs() -> List[Dict[str, Any]]:
    """Load all recommendation log events from JSONL files."""
    events = []
    
    # Find all recommendation log files
    pattern = os.path.join(LOG_DIR, 'recommendations_*.jsonl')
    log_files = glob.glob(pattern)
    
    for log_file in sorted(log_files):
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            events.append(event)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[WARNING] Failed to read {log_file}: {e}")
    
    return events

def analyze_recommendations():
    """Analyze recommendation logs and print insights."""
    print("=" * 80)
    print("RECOMMENDATION SYSTEM ANALYSIS")
    print("=" * 80)
    print()
    
    events = load_recommendation_logs()
    
    if not events:
        print("[INFO] No recommendation logs found.")
        print(f"       Looking in: {LOG_DIR}")
        print("       Logs will be created automatically when recommendations are used.")
        return
    
    print(f"Total log events: {len(events)}")
    print()
    
    # Group events by type
    by_type = defaultdict(list)
    for event in events:
        event_type = event.get('event_type', 'unknown')
        by_type[event_type].append(event)
    
    print("=" * 80)
    print("EVENT BREAKDOWN")
    print("=" * 80)
    for event_type, type_events in by_type.items():
        print(f"{event_type}: {len(type_events)}")
    print()
    
    # Analyze recommendation generation
    generated = by_type.get('recommendation_generated', [])
    if generated:
        print("=" * 80)
        print("RECOMMENDATION GENERATION ANALYSIS")
        print("=" * 80)
        
        total_recs = sum(len(e.get('recommendations', [])) for e in generated)
        print(f"Total recommendations generated: {total_recs}")
        print(f"Average per generation: {total_recs / len(generated):.1f}")
        
        # Mode breakdown
        modes = Counter(e.get('mode') for e in generated)
        print("\nMode breakdown:")
        for mode, count in modes.items():
            print(f"  {mode}: {count}")
        
        # Metrics used
        all_metrics = []
        for e in generated:
            all_metrics.extend(e.get('metrics', []))
        metric_counts = Counter(all_metrics)
        print("\nMost used metrics:")
        for metric, count in metric_counts.most_common(10):
            print(f"  {metric}: {count}")
        
        print()
    
    # Analyze recommendation selection
    selected = by_type.get('recommendation_selected', [])
    if selected:
        print("=" * 80)
        print("RECOMMENDATION SELECTION ANALYSIS")
        print("=" * 80)
        
        print(f"Total recommendations selected: {len(selected)}")
        
        # Action breakdown
        actions = Counter(e.get('action') for e in selected)
        print("\nAction breakdown:")
        for action, count in actions.items():
            print(f"  {action}: {count}")
        
        # Score distribution
        scores = [e.get('recommendation_score') for e in selected if e.get('recommendation_score') is not None]
        if scores:
            print(f"\nScore statistics:")
            print(f"  Average: {sum(scores) / len(scores):.1f}")
            print(f"  Min: {min(scores):.1f}")
            print(f"  Max: {max(scores):.1f}")
        
        # Most selected tasks
        task_names = [e.get('task_name') for e in selected if e.get('task_name')]
        task_counts = Counter(task_names)
        print("\nMost selected tasks:")
        for task, count in task_counts.most_common(10):
            print(f"  {task}: {count}")
        
        print()
    
    # Analyze outcomes
    outcomes = by_type.get('recommendation_outcome', [])
    if outcomes:
        print("=" * 80)
        print("RECOMMENDATION OUTCOME ANALYSIS")
        print("=" * 80)
        
        outcome_types = Counter(e.get('outcome') for e in outcomes)
        print("Outcome breakdown:")
        for outcome, count in outcome_types.items():
            print(f"  {outcome}: {count}")
        
        # Completion rate
        completed = sum(1 for e in outcomes if e.get('outcome') == 'completed')
        if outcomes:
            completion_rate = (completed / len(outcomes)) * 100
            print(f"\nCompletion rate: {completion_rate:.1f}% ({completed}/{len(outcomes)})")
        
        # Relief accuracy
        relief_accuracies = [
            e.get('relief_accuracy') 
            for e in outcomes 
            if e.get('relief_accuracy') is not None
        ]
        if relief_accuracies:
            print(f"\nRelief prediction accuracy:")
            print(f"  Average error: {sum(relief_accuracies) / len(relief_accuracies):.1f}")
            print(f"  Min error: {min(relief_accuracies):.1f}")
            print(f"  Max error: {max(relief_accuracies):.1f}")
        
        print()
    
    # Conversion funnel
    if generated and selected:
        print("=" * 80)
        print("CONVERSION FUNNEL")
        print("=" * 80)
        
        total_generated = sum(len(e.get('recommendations', [])) for e in generated)
        total_selected = len(selected)
        
        if total_generated > 0:
            selection_rate = (total_selected / total_generated) * 100
            print(f"Recommendations generated: {total_generated}")
            print(f"Recommendations selected: {total_selected}")
            print(f"Selection rate: {selection_rate:.2f}%")
        
        if selected and outcomes:
            completed = sum(1 for e in outcomes if e.get('outcome') == 'completed')
            completion_rate = (completed / len(selected)) * 100
            print(f"Completion rate (of selected): {completion_rate:.1f}% ({completed}/{len(selected)})")
        
        print()
    
    # Time-based analysis
    print("=" * 80)
    print("TIME-BASED ANALYSIS")
    print("=" * 80)
    
    # Group by date
    by_date = defaultdict(lambda: {'generated': 0, 'selected': 0, 'completed': 0})
    for event in events:
        timestamp = event.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
                event_type = event.get('event_type', '')
                
                if event_type == 'recommendation_generated':
                    by_date[date_str]['generated'] += len(event.get('recommendations', []))
                elif event_type == 'recommendation_selected':
                    by_date[date_str]['selected'] += 1
                elif event_type == 'recommendation_outcome' and event.get('outcome') == 'completed':
                    by_date[date_str]['completed'] += 1
            except Exception:
                pass
    
    if by_date:
        print("\nDaily activity (last 7 days):")
        sorted_dates = sorted(by_date.keys(), reverse=True)[:7]
        for date_str in sorted_dates:
            stats = by_date[date_str]
            print(f"  {date_str}: {stats['generated']} generated, {stats['selected']} selected, {stats['completed']} completed")
    
    print()

if __name__ == '__main__':
    try:
        analyze_recommendations()
    except Exception as e:
        print(f"[ERROR] Failed to analyze recommendations: {e}")
        import traceback
        traceback.print_exc()
