#!/usr/bin/env python3
"""
Graphic Aid: Volumetric Productivity Score - Base Productivity Component

Visualizes base productivity score distribution and calculation.
Shows per-task productivity scores before volume adjustment.
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


def generate_base_image(output_path=None):
    """Generate base productivity score visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'volumetric_productivity_base.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Base productivity score range by task type
    task_types = ['Work (3-5x)', 'Self Care (varies)', 'Play (1x or penalty)']
    score_ranges = [
        (0, 500),  # Work: 0-100 completion × 3-5x multiplier
        (0, 200),  # Self Care: 0-100 completion × 1-2x multiplier (simplified)
        (-30, 100),  # Play: can be negative (penalty) or neutral
    ]
    
    x_pos = np.arange(len(task_types))
    colors = ['blue', 'green', 'orange']
    
    for i, (task_type, (min_score, max_score), color) in enumerate(zip(task_types, score_ranges, colors)):
        axes[0].barh(i, max_score - min_score, left=min_score, color=color, alpha=0.7, edgecolor='black')
        axes[0].text((min_score + max_score) / 2, i, f'{min_score} to {max_score}', 
                    ha='center', va='center', fontsize=10, fontweight='bold')
    
    axes[0].set_yticks(x_pos)
    axes[0].set_yticklabels(task_types)
    axes[0].set_xlabel('Base Productivity Score Range', fontsize=11)
    axes[0].set_title('Base Productivity Score Range by Task Type\n(Per-task, before volume adjustment)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3, axis='x')
    axes[0].axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    axes[0].set_xlim(-50, 550)
    
    # Plot 2: Example base scores
    examples = [
        ('Work 100%', 100, 4.0, 400, 'Work task, 100% completion, 4x multiplier'),
        ('Work 75%', 75, 3.5, 262.5, 'Work task, 75% completion, 3.5x multiplier'),
        ('Self Care 100%', 100, 1.0, 100, 'Self care, 100% completion'),
        ('Play 100%', 100, 1.0, 100, 'Play, 100% completion (no penalty)'),
        ('Play Penalty', 100, -0.3, -30, 'Play exceeds work by 2x (penalty)'),
    ]
    
    example_names = [e[0] for e in examples]
    example_scores = [e[3] for e in examples]
    
    x_pos2 = np.arange(len(examples))
    colors2 = ['blue', 'lightblue', 'green', 'orange', 'red']
    bars = axes[1].bar(x_pos2, example_scores, color=colors2, alpha=0.7, edgecolor='black')
    axes[1].set_xlabel('Example Task', fontsize=11)
    axes[1].set_ylabel('Base Productivity Score', fontsize=11)
    axes[1].set_title('Base Productivity Score: Example Tasks', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos2)
    axes[1].set_xticklabels([e[0] for e in examples], rotation=45, ha='right')
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    
    # Add value labels on bars
    for i, (bar, score, example) in enumerate(zip(bars, example_scores, examples)):
        height = bar.get_height()
        y_pos = height + 20 if height >= 0 else height - 30
        axes[1].text(bar.get_x() + bar.get_width()/2., y_pos,
                    f'{score:.1f}',
                    ha='center', va='bottom' if height >= 0 else 'top', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    plt.suptitle('Volumetric Productivity Score: Base Productivity Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_base_image()

