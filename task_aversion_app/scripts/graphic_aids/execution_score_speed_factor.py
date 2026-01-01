#!/usr/bin/env python3
"""
Graphic Aid: Execution Score - Speed Factor

Visualizes how the speed factor is calculated based on time ratio (actual/estimate).
Shows the piecewise function with different regions.
"""

import matplotlib.pyplot as plt
import numpy as np

def calculate_speed_factor(time_ratio):
    """Calculate speed factor based on time ratio."""
    if time_ratio <= 0.5:
        # Very fast: 2x speed or faster → max bonus
        return 1.0
    elif time_ratio <= 1.0:
        # Fast: completed within estimate → linear bonus
        # 0.5 → 1.0, 1.0 → 0.5
        return 1.0 - (time_ratio - 0.5) * 1.0
    else:
        # Slow: exceeded estimate → diminishing penalty
        # 1.0 → 0.5, 2.0 → 0.25, 3.0 → 0.125
        return 0.5 * (1.0 / time_ratio)

# Create figure
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: Speed factor vs time ratio
time_ratio_range = np.linspace(0.1, 3.0, 300)
speed_factors = [calculate_speed_factor(tr) for tr in time_ratio_range]

axes[0].plot(time_ratio_range, speed_factors, 'g-', linewidth=2, label='Speed Factor')
axes[0].axvline(x=0.5, color='r', linestyle='--', alpha=0.5, label='Very Fast Threshold (0.5)')
axes[0].axvline(x=1.0, color='orange', linestyle='--', alpha=0.5, label='Estimate (1.0)')
axes[0].axhline(y=1.0, color='b', linestyle='--', alpha=0.3, label='Max (1.0)')
axes[0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.3, label='Neutral (0.5)')
axes[0].set_xlabel('Time Ratio (actual / estimate)', fontsize=11)
axes[0].set_ylabel('Speed Factor', fontsize=11)
axes[0].set_title('Speed Factor vs Time Ratio\n(Fast = High Score)', fontsize=12, fontweight='bold')
axes[0].grid(True, alpha=0.3)
axes[0].legend()
axes[0].set_ylim(0, 1.1)
axes[0].set_xlim(0, 3.0)

# Add region labels
axes[0].text(0.25, 0.95, 'Very Fast\n(2x speed or faster)\nFactor = 1.0', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
axes[0].text(0.75, 0.75, 'Fast\n(within estimate)\nLinear: 0.5 → 1.0', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
axes[0].text(2.0, 0.25, 'Slow\n(exceeded estimate)\nDiminishing penalty', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))

# Plot 2: Example scenarios
scenarios = [
    ('Very Fast (0.25x)', 0.25, 'Completed in 15 min\n(estimated 60 min)'),
    ('Fast (0.5x)', 0.5, 'Completed in 30 min\n(estimated 60 min)'),
    ('On Time (1.0x)', 1.0, 'Completed in 60 min\n(estimated 60 min)'),
    ('Slow (2.0x)', 2.0, 'Completed in 120 min\n(estimated 60 min)'),
    ('Very Slow (3.0x)', 3.0, 'Completed in 180 min\n(estimated 60 min)'),
]

scenario_names = [s[0] for s in scenarios]
scenario_ratios = [s[1] for s in scenarios]
scenario_factors = [calculate_speed_factor(s[1]) for s in scenarios]

x_pos = np.arange(len(scenarios))
bars = axes[1].bar(x_pos, scenario_factors, color=['green', 'lightgreen', 'yellow', 'orange', 'red'], alpha=0.7)
axes[1].set_xlabel('Scenario', fontsize=11)
axes[1].set_ylabel('Speed Factor', fontsize=11)
axes[1].set_title('Speed Factor: Example Scenarios', fontsize=12, fontweight='bold')
axes[1].set_xticks(x_pos)
axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
axes[1].set_ylim(0, 1.1)
axes[1].grid(True, alpha=0.3, axis='y')

# Add value labels on bars
for i, (bar, factor, scenario) in enumerate(zip(bars, scenario_factors, scenarios)):
    height = bar.get_height()
    axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                f'{factor:.2f}\n{scenario[2]}',
                ha='center', va='bottom', fontsize=8)

plt.tight_layout()
plt.suptitle('Execution Score: Speed Factor Component', fontsize=14, fontweight='bold', y=1.02)

# Save figure
output_path = 'execution_score_speed_factor.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"[PASS] Graphic saved to: {output_path}")
print(f"[INFO] Speed factor rewards fast completion (2x speed or faster = max)")
print(f"[INFO] Formula: piecewise function based on time_ratio = actual / estimate")

plt.show()

