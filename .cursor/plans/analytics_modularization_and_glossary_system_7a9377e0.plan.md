---
name: Analytics Modularization and Glossary System
overview: Refactor analytics page into modular architecture with individual graphic aid scripts, module-based organization, and a glossary page for navigation and search. Main analytics page will have loading screen, while glossary page provides module links and search functionality without analytics elements.
todos:
  - id: create_structure
    content: Create directory structure (analytics/, modules/, graphic_aids/) and base files
    status: pending
  - id: extract_stress_dimensions
    content: Extract stress dimension charts into graphic_aids/stress_dimensions_bars.py and stress_dimensions_timeline.py (lines 448-598)
    status: pending
    dependencies:
      - create_structure
  - id: extract_metric_comparison
    content: Extract metric comparison scatter into graphic_aids/metric_comparison_scatter.py (lines 621-1013)
    status: pending
    dependencies:
      - create_structure
  - id: extract_relief_trend
    content: Extract relief trend chart into graphic_aids/relief_trend_chart.py (lines 292-307)
    status: pending
    dependencies:
      - create_structure
  - id: extract_attribute_distribution
    content: Extract attribute distribution into graphic_aids/attribute_distribution.py (lines 310-326)
    status: pending
    dependencies:
      - create_structure
  - id: extract_trends_interactive
    content: Extract interactive trends into graphic_aids/trends_interactive.py (lines 328-420)
    status: pending
    dependencies:
      - create_structure
  - id: extract_aversion_formulas
    content: Extract aversion formulas comparison into graphic_aids/aversion_cards.py (lines 224-267)
    status: pending
    dependencies:
      - create_structure
  - id: migrate_emotional_flow
    content: Migrate existing emotional flow page to new structure in modules/emotional_flow.py
    status: pending
    dependencies:
      - create_structure
  - id: create_shared_utils
    content: Create shared.py with common imports and constants (analytics_service, ATTRIBUTE_OPTIONS)
    status: pending
    dependencies:
      - create_structure
  - id: extract_summary_metrics
    content: Extract summary metrics cards into graphic_aids/summary_metrics.py (lines 60-96)
    status: pending
    dependencies:
      - create_structure
  - id: extract_productivity_volume
    content: Extract productivity volume cards into graphic_aids/productivity_volume_cards.py (lines 98-137)
    status: pending
    dependencies:
      - create_structure
  - id: extract_life_balance
    content: Extract life balance cards into graphic_aids/life_balance_cards.py (lines 139-171)
    status: pending
    dependencies:
      - create_structure
  - id: extract_obstacles
    content: Extract obstacles cards into graphic_aids/obstacles_cards.py (lines 173-222)
    status: pending
    dependencies:
      - create_structure
  - id: extract_task_rankings
    content: Extract task rankings into graphic_aids/task_rankings.py (lines 1134-1177)
    status: pending
    dependencies:
      - create_structure
  - id: extract_stress_efficiency
    content: Extract stress efficiency leaderboard into graphic_aids/stress_efficiency_leaderboard.py (lines 1180-1210)
    status: pending
    dependencies:
      - create_structure
  - id: extract_correlation_explorer
    content: Extract correlation explorer into graphic_aids/correlation_explorer.py (lines 1016-1131)
    status: pending
    dependencies:
      - create_structure
  - id: create_overview_module
    content: Create modules/overview.py with summary metrics
    status: pending
    dependencies:
      - extract_summary_metrics
  - id: create_productivity_module
    content: Create modules/productivity.py with productivity volume and life balance
    status: pending
    dependencies:
      - extract_productivity_volume
      - extract_life_balance
  - id: create_stress_module
    content: Create modules/stress.py with stress dimensions and efficiency
    status: pending
    dependencies:
      - extract_stress
      - extract_stress_efficiency
  - id: create_task_performance_module
    content: Create modules/task_performance.py with task rankings
    status: pending
    dependencies:
      - extract_task_rankings
  - id: create_trends_module
    content: Create modules/trends.py with relief trends, attribute distribution, and interactive trends
    status: pending
    dependencies:
      - extract_trends
  - id: create_metric_relationships_module
    content: Create modules/metric_relationships.py with metric comparison scatter
    status: pending
    dependencies:
      - extract_trends
  - id: create_aversion_module
    content: Create modules/aversion.py with obstacles and aversion cards
    status: pending
    dependencies:
      - extract_obstacles
      - extract_aversion_formulas
  - id: create_developer_tools_module
    content: Create modules/developer_tools.py with correlation explorer
    status: pending
    dependencies:
      - extract_correlation_explorer
  - id: create_glossary_page
    content: Create glossary_page.py with module list and search functionality (NO analytics elements)
    status: pending
    dependencies:
      - create_structure
  - id: create_main_page
    content: Create main_page.py with loading screen and navigation
    status: pending
    dependencies:
      - create_structure
  - id: update_routing
    content: Update register_analytics_page() to use new routes and pages
    status: pending
    dependencies:
      - create_glossary_page
      - create_main_page
  - id: test_migration
    content: Test all graphic aids work correctly after migration
    status: pending
    dependencies:
      - update_routing
