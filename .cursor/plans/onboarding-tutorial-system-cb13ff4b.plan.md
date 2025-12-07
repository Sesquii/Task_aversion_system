<!-- cb13ff4b-da98-4e74-b84e-a72885f1a6bf f1329ef5-3caf-4a2b-b018-d4cede3d97a0 -->
# Onboarding and Tutorial System

## Overview

Implement an onboarding system with three main components: (1) interactive tutorial with two-path welcome (guided tour vs. explore on own), (2) Ctrl+Left Click tooltip system for contextual help with semi-automated content generation, and (3) mental health survey for ML data collection. The system uses browser localStorage for anonymous user identification and is ready for future authentication integration.

## Phase 1: User State Management

### 1.1 Anonymous User Identification

**New File**: `backend/user_state.py`

- Create `UserStateManager` class to handle anonymous user identification
- Use browser localStorage via JavaScript to store unique user ID
- Generate UUID on first visit, persist across sessions
- Store user preferences (tutorial completed, tutorial choice, tooltip mode enabled, etc.)
- Methods: `get_user_id()`, `get_user_preferences()`, `update_preference()`, `is_new_user()`
- JavaScript helper functions to read/write localStorage from Python backend

### 1.2 User Preferences Storage

**Modified File**: `backend/user_state.py`

- Store preferences in CSV: `data/user_preferences.csv`
- Fields: `user_id`, `tutorial_completed`, `tutorial_choice` (guided/explore), `tutorial_auto_show`, `tooltip_mode_enabled`, `survey_completed`, `created_at`, `last_active`
- Link survey responses to user_id for ML training

## Phase 2: Tooltip System

### 2.1 Tooltip Content Generation (Semi-Automated with Manual Review)

**New File**: `scripts/generate_tooltips.py`

- Generate 10 variations per UI element using ChatGPT/Gemini API (free tier)
- Target ~50-100 core UI elements = 500-1000 tooltip strings
- Output to `data/tooltips_raw.json` for manual review
- After manual review, copy approved tooltips to `data/tooltips.json` with structure:
  ```json
  {
    "element_id": ["variation1", "variation2", ...],
    "tutorial_button": ["Click to start the interactive tutorial", "Learn how to use the app", ...]
  }
  ```

- Include fun/easter egg tooltips (e.g., tutorial button: "Congratulations, you completed the tutorial button tutorial!")
- Script can be re-run incrementally as new UI elements are added
- Manual review ensures quality and coherence before deployment

### 2.2 Tooltip JavaScript System

**New File**: `task_aversion_app/assets/tooltip_system.js`

- Implement Ctrl+Left Click detection
- Show random tooltip from variations array for clicked element
- Position tooltip near cursor with smooth animation
- Add visual indicator (small badge/icon) when tooltip mode is active
- Store tooltip mode preference in localStorage
- Graceful fallback if no tooltip found for element
- Load tooltips from JSON file via fetch or embedded in page

### 2.3 Tooltip Integration

**Modified Files**: `ui/dashboard.py`, `ui/*.py`

- Add `data-tooltip-id` attributes to all core UI elements
- Include tooltip script in dashboard head
- Create helper function `add_tooltip_support(element, tooltip_id)` for consistent integration
- Load tooltip JSON data and make available to JavaScript

## Phase 3: Interactive Tutorial

### 3.1 Tutorial Welcome Modal (Two-Path Choice)

**New File**: `ui/tutorial.py`

- Create `show_tutorial_welcome()` function that displays initial choice modal
- Two main options:

  1. **"Take Guided Tour"** → launches step-by-step walkthrough (Phase 3.3)
  2. **"Explore on My Own"** → shows brief message: "Press Ctrl+Left Click on any UI element to see helpful tooltips and hints. You can always access the tutorial again from the menu."

- Modal includes: title, description, two large prominent buttons, "Don't show again" checkbox
- Choice saved to user preferences (`tutorial_choice` field)
- If "Explore on My Own" selected, show tooltip mode indicator

### 3.2 Tutorial Content Structure

**New File**: `data/tutorial_steps.json`

- Define tutorial steps with:
  - `step_id`, `title`, `description`, `target_element` (CSS selector), `highlight_selector`, `position` (top/bottom/left/right)
- Steps covering: dashboard overview, creating tasks, initializing tasks, completing tasks, analytics, recommendations
- Each step includes navigation hints and context

### 3.3 Step-by-Step Walkthrough Component

**New File**: `ui/tutorial.py`

- Create `TutorialWalkthrough` class using NiceGUI
- Modal overlay with step-by-step navigation
- Highlight target elements with semi-transparent overlay + spotlight effect
- Previous/Next/Skip buttons
- Progress indicator (step X of Y)
- Each step shows: title, description, highlighted element, navigation controls
- "Don't show again" checkbox (saves to user preferences)

### 3.4 Tutorial Integration

**Modified File**: `ui/dashboard.py`

- Add "Tutorial" button in header/navigation
- Check `user_preferences` on page load for new users
- Auto-show tutorial welcome modal if `tutorial_completed=False` and `tutorial_auto_show=True`
- Register tutorial functions
- Handle both tutorial paths (guided vs. explore)

