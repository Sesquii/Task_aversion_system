# Naming Convention: Direct vs Derived (Inferred) Metrics

## Purpose

This document defines how we name **direct** (user-reported) and **derived** (computed/inferred) metrics so that code, UI, and analytics stay consistent. Use this convention for all existing and future scores.

## Definitions

- **Direct:** Value comes from user input (sliders, forms). Stored as submitted; no formula.
- **Derived (inferred):** Value is computed from other inputs (e.g. formula over multiple sliders or external data). Not stored as a raw user input; calculated in analytics or at save time.

## Naming Rules

### Direct metrics

- **Storage keys:** Use `expected_<name>` for initialization (predicted) and `actual_<name>` for completion.
- **Examples:** `expected_stress`, `actual_stress`, `expected_relief`, `actual_relief`.
- **UI:** Label as "Expected …" / "Actual …" or "… (reported)" where helpful.
- **Do not** default direct-metric sliders from derived metrics (e.g. do not use `stress_level` to set the "Actual overall stress" slider).

### Derived metrics

- **Storage keys:** Use a distinct key that indicates computation, e.g. `<name>_level`, `<name>_derived`, or `<name>_computed`. Prefer `*_level` when it denotes an aggregate level (e.g. stress level from components).
- **Examples:** `stress_level` (derived stress from components), `net_wellbeing` (derived from relief and stress).
- **UI:** Label as "… (calculated)" or "Derived …" where it helps distinguish from direct (e.g. "Derived stress" or "Stress (calculated)").
- **Analytics:** Use derived metrics for dashboards, rankings, and formulas; do not overwrite or confuse with direct keys.

### Mapping (stress example)

| Concept            | Type    | Storage key(s)        | Notes                                      |
|--------------------|---------|------------------------|--------------------------------------------|
| Direct stress (init)   | Direct  | `expected_stress`      | User-reported at initialization           |
| Direct stress (done)   | Direct  | `actual_stress`        | User-reported at completion                |
| Derived stress         | Derived | `stress_level`         | Formula over cognitive, emotional, physical, aversion |

Other metrics (relief, emotional load, etc.) follow the same idea: `expected_*` / `actual_*` = direct; computed aggregates use their own keys (e.g. `stress_level`, `net_wellbeing`).

## For New Metrics

When adding a new user-reported score:

1. **Direct:** Store as `expected_<metric>` and/or `actual_<metric>` in predicted/actual payloads. Do not use these keys for formula outputs.
2. **Derived:** Use a separate key (e.g. `<metric>_level`, `<metric>_derived`) and compute in analytics or backend. Do not use the same key as the direct slider value.
3. **Defaults:** Slider defaults for direct metrics may use previous direct values or task-template defaults; never default a direct slider from a derived metric of the same concept.
4. **Docs:** Update this doc and `relief_stress_formulas.md` (or the relevant formula doc) with the new keys and whether they are direct or derived.

## References

- Stress formulas and direct vs derived stress: `relief_stress_formulas.md`
- Factor concepts and misperception: `factors_concept.md`
- Metric key constants (code): `backend/metric_keys.py`