---

# Analytics Modularization and Glossary System Plan

**Created:** 2025-01-XX**Status:** Planning**Priority:** Medium (improves maintainability and UX)

## Overview

Refactor the monolithic `analytics_page.py` (1500+ lines) into a modular architecture:

- Individual graphic aid scripts (one per visualization)
- Module-based organization (group related graphic aids)
- Main analytics page with loading screen
- Glossary page for navigation and search (no analytics elements, just links)

## Goals

1. Break down analytics page into maintainable modules
2. Create reusable graphic aid components (one script per aid)
3. Implement module loader system
4. Create glossary page with search functionality
5. Add loading screen to main analytics page
6. Improve code organization and maintainability

## Architecture

### Directory Structure

```javascript
task_aversion_app/
├── ui/
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── main_page.py          # Main analytics page with loading screen
│   │   ├── glossary_page.py     # Glossary/search page (no analytics elements)
│   │   ├── modules/
│   │   │   ├── __init__.py
│   │   │   ├── overview.py       # Overview module loader
│   │   │   ├── relief.py         # Relief analytics module loader
│   │   │   ├── stress.py         # Stress analytics module loader
│   │   │   ├── productivity.py   # Productivity analytics module loader
│   │   │   ├── emotional_flow.py # Emotional flow module loader
│   │   │   └── aversion.py       # Aversion analytics module loader
│   │   └── graphic_aids/
│   │       ├── __init__.py
│   │       ├── dashboard_metrics.py      # Dashboard metrics cards
│   │       ├── relief_summary.py         # Relief summary visualization
│   │       ├── aversion_formulas.py      # Aversion formula comparisons
│   │       ├── attribute_box_plot.py     # Attribute distribution box plots
│   │       ├── multi_attribute_trends.py # Multi-attribute trend charts
│   │       ├── stress_dimensions.py      # Stress dimension bar charts
│   │       ├── emotional_flow_chart.py   # Emotional flow visualization
│   │       ├── productivity_volume.py    # Productivity volume charts
│   │       ├── life_balance.py          # Life balance metrics
│   │       └── ... (one per graphic aid)
│   └── analytics_page.py         # Legacy file (deprecate after migration)
```

### Module System

Each module file (`modules/overview.py`, etc.) will:

- Import relevant graphic aids
- Define which graphic aids belong to the module
- Provide a `render_module()` function that loads all aids for that module

### Graphic Aid System

Each graphic aid file (`graphic_aids/dashboard_metrics.py`, etc.) will:

- Be self-contained (one visualization/component)
- Export a `render()` function that takes data and renders the visualization
- Handle its own data fetching or receive data as parameter
- Be reusable across modules if needed

### Glossary Page

The glossary page will:

- **NOT contain any analytics elements** (no charts, no data)
- List all modules with descriptions
- Provide search functionality to find graphic aids by name
- Link to modules (navigate to module page)
- Link to individual graphic aids (navigate to graphic aid page)
- Have clean, simple navigation-focused UI

