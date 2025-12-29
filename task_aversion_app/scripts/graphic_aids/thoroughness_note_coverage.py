#!/usr/bin/env python3
"""
Graphic Aid: Thoroughness Factor - Note Coverage Component

Visualizes how the base factor scales with note coverage percentage.
Shows the linear relationship: base_factor = 0.5 + (note_coverage * 0.5)
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def generate_note_coverage_image(output_path=None):
    """Generate note coverage visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'thoroughness_note_coverage.png')
    
    # Create figure with 2 subplots
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Formula: base_factor = 0.5 + (note_coverage * 0.5)
    note_coverage_range = np.linspace(0, 1.0, 200)  # 0% to 100% coverage
    base_factors = [0.5 + (coverage * 0.5) for coverage in note_coverage_range]
    
    # Plot 1: Base Factor vs Note Coverage
    axes[0].plot(note_coverage_range * 100, base_factors, 'b-', linewidth=2, label='Base Factor')
    axes[0].axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Min (0.5) - No Notes')
    axes[0].axhline(y=1.0, color='g', linestyle='--', alpha=0.5, label='Max (1.0) - All Tasks Have Notes')
    axes[0].axvline(x=0, color='orange', linestyle=':', alpha=0.5, label='0% Coverage')
    axes[0].axvline(x=100, color='purple', linestyle=':', alpha=0.5, label='100% Coverage')
    axes[0].set_xlabel('Note Coverage (%)', fontsize=11)
    axes[0].set_ylabel('Base Factor', fontsize=11)
    axes[0].set_title('Base Factor vs Note Coverage\n(base_factor = 0.5 + (coverage × 0.5))', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='lower right')
    axes[0].set_xlim(0, 100)
    axes[0].set_ylim(0.4, 1.1)
    
    # Add example points
    example_points = [
        (0, 0.5, 'No Notes'),
        (25, 0.625, '25% Coverage'),
        (50, 0.75, '50% Coverage'),
        (75, 0.875, '75% Coverage'),
        (100, 1.0, 'Full Coverage'),
    ]
    
    for coverage_pct, factor, label in example_points:
        axes[0].plot(coverage_pct, factor, 'ro', markersize=8)
        axes[0].annotate(f'{label}\nFactor: {factor:.2f}', 
                        xy=(coverage_pct, factor), xytext=(5, 5), 
                        textcoords='offset points', fontsize=9,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    
    # Plot 2: Impact on final thoroughness factor (showing different coverage levels)
    coverage_levels = [0, 25, 50, 75, 100]
    base_factors_levels = [0.5 + (c / 100.0 * 0.5) for c in coverage_levels]
    
    x_pos = np.arange(len(coverage_levels))
    colors = ['red', 'orange', 'yellow', 'lightgreen', 'green']
    
    bars = axes[1].bar(x_pos, base_factors_levels, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    axes[1].axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Minimum (0.5)')
    axes[1].axhline(y=1.0, color='g', linestyle='--', alpha=0.5, label='Maximum (1.0)')
    axes[1].set_xlabel('Note Coverage (%)', fontsize=11)
    axes[1].set_ylabel('Base Factor', fontsize=11)
    axes[1].set_title('Base Factor by Coverage Level', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([f'{c}%' for c in coverage_levels])
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].set_ylim(0.4, 1.1)
    
    # Add value labels on bars
    for i, factor in enumerate(base_factors_levels):
        axes[1].text(i, factor + 0.02, f'{factor:.2f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.suptitle('Thoroughness Factor: Note Coverage Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_note_coverage_image()
    print("[PASS] Generated: thoroughness_note_coverage.png")
    print("[INFO] Base factor ranges from 0.5 (no notes) to 1.0 (all tasks have notes)")
    print("[INFO] Formula: base_factor = 0.5 + (note_coverage * 0.5)")
