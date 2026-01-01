#!/usr/bin/env python3
"""
Graphic Aid: Volumetric Productivity Score - Calculation Component

Visualizes volumetric productivity calculation: base_score × volume_multiplier.
Shows how volume adjustment affects final productivity score.
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


def calculate_volumetric(base_score, volume_score):
    """Calculate volumetric productivity score."""
    volume_multiplier = 0.5 + (volume_score / 100.0) * 1.0
    return base_score * volume_multiplier


def generate_calculation_image(output_path=None):
    """Generate volumetric productivity calculation visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'volumetric_productivity_calculation.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Volumetric score vs volume score (fixed base)
    base_score = 300.0  # Example base productivity
    volume_score_range = np.linspace(0, 100, 100)
    volumetric_scores = [calculate_volumetric(base_score, v) for v in volume_score_range]
    
    axes[0].plot(volume_score_range, volumetric_scores, 'b-', linewidth=3, label='Volumetric Score')
    axes[0].axhline(y=base_score, color='gray', linestyle='--', alpha=0.5, label=f'Base Score ({base_score})')
    axes[0].axvline(x=0, color='red', linestyle=':', alpha=0.3, label='No Volume (0.5x)')
    axes[0].axvline(x=50, color='orange', linestyle=':', alpha=0.3, label='Moderate (1.0x)')
    axes[0].axvline(x=100, color='green', linestyle=':', alpha=0.3, label='High (1.5x)')
    axes[0].fill_between(volume_score_range, base_score * 0.5, base_score * 1.5, alpha=0.2, color='yellow', label='Range')
    axes[0].set_xlabel('Work Volume Score (0-100)', fontsize=11)
    axes[0].set_ylabel('Volumetric Productivity Score', fontsize=11)
    axes[0].set_title(f'Volumetric Score vs Volume\n(Base Score = {base_score})', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 100)
    
    # Add formula annotation
    axes[0].text(50, base_score * 1.2, 'Formula:\nvolumetric = base ×\nvolume_multiplier', 
                ha='center', fontsize=10, bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
    
    # Plot 2: Example calculations
    examples = [
        ('Base 100, Low Vol', 100, 25, 75, 'Base 100 × 0.75x = 75'),
        ('Base 100, Mod Vol', 100, 50, 100, 'Base 100 × 1.0x = 100'),
        ('Base 100, High Vol', 100, 75, 125, 'Base 100 × 1.25x = 125'),
        ('Base 300, Low Vol', 300, 25, 225, 'Base 300 × 0.75x = 225'),
        ('Base 300, Mod Vol', 300, 50, 300, 'Base 300 × 1.0x = 300'),
        ('Base 300, High Vol', 300, 75, 375, 'Base 300 × 1.25x = 375'),
    ]
    
    example_names = [e[0] for e in examples]
    base_scores = [e[1] for e in examples]
    volumetric_scores_ex = [e[3] for e in examples]
    
    x_pos = np.arange(len(examples))
    width = 0.35
    
    bars1 = axes[1].bar(x_pos - width/2, base_scores, width, label='Base Score', color='lightblue', alpha=0.7, edgecolor='black')
    bars2 = axes[1].bar(x_pos + width/2, volumetric_scores_ex, width, label='Volumetric Score', color='blue', alpha=0.7, edgecolor='black')
    
    axes[1].set_xlabel('Example', fontsize=11)
    axes[1].set_ylabel('Productivity Score', fontsize=11)
    axes[1].set_title('Base vs Volumetric Score: Examples', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([e[0] for e in examples], rotation=45, ha='right')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            axes[1].text(bar.get_x() + bar.get_width()/2., height + 10,
                        f'{height:.0f}',
                        ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    plt.tight_layout()
    plt.suptitle('Volumetric Productivity Score: Calculation Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_calculation_image()

