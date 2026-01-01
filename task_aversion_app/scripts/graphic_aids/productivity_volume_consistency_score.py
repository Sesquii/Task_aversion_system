#!/usr/bin/env python3
"""
Graphic Aid: Productivity Volume - Work Consistency Score Component

Visualizes how variance in daily work times affects consistency score.
Lower variance = higher consistency score (0-100).
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


def calculate_consistency_score(variance, max_variance=240.0**2):
    """Calculate consistency score from variance."""
    return max(0.0, min(100.0, 100.0 * (1.0 - min(1.0, variance / max_variance))))


def generate_consistency_score_image(output_path=None):
    """Generate work consistency score visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_volume_consistency_score.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Consistency score vs variance
    max_variance = 240.0 ** 2  # 4 hours squared
    variance_range = np.linspace(0, max_variance * 1.2, 500)
    consistency_scores = [calculate_consistency_score(v, max_variance) for v in variance_range]
    
    axes[0].plot(variance_range / (240.0**2), consistency_scores, 'b-', linewidth=3, label='Consistency Score')
    axes[0].axvline(x=0.5, color='yellow', linestyle='--', alpha=0.5, label='50% variance (50 score)')
    axes[0].axvline(x=1.0, color='orange', linestyle='--', alpha=0.5, label='100% variance (0 score)')
    axes[0].axhline(y=50, color='yellow', linestyle=':', alpha=0.3)
    axes[0].axhline(y=100, color='green', linestyle=':', alpha=0.3)
    axes[0].set_xlabel('Variance (normalized to max variance)', fontsize=11)
    axes[0].set_ylabel('Consistency Score (0-100)', fontsize=11)
    axes[0].set_title('Work Consistency Score vs Variance\n(Lower Variance = Higher Consistency)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0, 105)
    axes[0].set_xlim(0, 1.2)
    
    # Add region labels
    axes[0].text(0.25, 75, 'High Consistency\n(Low variance)\n75-100 score', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    axes[0].text(0.75, 25, 'Low Consistency\n(High variance)\n0-25 score', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    
    # Plot 2: Example daily work time patterns
    patterns = [
        ('Perfectly Consistent', [360, 360, 360, 360, 360], 'Same 6h every day'),
        ('Very Consistent', [330, 360, 350, 370, 360], 'Small variation (±30 min)'),
        ('Moderately Consistent', [300, 360, 420, 330, 390], 'Moderate variation (±60 min)'),
        ('Inconsistent', [180, 480, 240, 540, 300], 'Large variation (±180 min)'),
        ('Very Inconsistent', [120, 600, 180, 480, 240], 'Very large variation (±240 min)'),
    ]
    
    pattern_names = [p[0] for p in patterns]
    pattern_variances = [np.var(p[1]) for p in patterns]
    pattern_scores = [calculate_consistency_score(v) for v in pattern_variances]
    
    x_pos = np.arange(len(patterns))
    colors = ['green', 'lightgreen', 'yellow', 'orange', 'red']
    bars = axes[1].bar(x_pos, pattern_scores, color=colors, alpha=0.7, edgecolor='black')
    axes[1].set_xlabel('Work Pattern', fontsize=11)
    axes[1].set_ylabel('Consistency Score', fontsize=11)
    axes[1].set_title('Consistency Score: Example Work Patterns', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([p[0] for p in patterns], rotation=45, ha='right')
    axes[1].set_ylim(0, 105)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, score, pattern) in enumerate(zip(bars, pattern_scores, patterns)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 2,
                    f'{score:.1f}\n{pattern[2]}',
                    ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.suptitle('Productivity Volume: Work Consistency Score Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_consistency_score_image()

