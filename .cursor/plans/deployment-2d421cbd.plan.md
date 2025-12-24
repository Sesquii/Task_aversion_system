---
name: ""
overview: ""
todos: []
---

# Deployment & Data Plan

**Decisions**

- Database: **CURRENT STATE**: Migrated to SQLite locally with `SQLite_migration/` folder approach. This plan originally suggested going straight to Postgres, but SQLite migration was done first (which is fine - easier to test locally). **VPS STATUS**: Not deployed yet - Need to convert SQLite migrations to PostgreSQL when deploying to VPS.
- Migration Strategy: Using numbered migration scripts in `SQLite_migration/` folder (001, 002, etc.) - see `SQLite_migration/README.md` for details. Minimum one migration per week to keep app moving.
- Deployment: **CURRENT STATE**: Docker path already started. Systemd + nginx on the Ubuntu 22.04 VPS (simpler now); revisit Docker later if you want image-based releases/rollbacks.
- VPS Progress: SSH access complete, code not on server yet.
- Domain: Point `TaskAversionSystem.com` A/AAAA to the VPS; Let’s Encrypt via nginx.
- Auth interim: Enforce unique usernames (case-insensitive), with clear UI notice that this is a temporary, no-password system.
- User cap initially: ~20–30 concurrent/light users until load-tested; adjust after a basic load test.

**Steps**

1. Postgres setup: install Postgres, create DB/user, configure env vars/secrets for the app; add simple backup script. **STATUS**: Not started - VPS setup only partially done (SSH access complete, code not on server yet).
2. App migration off CSV: **LOCAL ONLY** - Migrated to SQLite locally using `migrate_csv_to_database.py` and `SQLite_migration/` scripts. Code paths switched to DB locally (with CSV fallback option). **VPS STATUS**: Not done - Need to convert SQLite migrations to PostgreSQL and run on VPS when deploying.
3. Username policy & UI notice: enforce uniqueness, add inline UI notice about temporary auth; reject duplicates with a helpful message.
4. Nginx + TLS: reverse proxy to app, obtain/renew Let's Encrypt cert for `TaskAversionSystem.com`.
5. Systemd service: unit file to run the app (gunicorn/uvicorn as needed), environment file for secrets, start/enable service.
6. Smoke & load checks: smoke test through domain; run a light load test (e.g., 20→50 virtual users) to size initial max users.
7. Release cadence: tag/releases from main; keep a deploy branch/tag for the VPS; migrations run per release (weekly/biweekly OK).

**Notes**

- Schema changes: **CURRENT**: Ad-hoc migrations in `SQLite_migration/` folder as features are added. Scripts are numbered and versioned. **FUTURE**: When moving to PostgreSQL, can batch migrations or continue ad-hoc approach. See `SQLite_migration/README.md` for current process.
- Future Docker path: once stable, add Dockerfile/compose for image-based releases and fast rollbacks.
- Procfile platforms skipped: ephemeral disk/quotas would constrain your CSV/log usage and add cost.

**Simple flow**

```mermaid
flowchart TD
  User --> Nginx
  Nginx --> App[App (systemd service)]
  App --> PG[Postgres]
  App --> Logs[Backups/Logs]
```