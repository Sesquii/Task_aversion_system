#!/usr/bin/env python3
"""
Graphic Aid: Execution Score - Difficulty Factor

Visualizes how the difficulty factor is calculated based on aversion and cognitive load.
Shows the exponential scaling curve.
"""

import matplotlib.pyplot as plt
import numpy as np
import math

def calculate_difficulty_bonus(aversion, load, w_aversion=0.7, w_load=0.3, k=50.0):
    """Calculate difficulty bonus using exponential decay formula."""
    combined_difficulty = (w_aversion * aversion) + (w_load * load)
    difficulty_bonus = 1.0 * (1.0 - math.exp(-combined_difficulty / k))
    return max(0.0, min(1.0, difficulty_bonus))

# Create figure
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Plot 1: Difficulty factor vs combined difficulty
combined_difficulty_range = np.linspace(0, 100, 200)
difficulty_factors = [calculate_difficulty_bonus(d, 0, w_aversion=1.0, w_load=0.0) for d in combined_difficulty_range]

axes[0].plot(combined_difficulty_range, difficulty_factors, 'b-', linewidth=2, label='Difficulty Factor')
axes[0].axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='Max (1.0)')
axes[0].set_xlabel('Combined Difficulty (0.7 × aversion + 0.3 × load)', fontsize=11)
axes[0].set_ylabel('Difficulty Factor', fontsize=11)
axes[0].set_title('Difficulty Factor vs Combined Difficulty\n(Exponential Scaling)', fontsize=12, fontweight='bold')
axes[0].grid(True, alpha=0.3)
axes[0].legend()
axes[0].set_ylim(0, 1.1)

# Plot 2: 3D surface showing aversion vs load
aversion_range = np.linspace(0, 100, 50)
load_range = np.linspace(0, 100, 50)
Aversion, Load = np.meshgrid(aversion_range, load_range)
Difficulty = np.zeros_like(Aversion)

for i in range(len(aversion_range)):
    for j in range(len(load_range)):
        Difficulty[j, i] = calculate_difficulty_bonus(aversion_range[i], load_range[j])

contour = axes[1].contourf(Aversion, Load, Difficulty, levels=20, cmap='viridis')
axes[1].set_xlabel('Aversion (0-100)', fontsize=11)
axes[1].set_ylabel('Cognitive Load (0-100)', fontsize=11)
axes[1].set_title('Difficulty Factor: Aversion × Load\n(Higher = More Difficult)', fontsize=12, fontweight='bold')
cbar = plt.colorbar(contour, ax=axes[1])
cbar.set_label('Difficulty Factor', fontsize=10)

# Add example points
example_points = [
    (20, 30, 'Easy Task'),
    (50, 50, 'Moderate Task'),
    (80, 70, 'Hard Task'),
]

for av, ld, label in example_points:
    factor = calculate_difficulty_bonus(av, ld)
    axes[1].plot(av, ld, 'ro', markersize=10)
    axes[1].annotate(f'{label}\nFactor: {factor:.2f}', 
                    xy=(av, ld), xytext=(10, 10), 
                    textcoords='offset points', fontsize=9,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.suptitle('Execution Score: Difficulty Factor Component', fontsize=14, fontweight='bold', y=1.02)

# Save figure
output_path = 'execution_score_difficulty_factor.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
print(f"[PASS] Graphic saved to: {output_path}")
print(f"[INFO] Difficulty factor ranges from 0.0 (easy) to 1.0 (very difficult)")
print(f"[INFO] Formula: bonus = 1.0 * (1 - exp(-(0.7 * aversion + 0.3 * load) / 50))")

plt.show()

