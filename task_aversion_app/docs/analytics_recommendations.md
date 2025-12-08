# Analytics & Recommendations Notes

## Data & Schema

- Each task instance now records the following attributes (see `backend/task_schema.py`): duration_minutes, relief_score, cognitive_load, emotional_load, environmental_effect, skills_improved, behavioral_score, net_relief.
- Attributes are stored as dedicated CSV columns plus mirrored inside the `actual` JSON payload so legacy entries remain valid.
- When historical rows miss a value, we backfill from JSON payloads or schema defaults to keep analytics resilient.

## Analytics Surfaces

1. **Compact analytics pulse (dashboard)**  
   - Collapsed card under "Active Tasks" showing counts, average relief, cognitive load, and timing signals.  
   - Includes a quick link to the full Analytics Studio.

2. **Analytics Studio (`/analytics`)**  
   - Built with NiceGUI + Plotly to allow interactive charts without switching stacks.  
   - Ships with a relief trend line, attribute distribution boxplot, and a recommendation lab that reuses the backend filters.  
   - Designed so swapping Plotly for Altair or pandas-profiling exports only touches this module.

## Recommendations

- Manual filters (duration, relief, cognitive load, focus metric) live in both the dashboard strip and the studio.  
- Backend `Analytics.recommendations()` returns category-based picks (shortest, highest relief, lowest cognitive load, highest net relief proxy).  
- The API is intentionally data-agnostic so an ML scorer (LightFM, matrix factorization, embeddings) can later inject ranked rows without UI changes.

## ML Roadmap Assumptions

| Phase | Goal | Tooling |
| --- | --- | --- |
| 1 | Synthetic bootstrapping | pandas, numpy, Faker for scenario data |
| 2 | Rule-based scoring (current) | Python heuristics leveraging schema attributes |
| 3 | Preference learning | scikit-learn pipelines (ridge, gradient boosting) |
| 4 | Hybrid recommendations | LightFM / PyTorch embedding models |

Additional considerations:

- Store intermediate features (e.g., rolling relief averages) in-memory first; persist once signal stabilizes.
- Use opt-in telemetry to collect label-quality data before training supervised recommenders.
- Keep manual filters visible even after ML launch to provide transparency and override levers.

