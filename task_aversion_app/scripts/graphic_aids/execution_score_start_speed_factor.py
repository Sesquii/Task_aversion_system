#!/usr/bin/env python3
"""
Graphic Aid: Execution Score - Start Speed Factor

Visualizes how the start speed factor is calculated based on delay from initialization to start.
Shows the piecewise function with different time thresholds.
"""

import matplotlib.pyplot as plt
import numpy as np
import math

def calculate_start_speed_factor(start_delay_minutes):
    """Calculate start speed factor based on delay from initialization to start."""
    if start_delay_minutes <= 5:
        return 1.0
    elif start_delay_minutes <= 30:
        # Linear: 5 min → 1.0, 30 min → 0.8
        return 1.0 - ((start_delay_minutes - 5) / 25.0) * 0.2
    elif start_delay_minutes <= 120:
        # Linear: 30 min → 0.8, 120 min → 0.5
        return 0.8 - ((start_delay_minutes - 30) / 90.0) * 0.3
    else:
        # Exponential decay: 120 min → 0.5, 480 min → ~0.125
        excess = start_delay_minutes - 120
        return 0.5 * math.exp(-excess / 240.0)

# Create figure
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: Start speed factor vs delay minutes
delay_range = np.linspace(0, 480, 500)  # 0 to 8 hours
start_speed_factors = [calculate_start_speed_factor(d) for d in delay_range]

axes[0].plot(delay_range, start_speed_factors, 'purple', linewidth=2, label='Start Speed Factor')
axes[0].axvline(x=5, color='g', linestyle='--', alpha=0.5, label='Perfect (5 min)')
axes[0].axvline(x=30, color='lightgreen', linestyle='--', alpha=0.5, label='Good (30 min)')
axes[0].axvline(x=120, color='orange', linestyle='--', alpha=0.5, label='Acceptable (2 hours)')
axes[0].axhline(y=1.0, color='b', linestyle='--', alpha=0.3, label='Max (1.0)')
axes[0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.3, label='Neutral (0.5)')
axes[0].set_xlabel('Start Delay (minutes from initialization)', fontsize=11)
axes[0].set_ylabel('Start Speed Factor', fontsize=11)
axes[0].set_title('Start Speed Factor vs Delay\n(Fast Start = High Score)', fontsize=12, fontweight='bold')
axes[0].grid(True, alpha=0.3)
axes[0].legend()
axes[0].set_ylim(0, 1.1)
axes[0].set_xlim(0, 480)

# Add region labels
axes[0].text(2.5, 0.95, 'Perfect\n(≤5 min)\nFactor = 1.0', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
axes[0].text(17.5, 0.9, 'Good\n(5-30 min)\nLinear: 1.0 → 0.8', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
axes[0].text(75, 0.65, 'Acceptable\n(30-120 min)\nLinear: 0.8 → 0.5', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
axes[0].text(300, 0.3, 'Poor\n(>120 min)\nExponential decay', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))

# Plot 2: Example scenarios
scenarios = [
    ('Immediate (2 min)', 2, 'Started 2 min after initialization'),
    ('Fast (10 min)', 10, 'Started 10 min after initialization'),
    ('Moderate (45 min)', 45, 'Started 45 min after initialization'),
    ('Delayed (3 hours)', 180, 'Started 3 hours after initialization'),
    ('Very Delayed (6 hours)', 360, 'Started 6 hours after initialization'),
]

scenario_names = [s[0] for s in scenarios]
scenario_delays = [s[1] for s in scenarios]
scenario_factors = [calculate_start_speed_factor(s[1]) for s in scenarios]

x_pos = np.arange(len(scenarios))
bars = axes[1].bar(x_pos, scenario_factors, color=['green', 'lightgreen', 'yellow', 'orange', 'red'], alpha=0.7)
axes[1].set_xlabel('Scenario', fontsize=11)
axes[1].set_ylabel('Start Speed Factor', fontsize=11)
axes[1].set_title('Start Speed Factor: Example Scenarios', fontsize=12, fontweight='bold')
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
plt.suptitle('Execution Score: Start Speed Factor Component\n(Procrastination Resistance)', fontsize=14, fontweight='bold', y=1.02)

# Save figure
output_path = 'execution_score_start_speed_factor.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"[PASS] Graphic saved to: {output_path}")
print(f"[INFO] Start speed factor rewards fast starts (≤5 min = perfect)")
print(f"[INFO] Formula: piecewise function with linear and exponential regions")

plt.show()

