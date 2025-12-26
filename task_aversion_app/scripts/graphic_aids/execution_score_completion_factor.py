#!/usr/bin/env python3
"""
Graphic Aid: Execution Score - Completion Factor

Visualizes how the completion factor is calculated based on completion percentage.
Shows the piecewise function with different completion thresholds.
"""

import matplotlib.pyplot as plt
import numpy as np

def calculate_completion_factor(completion_pct):
    """Calculate completion factor based on completion percentage."""
    if completion_pct >= 100.0:
        return 1.0
    elif completion_pct >= 90.0:
        # Near-complete: slight penalty
        return 0.9 + (completion_pct - 90.0) / 10.0 * 0.1
    elif completion_pct >= 50.0:
        # Partial: moderate penalty
        return 0.5 + (completion_pct - 50.0) / 40.0 * 0.4
    else:
        # Low completion: significant penalty
        return completion_pct / 50.0 * 0.5

# Create figure
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: Completion factor vs completion percentage
completion_range = np.linspace(0, 100, 500)
completion_factors = [calculate_completion_factor(cp) for cp in completion_range]

axes[0].plot(completion_range, completion_factors, 'blue', linewidth=2, label='Completion Factor')
axes[0].axvline(x=50, color='orange', linestyle='--', alpha=0.5, label='Partial (50%)')
axes[0].axvline(x=90, color='yellow', linestyle='--', alpha=0.5, label='Near-Complete (90%)')
axes[0].axvline(x=100, color='g', linestyle='--', alpha=0.5, label='Full (100%)')
axes[0].axhline(y=1.0, color='b', linestyle='--', alpha=0.3, label='Max (1.0)')
axes[0].axhline(y=0.5, color='gray', linestyle='--', alpha=0.3, label='Neutral (0.5)')
axes[0].set_xlabel('Completion Percentage (%)', fontsize=11)
axes[0].set_ylabel('Completion Factor', fontsize=11)
axes[0].set_title('Completion Factor vs Completion %\n(Full Completion = Max Score)', fontsize=12, fontweight='bold')
axes[0].grid(True, alpha=0.3)
axes[0].legend()
axes[0].set_ylim(0, 1.1)
axes[0].set_xlim(0, 100)

# Add region labels
axes[0].text(25, 0.25, 'Low\n(<50%)\nSignificant penalty', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7))
axes[0].text(70, 0.7, 'Partial\n(50-90%)\nModerate penalty', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))
axes[0].text(95, 0.95, 'Near-Complete\n(90-100%)\nSlight penalty', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7))
axes[0].text(100, 1.0, 'Full\n(100%)\nFactor = 1.0', 
            ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='green', alpha=0.7))

# Plot 2: Example scenarios
scenarios = [
    ('Low (25%)', 25, 'Only 25% completed'),
    ('Partial (60%)', 60, '60% completed'),
    ('Near-Complete (95%)', 95, '95% completed'),
    ('Full (100%)', 100, '100% completed'),
]

scenario_names = [s[0] for s in scenarios]
scenario_percentages = [s[1] for s in scenarios]
scenario_factors = [calculate_completion_factor(s[1]) for s in scenarios]

x_pos = np.arange(len(scenarios))
bars = axes[1].bar(x_pos, scenario_factors, color=['red', 'orange', 'yellow', 'green'], alpha=0.7)
axes[1].set_xlabel('Scenario', fontsize=11)
axes[1].set_ylabel('Completion Factor', fontsize=11)
axes[1].set_title('Completion Factor: Example Scenarios', fontsize=12, fontweight='bold')
axes[1].set_xticks(x_pos)
axes[1].set_xticklabels([s[0] for s in scenarios], rotation=45, ha='right')
axes[1].set_ylim(0, 1.1)
axes[1].grid(True, alpha=0.3, axis='y')

# Add value labels on bars
for i, (bar, factor, scenario) in enumerate(zip(bars, scenario_factors, scenarios)):
    height = bar.get_height()
    axes[1].text(bar.get_x() + bar.get_width()/2., height + 0.02,
                f'{factor:.2f}\n{scenario[2]}',
                ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.suptitle('Execution Score: Completion Factor Component', fontsize=14, fontweight='bold', y=1.02)

# Save figure
output_path = 'execution_score_completion_factor.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"[PASS] Graphic saved to: {output_path}")
print(f"[INFO] Completion factor rewards full completion (100% = max)")
print(f"[INFO] Formula: piecewise function with different penalty regions")

plt.show()

