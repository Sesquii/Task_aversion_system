# Grit Score – Conclusions and Next Steps

## What to Keep
- Preserve the existing grit intent: persistence + “took longer than expected” is distinct from productivity/efficiency.
- Keep the current analysis file (now in this folder) as reference.

## Persistence Scaling (requested changes)
- Two-stage curve: square-root-like up to 25× completions, then logarithmic afterward.
- Target anchors (approximate):
  - 2× ≈ 1.015x
  - 10× ≈ 1.2x
  - 25× ≈ 1.5x
  - 50× ≈ 2.0x
  - 100× ≈ 5.0x (but see familiarity decay below)
- After very high repetitions (e.g., 100×+), introduce a **familiarity decay** so routine/habit does not keep inflating grit. Option: taper/decline after 100×, and strongly downweight beyond 1000×.

## Time Bonus Expectations
- Tie time bonus to completion count and task difficulty.
- After ~50 completions, time bonus should become negligible; early runs should get most of the time-based grit credit (especially the first completion when it takes 2× longer but finishes 100% despite adversity/negative affect).
- Time bonus should weight difficulty over time; harder tasks get more credit for taking longer.
- Consider capping and/or diminishing returns on extreme overruns so it can’t dominate.

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
- Design the hybrid sqrt→log curve to hit the anchors; it can be approximate rather than exact.
- Add familiarity decay after 100× (taper or downweight multiplier; possibly separate component).
- Rework time bonus to depend on completion count + difficulty; apply diminishing returns and a cap.
- Add the overrun pop-up flow and the survey-correlation rule(s) once UI patterns are chosen (multiple choice + optional free text).

