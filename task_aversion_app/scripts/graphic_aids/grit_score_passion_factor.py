#!/usr/bin/env python3
"""
Theoretical visualization: Grit Score - Passion Factor.
Shows passion factor vs (relief_norm - emotional_norm); dampened if completion < 100%.
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def passion_factor(passion_delta: float, completion_100: bool = True) -> float:
    """passion_delta = relief_norm - emotional_norm; factor = 1.0 + delta*0.5, dampened if not 100%."""
    f = 1.0 + passion_delta * 0.5
    if not completion_100:
        f *= 0.9
    return max(0.5, min(1.5, f))


def generate_passion_factor_image(output_path=None):
    """Generate passion factor theoretical image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'grit_score_passion_factor.png')
    fig, ax = plt.subplots(figsize=(10, 6))
    delta = np.linspace(-1, 1, 200)
    full = [passion_factor(d, True) for d in delta]
    partial = [passion_factor(d, False) for d in delta]
    ax.plot(delta, full, 'b-', linewidth=2, label='Completion 100%')
    ax.plot(delta, partial, 'b--', linewidth=1.5, label='Completion < 100% (x0.9)')
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Passion delta (relief/100 - emotional_load/100)', fontsize=11)
    ax.set_ylabel('Passion factor', fontsize=11)
    ax.set_title('Grit Score: Passion Factor (0.5-1.5)\nRelief vs emotional load', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_ylim(0.4, 1.6)
    plt.tight_layout()
    plt.suptitle('Grit Score: Passion Factor Component', fontsize=14, fontweight='bold', y=1.02)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_passion_factor_image()
