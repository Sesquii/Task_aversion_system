# Popup System Rules (Popups, Escalation, and Sensitivity)

## Scope and Goals
- Define how and when popups are shown across the app (not only time overruns).
- Encourage honest, low-friction self-reflection; avoid interruption fatigue.
- Support adaptive questioning: brief/encouraging first, deeper only when patterns repeat.
- Allow popups without immediate scoring; they can inform future scoring/analytics.

## Core Principles
- **One relevant question beats many mediocre ones**: prioritize a single, high-value prompt.
- **Progressive depth**: first occurrence = brief/encouraging; repeated occurrences can add depth.
- **User agency**: every popup includes “Helpful?” toggle + optional comment to improve tuning.
- **Safety and respect**: default to fewer questions when context is thin; avoid invasive stacks.
- **Celebrate sparingly**: milestone-based positive popups; no spam for routine wins.
- **Track counts per trigger**: drive escalation, throttling, and milestone rewards.

## Trigger Framework
- Triggers can be time-based, completion-based, affect-based, behavioral, survey-correlated, or data-quality.
- Maintain per-trigger counters (per user + per task) to control escalation and throttling.
- Global constraints: max 1 popup per task completion; daily cap (configurable); show a “You can change max popups/day in Settings (currently X)” notice after hitting the cap.

### Time-Based (1.x)
- **1.1 Time Overrun (baseline grit)**: `time_actual > 2x time_estimate` and `time_estimate > 0`.
  - Branch A (Focused): brief reflection; ask pride vs frustration; optional “what made it longer?”
  - Branch B (Not focused): first time → light encouragement; repeated → gradually deeper (“what got in the way?” with options like shame/confusion/distraction/other).
- **1.2 Extreme Overrun**: `time_actual > 5x time_estimate`.
  - Tone: acknowledge the win first (“You pulled this off despite a huge overrun”).
  - Avoid telling them to break down the task if they already succeeded; instead offer “want ideas to prevent this next time?” or “would it help to log what surprised you?”
- **1.3 Time Underrun (quality check)**: `time_actual < 0.5x time_estimate` and `completion_percent >= 100`.
  - Be cautious when info is limited: prefer a single relevant question; skip if context is weak.

### Completion-Based (2.x)
- **2.1 Partial Completion (50–99%)**: “Did you try your best? Bored or distracted?” Encourage brief branch; partial grit credit logic lives in scoring, not required here.
- **2.2 Very Low Completion (<50%)**: empathetic check; suggest breakdown only if user signals overwhelm; keep it brief.
- **2.3 First-Time Hard Task**: completion_count == 1 and difficulty high → short, encouraging recognition; optional feeling check.

### Affect-Based (3.x)
- **3.1 Negative affect but completed**: high emotional load + low relief → recognize grit; offer supportive follow-up, not interrogation. (Note: see analytics module for any existing handling; align with it.)
- **3.2 High relief after difficulty**: short congrats, optional “what helped?” prompt.
- **3.3 Emotional spike**: **Removed for now** per user preference. Do not trigger.

### Behavioral Patterns (4.x)
- **4.1 High delay before start**: gentle probe; if context thin, skip. Options: avoidance, busy, unclear start. Keep to one question.
- **4.2 Repeated cancellations**: include option “I didn’t label/setup the task correctly”; offer task review/breakdown only if user opts in.
- **4.3 Rapid streaks / possible rushing**: if multiple very short tasks with low relief, offer a single suggestion and link to an analytics view comparing efficiency vs task length (only if available). Gate on count to avoid nagging.

### Survey-Correlated (5.x)
- Use survey signals (e.g., procrastination, perfectionism, anxiety) to personalize wording.
- **5.1 Procrastination match**: if flagged and pattern fits, ask briefly; suggest holding the reason in mind; ask what about this task reduced procrastination when it’s a positive outlier.
- **5.2 Perfectionism match**: existing setup is good; keep.
- **5.3 Anxiety match**: keep as-is.

### Data Quality (6.x)
- **6.1 Missing relief after completion**: light-touch single slider ask.
- **6.2 Relief/emotion contradiction**: careful, single clarifying question only.

## Escalation & Familiarity Handling
- Maintain per-trigger counters. Use tiers:
  - Tier 0 (first time): brief, encouraging, low intrusiveness.
  - Tier 1–2 (repeats): allow one deeper/more personal follow-up, especially for negative affect (e.g., shame/confusion) or repeated distraction.
  - Tier 3+ (habitual): optionally surface strengths (“You’re consistently great at X; can you borrow that approach here?”) or tailored suggestions. Still keep to one key question.
- For positive triggers (good affect, consistent success): only show at milestones (e.g., 5th, 10th, 25th, 50th) to reward consistency without spam.

## UX Safeguards
- **Helpful toggle**: every popup has “Helpful?” + optional comment to tune future prompts.
- **One-per-completion**: never stack multiple popups on a single completion event.
- **Cooldowns**: per-trigger cooldown (e.g., 24h), daily cap with final notice linking to settings and showing current cap.
- **Skip when low context**: if data is too sparse, prefer no popup.

## Scoring Integration Guidance
- Popups may exist without immediate score effects; they can inform future scoring.
- For grit-related prompts: allow responses to modulate time-bonus or persistence scoring when available, but do not require scoring to deploy the popup.

## Implementation Pointers (NiceGUI/analytics)
- Store per-trigger counts per user (and optionally per task) to drive tiers and cooldowns.
- Store popup responses (value, free text, helpful flag) in a lightweight store/table.
- Provide a settings link/control for max popups per day and for disabling specific trigger types.
- Keep language empathetic; front-load acknowledgment when user already succeeded at a hard thing.