## Implementation Strategy

### Phase 1: Create Directory Structure and Base Files

**Files to create:**

- `ui/analytics/__init__.py` - Package initialization
- `ui/analytics/main_page.py` - Main analytics page with loading screen
- `ui/analytics/glossary_page.py` - Glossary/search page
- `ui/analytics/shared.py` - Shared utilities (common imports, constants, ATTRIBUTE_OPTIONS)
- `ui/analytics/modules/__init__.py` - Modules package
- `ui/analytics/graphic_aids/__init__.py` - Graphic aids package
- `ui/analytics/graphic_aids/base.py` - Base class for graphic aids

**Tasks:**

1. Create directory structure
2. Set up package initialization files
3. Create base classes/interfaces for modules and graphic aids
4. Create `shared.py` with common imports (analytics_service, ATTRIBUTE_OPTIONS, etc.)

### Phase 2: Extract Graphic Aids

**Files to create/modify:**

- Extract each visualization from `analytics_page.py` into individual files
- Start with most independent visualizations first

**Graphic Aids to Extract (with line references from current `analytics_page.py`):**

1. `summary_metrics.py` - Dashboard metrics cards (lines 60-96)
2. `productivity_volume_cards.py` - Productivity volume section (lines 98-137)
3. `life_balance_cards.py` - Life balance section (lines 139-171)
4. `obstacles_cards.py` - Overcoming obstacles section (lines 173-222)
5. `aversion_cards.py` - Aversion analytics formulas (lines 237-309)
6. `relief_trend_chart.py` - Total relief trend (lines 292-307)
7. `attribute_distribution.py` - Attribute box plot (lines 310-326)
8. `trends_interactive.py` - Interactive multi-attribute trends (lines 328-420)
9. `stress_dimensions_bars.py` - Stress dimension bar charts (lines 448-534)
10. `stress_dimensions_timeline.py` - Stress dimension time series (lines 536-598)
11. `metric_comparison_scatter.py` - Metric comparison with efficiency analysis (lines 621-1013)
12. `correlation_explorer.py` - Correlation explorer (lines 1016-1131)
13. `task_rankings.py` - Task performance rankings (lines 1134-1177)
14. `stress_efficiency_leaderboard.py` - Stress efficiency leaderboard (lines 1180-1210)
15. `emotional_flow_chart.py` - Emotional flow visualization (from `build_emotional_flow_page()`)
16. Additional graphic aids as identified during extraction

**Tasks:**

1. For each graphic aid:

- Create new file in `graphic_aids/`
- Extract visualization code
- Create `render(data)` function
- Handle data fetching or accept data parameter
- Test in isolation

### Phase 3: Create Module System

**Files to create:**

- `modules/overview.py` - Overview module (dashboard metrics, summary stats)
- `modules/productivity.py` - Productivity & volume module
- `modules/stress.py` - Stress analysis module
- `modules/emotional_flow.py` - Emotional flow module (migrate existing)
- `modules/task_performance.py` - Task performance module
- `modules/trends.py` - Trends & patterns module
- `modules/metric_relationships.py` - Metric relationships module
- `modules/aversion.py` - Aversion & obstacles module
- `modules/developer_tools.py` - Developer tools module

**Tasks:**

1. For each module:

- Define which graphic aids belong to it
- Create `render_module()` function
- Load and render all graphic aids for that module
- Handle module-specific data loading

**Module Definitions (9 modules total):**

1. **Overview Module** (`modules/overview.py`):

   - `summary_metrics.py` - Dashboard metrics cards (lines 60-96)

2. **Productivity & Volume Module** (`modules/productivity.py`):

   - `productivity_volume_cards.py` - Productivity volume section (lines 98-137)
   - `life_balance_cards.py` - Life balance section (lines 139-171)

3. **Stress Analysis Module** (`modules/stress.py`):

   - `stress_dimensions_bars.py` - Bar charts (lines 448-534)
   - `stress_dimensions_timeline.py` - Time series line chart (lines 536-598)
   - `stress_efficiency_leaderboard.py` - Leaderboard table (lines 1180-1210)

