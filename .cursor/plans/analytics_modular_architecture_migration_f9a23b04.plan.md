---
name: Analytics Modular Architecture Migration
overview: Refactor the monolithic analytics page into a modular architecture with separate element files, module pages, and a navigation home page. Each visualization becomes its own element file, modules compose elements, and migration happens one module per commit.
todos:
  - id: setup_infrastructure
    content: Create directory structure (ui/analytics/, pages/, elements/) and __init__.py files
    status: pending
  - id: create_shared
    content: Create ui/analytics/shared.py with common imports and analytics_service
    status: pending
    dependencies:
      - setup_infrastructure
  - id: create_home
    content: Create ui/analytics/home.py with module navigation page
    status: pending
    dependencies:
      - setup_infrastructure
  - id: extract_summary_metrics
    content: Extract summary metrics cards to elements/summary_metrics.py
    status: pending
    dependencies:
      - create_shared
  - id: create_dashboard_module
    content: Create pages/dashboard_overview.py module using summary_metrics element
    status: pending
    dependencies:
      - extract_summary_metrics
  - id: extract_productivity_elements
    content: Extract productivity volume and life balance to separate element files
    status: pending
    dependencies:
      - create_shared
  - id: create_productivity_module
    content: Create pages/productivity_volume.py module
    status: pending
    dependencies:
      - extract_productivity_elements
  - id: extract_stress_elements
    content: Extract stress dimension visualizations to element files
    status: pending
    dependencies:
      - create_shared
  - id: create_stress_module
    content: Create pages/stress_analysis.py module
    status: pending
    dependencies:
      - extract_stress_elements
  - id: migrate_emotional_flow
    content: Move existing emotional flow page to new structure (pages/emotional_flow.py)
    status: pending
    dependencies:
      - setup_infrastructure
  - id: extract_task_elements
    content: Extract task rankings to elements/task_rankings.py
    status: pending
    dependencies:
      - create_shared
  - id: create_task_module
    content: Create pages/task_performance.py module
    status: pending
    dependencies:
      - extract_task_elements
  - id: extract_trends_elements
    content: Extract trends and distribution visualizations to element files
    status: pending
    dependencies:
      - create_shared
  - id: create_trends_module
    content: Create pages/trends_patterns.py module
    status: pending
    dependencies:
      - extract_trends_elements
  - id: extract_metric_elements
    content: Extract metric comparison scatter plot to element file
    status: pending
    dependencies:
      - create_shared
  - id: create_metric_module
    content: Create pages/metric_relationships.py module
    status: pending
    dependencies:
      - extract_metric_elements
  - id: extract_aversion_elements
    content: Extract obstacles and aversion analytics to element files
    status: pending
    dependencies:
      - create_shared
  - id: create_aversion_module
    content: Create pages/aversion_obstacles.py module
    status: pending
    dependencies:
      - extract_aversion_elements
  - id: extract_dev_tools
    content: Extract correlation explorer to elements/correlation_explorer.py
    status: pending
    dependencies:
      - create_shared
  - id: create_dev_module
    content: Create pages/developer_tools.py module
    status: pending
    dependencies:
      - extract_dev_tools
  - id: update_app_imports
    content: Update app.py to import analytics from new location
    status: pending
    dependencies:
      - create_home
  - id: cleanup_old_file
    content: Remove or deprecate old analytics_page.py after all modules migrated
    status: pending
    dependencies:
      - update_app_imports
---

# Analytics Modular Architecture Migration Plan

## Architecture Overview

The analytics system will be refactored from a single 1200+ line file into a modular architecture:

```
ui/analytics/
├── __init__.py                    # Module registration
├── home.py                        # Navigation home page
├── pages/                         # Module page files
│   ├── __init__.py
│   ├── dashboard_overview.py     # Summary metrics
│   ├── productivity_volume.py    # Productivity & work/play balance
│   ├── stress_analysis.py        # Stress dimensions & efficiency
│   ├── emotional_flow.py         # Emotion tracking (already exists)
│   ├── task_performance.py       # Task rankings & leaderboards
│   ├── trends_patterns.py        # Time series & distributions
│   ├── metric_relationships.py  # Scatter plots & correlations
│   ├── aversion_obstacles.py     # Aversion analytics
│   └── developer_tools.py        # Advanced correlation tools
└── elements/                      # Individual visualization elements
    ├── __init__.py
    ├── summary_metrics.py       # Dashboard metric cards
    ├── productivity_volume_cards.py
    ├── life_balance_cards.py
    ├── obstacles_cards.py
    ├── aversion_cards.py
    ├── relief_trend_chart.py
    ├── attribute_distribution.py
    ├── trends_interactive.py
    ├── stress_dimensions_bars.py
    ├── stress_dimensions_timeline.py
    ├── stress_efficiency_leaderboard.py
    ├── task_rankings.py
    ├── metric_comparison_scatter.py
    ├── correlation_explorer.py
    └── [emotional flow elements already exist]
```

## Element-to-Module Mapping

### Module 1: Dashboard Overview (`pages/dashboard_overview.py`)

**Elements:**

- `elements/summary_metrics.py` - All metric cards from `build_analytics_page()` lines 51-88

### Module 2: Productivity & Volume (`pages/productivity_volume.py`)

**Elements:**

- `elements/productivity_volume_cards.py` - Productivity volume section (lines 86-137)
- `elements/life_balance_cards.py` - Life balance section (lines 139-171)

### Module 3: Stress Analysis (`pages/stress_analysis.py`)

**Elements:**

- `elements/stress_dimensions_bars.py` - Bar charts (lines 448-534)
- `elements/stress_dimensions_timeline.py` - Time series line chart (lines 536-598)
- `elements/stress_efficiency_leaderboard.py` - Leaderboard table (lines 1180-1210)

