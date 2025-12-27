#!/usr/bin/env python3
"""
Graphic Aid: Productivity Score - Goal-Based Adjustment

Visualizes how goal achievement ratio affects productivity score multiplier.
Shows the piecewise linear function with different regions.
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


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


def generate_goal_adjustment_image(output_path=None):
    """Generate goal adjustment visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_goal_adjustment.png')
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Multiplier vs Goal Achievement Ratio
    ratio_range = np.linspace(0, 1.5, 300)
    multipliers = [calculate_goal_multiplier(r) for r in ratio_range]
    
    axes[0].plot(ratio_range, multipliers, 'purple', linewidth=2, label='Goal Multiplier')
    axes[0].axvline(x=0.8, color='orange', linestyle='--', alpha=0.5, label='80% Goal')
    axes[0].axvline(x=1.0, color='green', linestyle='--', alpha=0.5, label='100% Goal')
    axes[0].axvline(x=1.2, color='darkgreen', linestyle='--', alpha=0.5, label='120% Goal')
    axes[0].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='No Change (1.0x)')
    axes[0].set_xlabel('Goal Achievement Ratio (actual / goal)', fontsize=11)
    axes[0].set_ylabel('Goal Multiplier', fontsize=11)
    axes[0].set_title('Goal Multiplier vs Achievement Ratio\n(Above goal = Bonus, Below = Penalty)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 1.5)
    axes[0].set_ylim(0.75, 1.25)
    
    # Add region labels
    axes[0].text(0.4, 0.85, '<80%\nPenalty\n0.8-0.9x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    axes[0].text(0.9, 0.95, '80-100%\nRecovery\n0.9-1.0x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    axes[0].text(1.1, 1.1, '100-120%\nBonus\n1.0-1.2x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    axes[0].text(1.35, 1.2, '≥120%\nMax Bonus\n1.2x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='green', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('50% Goal', 0.5, 'Half of goal achieved'),
        ('80% Goal', 0.8, '80% of goal achieved'),
        ('100% Goal', 1.0, 'Goal exactly met'),
        ('110% Goal', 1.1, '10% above goal'),
        ('130% Goal', 1.3, '30% above goal'),
    ]
    
    scenario_ratios = [s[1] for s in scenarios]
    scenario_multipliers = [calculate_goal_multiplier(s[1]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    bars = axes[1].bar(x_pos, scenario_multipliers, color=['red', 'orange', 'green', 'lightgreen', 'darkgreen'], alpha=0.7)
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Goal Multiplier', fontsize=11)
    axes[1].set_title('Goal Multiplier: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0.75, 1.25)
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    
    # Add value labels on bars
    for i, (bar, mult, scenario) in enumerate(zip(bars, scenario_multipliers, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{mult:.3f}x\n{scenario[2]}',
                    ha='center', va='bottom', fontsize=8)
    
    # Plot 3: Impact on final score (assuming baseline score of 300)
    baseline_score = 300.0
    ratio_range_2 = np.linspace(0, 1.5, 300)
    final_scores = [baseline_score * calculate_goal_multiplier(r) for r in ratio_range_2]
    
    axes[2].plot(ratio_range_2, final_scores, 'purple', linewidth=2, label='Final Score (baseline=300)')
    axes[2].axvline(x=1.0, color='green', linestyle='--', alpha=0.5, label='100% Goal')
    axes[2].axhline(y=baseline_score, color='gray', linestyle='--', alpha=0.5, label='Baseline (300)')
    axes[2].set_xlabel('Goal Achievement Ratio', fontsize=11)
    axes[2].set_ylabel('Final Score', fontsize=11)
    axes[2].set_title('Final Score Impact\n(Baseline = 300)', fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()
    axes[2].set_xlim(0, 1.5)
    axes[2].set_ylim(225, 375)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Goal-Based Adjustment Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_goal_adjustment_image()
    print("[PASS] Generated: productivity_score_goal_adjustment.png")