4. **Emotional Flow Module** (`modules/emotional_flow.py`):

   - Already exists, but needs to be moved to new structure
   - `emotional_flow_chart.py` - Emotional flow visualization
   - Additional emotional flow elements (transitions, load vs relief, etc.)

5. **Task Performance Module** (`modules/task_performance.py`):

   - `task_rankings.py` - Task performance rankings (lines 1134-1177)

6. **Trends & Patterns Module** (`modules/trends.py`):

   - `relief_trend_chart.py` - Total relief trend (lines 292-307)
   - `attribute_distribution.py` - Attribute box plot (lines 310-326)
   - `trends_interactive.py` - Interactive trends section (lines 328-420)

7. **Metric Relationships Module** (`modules/metric_relationships.py`):

   - `metric_comparison_scatter.py` - Metric comparison with efficiency analysis (lines 621-1013)

8. **Aversion & Obstacles Module** (`modules/aversion.py`):

   - `obstacles_cards.py` - Overcoming obstacles section (lines 173-222)
   - `aversion_cards.py` - Aversion analytics section (lines 224-267)

9. **Developer Tools Module** (`modules/developer_tools.py`):

   - `correlation_explorer.py` - Correlation explorer (lines 1016-1131)

### Phase 4: Create Glossary Page

**File:** `ui/analytics/glossary_page.py`**Features:**

1. **Module List Section**:

- Display all modules with descriptions
- Link to each module page
- Visual cards for each module

2. **Search Functionality**:

- Search bar at top of page
- Search by graphic aid name or description
- Display matching graphic aids
- Link directly to graphic aid page

3. **Graphic Aid Index** (optional):

- List all graphic aids grouped by module
- Quick links to each graphic aid

**UI Requirements:**

- Clean, navigation-focused design
- NO analytics elements (no charts, no data visualizations)
- Search bar prominently displayed
- Module cards with descriptions
- Links to modules and graphic aids

### Phase 5: Create Main Analytics Page with Loading Screen

**File:** `ui/analytics/main_page.py`**Features:**

1. **Loading Screen**:

- Show loading spinner immediately on page load
- Display "Analytics may take a while to load" message
- Show progress indicator if possible
- Load data asynchronously

2. **Module Navigation**:

- Link to glossary page
- Quick links to common modules
- Recent modules section

3. **Default View** (optional):

- Show overview module by default
- Or redirect to glossary page

### Phase 6: Create Individual Graphic Aid Pages

**Files to create:**

- Individual page routes for each graphic aid
- Allow viewing graphic aids in isolation
- Useful for deep-dive analysis

**Route Pattern:**

- `/analytics/graphic-aid/{aid_name}` - Individual graphic aid page
- `/analytics/module/{module_name}` - Module page (loads all aids for module)

### Phase 7: Update Routing and Registration

**Files to modify:**

- `ui/analytics_page.py` - Update `register_analytics_page()` function
- `app.py` - Ensure new routes are registered

**Routes:**

- `/analytics` - Main analytics page (with loading screen)
- `/analytics/glossary` - Glossary/search page
- `/analytics/module/{module_name}` - Module pages
- `/analytics/graphic-aid/{aid_name}` - Individual graphic aid pages
- `/analytics/emotional-flow` - Keep existing emotional flow page (or migrate to module)

## Technical Details

### Shared Utilities File

```python
# ui/analytics/shared.py
# Common imports and constants
from nicegui import ui
import pandas as pd
import plotly.express as px
from backend.analytics import Analytics
from backend.task_schema import TASK_ATTRIBUTES

analytics_service = Analytics()

# Attribute options for trends / correlations
NUMERIC_ATTRIBUTE_OPTIONS = [
    {'label': attr.label, 'value': attr.key}
    for attr in TASK_ATTRIBUTES
    if attr.dtype == 'numeric'
]

CALCULATED_METRICS = [
    {'label': 'Stress Level', 'value': 'stress_level'},
    {'label': 'Net Wellbeing', 'value': 'net_wellbeing'},
    # ... etc (from existing analytics_page.py)
]

ATTRIBUTE_OPTIONS = NUMERIC_ATTRIBUTE_OPTIONS + CALCULATED_METRICS
ATTRIBUTE_LABELS = {opt['value']: opt['label'] for opt in ATTRIBUTE_OPTIONS}
```

