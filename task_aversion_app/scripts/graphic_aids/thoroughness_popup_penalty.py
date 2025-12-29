#!/usr/bin/env python3
"""
Graphic Aid: Thoroughness Factor - Popup Penalty Component

Visualizes how popup penalty is calculated based on frequency of no-slider popups.
Shows the exponential decay penalty curve: popup_penalty = -0.2 * (1 - exp(-popup_ratio * 2.0))
"""

import matplotlib.pyplot as plt
import numpy as np
import math
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def calculate_popup_penalty(popup_count):
    """Calculate popup penalty using exponential decay formula."""
    # Scale: 0-10 popups maps to 0.0 to -0.2 penalty
    popup_ratio = min(1.0, popup_count / 10.0)
    popup_penalty = -0.2 * (1.0 - math.exp(-popup_ratio * 2.0))
    return popup_penalty


def generate_popup_penalty_image(output_path=None):
    """Generate popup penalty visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'thoroughness_popup_penalty.png')
    
    # Create figure with 2 subplots
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Popup Penalty vs Popup Count
    popup_count_range = np.linspace(0, 20, 200)  # 0 to 20 popups
    popup_penalties = [calculate_popup_penalty(count) for count in popup_count_range]
    
    axes[0].plot(popup_count_range, popup_penalties, 'r-', linewidth=2, label='Popup Penalty')
    axes[0].axhline(y=0.0, color='g', linestyle='--', alpha=0.5, label='No Penalty (0.0)')
    axes[0].axhline(y=-0.2, color='r', linestyle='--', alpha=0.5, label='Max Penalty (-0.2)')
    axes[0].axvline(x=10, color='orange', linestyle='--', alpha=0.5, label='Max Penalty Threshold (10 popups)')
    axes[0].set_xlabel('Popup Count (Last 30 Days)', fontsize=11)
    axes[0].set_ylabel('Popup Penalty', fontsize=11)
    axes[0].set_title('Popup Penalty vs Popup Count\n(Exponential Decay Penalty)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 20)
    axes[0].set_ylim(-0.25, 0.05)
    
    # Add example points
    example_points = [
        (0, 0.0, 'No Popups'),
        (2, calculate_popup_penalty(2), '2 Popups'),
        (5, calculate_popup_penalty(5), '5 Popups'),
        (10, calculate_popup_penalty(10), '10 Popups (Max)'),
        (15, calculate_popup_penalty(15), '15 Popups'),
        (20, calculate_popup_penalty(20), '20 Popups'),
    ]
    
    for count, penalty, label in example_points:
        axes[0].plot(count, penalty, 'ro', markersize=8)
        axes[0].annotate(f'{label}\nPenalty: {penalty:.3f}', 
                        xy=(count, penalty), xytext=(5, -5), 
                        textcoords='offset points', fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    
    # Plot 2: Penalty distribution showing impact
    popup_levels = [0, 2, 5, 10, 15, 20]
    penalty_levels = [calculate_popup_penalty(c) for c in popup_levels]
    
    x_pos = np.arange(len(popup_levels))
    colors = ['green', 'lightgreen', 'yellow', 'orange', 'red', 'darkred']
    
    bars = axes[1].bar(x_pos, penalty_levels, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    axes[1].axhline(y=0.0, color='g', linestyle='--', alpha=0.5, label='No Penalty (0.0)')
    axes[1].axhline(y=-0.2, color='r', linestyle='--', alpha=0.5, label='Maximum (-0.2)')
    axes[1].set_xlabel('Popup Count (Last 30 Days)', fontsize=11)
    axes[1].set_ylabel('Popup Penalty', fontsize=11)
    axes[1].set_title('Popup Penalty by Count\n(Negative Impact)', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([f'{c}' for c in popup_levels])
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].set_ylim(-0.25, 0.05)
    
    # Add value labels on bars
    for i, penalty in enumerate(penalty_levels):
        axes[1].text(i, penalty - 0.01, f'{penalty:.3f}', ha='center', va='top', fontsize=9, fontweight='bold')
    
    # Add annotation about penalty
    axes[1].text(0.5, 0.15, 'Penalty reduces thoroughness factor\n10+ popups = maximum penalty (-0.2)\nFewer popups = better tracking', 
                transform=axes[1].transAxes, fontsize=9, 
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.7),
                ha='center')
    
    plt.tight_layout()
    plt.suptitle('Thoroughness Factor: Popup Penalty Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_popup_penalty_image()
    print("[PASS] Generated: thoroughness_popup_penalty.png")
    print("[INFO] Popup penalty ranges from 0.0 (no popups) to -0.2 (10+ popups)")
    print("[INFO] Formula: popup_penalty = -0.2 * (1 - exp(-popup_ratio * 2.0))")
    print("[INFO] Uses exponential decay for smooth penalty curve")
