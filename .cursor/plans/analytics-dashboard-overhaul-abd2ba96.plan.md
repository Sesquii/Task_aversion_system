<!-- abd2ba96-8431-41ff-8db9-436683c7947c 0b0ae264-cddf-4652-aa1f-04cd03fc98c7 -->
# Analytics Dashboard Overhaul Plan

## Overview

Enhance the analytics dashboard with:

1. **Time-series trends per day** for all attributes in the attribute distribution
2. **Flexible "Trends" UI** for selecting attributes and statistical aggregations to display over time
3. **Developer correlation experimentation section** for exploring relationships between variables without ML

## Implementation Details

### 1. Backend: Daily Time-Series Data Methods (`backend/analytics.py`)

Add new methods to the `Analytics` class:

- **`get_attribute_trends(attribute_key: str, aggregation: str = 'mean', days: int = 90)`**
- Groups completed instances by day (using `completed_at`)
- Applies aggregation (mean, sum, median, min, max, count) to the specified attribute
- Returns dict with `dates` (list of date strings) and `values` (list of aggregated values)
- Similar pattern to existing `get_weekly_hours_history()` method

- **`get_multi_attribute_trends(attribute_keys: List[str], aggregation: str = 'mean', days: int = 90)`**
- Returns trends for multiple attributes in one call
- Returns dict with structure: `{attribute_key: {'dates': [...], 'values': [...]}}`

- **`calculate_correlation(attribute_x: str, attribute_y: str, method: str = 'pearson')`**
- Calculates correlation coefficient between two attributes
- Returns correlation value, p-value, and sample size
- Uses pandas `corr()` method

- **`find_threshold_relationships(dependent_var: str, independent_var: str, bins: int = 10)`**
- Bins independent variable into ranges
- Calculates average dependent variable for each bin
- Identifies bins with maximum/minimum dependent values
- Returns dict with bin ranges, averages, and optimal threshold suggestions

- **`get_scatter_data(attribute_x: str, attribute_y: str)`**
- Returns paired values for scatter plot visualization
- Filters to completed instances with both attributes present

### 2. Frontend: Trends Section (`ui/analytics_page.py`)

Add new UI section after the existing charts:

- **Trends Viewer Card**
- Multi-select dropdown for attributes (from `TASK_ATTRIBUTES` + calculated metrics)
- Dropdown for aggregation method (mean, sum, median, min, max, count)
- Time range selector (30, 60, 90 days)
- Single Plotly line chart showing selected attributes over time
- Each attribute as a separate line with different color
- Legend to toggle series visibility

- **Replace or enhance existing "Attribute distribution" section**
- Add clickable attribute names that open trend chart for that attribute
- Or add small trend previews next to each attribute in the box plot

### 3. Frontend: Developer Correlation Section (`ui/analytics_page.py`)

Add collapsible/hidden section (toggle with button or keyboard shortcut):

- **Correlation Explorer**
- Two dropdowns: Independent Variable (X-axis) and Dependent Variable (Y-axis)
- Scatter plot showing relationship
- Display correlation coefficient and p-value
- Threshold analysis section:
- Shows binned analysis (independent variable binned, dependent variable averaged per bin)
- Highlights optimal threshold ranges
- Example: "Cognitive Load 30-50 → Average Relief: 65.2 (max)"

- **Multi-Variable Experimentation**
- Add multiple variable pairs
- Compare correlations side-by-side
- Export findings as text summary

### 4. UI Organization

- Keep existing charts (relief trend, attribute distribution box plot)
- Add "Trends" section as new card/section
- Add "Developer Tools" section (collapsible, marked as experimental)
- Use existing Plotly integration (no new dependencies)

### 5. Data Handling

- All data comes from existing `task_instances.csv` via `_load_instances()`
- No new data files created
- Use `completed_at` timestamp for day grouping
- Handle missing values gracefully (skip days/instances without data)

## Files to Modify

1. **`backend/analytics.py`**

- Add `get_attribute_trends()` method
- Add `get_multi_attribute_trends()` method  
- Add `calculate_correlation()` method
- Add `find_threshold_relationships()` method
- Add `get_scatter_data()` method

2. **`ui/analytics_page.py`**

- Add `_render_trends_section()` function
- Add `_render_correlation_explorer()` function
- Update `build_analytics_page()` to include new sections
- Add developer toggle/button for correlation section

## Technical Notes

- Use pandas `groupby` with date extraction for daily aggregation
- Use pandas `corr()` and scipy `stats` for correlation calculations with p-values
- Use Plotly `go.Scatter` for multi-line trends chart
- Use Plotly `go.Scatter` with mode='markers' for scatter plots
- Normalization: min-max scaling formula: `(value - min) / (max - min)`
- Follow existing patterns from `get_weekly_hours_history()` for consistency
- All aggregations computed on-the-fly (no caching needed initially)
- Statistical tooltips: Store metadata dict with name, description, statistician, search_term for each statistic

## User Experience

- Trends section: User-friendly, always visible
- Correlation section: Hidden by default, accessible via "Developer Tools" button
- Clear labeling of experimental features
- Responsive charts that work on different screen sizes

### To-dos

- [ ] Add get_attribute_trends() and get_multi_attribute_trends() methods to Analytics class for daily time-series aggregation
- [ ] Add calculate_correlation(), find_threshold_relationships(), and get_scatter_data() methods to Analytics class
- [ ] Create _render_trends_section() with attribute selector, aggregation dropdown, and multi-line Plotly chart
- [ ] Create _render_correlation_explorer() with scatter plots, correlation display, and threshold analysis
- [ ] Integrate new sections into build_analytics_page() with proper layout and developer toggle