## Phase 4: Mental Health Survey

### 4.1 Survey Data Model

**New File**: `backend/survey.py`

- Create `SurveyManager` class
- Store survey responses in `data/survey_responses.csv`
- Fields: `user_id`, `response_id`, `question_category`, `question_id`, `response_value`, `response_text`, `timestamp`
- Link to user_id for ML correlation analysis
- Support multiple responses per user (for updates over time)

### 4.2 Survey Questions Design

**New File**: `data/survey_questions.json`

- Define survey structure with categories:
  - **Struggles** (required): Multi-select checklist
    - Options: Overwhelmed, Procrastination, Self-doubt, Motivation issues, Time management, Focus/concentration, Anxiety, Perfectionism, Burnout, Other (with text field)
  - **Mental Health Diagnoses** (optional - clearly marked):
    - Large disclaimer at top: "This section is completely optional. Your responses help us understand patterns but are never required. You can skip this entire section."
    - Multi-select: ADHD, Anxiety disorders, Depression, Bipolar, OCD, PTSD, Autism spectrum, Other (text field), Prefer not to answer
    - Medications (optional text field)
  - **Task Patterns** (optional): 
    - Procrastination frequency (scale 1-10)
    - Common stress triggers (multi-select)
    - Current coping strategies (text)
  - **Wellbeing Baseline** (optional):
    - Typical stress levels (scale)
    - Relief patterns (when do you feel relief?) (text)
- Each question: `question_id`, `category`, `question_text`, `type` (multiple_choice, scale, text, checkbox), `options` (if applicable), `required` (boolean), `optional_note` (for optional questions)

### 4.3 Survey UI

**New File**: `ui/survey_page.py`

- Create multi-step survey form
- Progress indicator showing completion percentage
- Save responses incrementally (don't lose progress on refresh)
- "Mental Health Survey" button in dashboard/settings
- Clear visual distinction between required and optional sections
- Large, prominent disclaimer for optional diagnosis section
- Completion tracking in user preferences
- Allow users to return and update responses later

## Phase 5: Onboarding Flow Integration

### 5.1 First-Time User Experience

**Modified File**: `ui/dashboard.py`

- On page load, check if new user via `UserStateManager.is_new_user()`
- If new user: show tutorial welcome modal (from Phase 3.1)
- Tutorial welcome offers two paths:

  1. "Take Guided Tour" → step-by-step walkthrough
  2. "Explore on My Own" → brief Ctrl+Left Click explanation, then dismiss

- After tutorial choice, optionally prompt for survey (non-blocking, can be dismissed)
- Store user creation timestamp and tutorial choice

### 5.2 Settings Integration

**Modified File**: `ui/settings_page.py` (or create if doesn't exist)

- Add onboarding section:
  - "Show Tutorial Again" button (resets tutorial_completed flag)
  - "Enable Tooltip Mode" toggle (turns on/off tooltip indicator)
  - "Take Mental Health Survey" button
  - "Reset Onboarding" option (for testing - clears all onboarding preferences)

## Implementation Notes

### Cost Efficiency Analysis

- **Tooltip Generation**: Semi-automated approach
  - Generate batch via free tier API (ChatGPT/Gemini) = ~$0-5 for 1000 strings
  - Output to `tooltips_raw.json` for manual review
  - After review, approved tooltips go to `tooltips.json`
  - Script can be re-run incrementally as UI evolves
  - Manual review ensures quality and coherence
- **Recommendation**: Automated generation + manual review workflow balances efficiency with quality control

### Technical Considerations

- NiceGUI supports JavaScript via `ui.run_javascript()` and `ui.add_head_html()`
- Use localStorage for client-side user ID persistence (better than IP for reliability)
- Tooltip system uses event delegation for efficiency
- Tutorial uses CSS overlays + JavaScript for element highlighting
- User state syncs between localStorage (client) and CSV (server) via JavaScript bridge

### Future ML Integration

- Survey responses linked to user_id
- Task performance data already linked via instance_manager
- Ready for correlation analysis: user profiles → task patterns → optimization recommendations
- Struggles and diagnoses data will enable pattern recognition across psychological profiles

## Files to Create

- `backend/user_state.py` - User state management
- `backend/survey.py` - Survey data management  
- `ui/tutorial.py` - Tutorial welcome modal and walkthrough component
- `ui/survey_page.py` - Survey UI
- `task_aversion_app/assets/tooltip_system.js` - Tooltip JavaScript
- `data/tooltips.json` - Tooltip content (after manual review)
- `data/tooltips_raw.json` - Raw generated tooltips (for review)
- `data/tutorial_steps.json` - Tutorial step definitions
- `data/survey_questions.json` - Survey question definitions
- `scripts/generate_tooltips.py` - Semi-automated tooltip generation script
- `data/user_preferences.csv` - User preferences storage
- `data/survey_responses.csv` - Survey response storage

## Files to Modify

- `ui/dashboard.py` - Add tutorial button, tooltip integration, new user check, tutorial welcome modal
- `ui/settings_page.py` - Add onboarding controls (or create if missing)
- `app.py` - Register survey page route
- `requirements.txt` - Add any new dependencies (if needed for API calls in tooltip generation script)