# Initial Popup Integration Plan

## Scope

- Implement popup state in SQLite (via existing `backend/database.py` engine) with fallback-safe code (no DB URL assumptions beyond default).
- Add dispatcher + rule evaluation for all task-related flows (complete, start, cancel/list minimal checks) with one-popup-per-completion and daily caps.

## Plan

1) **Schema + Models**

- Add popup tables in DB: `popup_triggers` (user_id, trigger_id, task_id?, count, last_shown_at, helpful, last_response, last_comment), `popup_responses` (log entries).  
- Initialize via `backend/database.py` migration-friendly pattern (respect existing Base).  
- Add helper in `backend/analytics.py` or new `backend/popup_state.py` for CRUD (counts, cooldown checks).

2) **Rule Catalog Wiring**

- Encode trigger definitions referenced from `docs/features/popups/popup_rules.md` into code: ids, priority, cooldown, daily cap participation, milestone flags, disabled triggers (e.g., 3.3).  
- Include per-trigger tier logic (count-based) and milestone logic for positive triggers.

3) **Dispatcher Service**

- New module `backend/popup_dispatcher.py`:  
- `evaluate_triggers(completion_context, survey_context, settings)` → returns highest-priority popup (or none) honoring caps, cooldowns, one-per-event.  
- Applies tiered copy per trigger and includes “Helpful?” flag in payload.

4) **UI Hook Points (NiceGUI)**

- `ui/complete_task.py`: after saving completion, call dispatcher with context (actual/predicted, completion %, time ratios, affect, counts). Render modal with primary question, branch options, helpful toggle.  
- `ui/dashboard.py`/`ui/list` flows: minimal hook (e.g., cancellation/repeated cancellations) calling dispatcher; if no trigger, no modal.  
- Respect daily cap: if hit, show single notice with link to Settings and current cap.

5) **Settings & Defaults**

- Add simple settings access (per-user daily cap default, maybe in user_state or popup_state).  
- Provide default cooldown (e.g., 24h) and cap values; make them configurable later.

6) **Data & Logging**

- Persist popup shows/responses/helpful flag.  
- Ensure graceful no-op if DB unavailable (return no popup rather than error).

7) **Tests/Validation**

- Unit-style tests for dispatcher tier selection, cooldown, cap, disabled trigger.  
- Small integration smoke: simulate completion context and verify one popup emitted.

8) **Docs**

- Update `docs/features/popups/popup_rules.md` with implemented trigger ids/tiers mapping; note SQLite backing and fallback behavior.