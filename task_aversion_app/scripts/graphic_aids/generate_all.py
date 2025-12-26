#!/usr/bin/env python3
"""
Generate all graphic aid images for the analytics glossary.
This module provides functions to generate images that can be embedded in the web UI.
"""

import os
import sys
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for web
import matplotlib.pyplot as plt
import numpy as np
import math

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def generate_difficulty_factor_image(output_path=None):
    """Generate difficulty factor visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_difficulty_factor.png')
    
    def calculate_difficulty_bonus(aversion, load, w_aversion=0.7, w_load=0.3, k=50.0):
        """Calculate difficulty bonus using exponential decay formula."""
        combined_difficulty = (w_aversion * aversion) + (w_load * load)
        difficulty_bonus = 1.0 * (1.0 - math.exp(-combined_difficulty / k))
        return max(0.0, min(1.0, difficulty_bonus))
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Difficulty factor vs combined difficulty
    combined_difficulty_range = np.linspace(0, 100, 200)
    difficulty_factors = [calculate_difficulty_bonus(d, 0, w_aversion=1.0, w_load=0.0) for d in combined_difficulty_range]
    
    axes[0].plot(combined_difficulty_range, difficulty_factors, 'b-', linewidth=2, label='Difficulty Factor')
    axes[0].axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Max (1.0)')
    axes[0].set_xlabel('Combined Difficulty (0.7 × aversion + 0.3 × load)', fontsize=11)
    axes[0].set_ylabel('Difficulty Factor', fontsize=11)
    axes[0].set_title('Difficulty Factor vs Combined Difficulty\n(Exponential Scaling)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 1.1)
    
    # Plot 2: 3D surface showing aversion vs load
    aversion_range = np.linspace(0, 100, 50)
    load_range = np.linspace(0, 100, 50)
    Aversion, Load = np.meshgrid(aversion_range, load_range)
    Difficulty = np.zeros_like(Aversion)
    
    for i in range(len(aversion_range)):
        for j in range(len(load_range)):
            Difficulty[j, i] = calculate_difficulty_bonus(aversion_range[i], load_range[j])
    
    contour = axes[1].contourf(Aversion, Load, Difficulty, levels=20, cmap='viridis')
    axes[1].set_xlabel('Aversion (0-100)', fontsize=11)
    axes[1].set_ylabel('Cognitive Load (0-100)', fontsize=11)
    axes[1].set_title('Difficulty Factor: Aversion × Load\n(Higher = More Difficult)', fontsize=12, fontweight='bold')
    cbar = plt.colorbar(contour, ax=axes[1])
    cbar.set_label('Difficulty Factor', fontsize=10)
    
    # Add example points
    example_points = [
        (20, 30, 'Easy Task'),
        (50, 50, 'Moderate Task'),
        (80, 70, 'Hard Task'),
    ]
    
    for av, ld, label in example_points:
        factor = calculate_difficulty_bonus(av, ld)
        axes[1].plot(av, ld, 'ro', markersize=10)
        axes[1].annotate(f'{label}\nFactor: {factor:.2f}', 
                        xy=(av, ld), xytext=(10, 10), 
                        textcoords='offset points', fontsize=9,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Difficulty Factor Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_speed_factor_image(output_path=None):
    """Generate speed factor visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_speed_factor.png')
    
    def calculate_speed_factor(time_ratio):
        """Calculate speed factor based on time ratio."""
        if time_ratio <= 0.5:
            return 1.0
        elif time_ratio <= 1.0:
            return 1.0 - (time_ratio - 0.5) * 1.0
        else:
            return 0.5 * (1.0 / time_ratio)
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Speed factor vs time ratio
    time_ratio_range = np.linspace(0.1, 3.0, 300)
    speed_factors = [calculate_speed_factor(tr) for tr in time_ratio_range]
    
    axes[0].plot(time_ratio_range, speed_factors, 'g-', linewidth=2, label='Speed Factor')
    axes[0].axvline(x=0.5, color='r', linestyle='--', alpha=0.5, label='Very Fast Threshold (0.5)')
    axes[0].axvline(x=1.0, color='orange', linestyle='--', alpha=0.5, label='Estimate (1.0)')
    axes[0].axhline(y=1.0, color='b', linestyle='--', alpha=0.3, label='Max (1.0)')
    axes[0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.3, label='Neutral (0.5)')
    axes[0].set_xlabel('Time Ratio (actual / estimate)', fontsize=11)
    axes[0].set_ylabel('Speed Factor', fontsize=11)
    axes[0].set_title('Speed Factor vs Time Ratio\n(Fast = High Score)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 1.1)
    axes[0].set_xlim(0, 3.0)
    
    # Add region labels
    axes[0].text(0.25, 0.95, 'Very Fast\n(2x speed or faster)\nFactor = 1.0', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    axes[0].text(0.75, 0.75, 'Fast\n(within estimate)\nLinear: 0.5 → 1.0', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    axes[0].text(2.0, 0.25, 'Slow\n(exceeded estimate)\nDiminishing penalty', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('Very Fast (0.25x)', 0.25, 'Completed in 15 min\n(estimated 60 min)'),
        ('Fast (0.5x)', 0.5, 'Completed in 30 min\n(estimated 60 min)'),
        ('On Time (1.0x)', 1.0, 'Completed in 60 min\n(estimated 60 min)'),
        ('Slow (2.0x)', 2.0, 'Completed in 120 min\n(estimated 60 min)'),
        ('Very Slow (3.0x)', 3.0, 'Completed in 180 min\n(estimated 60 min)'),
    ]
    
    scenario_names = [s[0] for s in scenarios]
    scenario_ratios = [s[1] for s in scenarios]
    scenario_factors = [calculate_speed_factor(s[1]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    bars = axes[1].bar(x_pos, scenario_factors, color=['green', 'lightgreen', 'yellow', 'orange', 'red'], alpha=0.7)
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Speed Factor', fontsize=11)
    axes[1].set_title('Speed Factor: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0, 1.1)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, factor, scenario) in enumerate(zip(bars, scenario_factors, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{factor:.2f}\n{scenario[2]}',
                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Speed Factor Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_start_speed_factor_image(output_path=None):
    """Generate start speed factor visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_start_speed_factor.png')
    
    def calculate_start_speed_factor(start_delay_minutes):
        """Calculate start speed factor based on delay from initialization to start."""
        if start_delay_minutes <= 5:
            return 1.0
        elif start_delay_minutes <= 30:
            return 1.0 - ((start_delay_minutes - 5) / 25.0) * 0.2
        elif start_delay_minutes <= 120:
            return 0.8 - ((start_delay_minutes - 30) / 90.0) * 0.3
        else:
            excess = start_delay_minutes - 120
            return 0.5 * math.exp(-excess / 240.0)
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Start speed factor vs delay minutes
    delay_range = np.linspace(0, 480, 500)  # 0 to 8 hours
    start_speed_factors = [calculate_start_speed_factor(d) for d in delay_range]
    
    axes[0].plot(delay_range, start_speed_factors, 'purple', linewidth=2, label='Start Speed Factor')
    axes[0].axvline(x=5, color='g', linestyle='--', alpha=0.5, label='Perfect (5 min)')
    axes[0].axvline(x=30, color='lightgreen', linestyle='--', alpha=0.5, label='Good (30 min)')
    axes[0].axvline(x=120, color='orange', linestyle='--', alpha=0.5, label='Acceptable (2 hours)')
    axes[0].axhline(y=1.0, color='b', linestyle='--', alpha=0.3, label='Max (1.0)')
    axes[0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.3, label='Neutral (0.5)')
    axes[0].set_xlabel('Start Delay (minutes from initialization)', fontsize=11)
    axes[0].set_ylabel('Start Speed Factor', fontsize=11)
    axes[0].set_title('Start Speed Factor vs Delay\n(Fast Start = High Score)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 1.1)
    axes[0].set_xlim(0, 480)
    
    # Add region labels
    axes[0].text(2.5, 0.95, 'Perfect\n(≤5 min)\nFactor = 1.0', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    axes[0].text(17.5, 0.9, 'Good\n(5-30 min)\nLinear: 1.0 → 0.8', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    axes[0].text(75, 0.65, 'Acceptable\n(30-120 min)\nLinear: 0.8 → 0.5', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    axes[0].text(300, 0.3, 'Poor\n(>120 min)\nExponential decay', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('Immediate (2 min)', 2, 'Started 2 min after initialization'),
        ('Fast (10 min)', 10, 'Started 10 min after initialization'),
        ('Moderate (45 min)', 45, 'Started 45 min after initialization'),
        ('Delayed (3 hours)', 180, 'Started 3 hours after initialization'),
        ('Very Delayed (6 hours)', 360, 'Started 6 hours after initialization'),
    ]
    
    scenario_names = [s[0] for s in scenarios]
    scenario_delays = [s[1] for s in scenarios]
    scenario_factors = [calculate_start_speed_factor(s[1]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    bars = axes[1].bar(x_pos, scenario_factors, color=['green', 'lightgreen', 'yellow', 'orange', 'red'], alpha=0.7)
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Start Speed Factor', fontsize=11)
    axes[1].set_title('Start Speed Factor: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0, 1.1)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, factor, scenario) in enumerate(zip(bars, scenario_factors, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{factor:.2f}\n{scenario[2]}',
                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Start Speed Factor Component\n(Procrastination Resistance)', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


def generate_completion_factor_image(output_path=None):
    """Generate completion factor visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'execution_score_completion_factor.png')
    
    def calculate_completion_factor(completion_pct):
        """Calculate completion factor based on completion percentage."""
        if completion_pct >= 100.0:
            return 1.0
        elif completion_pct >= 90.0:
            return 0.9 + (completion_pct - 90.0) / 10.0 * 0.1
        elif completion_pct >= 50.0:
            return 0.5 + (completion_pct - 50.0) / 40.0 * 0.4
        else:
            return completion_pct / 50.0 * 0.5
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Completion factor vs completion percentage
    completion_range = np.linspace(0, 100, 500)
    completion_factors = [calculate_completion_factor(cp) for cp in completion_range]
    
    axes[0].plot(completion_range, completion_factors, 'blue', linewidth=2, label='Completion Factor')
    axes[0].axvline(x=50, color='orange', linestyle='--', alpha=0.5, label='Partial (50%)')
    axes[0].axvline(x=90, color='yellow', linestyle='--', alpha=0.5, label='Near-Complete (90%)')
    axes[0].axvline(x=100, color='g', linestyle='--', alpha=0.5, label='Full (100%)')
    axes[0].axhline(y=1.0, color='b', linestyle='--', alpha=0.3, label='Max (1.0)')
    axes[0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.3, label='Neutral (0.5)')
    axes[0].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[0].set_ylabel('Completion Factor', fontsize=11)
    axes[0].set_title('Completion Factor vs Completion %\n(Full Completion = Max Score)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 1.1)
    axes[0].set_xlim(0, 100)
    
    # Add region labels
    axes[0].text(25, 0.25, 'Low\n(<50%)\nSignificant penalty', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    axes[0].text(70, 0.7, 'Partial\n(50-90%)\nModerate penalty', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    axes[0].text(95, 0.95, 'Near-Complete\n(90-100%)\nSlight penalty', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    axes[0].text(100, 1.0, 'Full\n(100%)\nFactor = 1.0', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='green', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('Low (25%)', 25, 'Only 25% completed'),
        ('Partial (60%)', 60, '60% completed'),
        ('Near-Complete (95%)', 95, '95% completed'),
        ('Full (100%)', 100, '100% completed'),
    ]
    
    scenario_names = [s[0] for s in scenarios]
    scenario_percentages = [s[1] for s in scenarios]
    scenario_factors = [calculate_completion_factor(s[1]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    bars = axes[1].bar(x_pos, scenario_factors, color=['red', 'orange', 'yellow', 'green'], alpha=0.7)
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Completion Factor', fontsize=11)
    axes[1].set_title('Completion Factor: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0, 1.1)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, factor, scenario) in enumerate(zip(bars, scenario_factors, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{factor:.2f}\n{scenario[2]}',
                    ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.suptitle('Execution Score: Completion Factor Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


# Mapping of script names to generator functions
GRAPHIC_AID_GENERATORS = {
    'execution_score_difficulty_factor.py': generate_difficulty_factor_image,
    'execution_score_speed_factor.py': generate_speed_factor_image,
    'execution_score_start_speed_factor.py': generate_start_speed_factor_image,
    'execution_score_completion_factor.py': generate_completion_factor_image,
}


def generate_all_images():
    """Generate all graphic aid images."""
    results = {}
    for script_name, generator_func in GRAPHIC_AID_GENERATORS.items():
        try:
            image_path = generator_func()
            results[script_name] = {'status': 'success', 'path': image_path}
            print(f"[PASS] Generated: {image_path}")
        except Exception as e:
            results[script_name] = {'status': 'error', 'error': str(e)}
            print(f"[FAIL] Error generating {script_name}: {e}")
    return results


if __name__ == '__main__':
    generate_all_images()

