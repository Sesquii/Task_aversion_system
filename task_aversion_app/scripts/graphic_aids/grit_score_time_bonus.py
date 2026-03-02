#!/usr/bin/env python3
"""
Theoretical visualization: Grit Score - Time Bonus.
Shows time_bonus vs time_ratio and vs completion_count (diminishing returns and fade).
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def time_bonus(time_ratio: float, completion_count: int = 5, difficulty_factor: float = 0.5) -> float:
    """Time bonus: linear up to 2x longer, diminishing beyond; difficulty-weighted; fades with reps."""
    if time_ratio <= 1.0:
        return 1.0
    excess = time_ratio - 1.0
    if excess <= 1.0:
        base = 1.0 + excess * 0.8
    else:
        base = 1.8 + (excess - 1.0) * 0.2
    base = min(3.0, base)
    weighted = 1.0 + (base - 1.0) * (0.5 + 0.5 * difficulty_factor)
    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
    return 1.0 + (weighted - 1.0) * fade


def generate_time_bonus_image(output_path=None):
    """Generate time bonus theoretical image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'grit_score_time_bonus.png')
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    # Left: time_bonus vs time_ratio (few reps, no fade)
    ratio = np.linspace(0.5, 4.0, 200)
    bonus_lo = [time_bonus(float(r), 5, 0.0) for r in ratio]
    bonus_hi = [time_bonus(float(r), 5, 1.0) for r in ratio]
    axes[0].plot(ratio, bonus_lo, 'b-', linewidth=2, label='Easy task (difficulty=0)')
    axes[0].plot(ratio, bonus_hi, 'g-', linewidth=2, label='Hard task (difficulty=1)')
    axes[0].axvline(x=1.0, color='gray', linestyle='--', alpha=0.5)
    axes[0].axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    axes[0].set_xlabel('Time ratio (actual / estimate)', fontsize=11)
    axes[0].set_ylabel('Time bonus', fontsize=11)
    axes[0].set_title('Time bonus vs time ratio\n(diminishing returns beyond 2x)', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    axes[0].set_ylim(0.9, 3.2)
    # Right: fade vs completion_count (at fixed time_ratio=2.0)
    counts = np.arange(1, 101)
    at_2x = [time_bonus(2.0, int(c), 0.5) for c in counts]
    axes[1].plot(counts, at_2x, 'purple', linewidth=2, label='Time bonus at 2x longer')
    axes[1].axvline(x=10, color='orange', linestyle='--', alpha=0.6, label='Fade starts (10)')
    axes[1].set_xlabel('Completion count (same task)', fontsize=11)
    axes[1].set_ylabel('Time bonus', fontsize=11)
    axes[1].set_title('Time bonus fade with repetition', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    axes[1].set_ylim(0.9, 2.2)
    plt.tight_layout()
    plt.suptitle('Grit Score: Time Bonus (1.0-3.0)', fontsize=14, fontweight='bold', y=1.02)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_time_bonus_image()
