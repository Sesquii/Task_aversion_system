---
name: Multimodal implementation clarification
overview: Clarifying questions to scope the multimodal login feature (app modes beyond mobile/desktop), analysis-only mode, global/synthetic data, and cognitive profiling before drafting an implementation plan.
todos: []
isProject: false
---

# Multimodal Implementation — Clarification Questions

These questions will narrow scope and priorities so we can draft a concrete implementation plan. Current state: **UI mode** is layout-only (mobile vs desktop) stored in `app.storage.browser['ui_mode']` and chosen at [choose_experience.py](task_aversion_app/ui/choose_experience.py) or from [login](task_aversion_app/ui/login.py) / [settings](task_aversion_app/ui/settings_page.py); index in [app.py](task_aversion_app/app.py) branches on `ui_mode` to build desktop or mobile dashboard. Analytics are per-user in [backend/analytics.py](task_aversion_app/backend/analytics.py); no cross-user or synthetic data today.

---

## 1. Scope and phasing

- **Q1.** Should we implement everything in one go, or phase it? For example: (A) Phase 1: mode selection + analysis-only shell (no workflow); Phase 2: global/synthetic data and comparison; Phase 3: cognitive profiling and correlation index. Or do you want a different phasing?
- **Q2.** For "multiple modes at login": is **Analysis-only** the only extra mode for the first version, or do you want a generic **app mode** framework from the start (e.g. Workflow | Analysis-only | future "Research" or "Coach") so adding modes later is just config?

---

## 2. Mode vs layout

- **Q3.** Should **app mode** (e.g. Workflow vs Analysis-only) be **separate** from **layout** (mobile vs desktop)? So a user could choose "Analysis only" and then still choose Desktop or Mobile layout for that mode on this device?
- **Q4.** Where should app mode be chosen: only at login/choose-experience, or also switchable from Settings or from the dashboard (e.g. "Switch to Analysis mode")?

---

## 3. Analysis-only mode

- **Q5.** In Analysis-only mode, should the app **hide** task creation/execution (dashboard, initialize, complete) entirely and only show analytics/comparison/glossary, or still show them but de-emphasized (e.g. in a tab or secondary nav)?
- **Q6.** When you say "migrate all of analytics into a more robust data driven system": do you mean (A) refactoring the current analytics backend/API and UI into a cleaner data-driven design as part of this feature, or (B) keeping current analytics as-is and adding new comparison/global/synthetic features on top, or (C) something else (e.g. align with the client-side analytics migration in [analytics-migration-client.mdc](.cursor/rules/analytics-migration-client.mdc))?

---

## 4. Global and aggregate data

- **Q7.** For "overall averages from all users" / global data: **anonymized aggregates only** (e.g. means, distributions, no PII)? Any compliance or policy constraints (e.g. GDPR, opt-in for contributing to aggregates)?
- **Q8.** Who can access features that use global/synthetic data: **all authenticated users**, or only users with a flag/role (e.g. beta, researcher)?

---

## 5. Synthetic data and traits

- **Q9.** Where should synthetic datasets live: (A) **database** as special synthetic users (e.g. `user_id` or `source_type` = synthetic), (B) **on-the-fly** generation when needed, or (C) **precomputed** files (e.g. JSON/CSV) loaded by the app?
- **Q10.** Who defines the **traits/profiles** (e.g. "procrastination + ADHD", "high consistency"): a **fixed curated list** you define, or **configurable** (e.g. admin UI or config file) so new profiles can be added without code changes?
- **Q11.** Should synthetic data be **purely model-generated** (formulas/scripts), or **based on anonymized real-user statistics** where possible (e.g. shape of distributions from real data, then generate synthetic instances)?

---

## 6. Cognitive profile and correlation index

- **Q12.** What should define a **cognitive profile** in your system: (A) **survey dimensions** (from [survey_questions.json](task_aversion_app/data/survey_questions.json) and [SurveyManager](task_aversion_app/backend/survey.py) / survey_responses), (B) **task/instance metrics** (e.g. relief, difficulty, completion patterns from [backend/analytics.py](task_aversion_app/backend/analytics.py)), (C) a **new set of dimensions** (e.g. procrastination score, consistency index), or (D) a **combination** of these?
- **Q13.** For the **correlation index** ("which cognitive profile a user fits best"): is the desired output (A) a single "best fit" profile + match percentage (e.g. "78% match: Procrastination + ADHD"), (B) a ranked list of profiles with scores, (C) a visual (e.g. radar or bar chart vs synthetic profiles), and/or (D) an exportable report? Any other outputs?

---

## 7. Technical and product constraints

- **Q14.** Should the plan **assume** the current server-side analytics as the source of truth (per [analytics-migration-client.mdc](.cursor/rules/analytics-migration-client.mdc)), or explicitly **align** with a future client-side analytics migration (e.g. analysis-only mode consuming the same API that a future client analytics module would use)?
- **Q15.** Any **hard constraints**: e.g. no new backend language, must work with existing DB (PostgreSQL/SQLite), or must not break existing mobile/desktop layout selection?

---

Once you answer these (even briefly), we can produce a concrete implementation plan with phases, data model changes, and file-level steps.
