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
        
        instances = instance_manager.list_recent_completed(limit=limit)
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


# Mapping of data-driven generators
DATA_DRIVEN_GENERATORS = {
    'execution_score_difficulty_factor_data.png': generate_difficulty_factor_data_image,
    'execution_score_speed_factor_data.png': generate_speed_factor_data_image,
    'execution_score_start_speed_factor_data.png': generate_start_speed_factor_data_image,
    'execution_score_completion_factor_data.png': generate_completion_factor_data_image,
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

