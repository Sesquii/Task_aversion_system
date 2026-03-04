"""
Canonical storage keys for direct (user-reported) vs derived (computed) metrics.

Use these constants so naming stays consistent and we never confuse direct
slider values with derived/formula outputs. See docs/naming_direct_vs_derived.md.
"""

# ---- Stress ----
# Direct: user-reported overall stress from sliders (init and completion).
EXPECTED_STRESS = "expected_stress"  # direct, init
ACTUAL_STRESS = "actual_stress"      # direct, completion
# Derived: computed from cognitive, emotional, physical, aversion (formula).
STRESS_DERIVED = "stress_level"      # derived; do not use for slider defaults

# ---- Relief (for consistency; relief is direct only, no derived relief key) ----
EXPECTED_RELIEF = "expected_relief"
ACTUAL_RELIEF = "actual_relief"
