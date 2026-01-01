Task Aversion System: Data-driven productivity analytics that quantifies task performance through psychological tracking. System calculates ~12 scoring metrics from user input and derived calculations.

Data Sources: ~40% direct user input (relief score 0-100, stress components, aversion, time estimates/actuals, emotions, completion %). ~60% calculated metrics (execution score, net wellbeing, stress efficiency, work volume/consistency, time tracking consistency, life balance, behavioral score, productivity score, grit score).

Execution Score (one of ~12, production-ready): 4-factor multiplicative model: 50 × (1+difficulty) × (0.5+0.5×speed) × (0.5+0.5×start_speed) × completion. Difficulty uses exponential: 1.0×(1-exp(-(0.7×aversion+0.3×load)/50)). Speed factor based on actual/estimated time ratio with linear/exponential decay.

Composite Score: Weighted combination of 12 components normalized 0-100. Formula: Σ(Component×Weight)/Σ(Weights). Includes work volume (tiered: 0-2h=0-25, 2-4h=25-50, 4-6h=50-75, 6-8h=75-100), time tracking consistency (exponential: 100×(1-exp(-coverage×2.0))), net wellbeing (relief-stress, normalized 50=neutral), stress efficiency (relief/stress ratio).

Tech: Python 3.8+, NiceGUI, pandas/SQLAlchemy, CSV/PostgreSQL dual-mode. Analytics module: 7,400+ lines, 5,000+ lines formula logic. Scales to 100+ templates, 1,000+ instances, sub-second queries.

Innovation: Quantifies psychological states into metrics. Multiplicative scoring ensures balanced performance. Exponential decay prevents gaming.
