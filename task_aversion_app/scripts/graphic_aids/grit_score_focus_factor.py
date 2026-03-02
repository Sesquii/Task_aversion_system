#!/usr/bin/env python3
"""
Theoretical visualization: Grit Score - Focus Factor.
Shows focus factor vs (positive - negative) emotion score; 100% emotion-based.
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_script_dir = os.path.dirname(os.path.abspath(__file__))
_images_dir = os.path.normpath(os.path.join(_script_dir, '..', '..', 'assets', 'graphic_aids'))
os.makedirs(_images_dir, exist_ok=True)


def focus_factor_scaled(net_emotion: float) -> float:
    """focus_factor = 0.5 + (positive - negative)*0.5, scaled to 0.5-1.5."""
    focus = 0.5 + net_emotion * 0.5  # net in [-1,1] -> focus in [0,1]
    scaled = 0.5 + focus * 1.0  # -> 0.5-1.5
    return max(0.5, min(1.5, scaled))


def generate_focus_factor_image(output_path=None):
    """Generate focus factor theoretical image."""
    if output_path is None:
        output_path = os.path.join(_images_dir, 'grit_score_focus_factor.png')
    fig, ax = plt.subplots(figsize=(10, 6))
    net = np.linspace(-1, 1, 200)
    scaled = [focus_factor_scaled(n) for n in net]
    ax.plot(net, scaled, 'purple', linewidth=2, label='Focus factor (scaled 0.5-1.5)')
    ax.axhline(y=1.0, color='gray', linestyle='--', alpha=0.5, label='Neutral (1.0)')
    ax.axvline(x=0, color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Net emotion (positive - negative, normalized -1 to 1)', fontsize=11)
    ax.set_ylabel('Focus factor scaled', fontsize=11)
    ax.set_title('Grit Score: Focus Factor (emotion-based)\nFocus-positive vs focus-negative emotions', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_ylim(0.4, 1.6)
    ax.fill_between(net, 0.5, scaled, where=(np.array(scaled) >= 1.0), alpha=0.2, color='green')
    ax.fill_between(net, scaled, 1.5, where=(np.array(scaled) <= 1.0), alpha=0.2, color='red')
    plt.tight_layout()
    plt.suptitle('Grit Score: Focus Factor Component', fontsize=14, fontweight='bold', y=1.02)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    return output_path


if __name__ == '__main__':
    generate_focus_factor_image()
