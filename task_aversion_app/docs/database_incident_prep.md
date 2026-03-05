# Database Incident Prep: "Data Missing" / Stale Reads

This doc summarizes **likely causes** for the kind of issue you saw (recent data missing for a while, then back) and how the codebase makes some causes more or less plausible. Use it to stay calm and know what to check next time.

## What the app does (relevant to DB)

- **Single `DATABASE_URL`** – One connection string; no separate read-replica URL in code.
- **SQLAlchemy pool** – PostgreSQL: `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`. SQLite: `StaticPool` (single connection per process).
- **No explicit proxy** – No PgBouncer or other proxy in the app; you’d only have one if you added it on the VPS.
- **Caches** – InstanceManager and Analytics use in-memory, TTL-based caches (e.g. 2–5 minutes). Cache invalidation runs on create/update/delete/pause and on key pages (e.g. complete task, initialize task).

## Five potential causes vs this codebase

| Cause | Plausible here? | Why |
|-------|------------------|-----|
| **1. Read replica / replication lag** | **Low** (unless hosting gives you one) | App uses one `DATABASE_URL` and one engine. There’s no code path that sends reads to a replica. Only plausible if your VPS/managed DB automatically routes reads to a replica and you’re not aware of it. |
| **2. Wrong DB instance / connection** | **Possible** | If `DATABASE_URL` or env was temporarily wrong (e.g. backup, old instance), or a deploy pointed at another DB, you’d see “missing” data until fixed. Check deployment history and env on the box. |
| **3. Storage / volume / mount (VPS)** | **Possible** | Disk full, volume unmounted, or DB using a different data directory after a restart can look like “data gone then back” when the correct volume is used again. |
| **4. DB process restart / recovery** | **Possible** | Restart, crash, or failover can make the DB briefly serve an older state or refuse connections. Once recovery finishes, data “reappears.” |
| **5. Connection pool / proxy** | **Low** (proxy) / **Possible** (pool) | No app-level proxy. Stale or stuck connections in the pool could theoretically serve old data until they’re recycled; `pool_pre_ping=True` reduces that. |

So for **this** codebase, the most plausible explanations are: **wrong instance/env (2), storage/mount (3), or DB restart/recovery (4)**. Replica (1) and proxy (5) are less likely unless you introduce them outside the app.

## What we added to help next time

1. **Database diagnostics log**  
   - **File:** `task_aversion_app/logs/database_diagnostics.log`  
   - **Enabled by:** `ENABLE_DATABASE_DIAGNOSTICS=1` (default on).  
   - **At startup** we log a “DB identity” line:
     - **PostgreSQL:** `server_version` and `pg_is_in_recovery()` (so you can see if you’re on a replica or if version changed after a restart).
     - **SQLite:** just “connected ok”.
   - **On connection errors** we log `OperationalError` (e.g. “server closed connection”, “connection refused”) with timestamp and operation, so you can correlate “data missing” with a restart or network blip.
   - If “data missing” happens again, check that file: **new identity lines** (e.g. after a restart), **different `in_recovery`**, or **connection error** lines can support “restart” or “replica” as a cause.

2. **Cache behavior**  
   - Init-from-template, complete-task, and delete now invalidate instance caches and (where relevant) pass `user_id`, so the UI and backend see fresh data after those actions. If the problem was partly stale cache, you’re already in better shape.

## What to do if it happens again

1. **Don’t panic** – Data was almost certainly still on the primary; the issue is usually *visibility* (wrong connection, restart, cache, or replica lag).
2. **Check `logs/database_diagnostics.log`** – Look for:
   - New “DB identity” lines (app or DB restarts).
   - `in_recovery=true` (if you’re on PostgreSQL and didn’t expect a replica).
3. **Check the VPS / hosting** – Recent restarts, disk, mount points, failover, or env changes (e.g. `DATABASE_URL`).
4. **Quick mitigation** – Restart the app so all connections and caches are refreshed; often “data back” is just that.

## Your setup (answered)

- **VPS:** Single CPU, cheap option, root access. Uptime may have failed temporarily; **DB restart/recovery is very plausible** (cause 4).
- **Fritz:** ~5 minutes of visible glitch. You started a task, ~80 minutes later the UI showed a task from almost a day ago; ~5 minutes after you exported data, things corrected (plus the cache/delete fixes). Suggests temporary wrong state (restart, stale connection, or cache) then recovery.
- **Users:** Multi-user app but no other regular users you’re aware of. Use `python scripts/list_users.py` (from `task_aversion_app`) to see how many users exist and when they last logged in.

**Most likely in this setup:** Single-node DB restart or brief outage (cheap VPS), with cache/connection making the “wrong task” visible until refresh or export triggered fresh reads.
