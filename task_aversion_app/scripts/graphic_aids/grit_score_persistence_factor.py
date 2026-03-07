#!/usr/bin/env python3
"""
Theoretical visualization: Grit Score - Persistence Factor.
Shows multiplier vs completion count with familiarity decay (and optional obstacle level).
"""
import os
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def persistence_multiplier(completion_count: int) -> float:
    """Raw growth then familiarity decay (matches analytics batch)."""
    raw = 1.0 + 0.015 * max(0, completion_count - 1) ** 1.001
    if completion_count > 100:
        decay = 1.0 / (1.0 + (completion_count - 100) / 200.0)
    else:
        decay = 1.0
    return max(1.0, min(5.0, raw * decay))


def generate_persistence_factor_image(output_path=None):
    """Generate persistence factor theoretical image. Saves to output_path."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'grit_score_persistence_factor.png')
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    # Left: multiplier vs completion count
    counts = np.arange(1, 251)
    mults = [persistence_multiplier(int(c)) for c in counts]
    axes[0].plot(counts, mults, 'b-', linewidth=2, label='Persistence multiplier')
    axes[0].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    axes[0].axvline(x=100, color='orange', linestyle='--', alpha=0.6, label='Decay starts (100)')
    axes[0].set_xlabel('Completion count (same task)', fontsize=11)
    axes[0].set_ylabel('Multiplier', fontsize=11)
    axes[0].set_title('Persistence multiplier vs completion count\n(familiarity decay after 100)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0.9, 5.5)
    # Right: obstacle/aversion component sketch (combined load 0-100 -> score 0.5-1.0)
    combined = np.linspace(0, 100, 100)
    obstacle = np.where(combined <= 50, combined / 100.0, 0.5 + ((combined - 50) / 50.0) * 0.5)
    obstacle = np.where(combined > 0, obstacle, 0.5)
    axes[1].plot(combined, obstacle, 'g-', linewidth=2, label='Obstacle score (40% weight)')
    axes[1].set_xlabel('Combined cognitive/emotional load (0-100)', fontsize=11)
    axes[1].set_ylabel('Obstacle score', fontsize=11)
    axes[1].set_title('Obstacle overcoming component\n(part of persistence factor)', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_ylim(0, 1.1)
    plt.tight_layout()
    plt.suptitle('Grit Score: Persistence Factor (0.5-1.5 scaled)', fontsize=14, fontweight='bold', y=1.02)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_persistence_factor_image()
