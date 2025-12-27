#!/usr/bin/env python3
"""
Graphic Aid: Productivity Score - Weekly Average Bonus/Penalty

Visualizes how deviation from weekly average affects productivity score.
Shows both linear and flattened_square curve types.
"""

import matplotlib.pyplot as plt
import numpy as np
import os
import math

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def calculate_weekly_multiplier(time_percentage_diff, curve_type='flattened_square', strength=1.0):
    """Calculate weekly average multiplier."""
    if curve_type == 'flattened_square':
        effect = math.copysign((abs(time_percentage_diff) ** 2) / 100.0, time_percentage_diff)
        multiplier = 1.0 - (0.01 * strength * effect)
    else:  # linear
        multiplier = 1.0 - (0.01 * strength * time_percentage_diff)
    return max(0.5, min(1.5, multiplier))  # Cap at reasonable range


def generate_weekly_avg_bonus_image(output_path=None):
    """Generate weekly average bonus visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_weekly_avg_bonus.png')
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Multiplier vs Percentage Deviation (both curve types)
    deviation_range = np.linspace(-100, 100, 200)
    linear_multipliers = [calculate_weekly_multiplier(d, 'linear', 1.0) for d in deviation_range]
    square_multipliers = [calculate_weekly_multiplier(d, 'flattened_square', 1.0) for d in deviation_range]
    
    axes[0].plot(deviation_range, linear_multipliers, 'b-', linewidth=2, label='Linear', alpha=0.7)
    axes[0].plot(deviation_range, square_multipliers, 'r-', linewidth=2, label='Flattened Square', alpha=0.7)
    axes[0].axvline(x=0, color='gray', linestyle='--', alpha=0.5, label='Average (0%)')
    axes[0].axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='No Change (1.0x)')
    axes[0].set_xlabel('Percentage Deviation from Weekly Average (%)', fontsize=11)
    axes[0].set_ylabel('Weekly Multiplier', fontsize=11)
    axes[0].set_title('Weekly Multiplier vs Deviation\n(Faster = Bonus, Slower = Penalty)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(-100, 100)
    axes[0].set_ylim(0.5, 1.5)
    
    # Plot 2: Effect of strength parameter
    deviation_range_2 = np.linspace(-50, 50, 200)
    strengths = [0.5, 1.0, 1.5, 2.0]
    colors = ['lightblue', 'blue', 'darkblue', 'purple']
    
    for strength, color in zip(strengths, colors):
        multipliers = [calculate_weekly_multiplier(d, 'flattened_square', strength) for d in deviation_range_2]
        axes[1].plot(deviation_range_2, multipliers, color=color, linewidth=2, label=f'Strength: {strength}', alpha=0.7)
    
    axes[1].axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    axes[1].axhline(y=1.0, color='green', linestyle='--', alpha=0.5)
    axes[1].set_xlabel('Percentage Deviation (%)', fontsize=11)
    axes[1].set_ylabel('Weekly Multiplier', fontsize=11)
    axes[1].set_title('Effect of Strength Parameter\n(Flattened Square Curve)', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_xlim(-50, 50)
    axes[1].set_ylim(0.5, 1.5)
    
    # Plot 3: Example scenarios
    scenarios = [
        ('50% Faster', -50, 'Completed in half the average time'),
        ('25% Faster', -25, 'Completed 25% faster'),
        ('On Average', 0, 'Completed at average time'),
        ('25% Slower', 25, 'Completed 25% slower'),
        ('50% Slower', 50, 'Completed 50% slower'),
    ]
    
    scenario_deviations = [s[1] for s in scenarios]
    scenario_multipliers = [calculate_weekly_multiplier(s[1], 'flattened_square', 1.0) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    bars = axes[2].bar(x_pos, scenario_multipliers, color=['darkgreen', 'green', 'yellow', 'orange', 'red'], alpha=0.7)
    axes[2].set_xlabel('Scenario', fontsize=11)
    axes[2].set_ylabel('Weekly Multiplier', fontsize=11)
    axes[2].set_title('Weekly Multiplier: Example Scenarios\n(Flattened Square, Strength=1.0)', fontsize=12, fontweight='bold')
    axes[2].set_xticks(x_pos)
    axes[2].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[2].set_ylim(0.5, 1.5)
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    
    # Add value labels on bars
    for i, (bar, mult, scenario) in enumerate(zip(bars, scenario_multipliers, scenarios)):
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{mult:.3f}x\n{scenario[2]}',
                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Weekly Average Bonus/Penalty Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_weekly_avg_bonus_image()
    print("[PASS] Generated: productivity_score_weekly_avg_bonus.png")
