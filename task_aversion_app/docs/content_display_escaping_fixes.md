# Content Display Escaping Fixes

This document details all the escaping fixes applied to prevent XSS (Cross-Site Scripting) attacks by escaping user-generated content before display.

## Overview

Added comprehensive XSS protection by applying `escape_for_display()` from `backend.security_utils` to all user-generated content displayed in UI pages. This prevents potential cross-site scripting (XSS) attacks by escaping HTML entities in user input before rendering.

## Pages Updated (23 total)

### 1. dashboard.py
- Escape task names
- Escape descriptions
- Escape notes
- Escape pause reasons
- Escape search queries
- Escape initialization descriptions
- Escape task names in completed tasks lists
- Escape task names in template card markdown (multiple locations)

### 2. complete_task.py
- Escape task descriptions
- Escape shared notes

### 3. cancelled_tasks_page.py
- Escape task names
- Escape cancellation notes
- Escape custom category labels (in statistics and category management sections)

### 4. cancellation_penalties_page.py
- Escape custom category labels

### 5. notes_page.py
- Escape note content displayed in markdown

### 6. task_editing_manager.py
- Escape task names in editing interface

### 7. analytics_page.py
- Escape task names in rankings
- Escape task names in leaderboards
- Escape task names in spike alerts

### 8. coursera_analysis.py
- Escape task names in summary displays

### 9. productivity_grit_tradeoff.py
- Escape task names in quadrant analysis
- Escape task names in task tables

### 10. cancel_task.py
- Escape task names in select dropdown options

### 11. add_log.py
- Escape task names in select dropdown options

### 12. productivity_settings_page.py
- Escape task names in primary task select dropdown

### 13. task_distribution.py
- Escape task names in pie charts
- Escape task names in statistics table

### 14. factors_comparison_analytics.py
- Escape task names in scatter plot hover templates
- Escape task names in task details table

### 15. relief_comparison_analytics.py
- Escape task names in Plotly scatter plot hover templates
- Escape task names in task details table

### 16. survey_page.py
- Escape question text
- Escape category titles
- Escape disclaimers displayed in survey form

### 17. initialize_task.py
- Escape emotion names displayed in emotion slider labels (user-entered emotions)

### 18. productivity_module.py
- Escape enhancement detail descriptions displayed in results

### 19. tutorial.py
- Escape tutorial step titles
- Escape tutorial step descriptions loaded from JSON configuration file

### 20. data_guide_page.py
- Escape markdown headers
- Escape titles displayed in labels
- Escape table cell content (from documentation file)

### 21. gap_handling.py
- Escape gap start/end date strings displayed in gap details

### 22. popup_modal.py
- Escape popup title
- Escape popup message
- Escape option labels displayed in modal dialog

### 23. login.py
- Escape user email displayed in current session information

## Display Contexts Updated

All user-generated content is now escaped using `escape_for_display()` before being displayed in:

- `ui.label()` calls
- `ui.markdown()` calls
- `ui.html()` calls (where user content is embedded)
- `ui.select()` dropdown options (task names)
- Plotly chart hover templates and data labels
- `ui.table()` row data (task names in tables)

## Security Improvements

- Prevents XSS attacks through malicious user input
- Safely displays HTML characters as text (e.g., `<script>` becomes `&lt;script&gt;`)
- Maintains display of legitimate text content while preventing code execution
- Consistent security approach across all UI pages

## Implementation Details

This addresses security concerns where user-generated content (task names, descriptions, notes) could potentially contain malicious scripts that would execute when rendered in the browser. All content is now sanitized before display while preserving the intended user experience.

The `escape_for_display()` function from `backend.security_utils` converts HTML special characters to their entity equivalents:
- `<` → `&lt;`
- `>` → `&gt;`
- `&` → `&amp;`
- `"` → `&quot;`
- `'` → `&#x27;`

This ensures that any HTML or script tags in user input are displayed as plain text rather than being interpreted as code by the browser.
