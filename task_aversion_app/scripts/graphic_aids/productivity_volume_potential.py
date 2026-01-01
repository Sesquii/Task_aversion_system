#!/usr/bin/env python3
"""
Graphic Aid: Productivity Volume - Productivity Potential Component

Visualizes productivity potential calculation: efficiency × target hours.
Shows gap between current and potential productivity.
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


def generate_potential_image(output_path=None):
    """Generate productivity potential visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_volume_potential.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Potential vs current work time (fixed efficiency)
    efficiency = 50.0  # Example efficiency score
    target_hours = 6.0  # Target: 6 hours/day
    work_time_range = np.linspace(1, 8, 100)  # 1 to 8 hours
    
    current_scores = [efficiency * (wt / 60.0) * 60.0 for wt in work_time_range]  # Convert to hours
    potential_scores = [efficiency * target_hours for _ in work_time_range]
    gaps = [target_hours - wt/60.0 for wt in work_time_range]
    
    axes[0].plot(work_time_range / 60, current_scores, 'b-', linewidth=3, label=f'Current Score (efficiency={efficiency})')
    axes[0].plot(work_time_range / 60, potential_scores, 'g--', linewidth=2, label=f'Potential Score (target={target_hours}h)')
    axes[0].fill_between(work_time_range / 60, current_scores, potential_scores, alpha=0.3, color='yellow', label='Gap')
    axes[0].axvline(x=target_hours, color='green', linestyle=':', alpha=0.5, label=f'Target ({target_hours}h)')
    axes[0].set_xlabel('Current Daily Work Time (hours)', fontsize=11)
    axes[0].set_ylabel('Productivity Score', fontsize=11)
    axes[0].set_title('Productivity Potential vs Current Work Time\n(Potential = Efficiency × Target Hours)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(1, 8)
    
    # Add annotation
    axes[0].annotate('Gap: Hours needed\nto reach target', 
                    xy=(3, efficiency * 3), xytext=(4.5, efficiency * 4.5),
                    arrowprops=dict(arrowstyle='->', color='red', lw=2),
                    fontsize=10, bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    # Plot 2: Potential multiplier vs current work time
    multipliers = [target_hours / max(wt/60.0, 0.1) for wt in work_time_range]
    
    axes[1].plot(work_time_range / 60, multipliers, 'purple', linewidth=3, label='Potential Multiplier')
    axes[1].axvline(x=target_hours, color='green', linestyle='--', alpha=0.5, label=f'Target ({target_hours}h)')
    axes[1].axhline(y=1.0, color='gray', linestyle=':', alpha=0.3, label='No Gap (1.0x)')
    axes[1].set_xlabel('Current Daily Work Time (hours)', fontsize=11)
    axes[1].set_ylabel('Potential Multiplier', fontsize=11)
    axes[1].set_title('Potential Multiplier vs Current Work Time\n(How much more you could achieve)', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_xlim(1, 8)
    axes[1].set_ylim(0.5, 6)
    
    # Add example points
    example_times = [2, 4, 6, 8]
    example_multipliers = [target_hours / t for t in example_times]
    for t, m in zip(example_times, example_multipliers):
        axes[1].plot(t, m, 'ro', markersize=10)
        axes[1].annotate(f'{t}h → {m:.1f}x', 
                        xy=(t, m), xytext=(10, 10), 
                        textcoords='offset points', fontsize=9,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.suptitle('Productivity Volume: Productivity Potential Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_potential_image()

