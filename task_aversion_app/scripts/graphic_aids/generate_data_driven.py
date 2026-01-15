#!/usr/bin/env python3
"""
Generate data-driven graphic aid images using actual user task instance data.
These visualizations show real patterns from the user's task execution history.
"""

import os
import sys
import json
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for web
import matplotlib.pyplot as plt
import numpy as np
import math
from datetime import datetime
import pandas as pd

# Add parent directory to path for imports
_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.normpath(os.path.join(_script_dir, '..', '..'))
sys.path.insert(0, _parent_dir)

_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def get_user_instances(limit=100):
    """Get user's task instances for visualization."""
    try:
        from backend.instance_manager import InstanceManager
        from backend.analytics import Analytics
        
        instance_manager = InstanceManager()
        analytics = Analytics()
        
        # Analysis script: intentionally use user_id=None to load all instances across all users
        instances = instance_manager.list_recent_completed(limit=limit, user_id=None)
        return instances, analytics
    except Exception as e:
        print(f"[GraphicAids] Error loading instances: {e}")
        return [], None


def generate_difficulty_factor_data_image(output_path=None):
    """Generate difficulty factor visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_difficulty_factor_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances or not analytics:
        # Fallback to theoretical if no data
        return None
    
    # Extract data from instances
    aversion_values = []
    load_values = []
    difficulty_factors = []
    
    for instance in instances:
        try:
            # Handle both dict and Series formats - always parse JSON strings
            predicted_raw = instance.get('predicted', '{}') if hasattr(instance, 'get') else (instance['predicted'] if 'predicted' in instance else '{}')
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance['actual'] if 'actual' in instance else '{}')
            
            # Parse JSON strings to dicts
            if isinstance(predicted_raw, str):
                predicted = json.loads(predicted_raw) if predicted_raw.strip() else {}
            else:
                predicted = predicted_raw if isinstance(predicted_raw, dict) else {}
            
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            # Extract aversion - try multiple field names
            aversion = (predicted.get('initial_aversion') or 
                       predicted.get('expected_aversion') or 
                       predicted.get('aversion'))
            
            # Calculate stress level from actual data if not directly stored
            stress_level = actual.get('stress_level')
            if stress_level is None:
                # Calculate from cognitive + emotional load
                actual_cognitive = actual.get('actual_cognitive') or actual.get('cognitive_load')
                actual_emotional = actual.get('actual_emotional') or actual.get('emotional_load')
                if actual_cognitive is not None and actual_emotional is not None:
                    stress_level = (float(actual_cognitive) + float(actual_emotional)) / 2.0
                elif actual_cognitive is not None:
                    stress_level = float(actual_cognitive)
                elif actual_emotional is not None:
                    stress_level = float(actual_emotional)
            
            # Extract mental energy - try multiple field names
            mental_energy = (predicted.get('expected_cognitive_load') or 
                           predicted.get('expected_mental_energy') or
                           predicted.get('mental_energy_needed') or 
                           predicted.get('cognitive_load'))
            
            # Extract task difficulty - try multiple field names
            task_difficulty = (predicted.get('expected_difficulty') or 
                              predicted.get('task_difficulty'))
            
            # Use aversion if available, or use default value (0) if missing
            if aversion is None:
                # Default to 0 if no aversion data (tasks with no aversion are non-aversive)
                aversion = 0.0
            
            # Ensure we have at least some data to work with
            if aversion is not None:
                # Calculate difficulty factor
                difficulty_factor = analytics.calculate_difficulty_bonus(
                    current_aversion=aversion,
                    stress_level=stress_level,
                    mental_energy=mental_energy,
                    task_difficulty=task_difficulty
                )
                
                aversion_values.append(float(aversion))
                # Calculate load
                if stress_level is not None:
                    load = float(stress_level)
                elif mental_energy is not None or task_difficulty is not None:
                    mental = float(mental_energy) if mental_energy is not None else 50.0
                    difficulty = float(task_difficulty) if task_difficulty is not None else 50.0
                    load = (mental + difficulty) / 2.0
                else:
                    load = 50.0
                
                load_values.append(load)
                difficulty_factors.append(difficulty_factor)
        except (ValueError, TypeError, AttributeError) as e:
            continue
    
    if not aversion_values:
        print(f"[GraphicAids] No aversion data found in {len(instances)} instances")
        print(f"[GraphicAids] Sample predicted keys: {list(predicted.keys()) if instances else 'no instances'}")
        return None
    
    print(f"[GraphicAids] Generated difficulty factor visualization with {len(aversion_values)} data points")
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Scatter plot of actual data
    axes[0].scatter(aversion_values, difficulty_factors, alpha=0.6, s=50, c=load_values, 
                   cmap='viridis', edgecolors='black', linewidth=0.5)
    axes[0].set_xlabel('Aversion (0-100)', fontsize=11)
    axes[0].set_ylabel('Difficulty Factor', fontsize=11)
    axes[0].set_title('Your Task Data: Aversion vs Difficulty Factor\n(Color = Cognitive Load)', 
                      fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(0, 100)
    axes[0].set_ylim(0, 1.1)
    cbar = plt.colorbar(axes[0].collections[0], ax=axes[0])
    cbar.set_label('Cognitive Load', fontsize=10)
    
    # Plot 2: Distribution of difficulty factors
    if len(difficulty_factors) > 0:
        axes[1].hist(difficulty_factors, bins=20, color='blue', alpha=0.7, edgecolor='black')
        axes[1].axvline(x=np.mean(difficulty_factors), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean: {np.mean(difficulty_factors):.2f}')
        axes[1].set_xlabel('Difficulty Factor', fontsize=11)
        axes[1].set_ylabel('Frequency', fontsize=11)
        axes[1].set_title(f'Distribution of Difficulty Factors\n({len(difficulty_factors)} tasks)', 
                         fontsize=12, fontweight='bold')
        axes[1].grid(True, alpha=0.3, axis='y')
        axes[1].legend()
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Difficulty Factor - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_speed_factor_data_image(output_path=None):
    """Generate speed factor visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_speed_factor_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances or not analytics:
        return None
    
    # Extract time ratio data
    time_ratios = []
    speed_factors = []
    
    for instance in instances:
        try:
            # Always parse JSON strings - handle both dict and Series formats
            predicted_raw = instance.get('predicted', '{}') if hasattr(instance, 'get') else (instance['predicted'] if 'predicted' in instance else '{}')
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance['actual'] if 'actual' in instance else '{}')
            
            # Parse JSON strings to dicts
            if isinstance(predicted_raw, str):
                predicted = json.loads(predicted_raw) if predicted_raw.strip() else {}
            else:
                predicted = predicted_raw if isinstance(predicted_raw, dict) else {}
            
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            # Extract time data - try multiple field names and also check CSV columns
            time_actual = actual.get('time_actual_minutes')
            if time_actual is None:
                # Fallback to CSV column if available
                if hasattr(instance, 'get'):
                    time_actual = instance.get('duration_minutes')
                elif 'duration_minutes' in instance:
                    time_actual = instance['duration_minutes']
            
            time_actual = float(time_actual or 0)
            
            time_estimate = float(predicted.get('time_estimate_minutes', 0) or 
                                 predicted.get('estimate', 0) or 0)
            
            if time_estimate > 0 and time_actual > 0:
                time_ratio = time_actual / time_estimate
                
                # Calculate speed factor
                if time_ratio <= 0.5:
                    speed_factor = 1.0
                elif time_ratio <= 1.0:
                    speed_factor = 1.0 - (time_ratio - 0.5) * 1.0
                else:
                    speed_factor = 0.5 * (1.0 / time_ratio)
                
                time_ratios.append(time_ratio)
                speed_factors.append(speed_factor)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not time_ratios:
        print(f"[GraphicAids] No time ratio data found in {len(instances)} instances")
        return None
    
    print(f"[GraphicAids] Generated speed factor visualization with {len(time_ratios)} data points")
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Scatter plot of actual time ratios vs speed factors
    axes[0].scatter(time_ratios, speed_factors, alpha=0.6, s=50, c='green', 
                   edgecolors='black', linewidth=0.5)
    # Add theoretical curve
    theoretical_ratios = np.linspace(0.1, 3.0, 300)
    theoretical_factors = []
    for tr in theoretical_ratios:
        if tr <= 0.5:
            theoretical_factors.append(1.0)
        elif tr <= 1.0:
            theoretical_factors.append(1.0 - (tr - 0.5) * 1.0)
        else:
            theoretical_factors.append(0.5 * (1.0 / tr))
    axes[0].plot(theoretical_ratios, theoretical_factors, 'r--', alpha=0.5, linewidth=2, label='Theoretical')
    axes[0].set_xlabel('Time Ratio (actual / estimate)', fontsize=11)
    axes[0].set_ylabel('Speed Factor', fontsize=11)
    axes[0].set_title('Your Task Data: Time Ratio vs Speed Factor', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, min(3.0, max(time_ratios) * 1.1) if time_ratios else 3.0)
    axes[0].set_ylim(0, 1.1)
    
    # Plot 2: Distribution of time ratios
    axes[1].hist(time_ratios, bins=20, color='green', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=1.0, color='orange', linestyle='--', linewidth=2, label='On Time (1.0)')
    axes[1].axvline(x=np.mean(time_ratios), color='red', linestyle='--', 
                    linewidth=2, label=f'Mean: {np.mean(time_ratios):.2f}')
    axes[1].set_xlabel('Time Ratio', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Time Ratios\n({len(time_ratios)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Speed Factor - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_start_speed_factor_data_image(output_path=None):
    """Generate start speed factor visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_start_speed_factor_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Extract start delay data
    start_delays = []
    start_speed_factors = []
    
    for instance in instances:
        try:
            initialized_at = instance.get('initialized_at')
            started_at = instance.get('started_at')
            completed_at = instance.get('completed_at')
            
            if initialized_at and completed_at:
                try:
                    if isinstance(initialized_at, str):
                        init_time = pd.to_datetime(initialized_at)
                    else:
                        init_time = initialized_at
                    
                    if started_at:
                        if isinstance(started_at, str):
                            start_time = pd.to_datetime(started_at)
                        else:
                            start_time = started_at
                        delay_minutes = (start_time - init_time).total_seconds() / 60.0
                    else:
                        if isinstance(completed_at, str):
                            complete_time = pd.to_datetime(completed_at)
                        else:
                            complete_time = completed_at
                        delay_minutes = (complete_time - init_time).total_seconds() / 60.0
                    
                    # Calculate start speed factor
                    if delay_minutes <= 5:
                        start_speed_factor = 1.0
                    elif delay_minutes <= 30:
                        start_speed_factor = 1.0 - ((delay_minutes - 5) / 25.0) * 0.2
                    elif delay_minutes <= 120:
                        start_speed_factor = 0.8 - ((delay_minutes - 30) / 90.0) * 0.3
                    else:
                        excess = delay_minutes - 120
                        start_speed_factor = 0.5 * math.exp(-excess / 240.0)
                    
                    start_delays.append(delay_minutes)
                    start_speed_factors.append(start_speed_factor)
                except (ValueError, TypeError, AttributeError):
                    continue
        except Exception:
            continue
    
    if not start_delays:
        print(f"[GraphicAids] No start delay data found in {len(instances)} instances")
        return None
    
    print(f"[GraphicAids] Generated start speed factor visualization with {len(start_delays)} data points")
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Scatter plot of actual delays vs start speed factors
    axes[0].scatter(start_delays, start_speed_factors, alpha=0.6, s=50, c='purple', 
                   edgecolors='black', linewidth=0.5)
    # Add theoretical curve
    theoretical_delays = np.linspace(0, min(480, max(start_delays) * 1.1) if start_delays else 480, 500)
    theoretical_factors = []
    for d in theoretical_delays:
        if d <= 5:
            theoretical_factors.append(1.0)
        elif d <= 30:
            theoretical_factors.append(1.0 - ((d - 5) / 25.0) * 0.2)
        elif d <= 120:
            theoretical_factors.append(0.8 - ((d - 30) / 90.0) * 0.3)
        else:
            excess = d - 120
            theoretical_factors.append(0.5 * math.exp(-excess / 240.0))
    axes[0].plot(theoretical_delays, theoretical_factors, 'r--', alpha=0.5, linewidth=2, label='Theoretical')
    axes[0].set_xlabel('Start Delay (minutes)', fontsize=11)
    axes[0].set_ylabel('Start Speed Factor', fontsize=11)
    axes[0].set_title('Your Task Data: Start Delay vs Start Speed Factor', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 1.1)
    
    # Plot 2: Distribution of start delays
    axes[1].hist(start_delays, bins=20, color='purple', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=5, color='green', linestyle='--', linewidth=2, label='Perfect (5 min)')
    axes[1].axvline(x=np.mean(start_delays), color='red', linestyle='--', 
                    linewidth=2, label=f'Mean: {np.mean(start_delays):.1f} min')
    axes[1].set_xlabel('Start Delay (minutes)', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Start Delays\n({len(start_delays)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Start Speed Factor - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_completion_factor_data_image(output_path=None):
    """Generate completion factor visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_completion_factor_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Extract completion data
    completion_percentages = []
    completion_factors = []
    
    for instance in instances:
        try:
            # Always parse JSON strings - handle both dict and Series formats
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance['actual'] if 'actual' in instance else '{}')
            
            # Parse JSON string to dict
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            # Extract completion percentage - default to 100 if not specified
            completion_pct = actual.get('completion_percent')
            if completion_pct is None:
                # If not in actual, assume 100% for completed tasks
                is_completed = instance.get('is_completed') if hasattr(instance, 'get') else (instance['is_completed'] if 'is_completed' in instance else False)
                if isinstance(is_completed, str):
                    is_completed = is_completed.lower() in ('true', '1', 'yes')
                elif not isinstance(is_completed, bool):
                    is_completed = False  # Default to False if not found or wrong type
                completion_pct = 100.0 if is_completed else 0.0
            else:
                completion_pct = float(completion_pct)
            
            # Calculate completion factor
            if completion_pct >= 100.0:
                completion_factor = 1.0
            elif completion_pct >= 90.0:
                completion_factor = 0.9 + (completion_pct - 90.0) / 10.0 * 0.1
            elif completion_pct >= 50.0:
                completion_factor = 0.5 + (completion_pct - 50.0) / 40.0 * 0.4
            else:
                completion_factor = completion_pct / 50.0 * 0.5
            
            completion_percentages.append(completion_pct)
            completion_factors.append(completion_factor)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not completion_percentages:
        print(f"[GraphicAids] No completion data found in {len(instances)} instances")
        return None
    
    print(f"[GraphicAids] Generated completion factor visualization with {len(completion_percentages)} data points")
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Scatter plot of actual completion percentages vs factors
    axes[0].scatter(completion_percentages, completion_factors, alpha=0.6, s=50, c='blue', 
                   edgecolors='black', linewidth=0.5)
    # Add theoretical curve
    theoretical_pcts = np.linspace(0, 100, 500)
    theoretical_factors = []
    for cp in theoretical_pcts:
        if cp >= 100.0:
            theoretical_factors.append(1.0)
        elif cp >= 90.0:
            theoretical_factors.append(0.9 + (cp - 90.0) / 10.0 * 0.1)
        elif cp >= 50.0:
            theoretical_factors.append(0.5 + (cp - 50.0) / 40.0 * 0.4)
        else:
            theoretical_factors.append(cp / 50.0 * 0.5)
    axes[0].plot(theoretical_pcts, theoretical_factors, 'r--', alpha=0.5, linewidth=2, label='Theoretical')
    axes[0].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[0].set_ylabel('Completion Factor', fontsize=11)
    axes[0].set_title('Your Task Data: Completion % vs Completion Factor', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 100)
    axes[0].set_ylim(0, 1.1)
    
    # Plot 2: Distribution of completion percentages
    axes[1].hist(completion_percentages, bins=20, color='blue', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=100, color='green', linestyle='--', linewidth=2, label='Full (100%)')
    axes[1].axvline(x=np.mean(completion_percentages), color='red', linestyle='--', 
                    linewidth=2, label=f'Mean: {np.mean(completion_percentages):.1f}%')
    axes[1].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Completion Percentages\n({len(completion_percentages)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Completion Factor - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_baseline_completion_data_image(output_path=None):
    """Generate baseline completion visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_baseline_completion_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Extract completion and score data
    completion_percentages = []
    baseline_scores = []
    task_types = []
    
    for instance in instances:
        try:
            # Parse JSON strings
            predicted_raw = instance.get('predicted', '{}') if hasattr(instance, 'get') else (instance.get('predicted', '{}') if 'predicted' in instance else '{}')
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            
            if isinstance(predicted_raw, str):
                predicted = json.loads(predicted_raw) if predicted_raw.strip() else {}
            else:
                predicted = predicted_raw if isinstance(predicted_raw, dict) else {}
            
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            completion_pct = float(actual.get('completion_percent', 100) or 100)
            
            # Get task type
            task_type = instance.get('task_type', 'Work') if hasattr(instance, 'get') else (instance.get('task_type', 'Work') if 'task_type' in instance else 'Work')
            task_type_lower = str(task_type).strip().lower()
            
            # Calculate baseline score using same logic as backend
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted.get('time_estimate_minutes', 0) or predicted.get('estimate', 0) or 0)
            
            if time_estimate > 0 and time_actual > 0:
                completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
            else:
                completion_time_ratio = 1.0
            
            if task_type_lower == 'work':
                if completion_time_ratio <= 1.0:
                    multiplier = 3.0
                elif completion_time_ratio >= 1.5:
                    multiplier = 5.0
                else:
                    smooth_factor = (completion_time_ratio - 1.0) / 0.5
                    multiplier = 3.0 + (2.0 * smooth_factor)
                baseline_score = completion_pct * multiplier
            elif task_type_lower in ['self care', 'selfcare', 'self-care']:
                multiplier = 1.0  # Simplified for demo
                baseline_score = completion_pct * multiplier
            else:
                multiplier = 1.0
                baseline_score = completion_pct * multiplier
            
            completion_percentages.append(completion_pct)
            baseline_scores.append(baseline_score)
            task_types.append(task_type_lower)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not completion_percentages:
        return None
    
    print(f"[GraphicAids] Generated baseline completion visualization with {len(completion_percentages)} data points")
    
    # Create figure with matching axes to theoretical
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Scatter plot with theoretical curves
    work_completion = np.linspace(0, 100, 200)
    work_scores = [cp * 3.0 for cp in work_completion]
    self_care_scores = [cp * 1.0 for cp in work_completion]
    play_scores = [cp * 1.0 for cp in work_completion]
    
    # Separate data by task type
    work_data = [(cp, score) for cp, score, tt in zip(completion_percentages, baseline_scores, task_types) if tt == 'work']
    self_care_data = [(cp, score) for cp, score, tt in zip(completion_percentages, baseline_scores, task_types) if tt in ['self care', 'selfcare', 'self-care']]
    play_data = [(cp, score) for cp, score, tt in zip(completion_percentages, baseline_scores, task_types) if tt == 'play']
    
    axes[0].plot(work_completion, work_scores, 'b--', linewidth=2, alpha=0.5, label='Work Theoretical (×3.0)')
    axes[0].plot(work_completion, self_care_scores, 'g--', linewidth=2, alpha=0.5, label='Self Care Theoretical (×1.0)')
    axes[0].plot(work_completion, play_scores, 'orange', linestyle='--', linewidth=2, alpha=0.5, label='Play Theoretical (×1.0)')
    
    if work_data:
        work_cp, work_sc = zip(*work_data)
        axes[0].scatter(work_cp, work_sc, alpha=0.6, s=50, c='blue', edgecolors='black', linewidth=0.5, label='Work Data')
    if self_care_data:
        sc_cp, sc_sc = zip(*self_care_data)
        axes[0].scatter(sc_cp, sc_sc, alpha=0.6, s=50, c='green', edgecolors='black', linewidth=0.5, label='Self Care Data')
    if play_data:
        p_cp, p_sc = zip(*play_data)
        axes[0].scatter(p_cp, p_sc, alpha=0.6, s=50, c='orange', edgecolors='black', linewidth=0.5, label='Play Data')
    
    axes[0].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[0].set_ylabel('Baseline Score', fontsize=11)
    axes[0].set_title('Your Data: Completion % vs Baseline Score', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 100)  # Match theoretical
    axes[0].set_ylim(0, 350)  # Match theoretical
    
    # Plot 2: Distribution of completion percentages
    axes[1].hist(completion_percentages, bins=20, color='blue', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=100, color='green', linestyle='--', linewidth=2, label='Full (100%)')
    axes[1].axvline(x=np.mean(completion_percentages), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(completion_percentages):.1f}%')
    axes[1].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Completion Percentages\n({len(completion_percentages)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    axes[1].set_xlim(0, 100)
    
    # Plot 3: Distribution of baseline scores
    axes[2].hist(baseline_scores, bins=20, color='purple', alpha=0.7, edgecolor='black')
    axes[2].axvline(x=np.mean(baseline_scores), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(baseline_scores):.1f}')
    axes[2].set_xlabel('Baseline Score', fontsize=11)
    axes[2].set_ylabel('Frequency', fontsize=11)
    axes[2].set_title(f'Distribution of Baseline Scores\n({len(baseline_scores)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].legend()
    axes[2].set_xlim(0, 550)  # Match theoretical
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Baseline Completion - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_work_multiplier_data_image(output_path=None):
    """Generate work multiplier visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_work_multiplier_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Extract work task data
    completion_time_ratios = []
    multipliers = []
    
    for instance in instances:
        try:
            # Parse JSON strings
            predicted_raw = instance.get('predicted', '{}') if hasattr(instance, 'get') else (instance.get('predicted', '{}') if 'predicted' in instance else '{}')
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            
            if isinstance(predicted_raw, str):
                predicted = json.loads(predicted_raw) if predicted_raw.strip() else {}
            else:
                predicted = predicted_raw if isinstance(predicted_raw, dict) else {}
            
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            task_type = instance.get('task_type', 'Work') if hasattr(instance, 'get') else (instance.get('task_type', 'Work') if 'task_type' in instance else 'Work')
            task_type_lower = str(task_type).strip().lower()
            
            if task_type_lower != 'work':
                continue
            
            completion_pct = float(actual.get('completion_percent', 100) or 100)
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            time_estimate = float(predicted.get('time_estimate_minutes', 0) or predicted.get('estimate', 0) or 0)
            
            if time_estimate > 0 and time_actual > 0:
                ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
                
                # Calculate multiplier
                if ratio <= 1.0:
                    multiplier = 3.0
                elif ratio >= 1.5:
                    multiplier = 5.0
                else:
                    smooth_factor = (ratio - 1.0) / 0.5
                    multiplier = 3.0 + (2.0 * smooth_factor)
                
                completion_time_ratios.append(ratio)
                multipliers.append(multiplier)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not completion_time_ratios:
        return None
    
    print(f"[GraphicAids] Generated work multiplier visualization with {len(completion_time_ratios)} data points")
    
    # Create figure with matching axes
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Scatter with theoretical curve
    ratio_range = np.linspace(0.5, 2.0, 200)
    theoretical_multipliers = []
    for r in ratio_range:
        if r <= 1.0:
            theoretical_multipliers.append(3.0)
        elif r >= 1.5:
            theoretical_multipliers.append(5.0)
        else:
            smooth_factor = (r - 1.0) / 0.5
            theoretical_multipliers.append(3.0 + (2.0 * smooth_factor))
    
    axes[0].plot(ratio_range, theoretical_multipliers, 'r--', linewidth=2, alpha=0.5, label='Theoretical')
    axes[0].scatter(completion_time_ratios, multipliers, alpha=0.6, s=50, c='blue', 
                   edgecolors='black', linewidth=0.5, label='Your Data')
    axes[0].axvline(x=1.0, color='r', linestyle='--', alpha=0.3)
    axes[0].axvline(x=1.5, color='orange', linestyle='--', alpha=0.3)
    axes[0].set_xlabel('Completion/Time Ratio', fontsize=11)
    axes[0].set_ylabel('Work Multiplier', fontsize=11)
    axes[0].set_title('Your Data: Ratio vs Work Multiplier', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0.5, 2.0)  # Match theoretical
    axes[0].set_ylim(2.5, 5.5)  # Match theoretical
    
    # Plot 2: Distribution of ratios
    axes[1].hist(completion_time_ratios, bins=20, color='green', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=1.0, color='orange', linestyle='--', linewidth=2, label='Efficient (1.0)')
    axes[1].axvline(x=np.mean(completion_time_ratios), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(completion_time_ratios):.2f}')
    axes[1].set_xlabel('Completion/Time Ratio', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Ratios\n({len(completion_time_ratios)} work tasks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    axes[1].set_xlim(0.5, 2.0)
    
    # Plot 3: Distribution of multipliers
    axes[2].hist(multipliers, bins=20, color='purple', alpha=0.7, edgecolor='black')
    axes[2].axvline(x=3.0, color='blue', linestyle='--', linewidth=2, label='Base (3.0x)')
    axes[2].axvline(x=5.0, color='green', linestyle='--', linewidth=2, label='Max (5.0x)')
    axes[2].axvline(x=np.mean(multipliers), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(multipliers):.2f}x')
    axes[2].set_xlabel('Work Multiplier', fontsize=11)
    axes[2].set_ylabel('Frequency', fontsize=11)
    axes[2].set_title(f'Distribution of Multipliers\n({len(multipliers)} work tasks)', 
                     fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].legend()
    axes[2].set_xlim(2.5, 5.5)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Work Multiplier - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def calculate_weekly_multiplier(time_percentage_diff, curve_type='flattened_square', strength=1.0):
    """Calculate weekly average multiplier."""
    if curve_type == 'flattened_square':
        effect = math.copysign((abs(time_percentage_diff) ** 2) / 100.0, time_percentage_diff)
        multiplier = 1.0 - (0.01 * strength * effect)
    else:  # linear
        multiplier = 1.0 - (0.01 * strength * time_percentage_diff)
    return max(0.5, min(1.5, multiplier))


def calculate_goal_multiplier(goal_achievement_ratio):
    """Calculate goal-based multiplier."""
    if goal_achievement_ratio >= 1.2:
        return 1.2
    elif goal_achievement_ratio >= 1.0:
        return 1.0 + (goal_achievement_ratio - 1.0) * 1.0
    elif goal_achievement_ratio >= 0.8:
        return 0.9 + (goal_achievement_ratio - 0.8) * 0.5
    else:
        multiplier = 0.8 + (goal_achievement_ratio / 0.8) * 0.1
        return max(0.8, multiplier)


def generate_weekly_avg_bonus_data_image(output_path=None):
    """Generate weekly average bonus visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_weekly_avg_bonus_data.png')
    
    instances, analytics = get_user_instances()
    
    if not instances:
        return None
    
    # Calculate weekly average from instances
    time_values = []
    for instance in instances:
        try:
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            if time_actual > 0:
                time_values.append(time_actual)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if len(time_values) < 3:
        return None
    
    weekly_avg = np.mean(time_values)
    
    # Extract deviation data
    deviations = []
    multipliers = []
    
    for instance in instances:
        try:
            actual_raw = instance.get('actual', '{}') if hasattr(instance, 'get') else (instance.get('actual', '{}') if 'actual' in instance else '{}')
            if isinstance(actual_raw, str):
                actual = json.loads(actual_raw) if actual_raw.strip() else {}
            else:
                actual = actual_raw if isinstance(actual_raw, dict) else {}
            
            time_actual = float(actual.get('time_actual_minutes', 0) or 0)
            if time_actual > 0 and weekly_avg > 0:
                deviation = ((time_actual - weekly_avg) / weekly_avg) * 100.0
                multiplier = calculate_weekly_multiplier(deviation, 'flattened_square', 1.0)
                
                deviations.append(deviation)
                multipliers.append(multiplier)
        except (ValueError, TypeError, AttributeError):
            continue
    
    if not deviations:
        return None
    
    print(f"[GraphicAids] Generated weekly avg bonus visualization with {len(deviations)} data points")
    
    # Create figure with matching axes
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Scatter with theoretical curve
    deviation_range = np.linspace(-100, 100, 200)
    theoretical_multipliers = [calculate_weekly_multiplier(d, 'flattened_square', 1.0) for d in deviation_range]
    
    axes[0].plot(deviation_range, theoretical_multipliers, 'r--', linewidth=2, alpha=0.5, label='Theoretical')
    axes[0].scatter(deviations, multipliers, alpha=0.6, s=50, c='blue', 
                   edgecolors='black', linewidth=0.5, label='Your Data')
    axes[0].axvline(x=0, color='gray', linestyle='--', alpha=0.3)
    axes[0].axhline(y=1.0, color='green', linestyle='--', alpha=0.3)
    axes[0].set_xlabel('Percentage Deviation from Weekly Average (%)', fontsize=11)
    axes[0].set_ylabel('Weekly Multiplier', fontsize=11)
    axes[0].set_title('Your Data: Deviation vs Weekly Multiplier', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(-100, 100)  # Match theoretical
    axes[0].set_ylim(0.5, 1.5)  # Match theoretical
    
    # Plot 2: Distribution of deviations
    axes[1].hist(deviations, bins=20, color='green', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=0, color='gray', linestyle='--', linewidth=2, label='Average (0%)')
    axes[1].axvline(x=np.mean(deviations), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(deviations):.1f}%')
    axes[1].set_xlabel('Percentage Deviation (%)', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Deviations\n({len(deviations)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    axes[1].set_xlim(-100, 100)
    
    # Plot 3: Distribution of multipliers
    axes[2].hist(multipliers, bins=20, color='purple', alpha=0.7, edgecolor='black')
    axes[2].axvline(x=1.0, color='green', linestyle='--', linewidth=2, label='No Change (1.0x)')
    axes[2].axvline(x=np.mean(multipliers), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(multipliers):.3f}x')
    axes[2].set_xlabel('Weekly Multiplier', fontsize=11)
    axes[2].set_ylabel('Frequency', fontsize=11)
    axes[2].set_title(f'Distribution of Multipliers\n({len(multipliers)} tasks)', 
                     fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].legend()
    axes[2].set_xlim(0.5, 1.5)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Weekly Average Bonus - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_goal_adjustment_data_image(output_path=None):
    """Generate goal adjustment visualization with actual user data."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_goal_adjustment_data.png')
    
    # Get goal data from user state
    try:
        from backend.user_state import UserStateManager
        from backend.productivity_tracker import ProductivityTracker
        
        user_state = UserStateManager()
        tracker = ProductivityTracker()
        DEFAULT_USER_ID = "default_user"
        
        goal_settings = user_state.get_productivity_goal_settings(DEFAULT_USER_ID)
        goal_hours = goal_settings.get('goal_hours_per_week', 40.0)
        
        # Get weekly history data
        history = tracker.get_productivity_history(DEFAULT_USER_ID, weeks=12)
        if not history:
            return None
        
        # Extract goal ratios
        goal_ratios = []
        multipliers = []
        
        for week_entry in history:
            if isinstance(week_entry, dict):
                actual_hours = week_entry.get('actual_hours', 0.0)
                if goal_hours > 0:
                    ratio = actual_hours / goal_hours
                    multiplier = calculate_goal_multiplier(ratio)
                    goal_ratios.append(ratio)
                    multipliers.append(multiplier)
    except Exception as e:
        print(f"[GraphicAids] Error loading goal data: {e}")
        return None
    
    if not goal_ratios:
        return None
    
    print(f"[GraphicAids] Generated goal adjustment visualization with {len(goal_ratios)} data points")
    
    # Create figure with matching axes
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Scatter with theoretical curve
    ratio_range = np.linspace(0, 1.5, 300)
    theoretical_multipliers = [calculate_goal_multiplier(r) for r in ratio_range]
    
    axes[0].plot(ratio_range, theoretical_multipliers, 'r--', linewidth=2, alpha=0.5, label='Theoretical')
    axes[0].scatter(goal_ratios, multipliers, alpha=0.6, s=50, c='blue', 
                   edgecolors='black', linewidth=0.5, label='Your Data')
    axes[0].axvline(x=1.0, color='green', linestyle='--', alpha=0.3)
    axes[0].set_xlabel('Goal Achievement Ratio (actual / goal)', fontsize=11)
    axes[0].set_ylabel('Goal Multiplier', fontsize=11)
    axes[0].set_title('Your Data: Goal Ratio vs Multiplier', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 1.5)  # Match theoretical
    axes[0].set_ylim(0.75, 1.25)  # Match theoretical
    
    # Plot 2: Distribution of goal ratios
    axes[1].hist(goal_ratios, bins=20, color='green', alpha=0.7, edgecolor='black')
    axes[1].axvline(x=1.0, color='green', linestyle='--', linewidth=2, label='100% Goal')
    axes[1].axvline(x=np.mean(goal_ratios), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(goal_ratios):.2f}')
    axes[1].set_xlabel('Goal Achievement Ratio', fontsize=11)
    axes[1].set_ylabel('Frequency', fontsize=11)
    axes[1].set_title(f'Distribution of Goal Ratios\n({len(goal_ratios)} weeks)', 
                     fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].legend()
    axes[1].set_xlim(0, 1.5)
    
    # Plot 3: Distribution of multipliers
    axes[2].hist(multipliers, bins=20, color='purple', alpha=0.7, edgecolor='black')
    axes[2].axvline(x=1.0, color='green', linestyle='--', linewidth=2, label='No Change (1.0x)')
    axes[2].axvline(x=np.mean(multipliers), color='red', linestyle='--', 
                   linewidth=2, label=f'Mean: {np.mean(multipliers):.3f}x')
    axes[2].set_xlabel('Goal Multiplier', fontsize=11)
    axes[2].set_ylabel('Frequency', fontsize=11)
    axes[2].set_title(f'Distribution of Multipliers\n({len(multipliers)} weeks)', 
                     fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].legend()
    axes[2].set_xlim(0.75, 1.25)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Goal Adjustment - Your Data', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


# Mapping of data-driven generators (must be after all function definitions)
DATA_DRIVEN_GENERATORS = {
    'execution_score_difficulty_factor_data.png': generate_difficulty_factor_data_image,
    'execution_score_speed_factor_data.png': generate_speed_factor_data_image,
    'execution_score_start_speed_factor_data.png': generate_start_speed_factor_data_image,
    'execution_score_completion_factor_data.png': generate_completion_factor_data_image,
    'productivity_score_baseline_completion_data.png': generate_baseline_completion_data_image,
    'productivity_score_work_multiplier_data.png': generate_work_multiplier_data_image,
    'productivity_score_weekly_avg_bonus_data.png': generate_weekly_avg_bonus_data_image,
    'productivity_score_goal_adjustment_data.png': generate_goal_adjustment_data_image,
}


def generate_all_data_images():
    """Generate all data-driven graphic aid images."""
    results = {}
    for image_name, generator_func in DATA_DRIVEN_GENERATORS.items():
        try:
            image_path = generator_func()
            if image_path:
                results[image_name] = {'status': 'success', 'path': image_path}
                print(f"[PASS] Generated: {image_path}")
            else:
                results[image_name] = {'status': 'no_data', 'message': 'Insufficient data'}
                print(f"[INFO] No data for: {image_name}")
        except Exception as e:
            results[image_name] = {'status': 'error', 'error': str(e)}
            print(f"[FAIL] Error generating {image_name}: {e}")
    return results


if __name__ == '__main__':
    generate_all_data_images()

