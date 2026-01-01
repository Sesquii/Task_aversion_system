#!/usr/bin/env python3
"""
Graphic Aid: Productivity Score - Work Task Multiplier

Visualizes how completion/time ratio affects work task multiplier (3.0x to 5.0x).
Shows the smooth transition between ratio thresholds.
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def calculate_work_multiplier(completion_time_ratio):
    """Calculate work task multiplier based on completion/time ratio."""
    if completion_time_ratio <= 1.0:
        return 3.0
    elif completion_time_ratio >= 1.5:
        return 5.0
    else:
        # Smooth transition between 1.0 and 1.5
        smooth_factor = (completion_time_ratio - 1.0) / 0.5
        return 3.0 + (2.0 * smooth_factor)


def generate_work_multiplier_image(output_path=None):
    """Generate work multiplier visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_work_multiplier.png')
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Plot 1: Multiplier vs Completion/Time Ratio
    ratio_range = np.linspace(0.5, 2.0, 200)
    multipliers = [calculate_work_multiplier(r) for r in ratio_range]
    
    axes[0].plot(ratio_range, multipliers, 'b-', linewidth=2, label='Work Multiplier')
    axes[0].axvline(x=1.0, color='r', linestyle='--', alpha=0.5, label='Efficient (1.0)')
    axes[0].axvline(x=1.5, color='orange', linestyle='--', alpha=0.5, label='Very Efficient (1.5)')
    axes[0].axhline(y=3.0, color='gray', linestyle='--', alpha=0.3, label='Base (3.0x)')
    axes[0].axhline(y=5.0, color='green', linestyle='--', alpha=0.3, label='Max (5.0x)')
    axes[0].set_xlabel('Completion/Time Ratio', fontsize=11)
    axes[0].set_ylabel('Work Multiplier', fontsize=11)
    axes[0].set_title('Work Multiplier vs Completion/Time Ratio\n(Higher ratio = More efficient)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0.5, 2.0)
    axes[0].set_ylim(2.5, 5.5)
    
    # Add region labels
    axes[0].text(0.75, 3.2, 'Base\n(≤1.0)\n3.0x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
    axes[0].text(1.25, 4.0, 'Transition\n(1.0-1.5)\n3.0x → 5.0x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    axes[0].text(1.75, 5.2, 'Max\n(≥1.5)\n5.0x', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    
    # Plot 2: Example scenarios with different ratios
    scenarios = [
        ('Slow (0.8x)', 0.8, 'Took longer than estimated'),
        ('On Time (1.0x)', 1.0, 'Completed as estimated'),
        ('Efficient (1.2x)', 1.2, 'Completed faster'),
        ('Very Efficient (1.5x)', 1.5, 'Completed much faster'),
        ('Extremely Efficient (2.0x)', 2.0, 'Completed very fast'),
    ]
    
    scenario_ratios = [s[1] for s in scenarios]
    scenario_multipliers = [calculate_work_multiplier(s[1]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    bars = axes[1].bar(x_pos, scenario_multipliers, color=['red', 'yellow', 'lightgreen', 'green', 'darkgreen'], alpha=0.7)
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Work Multiplier', fontsize=11)
    axes[1].set_title('Work Multiplier: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(2.5, 5.5)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, mult, scenario) in enumerate(zip(bars, scenario_multipliers, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.05,
                    f'{mult:.2f}x\n{scenario[2]}',
                    ha='center', va='bottom', fontsize=8)
    
    # Plot 3: Final score impact (completion_pct × multiplier)
    completion_pct = 100.0
    ratio_range_2 = np.linspace(0.5, 2.0, 200)
    final_scores = [completion_pct * calculate_work_multiplier(r) for r in ratio_range_2]
    
    axes[2].plot(ratio_range_2, final_scores, 'purple', linewidth=2, label='Final Score (100% completion)')
    axes[2].axvline(x=1.0, color='r', linestyle='--', alpha=0.5, label='Efficient (1.0)')
    axes[2].axvline(x=1.5, color='orange', linestyle='--', alpha=0.5, label='Very Efficient (1.5)')
    axes[2].set_xlabel('Completion/Time Ratio', fontsize=11)
    axes[2].set_ylabel('Final Baseline Score', fontsize=11)
    axes[2].set_title('Final Score vs Ratio\n(100% completion)', fontsize=12, fontweight='bold')
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()
    axes[2].set_xlim(0.5, 2.0)
    axes[2].set_ylim(250, 550)
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Work Task Multiplier Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_work_multiplier_image()
    print("[PASS] Generated: productivity_score_work_multiplier.png")
