#!/usr/bin/env python3
"""
Theoretical visualization: Grit Score - Disappointment Resilience.
Two curves: completion >= 100% (bonus up to 1.5x) vs completion < 100% (penalty down to 0.67x).
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def disappointment_resilience(disappointment_factor: float, completion_100: bool) -> float:
    """Resilience: bonus if completed 100%, penalty if not."""
    if disappointment_factor <= 0:
        return 1.0
    if completion_100:
        return min(1.5, 1.0 + disappointment_factor / 200.0)
    return max(0.67, 1.0 - disappointment_factor / 300.0)


def generate_disappointment_resilience_image(output_path=None):
    """Generate disappointment resilience theoretical image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'grit_score_disappointment_resilience.png')
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.linspace(0, 200, 200)
    bonus = [disappointment_resilience(float(v), True) for v in x]
    penalty = [disappointment_resilience(float(v), False) for v in x]
    ax.plot(x, bonus, 'g-', linewidth=2, label='Completion >= 100% (bonus, cap 1.5x)')
    ax.plot(x, penalty, 'r-', linewidth=2, label='Completion < 100% (penalty, floor 0.67x)')
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    ax.axhline(y=1.5, color='green', linestyle=':', alpha=0.5)
    ax.axhline(y=0.67, color='red', linestyle=':', alpha=0.5)
    ax.set_xlabel('Disappointment factor (expected_relief - actual_relief when negative)', fontsize=11)
    ax.set_ylabel('Disappointment resilience multiplier', fontsize=11)
    ax.set_title('Grit Score: Disappointment Resilience (0.67-1.5)\nComplete despite disappointment = bonus; give up = penalty', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_ylim(0.5, 1.6)
    plt.tight_layout()
    plt.suptitle('Grit Score: Disappointment Resilience Component', fontsize=14, fontweight='bold', y=1.02)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_disappointment_resilience_image()
