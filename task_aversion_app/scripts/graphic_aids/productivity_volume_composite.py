#!/usr/bin/env python3
"""
Graphic Aid: Productivity Volume - Composite Productivity Score Component

Visualizes composite productivity score: 40% efficiency + 40% volume + 20% consistency.
Shows how different combinations affect the final score.
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


def calculate_composite(efficiency, volume, consistency):
    """Calculate composite productivity score."""
    normalized_efficiency = min(100.0, efficiency / 2.0) if efficiency > 0 else 0.0
    return (normalized_efficiency * 0.4) + (volume * 0.4) + (consistency * 0.2)


def generate_composite_image(output_path=None):
    """Generate composite productivity score visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_volume_composite.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Composite score vs volume (fixed efficiency and consistency)
    efficiency = 100.0  # Example efficiency
    consistency = 75.0  # Example consistency
    volume_range = np.linspace(0, 100, 100)
    composite_scores = [calculate_composite(efficiency, v, consistency) for v in volume_range]
    
    axes[0].plot(volume_range, composite_scores, 'b-', linewidth=3, label='Composite Score')
    axes[0].axvline(x=50, color='orange', linestyle='--', alpha=0.5, label='Moderate Volume (50)')
    axes[0].axvline(x=75, color='green', linestyle='--', alpha=0.5, label='High Volume (75)')
    axes[0].axhline(y=50, color='gray', linestyle=':', alpha=0.3, label='Baseline (50)')
    axes[0].set_xlabel('Work Volume Score (0-100)', fontsize=11)
    axes[0].set_ylabel('Composite Productivity Score', fontsize=11)
    axes[0].set_title(f'Composite Score vs Volume\n(Efficiency={efficiency}, Consistency={consistency})', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 105)
    axes[0].set_xlim(0, 100)
    
    # Add formula annotation
    axes[0].text(50, 80, 'Formula:\n0.4×efficiency +\n0.4×volume +\n0.2×consistency', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('High All', 100, 100, 100, 'High efficiency, volume, consistency'),
        ('High Eff, Low Vol', 100, 30, 80, 'Efficient but low volume'),
        ('Low Eff, High Vol', 50, 80, 70, 'High volume but less efficient'),
        ('Balanced', 75, 60, 65, 'Moderate across all'),
        ('Low All', 40, 30, 50, 'Low across all metrics'),
    ]
    
    scenario_names = [s[0] for s in scenarios]
    scenario_scores = [calculate_composite(s[1], s[2], s[3]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    colors = ['green', 'yellow', 'orange', 'lightblue', 'red']
    bars = axes[1].bar(x_pos, scenario_scores, color=colors, alpha=0.7, edgecolor='black')
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Composite Score', fontsize=11)
    axes[1].set_title('Composite Score: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0, 105)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, score, scenario) in enumerate(zip(bars, scenario_scores, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 2,
                    f'{score:.1f}\n{scenario[4]}',
                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.suptitle('Productivity Volume: Composite Productivity Score Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_composite_image()