### Module 4: Emotional Flow (`pages/emotional_flow.py`)

**Status:** Already exists, but needs to be moved to new structure

**Elements:** (Already implemented)

- `elements/emotion_transitions.py`
- `elements/emotional_load_vs_relief.py`
- `elements/expected_vs_actual_emotional.py`
- `elements/emotion_trends.py`
- `elements/emotional_spikes.py`
- `elements/emotion_correlations.py`

### Module 5: Task Performance (`pages/task_performance.py`)

**Elements:**

- `elements/task_rankings.py` - Task performance rankings (lines 1134-1177)

### Module 6: Trends & Patterns (`pages/trends_patterns.py`)

**Elements:**

- `elements/relief_trend_chart.py` - Total relief trend (lines 292-307)
- `elements/attribute_distribution.py` - Attribute box plot (lines 310-325)
- `elements/trends_interactive.py` - Interactive trends section (lines 328-420)

### Module 7: Metric Relationships (`pages/metric_relationships.py`)

**Elements:**

- `elements/metric_comparison_scatter.py` - Metric comparison with efficiency analysis (lines 621-1013)

### Module 8: Aversion & Obstacles (`pages/aversion_obstacles.py`)

**Elements:**

- `elements/obstacles_cards.py` - Overcoming obstacles section (lines 173-222)
- `elements/aversion_cards.py` - Aversion analytics section (lines 224-267)

### Module 9: Developer Tools (`pages/developer_tools.py`)

**Elements:**

- `elements/correlation_explorer.py` - Correlation explorer (lines 1016-1131)

## Implementation Steps

### Phase 1: Setup Infrastructure

1. Create directory structure: `ui/analytics/`, `ui/analytics/pages/`, `ui/analytics/elements/`
2. Create `__init__.py` files
3. Create `ui/analytics/home.py` with module navigation
4. Create shared utilities file `ui/analytics/shared.py` for common imports and constants

### Phase 2: Extract Elements (One per commit)

For each element:

1. Create element file in `ui/analytics/elements/`
2. Extract visualization function from `analytics_page.py`
3. Ensure element is self-contained with proper imports
4. Test element in isolation if possible

### Phase 3: Create Module Pages (One per commit)

For each module:

1. Create module page file in `ui/analytics/pages/`
2. Import and compose relevant elements
3. Register route: `@ui.page('/analytics/{module-name}')`
4. Add navigation link to home page
5. Remove old code from `analytics_page.py`

### Phase 4: Update Home Page

1. Create module registry/list
2. Add module cards with descriptions
3. Link to each module page
4. Add "All Analytics" link (optional future feature)

### Phase 5: Cleanup

1. Remove old `analytics_page.py` or convert to legacy redirect
2. Update `app.py` to import from new location
3. Test all routes work correctly

## Migration Order (One Module Per Commit)

**Commit 1:** Infrastructure setup (directories, home page skeleton)

**Commit 2:** Module 1 - Dashboard Overview

**Commit 3:** Module 2 - Productivity & Volume

**Commit 4:** Module 3 - Stress Analysis

**Commit 5:** Module 4 - Emotional Flow (move existing)

**Commit 6:** Module 5 - Task Performance

**Commit 7:** Module 6 - Trends & Patterns

**Commit 8:** Module 7 - Metric Relationships

**Commit 9:** Module 8 - Aversion & Obstacles

**Commit 10:** Module 9 - Developer Tools

**Commit 11:** Final cleanup and route updates

## File Structure Details

### `ui/analytics/shared.py`

```python
# Common imports and constants
from nicegui import ui
import pandas as pd
import plotly.express as px
from backend.analytics import Analytics

analytics_service = Analytics()
# Import attribute options from existing analytics_page.py
```

### `ui/analytics/home.py`

```python
# Simple navigation page listing all modules
@ui.page('/analytics')
def analytics_home():
    ui.label("Analytics Modules").classes("text-2xl font-bold mb-4")
    # Module cards with descriptions and links
```

### Element File Pattern

```python
# ui/analytics/elements/element_name.py
from nicegui import ui
import pandas as pd
import plotly.express as px
from backend.analytics import Analytics

analytics_service = Analytics()

def render_element_name(data=None):
    """Render the [element name] visualization."""
    # Element implementation
    pass
```

### Module Page Pattern

```python
# ui/analytics/pages/module_name.py
from nicegui import ui
from ..elements import element1, element2, element3
from ..shared import analytics_service

def register_module():
    @ui.page('/analytics/module-name')
    def module_page():
        # Navigation
        ui.button("← Back to Analytics", on_click=lambda: ui.navigate.to('/analytics'))
        
        # Render elements
        element1.render_element1()
        element2.render_element2()
        element3.render_element3()
```

## Key Considerations

1. **Shared Dependencies:** Create `shared.py` for common imports (analytics_service, ATTRIBUTE_OPTIONS, etc.)
2. **Element Reusability:** Elements can be imported by multiple modules if needed
3. **Data Fetching:** Each element should fetch its own data or accept data as parameter
4. **Backward Compatibility:** Keep `/analytics` route working during migration
5. **Import Paths:** Use relative imports within analytics package
6. **Testing:** Test each module independently after migration

## Benefits

- **Maintainability:** Each element is isolated and testable
- **Scalability:** Easy to add new modules/elements
- **Performance:** Modules load independently
- **Developer Experience:** Clear separation of concerns
- **Git Workflow:** One module per commit reduces merge conflicts

## Migration Safety

- Keep old `analytics_page.py` until all modules migrated
- Use feature flags if needed during transition
- Test each commit before proceeding
- Maintain route compatibility throughout