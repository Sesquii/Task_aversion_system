# Agent master instructions: performance analysis scripts

You are adding **performance analysis scripts** for the Task Aversion app. Follow these rules on every run.

## Scope

- Add **only** performance analysis scripts under `task_aversion_app/scripts/performance/`.
- **Total target: 20-40 scripts** across all agents. This run's subprompt defines your slice and your **script count range (1-3 or 2-4)**. Produce only the number of scripts in the range specified.
- Run all scripts from `task_aversion_app`: `python scripts/performance/<script>.py [args]`.

## Outputs per run

- **Scripts:** New `.py` files in `task_aversion_app/scripts/performance/`.
- **Docs:** For **every** script added or changed, append a short entry to **the performance scripts README**: `task_aversion_app/scripts/performance/PERFORMANCE_SCRIPTS_README.md`. Each entry = script name, purpose, and how to run (e.g. "No DB", "needs query log", "needs PostgreSQL").

## Conventions

- **Console output:** ASCII-safe only (e.g. `[PASS]`, `[FAIL]`, `[INFO]`). No emojis in `print` (per workspace rules).
- **Code:** Standard library imports first, then third-party, then local. Use type hints where clear. Catch specific exceptions (e.g. `ValueError`, `OSError`), not bare `except Exception`.
- **Overlap:** Scripts may overlap in what they measure; avoid creating two scripts that do the same analysis under different names.

## Reference

- **Existing scripts and README table:** See the "Scripts" table and "Quick run" section in `task_aversion_app/scripts/performance/PERFORMANCE_SCRIPTS_README.md`. Match that pattern for new entries.
- **PostgreSQL scope:** Production uses PostgreSQL. PRAGMA is SQLite-only and need not be a category. See `task_aversion_app/scripts/performance/PERFORMANCE_POSTGRESQL_SCOPE.md`.

## SQL operation types (PostgreSQL)

Focus on: **SELECT**, **INSERT**, **UPDATE**, **DELETE**, **EXPLAIN** (plan analysis), **DDL** (CREATE/ALTER/INDEX), **maintenance** (VACUUM/ANALYZE). Scripts can focus on one type or overlap (e.g. SELECT + EXPLAIN).

## Pages and elements

- **Dashboard** (`/`, `ui/dashboard.py`): task list load (`tm.get_all`), active instances (`im.list_active_instances`), dashboard metrics (`an.get_dashboard_metrics`), composite scores (`an.get_all_scores_for_composite`), execution score (`an.get_execution_score_chunked`), relief summary, monitored metrics config, task notes, recent/recommendations.
- **Analytics** (`ui/analytics_page.py`): main analytics page, composite score load, emotional flow, relief comparison, factors comparison, glossary.
- **Settings** (`ui/settings_page.py`): settings landing, CSV import path, score weights, productivity settings, cancellation penalties.

## Quality bar

At least half of all scripts must produce **actionable performance data** (timings, counts, bottlenecks) or **teach DB/SQL concepts** (plans, indexes, locking) even if there is no immediate optimization.

---

**Chat snippet to use with each subprompt:** Paste this at the start of the agent chat, then add the subprompt:

```text
You are adding performance analysis scripts for the Task Aversion app. Before doing anything:
1. Read and follow task_aversion_app/scripts/performance/AGENT_MASTER_INSTRUCTIONS.md.
2. Apply the subprompt below. Produce only the number of scripts in the range specified (1-3 or 2-4). Add each to scripts/performance/ and append an entry to the performance scripts README (PERFORMANCE_SCRIPTS_README.md).
```
