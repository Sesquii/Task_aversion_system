#!/usr/bin/env python3
"""
Graphic Aid: Thoroughness Factor - Note Length Bonus Component

Visualizes how note length bonus is calculated using exponential decay.
Shows the diminishing returns curve: length_bonus = 0.3 * (1 - exp(-length_ratio * 2.0))
"""

import matplotlib.pyplot as plt
import numpy as np
import math
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def calculate_length_bonus(avg_note_length):
    """Calculate note length bonus using exponential decay formula."""
    # Scale: 0-500 chars maps to 0.0-0.3 bonus
    length_ratio = min(1.0, avg_note_length / 500.0)
    length_bonus = 0.3 * (1.0 - math.exp(-length_ratio * 2.0))
    return length_bonus


def generate_note_length_image(output_path=None):
    """Generate note length bonus visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'thoroughness_note_length.png')
    
    # Create figure with 2 subplots
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Length Bonus vs Average Note Length
    note_length_range = np.linspace(0, 1000, 200)  # 0 to 1000 characters
    length_bonuses = [calculate_length_bonus(length) for length in note_length_range]
    
    axes[0].plot(note_length_range, length_bonuses, 'b-', linewidth=2, label='Length Bonus')
    axes[0].axhline(y=0.3, color='g', linestyle='--', alpha=0.5, label='Max Bonus (0.3)')
    axes[0].axvline(x=500, color='orange', linestyle='--', alpha=0.5, label='Target (500 chars)')
    axes[0].set_xlabel('Average Note Length (characters)', fontsize=11)
    axes[0].set_ylabel('Length Bonus', fontsize=11)
    axes[0].set_title('Length Bonus vs Note Length\n(Exponential Decay)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 1000)
    axes[0].set_ylim(0, 0.35)
    
    # Add example points
    example_points = [
        (0, 0.0, 'No Notes'),
        (100, calculate_length_bonus(100), '100 chars'),
        (250, calculate_length_bonus(250), '250 chars'),
        (500, calculate_length_bonus(500), '500 chars (Target)'),
        (750, calculate_length_bonus(750), '750 chars'),
        (1000, calculate_length_bonus(1000), '1000 chars'),
    ]
    
    for length, bonus, label in example_points:
        axes[0].plot(length, bonus, 'ro', markersize=8)
        axes[0].annotate(f'{label}\nBonus: {bonus:.3f}', 
                        xy=(length, bonus), xytext=(5, 5), 
                        textcoords='offset points', fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    
    # Plot 2: Bonus distribution showing diminishing returns
    length_levels = [0, 100, 250, 500, 750, 1000]
    bonus_levels = [calculate_length_bonus(l) for l in length_levels]
    
    x_pos = np.arange(len(length_levels))
    colors = plt.cm.viridis(np.linspace(0, 1, len(length_levels)))
    
    bars = axes[1].bar(x_pos, bonus_levels, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    axes[1].axhline(y=0.3, color='g', linestyle='--', alpha=0.5, label='Maximum (0.3)')
    axes[1].set_xlabel('Average Note Length (characters)', fontsize=11)
    axes[1].set_ylabel('Length Bonus', fontsize=11)
    axes[1].set_title('Length Bonus by Note Length\n(Diminishing Returns)', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([f'{l}' for l in length_levels])
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].set_ylim(0, 0.35)
    
    # Add value labels on bars
    for i, bonus in enumerate(bonus_levels):
        axes[1].text(i, bonus + 0.01, f'{bonus:.3f}', ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Add annotation about diminishing returns
    axes[1].text(0.5, 0.25, 'Note: Bonus approaches 0.3\nbut never exceeds it\n(diminishing returns)', 
                transform=axes[1].transAxes, fontsize=9, 
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.7),
                ha='center')
    
    plt.tight_layout()
    plt.suptitle('Thoroughness Factor: Note Length Bonus Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_note_length_image()
    print("[PASS] Generated: thoroughness_note_length.png")
    print("[INFO] Length bonus ranges from 0.0 (no notes) to 0.3 (500+ chars)")
    print("[INFO] Formula: length_bonus = 0.3 * (1 - exp(-length_ratio * 2.0))")
    print("[INFO] Uses exponential decay for smooth diminishing returns")
