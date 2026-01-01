#!/usr/bin/env python3
"""
Graphic Aid: Productivity Score - Baseline Completion Component

Visualizes how completion percentage affects baseline productivity score.
Shows the linear relationship: baseline_score = completion_pct × multiplier
"""

import matplotlib.pyplot as plt
import numpy as np
import os

# Get the directory where images should be saved
_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def generate_baseline_completion_image(output_path=None):
    """Generate baseline completion visualization image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'productivity_score_baseline_completion.png')
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Fixed multipliers for different task types
    work_multiplier = 3.0  # Base work multiplier
    self_care_multiplier = 1.0  # Base self care multiplier
    play_multiplier = 1.0  # Neutral play multiplier
    
    completion_range = np.linspace(0, 100, 200)
    
    # Plot 1: Completion % vs Baseline Score for different task types
    work_scores = [cp * work_multiplier for cp in completion_range]
    self_care_scores = [cp * self_care_multiplier for cp in completion_range]
    play_scores = [cp * play_multiplier for cp in completion_range]
    
    axes[0].plot(completion_range, work_scores, 'b-', linewidth=2, label=f'Work (×{work_multiplier})')
    axes[0].plot(completion_range, self_care_scores, 'g-', linewidth=2, label=f'Self Care (×{self_care_multiplier})')
    axes[0].plot(completion_range, play_scores, 'orange', linewidth=2, label=f'Play (×{play_multiplier})')
    axes[0].axvline(x=100, color='r', linestyle='--', alpha=0.5, label='Full (100%)')
    axes[0].axvline(x=50, color='orange', linestyle='--', alpha=0.5, label='Half (50%)')
    axes[0].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[0].set_ylabel('Baseline Score', fontsize=11)
    axes[0].set_title('Baseline Score vs Completion %\n(score = completion_pct × multiplier)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_xlim(0, 100)
    axes[0].set_ylim(0, 350)
    
    # Plot 2: Score distribution for different completion levels
    completion_levels = [25, 50, 75, 90, 100]
    work_scores_levels = [cp * work_multiplier for cp in completion_levels]
    self_care_scores_levels = [cp * self_care_multiplier for cp in completion_levels]
    play_scores_levels = [cp * play_multiplier for cp in completion_levels]
    
    x_pos = np.arange(len(completion_levels))
    width = 0.25
    
    axes[1].bar(x_pos - width, work_scores_levels, width, label='Work', color='blue', alpha=0.7)
    axes[1].bar(x_pos, self_care_scores_levels, width, label='Self Care', color='green', alpha=0.7)
    axes[1].bar(x_pos + width, play_scores_levels, width, label='Play', color='orange', alpha=0.7)
    
    axes[1].set_xlabel('Completion Percentage (%)', fontsize=11)
    axes[1].set_ylabel('Baseline Score', fontsize=11)
    axes[1].set_title('Baseline Score by Completion Level', fontsize=12, fontweight='bold')
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels([f'{cp}%' for cp in completion_levels])
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')
    axes[1].set_ylim(0, 350)
    
    # Plot 3: Impact of completion on final score (showing multiplier effect)
    multipliers = [1.0, 2.0, 3.0, 4.0, 5.0]
    completion_pct = 100.0
    
    multiplier_scores = [completion_pct * mult for mult in multipliers]
    
    axes[2].bar(range(len(multipliers)), multiplier_scores, color='purple', alpha=0.7, edgecolor='black')
    axes[2].set_xlabel('Task Type Multiplier', fontsize=11)
    axes[2].set_ylabel('Baseline Score (at 100% completion)', fontsize=11)
    axes[2].set_title('Impact of Multiplier on Score\n(100% completion)', fontsize=12, fontweight='bold')
    axes[2].set_xticks(range(len(multipliers)))
    axes[2].set_xticklabels([f'{m:.1f}x' for m in multipliers])
    axes[2].grid(True, alpha=0.3, axis='y')
    axes[2].set_ylim(0, 550)
    
    # Add value labels on bars
    for i, score in enumerate(multiplier_scores):
        axes[2].text(i, score + 10, f'{score:.0f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.suptitle('Productivity Score: Baseline Completion Component', fontsize=14, fontweight='bold', y=1.02)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_baseline_completion_image()
    print("[PASS] Generated: productivity_score_baseline_completion.png")
