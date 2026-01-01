#!/usr/bin/env python3
"""
Graphic Aid: Productivity Volume - Work Volume Score Component

Visualizes how average daily work time maps to work volume score (0-100).
Uses tiered scoring system: 0-2h (0-25), 2-4h (25-50), 4-6h (50-75), 6-8h+ (75-100).
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


def calculate_work_volume_score(avg_daily_work_time_minutes):
    """Calculate work volume score from average daily work time."""
    if avg_daily_work_time_minutes <= 120:  # 2 hours
        return (avg_daily_work_time_minutes / 120) * 25
    elif avg_daily_work_time_minutes <= 240:  # 4 hours
        return 25 + ((avg_daily_work_time_minutes - 120) / 120) * 25
    elif avg_daily_work_time_minutes <= 360:  # 6 hours
        return 50 + ((avg_daily_work_time_minutes - 240) / 120) * 25
    else:  # 6+ hours
        return 75 + min(25, ((avg_daily_work_time_minutes - 360) / 120) * 25)


def generate_work_volume_score_image(output_path=None):
    """Generate work volume score visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_volume_work_volume_score.png')
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1: Work volume score vs average daily work time
    work_time_range = np.linspace(0, 600, 600)  # 0 to 10 hours
    volume_scores = [calculate_work_volume_score(t) for t in work_time_range]
    
    axes[0].plot(work_time_range / 60, volume_scores, 'b-', linewidth=3, label='Work Volume Score')
    axes[0].axvline(x=2, color='orange', linestyle='--', alpha=0.5, label='2 hours (25 score)')
    axes[0].axvline(x=4, color='yellow', linestyle='--', alpha=0.5, label='4 hours (50 score)')
    axes[0].axvline(x=6, color='green', linestyle='--', alpha=0.5, label='6 hours (75 score)')
    axes[0].axvline(x=8, color='darkgreen', linestyle='--', alpha=0.5, label='8 hours (100 score)')
    axes[0].axhline(y=25, color='orange', linestyle=':', alpha=0.3)
    axes[0].axhline(y=50, color='yellow', linestyle=':', alpha=0.3)
    axes[0].axhline(y=75, color='green', linestyle=':', alpha=0.3)
    axes[0].axhline(y=100, color='darkgreen', linestyle=':', alpha=0.3)
    axes[0].set_xlabel('Average Daily Work Time (hours)', fontsize=11)
    axes[0].set_ylabel('Work Volume Score (0-100)', fontsize=11)
    axes[0].set_title('Work Volume Score vs Daily Work Time\n(Tiered Scoring System)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='lower right')
    axes[0].set_ylim(0, 105)
    axes[0].set_xlim(0, 10)
    
    # Add tier labels
    axes[0].text(1, 12, 'Low Volume\n(0-2h)\n0-25 score', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
    axes[0].text(3, 37, 'Moderate\n(2-4h)\n25-50 score', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
    axes[0].text(5, 62, 'Good\n(4-6h)\n50-75 score', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
    axes[0].text(7, 87, 'High Volume\n(6-8h+)\n75-100 score', 
                ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='green', alpha=0.7))
    
    # Plot 2: Example scenarios
    scenarios = [
        ('1 hour/day', 60, 'Very low volume'),
        ('2 hours/day', 120, 'Low volume threshold'),
        ('3 hours/day', 180, 'Moderate volume'),
        ('4 hours/day', 240, 'Moderate volume threshold'),
        ('5 hours/day', 300, 'Good volume'),
        ('6 hours/day', 360, 'Good volume threshold'),
        ('7 hours/day', 420, 'High volume'),
        ('8 hours/day', 480, 'High volume threshold'),
    ]
    
    scenario_names = [s[0] for s in scenarios]
    scenario_scores = [calculate_work_volume_score(s[1]) for s in scenarios]
    
    x_pos = np.arange(len(scenarios))
    colors = ['red', 'orange', 'yellow', 'yellow', 'lightgreen', 'green', 'green', 'darkgreen']
    bars = axes[1].bar(x_pos, scenario_scores, color=colors, alpha=0.7, edgecolor='black')
    axes[1].set_xlabel('Scenario', fontsize=11)
    axes[1].set_ylabel('Work Volume Score', fontsize=11)
    axes[1].set_title('Work Volume Score: Example Scenarios', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
    axes[1].set_ylim(0, 105)
    axes[1].grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for i, (bar, score, scenario) in enumerate(zip(bars, scenario_scores, scenarios)):
        height = bar.get_height()
        axes[1].text(bar.get_x() + bar.get_width()/2., height + 2,
                    f'{score:.1f}',
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    plt.suptitle('Productivity Volume: Work Volume Score Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_work_volume_score_image()

