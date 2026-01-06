---
name: Grit and Grace Strategy Integration
overview: Define and integrate a dual strategy that pairs productivity (grit) with emotional awareness/self-regulation (grace), ensuring TAS is both a productivity and emotional-awareness tool for broad users.
todos:
  - id: philosophy-doc
    content: Write design philosophy (grit+grace, no diagnostics) and update README
    status: pending
  - id: ui-copy-cues
    content: Add brief UI copy pairing action with reflection on dashboard/analytics
    status: pending
    dependencies:
      - philosophy-doc
  - id: grit-grace-map
    content: Create feature map doc linking grit features to grace features
    status: pending
  - id: paired-recos
    content: Add optional paired grace suggestions to recommendations using state probs
    status: pending
  - id: dual-metrics
    content: Show productivity + emotional metrics side-by-side in analytics cards
    status: pending
  - id: survey-language
    content: Review survey wording for optionality/broad applicability; adjust title if needed
    status: pending
  - id: user-toggles
    content: Add settings toggles to show/hide intervention/paired grace suggestions
    status: pending
  - id: feedback-hooks
    content: Add quick feedback (thumbs) on suggestions for tuning
    status: pending
---

# Grit and Grace Strategy Integration

## Overview

Establish a clear, integrated strategy where TAS delivers both productivity (grit) and emotional awareness/self-regulation (grace). Ensure messaging, UX, analytics, and recommendations reflect both dimensions, without diagnostic framing, and remain broadly applicable (neurotypical and mental-health users alike).

---

## Phase 1: Positioning & Messaging

### 1.1 System Philosophy

**Files**: `README.md`, `docs/design_philosophy.md` (new)

- Articulate TAS as **both** productivity and emotional awareness in one flow.
- Add “grit + grace” language: execution strength + self-kindness/calibration.
- Explicitly state: no diagnostic labels required; works across user types.

### 1.2 UI Copy Cues

**Files**: `ui/dashboard.py`, `ui/analytics_page.py`

- Add short helper text that pairs actions (do) with reflection (feel/understand).
- Keep language non-judgmental and optional (“This might be a good time to…”).

---

## Phase 2: Feature Mapping (Grit ↔ Grace)

### 2.1 Map Existing Features

**Files**: `docs/grit_grace_map.md` (new)

- Grit: execution score, productivity score, task-type multipliers, efficiency, goal tracking.
- Grace: relief/stress/aversion sliders, self-care multipliers, belief scores, load/misalignment likelihoods, intervention prompts.
- Integration points: recommendations, analytics views showing both sides together.

### 2.2 Balance Checklist

**Files**: `docs/grit_grace_map.md`

- Checklist: ensure each core flow has a grit and a grace element:
- Task init: estimates + expected relief/aversion context.
- Task completion: completion % + relief/stress reflection.
- Recommendations: productivity picks + state-aware interventions.
- Analytics: productivity trends + emotional trends side-by-side.

---

## Phase 3: Recommendation & Intervention Layer

### 3.1 Pairing Recommendations

**Files**: `backend/analytics.py`

- When showing task recommendations, optionally surface a paired “grace” suggestion (e.g., short reflection or rest if load high).
- Use probabilistic state outputs from belief/state plan (already separate).

### 3.2 Tone & Framing

**Files**: `backend/analytics.py`, `ui/dashboard.py`

- Keep suggestions experimental, reversible, and low-cost (“try 10 minutes”).
- Show state probabilities to make suggestions transparent (optional badge/text).

---

## Phase 4: Analytics Presentation

### 4.1 Dual-Pane or Coupled Metrics

**Files**: `ui/analytics_page.py`

- Show productivity metric alongside an emotional/relief metric in the same card.
- Example: Productivity score trend next to relief/stress trend; show correlation.

### 4.2 Storytelling Cards

**Files**: `ui/analytics_page.py`

- Brief summaries: “When relief is high, your execution score improves by X.”
- Keep concise; avoid over-claiming causality.

---

## Phase 5: Broad Applicability & Safety

### 5.1 Survey/Onboarding Language

**Files**: `ui/survey_page.py`, `task_aversion_app/data/survey_questions.json`

- Ensure optional sections are clearly marked; avoid diagnostic tone.
- Rename to “Wellbeing & Productivity” if needed; emphasize optionality.

### 5.2 Override & Control

**Files**: `ui/settings_page.py`

- Add toggles for: show/hide intervention hints; show/hide paired grace suggestions.
- Preserve user authority: suggestions off by default for public? (decide in rollout).

---

## Phase 6: Validation

### 6.1 Balance Review

**Files**: `docs/grit_grace_map.md`

- Run a balance audit per release: are both sides visible and not overwhelming?

### 6.2 User Feedback Hooks

**Files**: `ui/dashboard.py`

- Lightweight thumbs-up/down on suggestions; log for later tuning.

---

## Success Criteria

- Messaging clearly states productivity + emotional awareness, no diagnostics required.
- UI shows paired grit/grace cues without clutter.
- Recommendations can surface paired grace suggestions when state warrants.
- Analytics present productivity and emotional signals together.
- Optional toggles give users control over suggestions/interventions.

---

## Notes

- Keep language humane and optional; avoid prescriptive tone.
- Don’t pathologize exploration; treat signals as probabilistic.
- Respect slider inputs as primary source; derived scores only augment.