### Graphic Aid Interface

```python
# ui/analytics/graphic_aids/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class GraphicAid(ABC):
    """Base class for graphic aids."""
    
    name: str  # Display name
    description: str  # Description for glossary
    module: str  # Which module this belongs to
    
    @abstractmethod
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render the graphic aid. Data is optional - can fetch internally."""
        pass
    
    def fetch_data(self) -> Dict[str, Any]:
        """Fetch data for this graphic aid. Override if needed."""
        from backend.analytics import Analytics
        analytics = Analytics()
        # Fetch specific data needed
        return {}
```

### Module Interface

```python
# ui/analytics/modules/base.py
from typing import List
from ui.analytics.graphic_aids import GraphicAid

class AnalyticsModule:
    """Base class for analytics modules."""
    
    name: str
    description: str
    graphic_aids: List[str]  # List of graphic aid names
    
    def render_module(self) -> None:
        """Render all graphic aids for this module."""
        for aid_name in self.graphic_aids:
            aid = get_graphic_aid(aid_name)
            if aid:
                aid.render()
```

### Graphic Aid File Pattern

```python
# ui/analytics/graphic_aids/element_name.py
from nicegui import ui
import pandas as pd
import plotly.express as px
from ui.analytics.shared import analytics_service, ATTRIBUTE_OPTIONS
from ui.analytics.graphic_aids.base import GraphicAid
from typing import Dict, Any, Optional

class ElementNameAid(GraphicAid):
    name = "Element Display Name"
    description = "Description for glossary"
    module = "module_name"
    
    def render(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Render the graphic aid. Data is optional - can fetch internally."""
        if data is None:
            data = self.fetch_data()
        
        # Element implementation
        with ui.card().classes("p-4 mb-4"):
            ui.label(self.name).classes("text-xl font-bold mb-2")
            # ... visualization code ...
    
    def fetch_data(self) -> Dict[str, Any]:
        """Fetch data for this graphic aid. Override if needed."""
        # Fetch specific data needed
        return {}
```

### Module Page Pattern

```python
# ui/analytics/modules/module_name.py
from nicegui import ui
from ..graphic_aids import element1, element2, element3
from ..shared import analytics_service

def register_module():
    @ui.page('/analytics/module/module-name')
    def module_page():
        # Navigation
        ui.button("← Back to Glossary", on_click=lambda: ui.navigate.to('/analytics/glossary'))
        
        # Module header
        ui.label("Module Name").classes("text-2xl font-bold mb-4")
        ui.label("Module description").classes("text-gray-500 mb-6")
        
        # Render graphic aids
        element1.Element1Aid().render()
        element2.Element2Aid().render()
        element3.Element3Aid().render()
```

### Glossary Page Implementation

