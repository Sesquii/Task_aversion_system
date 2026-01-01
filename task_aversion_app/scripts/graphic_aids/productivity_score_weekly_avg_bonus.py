#!/usr/bin/env python3
"""
Graphic Aid: Productivity Score - Efficiency Bonus/Penalty

Visualizes how efficiency (based on task estimate and completion percentage) affects productivity score.
Shows both linear and flattened_square curve types.
Efficiency ratio = (completion_pct * time_estimate) / (100 * time_actual)
"""

import matplotlib.pyplot as plt
import numpy as np
import os
import math

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def calculate_efficiency_multiplier(efficiency_ratio, curve_type='flattened_square', strength=1.0):
    """Calculate efficiency multiplier based on completion_time_ratio.
    
    Args:
        efficiency_ratio: (completion_pct * time_estimate) / (100 * time_actual)
        curve_type: 'linear' or 'flattened_square'
        strength: Strength of the adjustment (0.0-2.0)
    
    Returns:
        Efficiency multiplier (capped at 0.5 minimum)
    """
    efficiency_percentage_diff = (efficiency_ratio - 1.0) * 100.0
    
    if curve_type == 'flattened_square':
        # Invert: positive diff (efficient) should give bonus, negative (inefficient) should give penalty
        effect = math.copysign((abs(efficiency_percentage_diff) ** 2) / 100.0, efficiency_percentage_diff)
        multiplier = 1.0 - (0.01 * strength * -effect)
    else:  # linear
        # Invert: positive diff (efficient) should give bonus, negative (inefficient) should give penalty
        multiplier = 1.0 - (0.01 * strength * -efficiency_percentage_diff)
    
    # Cap both penalty and bonus to prevent extreme scores
    # Penalty: max 50% reduction (min multiplier = 0.5)
    # Bonus: max 50% increase (max multiplier = 1.5)
    return max(0.5, min(1.5, multiplier))


def generate_weekly_avg_bonus_image(output_path=None):
    """Generate efficiency bonus visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_weekly_avg_bonus.png')
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Multiplier vs Efficiency Ratio (both curve types)
    # Efficiency ratio range: 0.25 to 2.0 (0.25 = very inefficient, 2.0 = very efficient)
    efficiency_ratios = np.linspace(0.25, 2.0, 200)
    linear_multipliers = [calculate_efficiency_multiplier(r, 'linear', 1.0) for r in efficiency_ratios]
    square_multipliers = [calculate_efficiency_multiplier(r, 'flattened_square', 1.0) for r in efficiency_ratios]
    
    axes[0].plot(efficiency_ratios, linear_multipliers, 'b-', linewidth=2, label='Linear', alpha=0.7)
    axes[0].plot(efficiency_ratios, square_multipliers, 'r-', linewidth=2, label='Flattened Square', alpha=0.7)
    axes[0].axvline(x=1.0, color='gray', linestyle='--', alpha=0.5, label='Perfect Efficiency (1.0)')
    axes[0].axhline(y=1.0, color='green', linestyle='--', alpha=0.5, label='No Change (1.0x)')
    axes[0].set_xlabel('Efficiency Ratio\n(completion_pct × estimate) / (100 × actual)', fontsize=11)
    axes[0].set_ylabel('Efficiency Multiplier', fontsize=11)
    axes[0].set_title('Efficiency Multiplier vs Ratio\n(>1.0 = Bonus, <1.0 = Penalty)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0.25, 2.0)
    axes[0].set_ylim(0.5, 1.5)
    
    # Plot 2: Effect of strength parameter
    efficiency_ratios_2 = np.linspace(0.5, 1.5, 200)
    strengths = [0.5, 1.0, 1.5, 2.0]
    colors = ['lightblue', 'blue', 'darkblue', 'purple']
    
    for strength, color in zip(strengths, colors):
        multipliers = [calculate_efficiency_multiplier(r, 'flattened_square', strength) for r in efficiency_ratios_2]
        axes[1].plot(efficiency_ratios_2, multipliers, color=color, linewidth=2, label=f'Strength: {strength}', alpha=0.7)
    
    axes[1].axvline(x=1.0, color='gray', linestyle='--', alpha=0.5)
    axes[1].axhline(y=1.0, color='green', linestyle='--', alpha=0.5)
    axes[1].set_xlabel('Efficiency Ratio', fontsize=11)
    axes[1].set_ylabel('Efficiency Multiplier', fontsize=11)
    axes[1].set_title('Effect of Strength Parameter\n(Flattened Square Curve)', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_xlim(0.5, 1.5)
    axes[1].set_ylim(0.5, 1.5)
    
    # Plot 3: Example scenarios (showing how completion % affects efficiency)
    # Fixed time estimate of 30 minutes
    time_estimate = 30
    scenarios = [
        ('2x time, 200% done', 60, 200, 'Took 2x longer but completed 200%'),
        ('1.5x time, 150% done', 45, 150, 'Took 1.5x longer, completed 150%'),
        ('On estimate, 100%', 30, 100, 'Perfect: estimate time, 100% done'),
        ('0.75x time, 100% done', 22.5, 100, 'Faster than estimate, 100% done'),
        ('2x time, 100% done', 60, 100, 'Took 2x longer, only 100% done'),
    ]
    
    scenario_ratios = []
    scenario_multipliers = []
    for name, time_actual, completion_pct, desc in scenarios:
        efficiency_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
        multiplier = calculate_efficiency_multiplier(efficiency_ratio, 'flattened_square', 1.0)
        scenario_ratios.append(efficiency_ratio)
        scenario_multipliers.append(multiplier)
    
    x_pos = np.arange(len(scenarios))
    bars = axes[2].bar(x_pos, scenario_multipliers, color=['darkgreen', 'green', 'yellow', 'lightgreen', 'red'], alpha=0.7)
    axes[2].set_xlabel('Scenario', fontsize=11)
    axes[2].set_ylabel('Efficiency Multiplier', fontsize=11)
    axes[2].set_title('Efficiency Multiplier: Example Scenarios\n(Estimate: 30min, Flattened Square, Strength=1.0)', fontsize=12, fontweight='bold')
    axes[2].set_xticks(x_pos)
    axes[2].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right', fontsize=8)
    axes[2].set_ylim(0.5, 1.5)
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    
    # Add value labels on bars
    for i, (bar, mult, ratio, scenario) in enumerate(zip(bars, scenario_multipliers, scenario_ratios, scenarios)):
        height = bar.get_height()
        axes[2].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{mult:.3f}x\nratio: {ratio:.2f}',
                    ha='center', va='bottom', fontsize=7)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Efficiency Bonus/Penalty Component\n(Based on Task Estimate & Completion %)', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_weekly_avg_bonus_image()
    print("[PASS] Generated: productivity_score_weekly_avg_bonus.png")
