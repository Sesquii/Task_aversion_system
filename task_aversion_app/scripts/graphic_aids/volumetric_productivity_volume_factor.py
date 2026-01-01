#!/usr/bin/env python3
"""
Graphic Aid: Volumetric Productivity Score - Volume Factor Component

Visualizes volume factor calculation: 0.5x to 1.5x multiplier based on work volume score.
Shows how volume score (0-100) maps to volume multiplier.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def calculate_volume_multiplier(work_volume_score):
    """Calculate volume multiplier from work volume score."""
    return 0.5 + (work_volume_score / 100.0) * 1.0


def generate_volume_factor_image(output_path=None):
    """Generate volume factor visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'volumetric_productivity_volume_factor.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Volume multiplier vs work volume score
    volume_score_range = np.linspace(0, 100, 100)
    multipliers = [calculate_volume_multiplier(v) for v in volume_score_range]
    
    axes[0].plot(volume_score_range, multipliers, 'b-', linewidth=3, label='Volume Multiplier')
    axes[0].axvline(x=0, color='red', linestyle='--', alpha=0.5, label='No Volume (0.5x)')
    axes[0].axvline(x=50, color='orange', linestyle='--', alpha=0.5, label='Moderate Volume (1.0x)')
    axes[0].axvline(x=100, color='green', linestyle='--', alpha=0.5, label='High Volume (1.5x)')
    axes[0].axhline(y=0.5, color='red', linestyle=':', alpha=0.3, label='Min (0.5x)')
    axes[0].axhline(y=1.0, color='gray', linestyle=':', alpha=0.3, label='Neutral (1.0x)')
    axes[0].axhline(y=1.5, color='green', linestyle=':', alpha=0.3, label='Max (1.5x)')
    axes[0].set_xlabel('Work Volume Score (0-100)', fontsize=11)
    axes[0].set_ylabel('Volume Multiplier (0.5x - 1.5x)', fontsize=11)
    axes[0].set_title('Volume Multiplier vs Work Volume Score\n(Linear Mapping)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0.4, 1.6)
    axes[0].set_xlim(0, 100)
    
    # Add region labels
    axes[0].text(25, 0.75, 'Low Volume\n(0-50 score)\n0.5x - 1.0x\n(Penalty)', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    axes[0].text(75, 1.25, 'High Volume\n(50-100 score)\n1.0x - 1.5x\n(Bonus)', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('No Volume (0)', 0, 0.5, 'No work = 50% penalty'),
        ('Low Volume (25)', 25, 0.75, '2 hours/day = 25% penalty'),
        ('Moderate (50)', 50, 1.0, '4 hours/day = neutral'),
        ('Good (75)', 75, 1.25, '6 hours/day = 25% bonus'),
        ('High (100)', 100, 1.5, '8+ hours/day = 50% bonus'),
    ]
    
    scenario_names = [s[0] for s in scenarios]
    scenario_multipliers = [s[2] for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    colors = ['red', 'orange', 'yellow', 'lightgreen', 'green']
    bars = axes[1].bar(x_pos, scenario_multipliers, color=colors, alpha=0.7, edgecolor='black')
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Volume Multiplier', fontsize=11)
    axes[1].set_title('Volume Multiplier: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0.4, 1.6)
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Neutral (1.0x)')
    
    # Add value labels on bars
    for i, (bar, mult, scenario) in enumerate(zip(bars, scenario_multipliers, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{mult:.2f}x\n{scenario[3]}',
                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.suptitle('Volumetric Productivity Score: Volume Factor Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_volume_factor_image()

