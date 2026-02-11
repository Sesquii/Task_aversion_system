# Performance analysis: PostgreSQL scope

The **production** deployment uses **PostgreSQL**. Performance analysis and optimization should focus on PostgreSQL-relevant operations.

## PRAGMA is SQLite-only

**PRAGMA** is a SQLite-specific command. PostgreSQL does not use PRAGMA. Equivalent behavior in PostgreSQL:

| SQLite PRAGMA | PostgreSQL equivalent |
|---------------|------------------------|
| `PRAGMA foreign_keys = ON` | Foreign keys are always enforced; no setting needed. |
| `PRAGMA table_info(...)` | `information_schema.columns` or `pg_catalog.pg_attribute`. |
| Other PRAGMA (journal_mode, etc.) | Session/config via `SET`, or server/config. |

In this codebase, PRAGMA appears only in:

- **backend/database.py** – schema warm-up run only when `DATABASE_URL.startswith('sqlite')` (e.g. `PRAGMA table_info`).
- **SQLite_migration/** – migrations that run only against SQLite (e.g. `PRAGMA foreign_keys = ON`).

When the app runs with `DATABASE_URL=postgresql://...`, none of that code runs. Query logs and execution will show only:

- **SELECT**, **INSERT**, **UPDATE**, **DELETE**
- **EXPLAIN** (if you run plan analysis)
- DDL/maintenance (e.g. **CREATE INDEX**, **VACUUM**, **ANALYZE**) when you run migrations or maintenance scripts

So for a **PostgreSQL-final** performance plan:

- **Do not** spend analysis effort on PRAGMA-specific tuning or “at least 3 scripts per PRAGMA”; PRAGMA does not run in production.
- **Do** focus on SELECT, INSERT, UPDATE, DELETE, EXPLAIN, and maintenance (indexes, VACUUM/ANALYZE) in the app and in the `pg_*` scripts.

## Quick one-off: PostgreSQL query sites

Run the static analysis script that reports only PostgreSQL-relevant query sites (excludes PRAGMA, focuses on app code that runs against PostgreSQL):

```bash
cd task_aversion_app
python scripts/performance/pg_query_sites_static.py [--by-dir] [--top N]
```

This gives an early snapshot of where SELECT/INSERT/UPDATE/DELETE and ORM usage live, by file and directory, without a live database.

## pg_catalog.pg_class.relname in query logs

Query logs may show many executions of `SELECT pg_catalog.pg_class.relname` (and similar). These come from **SQLAlchemy's reflection** (table/column introspection), e.g. when the dialect resolves table names or column types. They are not from application SQL you wrote.

- **Cause:** Inspector or dialect metadata lookups against PostgreSQL system catalogs (`pg_class`, `pg_attribute`, etc.).
- **Impact:** Can add dozens of small queries per request if reflection runs often (e.g. per-query or per-connection).
- **To reduce:** Avoid repeated schema introspection in hot paths; reuse a single Inspector or metadata per process/connection; ensure connection pooling is used so that reflection is not repeated per request. The app does not call Inspector directly in hot paths; if these queries remain high, they may be from SQLAlchemy internals (e.g. result proxy or dialect) and may require SQLAlchemy version or configuration review.
