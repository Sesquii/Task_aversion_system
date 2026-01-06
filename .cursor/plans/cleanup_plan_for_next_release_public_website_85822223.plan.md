---
name: Cleanup Plan for Next Release/Public Website
overview: "Stabilize for public release: fix critical bugs, hide/remove experimental features, tighten docs/onboarding, and ensure core flows are solid."
todos:
  - id: bug-triage
    content: Create BUGLOG and triage P0/P1/P2; fix P0/P1
    status: pending
  - id: hide-experimental
    content: Hide/remove experimental surfaces (/experimental, formula controls) from public UI/README
    status: pending
  - id: clean-ui-help
    content: Tighten onboarding/help/tooltips; keep optional sections collapsible
    status: pending
  - id: doc-pass
    content: Update README with stable features/quickstart; add release notes/known issues
    status: pending
  - id: qa-checklist
    content: Create QA checklist and run core flow tests (init→complete→analytics→reco)
    status: pending
    dependencies:
      - bug-triage
      - hide-experimental
      - clean-ui-help
---

# Cleanup Plan for Next Release/Public Website

## Overview

Prepare a stable, public-facing build by fixing critical bugs, hiding/removing experimental features, tightening documentation/onboarding, and sanity-testing core flows. Deployment plans already exist; focus here is on product readiness.

---

## Phase 1: Bug Sweep and Triage

### 1.1 Collect & Triage Bugs

**Files**: `docs/BUGLOG.md` (new), existing TODO/bug markers

- Gather known significant bugs (data integrity, crashes, UI blockers).
- Triage severity: P0 (blocker), P1 (high), P2 (medium).

### 1.2 Fix P0/P1

**Scope**:

- Data integrity issues (saves, completion, scoring).
- Crashes in dashboard/analytics/recommendations.
- Broken flows: init task → complete task → analytics → recommendations.

Deliverable: P0/P1 resolved; P2 scheduled.

---

## Phase 2: Experimental Feature Audit

### 2.1 Identify Experimental Surfaces

**Files**: `ui/experimental_landing.py`, `/experimental` route, README experimental section

- List experimental pages/components (Formula Control System, goal tracking, dev toggles).

### 2.2 Hide/Remove for Public Build

- Option A: Feature-flag and default-off in public build.
- Option B: Remove from navigation/README; keep code reachable only via dev flag.
- Ensure `/experimental` is not linked in public UI/README.

### 2.3 Clean Copy

- Update README: mark experimental features as “dev only” or remove from main feature list.

---

## Phase 3: UI/UX Tightening

### 3.1 Onboarding/Help

**Files**: `ui/dashboard.py`, `ui/initialize_task.py`, `ui/complete_task.py`, `README.md`

- Add concise help/tooltips for core sliders; keep optional sections collapsible.
- Ensure wording is broad and non-diagnostic; optional sections clearly labeled.

### 3.2 Navigation & Clutter

- Remove dead links/placeholders.
- Ensure main menu shows only stable pages (Dashboard, Tasks, Analytics, Recommendations, Survey optional).

---

## Phase 4: Documentation Pass

### 4.1 Public-Facing README

**Files**: `README.md`

- Present stable feature set only.
- Add quickstart: init task → complete task → view analytics → use recommendations.
- Link Docker install already validated; note “tested locally, broader compatibility unverified.”

### 4.2 Changelog / Known Issues

**Files**: `docs/RELEASE_NOTES.md` (new)

- Summarize fixes, removed experimental items, known limitations.

---

## Phase 5: Sanity Test Core Flows

### 5.1 Happy Paths

- Init task (with required sliders) → complete task → see updated analytics/recommendations.
- Recommendation cards render without error; filters work.

### 5.2 Edge Checks

- Empty state: no tasks, no completions → UI graceful.
- Small dataset vs. larger sample data → pages load acceptably.

### 5.3 Acceptance Checklist

**Files**: `docs/QA_CHECKLIST.md` (new)

- Core workflows pass.
- No experimental links visible.
- No crashes on dashboard/analytics/reco pages.
- Survey optionality clear; language broad/non-diagnostic.

---

## Success Criteria

- P0/P1 bugs fixed; P2 tracked.
- Experimental features hidden or feature-flagged off in public build; README cleaned.
- Onboarding/help concise; navigation shows only stable features.
- Public README reflects stable scope; release notes/known issues documented.
- Core flows pass acceptance checklist without crashes.

---

## Notes

- Keep feature-flag approach simple (env var or constant) for experimental surfaces.
- Do not remove code needed for internal dev; just hide from public-facing UI/README.
- Keep language non-judgmental and optional around survey/emotional inputs.