```python
# ui/analytics/glossary_page.py
from nicegui import ui

# Module definitions
MODULES = [
    {
        'name': 'Overview',
        'description': 'Key metrics and summary statistics',
        'route': '/analytics/module/overview',
        'graphic_aids': ['dashboard_metrics', 'summary_stats']
    },
    {
        'name': 'Relief Analytics',
        'description': 'Relief scores, trends, and duration analysis',
        'route': '/analytics/module/relief',
        'graphic_aids': ['relief_summary', 'relief_trends']
    },
    # ... etc
]

# Graphic aid registry
GRAPHIC_AIDS = [
    {
        'name': 'Dashboard Metrics',
        'description': 'Key performance indicators',
        'module': 'Overview',
        'route': '/analytics/graphic-aid/dashboard_metrics'
    },
    # ... etc
]

def build_glossary_page():
    ui.label("Analytics Glossary").classes("text-2xl font-bold mb-4")
    ui.label("Browse modules and search for specific analytics visualizations.").classes(
        "text-gray-500 mb-6"
    )
    
    # Search bar
    with ui.card().classes("p-4 mb-6"):
        ui.label("Search Graphic Aids").classes("text-lg font-semibold mb-2")
        search_input = ui.input("Search by name or description").classes("w-full")
        search_results = ui.column().classes("mt-3")
        
        def update_search():
            search_results.clear()
            query = search_input.value.lower() if search_input.value else ""
            
            if not query:
                return
            
            matches = [
                aid for aid in GRAPHIC_AIDS
                if query in aid['name'].lower() or query in aid['description'].lower()
            ]
            
            if not matches:
                with search_results:
                    ui.label("No matches found").classes("text-gray-500")
            else:
                with search_results:
                    for aid in matches:
                        with ui.card().classes("p-3 mb-2"):
                            ui.label(aid['name']).classes("font-semibold")
                            ui.label(aid['description']).classes("text-sm text-gray-600 mb-2")
                            ui.button(
                                "View",
                                on_click=lambda a=aid: ui.navigate.to(a['route'])
                            ).classes("text-sm")
        
        search_input.on('input', update_search)
    
    # Module list
    with ui.card().classes("p-4"):
        ui.label("Analytics Modules").classes("text-lg font-semibold mb-4")
        with ui.row().classes("gap-4 flex-wrap"):
            for module in MODULES:
                with ui.card().classes("p-4 min-w-[250px] border border-blue-200"):
                    ui.label(module['name']).classes("text-lg font-bold mb-2")
                    ui.label(module['description']).classes("text-sm text-gray-600 mb-3")
                    ui.button(
                        "View Module",
                        on_click=lambda m=module: ui.navigate.to(m['route'])
                    ).classes("w-full")
                    ui.label(f"{len(module['graphic_aids'])} graphic aids").classes(
                        "text-xs text-gray-500 mt-2"
                    )
```

## Migration Strategy

### Migration Order (One Module Per Commit)

**Commit 1:** Infrastructure setup (directories, base files, shared.py, glossary skeleton, main page skeleton)

**Commit 2:** Module 1 - Overview (extract summary_metrics.py)

**Commit 3:** Module 2 - Productivity & Volume (extract productivity_volume_cards.py, life_balance_cards.py)

**Commit 4:** Module 3 - Stress Analysis (extract stress_dimensions_bars.py, stress_dimensions_timeline.py, stress_efficiency_leaderboard.py)

**Commit 5:** Module 4 - Emotional Flow (move existing emotional flow page to new structure)

**Commit 6:** Module 5 - Task Performance (extract task_rankings.py)

**Commit 7:** Module 6 - Trends & Patterns (extract relief_trend_chart.py, attribute_distribution.py, trends_interactive.py)

**Commit 8:** Module 7 - Metric Relationships (extract metric_comparison_scatter.py)

**Commit 9:** Module 8 - Aversion & Obstacles (extract obstacles_cards.py, aversion_cards.py)

**Commit 10:** Module 9 - Developer Tools (extract correlation_explorer.py)

**Commit 11:** Final cleanup, update routing, remove old code

### Migration Safety

- Keep old `analytics_page.py` until all modules migrated
- Use feature flags if needed during transition
- Test each module independently after migration
- Maintain backward compatibility: Keep `/analytics` route working during migration

## Testing Strategy

1. **Unit tests**: Test each graphic aid in isolation
2. **Integration tests**: Test module loading
3. **UI tests**: Verify glossary search works
4. **Performance tests**: Ensure loading screen works correctly
5. **Regression tests**: Verify all visualizations still work

## Success Criteria

- All graphic aids extracted into individual files
- Modules organized logically
- Glossary page functional with search
- Main analytics page has loading screen
- All existing visualizations still work
- Code is more maintainable (smaller files, clear structure)
- Users can navigate easily via glossary

## Dependencies

- Performance optimization plan (for loading screen implementation)
- Existing analytics backend (`backend/analytics.py`) - no changes needed

## Notes

- Keep old `analytics_page.py` during migration for reference