# Grit Score – Conclusions and Next Steps

## What to Keep
- Preserve the existing grit intent: persistence + “took longer than expected” is distinct from productivity/efficiency.
- Keep the current analysis file (now in this folder) as reference.

## Persistence Scaling (requested changes)
- Implemented two-stage growth (power ~sqrt to log-like):
  - Approx anchors: 2× ≈ 1.02x, 10× ≈ 1.22x, 25× ≈ 1.6x, 50× ≈ 2.6x, 100× ≈ 4.1x (before decay)
- Familiarity decay after 100×: multiplier tapers via decay factor (100→1.0, 300→~0.5, 500→~0.33, 1000→~0.18), capped at 5.0 overall to prevent runaway.

## Time Bonus Expectations
- Difficulty-weighted time bonus with diminishing returns and cap (~3.0x raw):
  - 1–2× overrun: up to 1.5x; beyond 2× grows slowly (0.2 per extra excess), capped.
  - Weighted by task difficulty: easy tasks get less lift, hard tasks get full lift.
  - Fades after repetitions: fade factor ~1.0 at 10 completions, ~0.5 at 50, ~0.31 at 90 → negligible after many repeats.

## Pop-up / Self-report Idea
- If actual time > ~2× estimate, show a prompt like:
  - “Did this task take extra work than expected? Be honest—have you been working with as much grit as possible? This will factor into your grit score and improve accuracy. If you haven’t been focused, that’s okay—honesty helps you improve.”
- Responses could branch:
  - “Yes, I was focused” → ask: “Were you more frustrated or proud overall?” “Did the pride outweigh the frustration?” (captures emotional flow from start to completion)
  - “No, I wasn’t focused” → ask why: shame, confusion, distraction, other (free text). Use to adjust grit and improve accuracy.
- Add a project rule to scan for places where time overruns trigger pop-ups and encourage these question branches (yes/no + follow-ups).
- Optionally add a second rule to correlate pop-up responses with survey data (e.g., procrastination responses) to tailor questions.

## Passion × Perseverance Split (possible redesign)
- Rename current grit score to **Persistence Score**.
- Define a **Passion Factor** and make Grit = Passion × Persistence.
- Passion candidates: positive affect during/after tasks, relative time invested vs. typical tasks, frequency of positive-completion affect, weighting by “highest well-being” tasks.
- Needs a dedicated design pass before coding.

## Implementation Notes (for future work)
- Implemented hybrid growth and decay as above.
- Time bonus now depends on difficulty, has diminishing returns and cap, and fades with repetition.
- Passion factor added: grit = persistence_score × passion_factor (relief vs emotional load, modest range 0.5–1.5, slightly damped if not fully completed).
- Add the overrun pop-up flow and the survey-correlation rule(s) once UI patterns are chosen (multiple choice + optional free text).

